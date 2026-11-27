"""Tests MQTT reels : conteneur et volume strictement jetables, base PostgreSQL dediee."""

import asyncio
import json
import re
import socket
import subprocess
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import paho.mqtt.client as mqtt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.db.catalogue import initialize_catalogue
from app.db.session import get_session
from app.ingest import worker as module
from app.ingest.worker import MqttWorker
from app.main import app, create_app
from app.models.tables import FogNode, SensorData
from app.services.ingest import MODEL_BY_KIND
from app.supervision.service import check_nodes

pytestmark = [pytest.mark.mqtt, pytest.mark.postgres]
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"
FILES = {
    "sensor": "sensor_ok.json",
    "prediction": "prediction_ok.json",
    "alert": "alert_ok.json",
    "fog_status": "fog_status_ok.json",
    "task_event": "task_event_ok.json",
}


@dataclass
class Broker:
    name: str
    port: int

    def docker(self, *args, check=True):
        if re.fullmatch(r"mp3_mqtt_test_[0-9a-f]{32}", self.name) is None:
            raise ValueError("Refusing to manage a non-test MQTT broker")
        return subprocess.run(
            ["docker", *args], check=check, capture_output=True, text=True, timeout=30
        )

    def restart(self):
        self.docker("restart", "--time", "2", self.name)
        self.port = int(self.docker("port", self.name, "1883/tcp").stdout.strip().rsplit(":", 1)[1])


@pytest.fixture
def broker(tmp_path):
    name = f"mp3_mqtt_test_{uuid4().hex}"
    configuration = tmp_path / "mosquitto.conf"
    configuration.write_text(
        "listener 1883\nallow_anonymous true\npersistence true\n"
        "persistence_location /mosquitto/data/\nautosave_interval 1\n",
        encoding="utf-8",
    )
    instance = Broker(name, 0)
    try:
        instance.docker(
            "run",
            "-d",
            "--pull",
            "never",
            "--name",
            name,
            "-p",
            "127.0.0.1::1883",
            "--mount",
            f"type=bind,source={configuration.resolve()},target=/mosquitto/config/mosquitto.conf,readonly",
            "--mount",
            f"type=volume,source={name}_data,target=/mosquitto/data",
            "eclipse-mosquitto:2",
        )
        port = int(instance.docker("port", name, "1883/tcp").stdout.strip().rsplit(":", 1)[1])
        instance = Broker(name, port)
        deadline = time.monotonic() + 10
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                if time.monotonic() > deadline:
                    pytest.fail(
                        f"Test broker failed to start: {instance.docker('logs', name).stderr}"
                    )
                time.sleep(0.05)
        yield instance
    finally:
        instance.docker("rm", "-f", name, check=False)
        instance.docker("volume", "rm", f"{name}_data", check=False)


@pytest_asyncio.fixture
async def mqtt_engine(committed_postgres_database):
    engine = create_async_engine(committed_postgres_database.url, pool_pre_ping=True)
    async with AsyncSession(engine) as session, session.begin():
        await initialize_catalogue(session)
    try:
        yield engine
    finally:
        await engine.dispose()


def options(broker, **changes):
    return Settings(_env_file=None).model_copy(
        update={
            "mqtt_host": "127.0.0.1",
            "mqtt_port": broker.port,
            "mqtt_client_id": f"mqtt-test-{uuid4().hex}",
            "mqtt_metrics_port": 0,
            "mqtt_retry_seconds": 0.05,
            "mqtt_retry_max_seconds": 0.2,
            "mqtt_connect_timeout_seconds": 2,
            "mqtt_database_timeout_seconds": 3,
            "mqtt_shutdown_seconds": 5,
            "mqtt_keepalive_seconds": 5,
            **changes,
        }
    )


async def eventually(predicate, task=None, timeout=12):
    deadline = time.monotonic() + timeout
    while True:
        if task is not None and task.done():
            task.result()
            raise AssertionError("worker stopped before expected result")
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        if time.monotonic() > deadline:
            raise AssertionError("MQTT result not observed before timeout")
        await asyncio.sleep(0.02)


@asynccontextmanager
async def running(engine, broker, settings=None):
    instance = MqttWorker(
        settings or options(broker), async_sessionmaker(engine, expire_on_commit=False)
    )
    stop = asyncio.Event()
    task = asyncio.create_task(instance.run(stop))
    try:
        await eventually(instance.ready.is_set, task)
        yield instance, task
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=8)


def item(kind, **changes):
    data = json.loads((FIXTURES / FILES[kind]).read_text(encoding="utf-8"))["payload"]
    data["message_id"] = f"mqtt-{uuid4().hex}"
    if kind == "alert":
        data["alert_id"] = f"mqtt-alert-{uuid4().hex}"
    if kind == "task_event":
        data["task_id"] = str(uuid4())
    data.update(changes)
    if kind == "sensor":
        topic = f"fog/{data['zone']}/sensor/{data['machine_id']}"
    elif kind == "task_event":
        topic = "tasks/events"
    else:
        suffix = {"prediction": "predictions", "alert": "alerts", "fog_status": "status"}[kind]
        topic = f"fog/{data['fog_id']}/{suffix}"
    return topic, data, kind == "fog_status"


def publish(broker, messages):
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"mqtt-publisher-{uuid4().hex}",
    )
    client.connect("127.0.0.1", broker.port, keepalive=10)
    client.loop_start()
    try:
        for topic, body, retained in messages:
            payload = body if isinstance(body, bytes) else json.dumps(body).encode()
            info = client.publish(topic, payload, qos=1, retain=retained)
            info.wait_for_publish(timeout=5)
            assert info.is_published()
    finally:
        client.disconnect()
        client.loop_stop()


def metric(instance, name, labels=None):
    return instance.metrics.registry.get_sample_value(f"fog_cloud_mqtt_{name}", labels or {}) or 0


async def rows(engine, model):
    async with AsyncSession(engine) as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_all_topics_commit_and_http_replay_is_a_duplicate(mqtt_engine, broker):
    messages = [
        item(kind, **({"fog_id": "FOG_B"} if kind == "prediction" else {})) for kind in FILES
    ]
    async with running(mqtt_engine, broker) as (instance, task):
        await asyncio.to_thread(publish, broker, messages)
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 5, task)
        for model in MODEL_BY_KIND.values():
            assert await rows(mqtt_engine, model) == 1
        await asyncio.to_thread(publish, broker, messages)
        await eventually(
            lambda: metric(instance, "duplicates_total", {"kind": "sensor"}) >= 1, task
        )

        async def test_session():
            async with AsyncSession(mqtt_engine, expire_on_commit=False) as session:
                yield session

        app.dependency_overrides[get_session] = test_session
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/api/v1/ingest/batch",
                    json={
                        "messages": [
                            {"kind": kind, "payload": msg[1]}
                            for kind, msg in zip(FILES, messages, strict=True)
                        ]
                    },
                    headers={"Authorization": "Bearer test-token"},
                )
                assert response.status_code == 207
                assert response.json()["duplicates"] == 5
                latest = await client.get("/api/v1/machines/M01/latest")
                assert latest.status_code == 200
                assert latest.json()["temperature"] == messages[0][1]["temperature"]
        finally:
            app.dependency_overrides.pop(get_session, None)


async def test_three_fog_topics_collaboration_and_dashboard_reads(mqtt_engine, broker):
    """Les trois zones traversent MQTT -> commit -> API, avec transferts A/B/C."""
    at = datetime.now(UTC)
    messages = []
    task_ids = {}
    for index, zone in enumerate("ABC"):
        fog = f"FOG_{zone}"
        for number in range(1 + 4 * index, 5 + 4 * index):
            messages.append(item(
                "sensor", machine_id=f"M{number:02d}", zone=zone, timestamp=at.isoformat()
            ))
        machine = f"M{1 + 4 * index:02d}"
        messages.extend([
            item("prediction", machine_id=machine, fog_id=fog, timestamp=at.isoformat()),
            item("alert", machine_id=machine, fog_id=fog, timestamp=at.isoformat()),
            item("fog_status", fog_id=fog, zone=zone, last_heartbeat=at.isoformat()),
        ])
        task_ids[zone] = str(uuid4())
        destination = f"FOG_{'ABC'[(index + 1) % 3]}"
        common = dict(task_id=task_ids[zone], created_at=at.isoformat())
        messages.extend([
            item("task_event", **common, source_fog=fog, destination_fog=None,
                 status="CREATED"),
            item("task_event", **common, source_fog=fog, destination_fog=destination,
                 status="MIGRATED"),
            item("task_event", **common, source_fog=destination, destination_fog=None,
                 status="COMPLETED", completed_at=(at + timedelta(seconds=1)).isoformat()),
        ])
    # Une analyse hors zone conserve la zone A de la machine M01.
    messages.append(item("prediction", fog_id="FOG_C", timestamp=at.isoformat()))
    factory = async_sessionmaker(mqtt_engine, expire_on_commit=False)
    application = create_app()

    async def isolated_session():
        async with factory() as session:
            yield session

    application.dependency_overrides[get_session] = isolated_session
    async with running(mqtt_engine, broker) as (instance, worker_task):
        await asyncio.to_thread(publish, broker, messages)
        await eventually(
            lambda: metric(instance, "acknowledgements_total") == len(messages), worker_task
        )
        assert sum(metric(instance, "accepted_total", {"kind": k}) for k in FILES) == len(
            messages
        )
        await check_nodes(factory, options(broker))
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            for index, zone in enumerate("ABC"):
                fog = f"FOG_{zone}"
                response = await client.get("/api/v1/measurements", params={"zone": zone})
                assert response.status_code == 200
                assert response.json()["meta"]["total"] == 4
                assert {row["machine_id"] for row in response.json()["items"]} == {
                    f"M{number:02d}" for number in range(1 + 4 * index, 5 + 4 * index)
                }
                alerts = await client.get("/api/v1/alerts", params={"fog_id": fog})
                assert alerts.status_code == 200 and alerts.json()["meta"]["total"] == 1
                node = await client.get(f"/api/v1/fog/nodes/{fog}")
                assert node.status_code == 200
                assert node.json()["effective_supervision_status"] == "REACHABLE"
                task = await client.get(f"/api/v1/tasks/{task_ids[zone]}")
                assert task.status_code == 200
                assert task.json()["origin_fog_id"] == fog
                assert task.json()["current_fog_id"] == f"FOG_{'ABC'[(index + 1) % 3]}"
                assert task.json()["status"] == "COMPLETED"
                events = await client.get(
                    "/api/v1/tasks/events", params={"task_id": task_ids[zone]}
                )
                assert events.status_code == 200 and events.json()["meta"]["total"] == 3
            cross_zone = await client.get(
                "/api/v1/predictions", params={"zone": "A", "fog_id": "FOG_C"}
            )
            assert cross_zone.status_code == 200 and cross_zone.json()["meta"]["total"] == 1

            offline = item("fog_status", fog_id="FOG_B", zone="B", status="OFFLINE",
                           last_heartbeat=datetime.now(UTC).isoformat())
            await asyncio.to_thread(publish, broker, [offline])
            await eventually(
                lambda: metric(instance, "acknowledgements_total") == len(messages) + 1,
                worker_task,
            )
            await check_nodes(factory, options(broker))
            node = await client.get("/api/v1/fog/nodes/FOG_B")
            assert node.json()["effective_supervision_status"] == "UNREACHABLE"
            online = item("fog_status", fog_id="FOG_B", zone="B", status="ONLINE",
                          last_heartbeat=datetime.now(UTC).isoformat())
            await asyncio.to_thread(publish, broker, [online])
            await eventually(
                lambda: metric(instance, "acknowledgements_total") == len(messages) + 2,
                worker_task,
            )
            await check_nodes(factory, options(broker))
            node = await client.get("/api/v1/fog/nodes/FOG_B")
            assert node.json()["effective_supervision_status"] == "REACHABLE"
            history = await client.get(
                "/api/v1/fog/supervision-history", params={"fog_id": "FOG_B"}
            )
            assert history.status_code == 200
            assert [row["supervision_status"] for row in history.json()["items"]] == [
                "REACHABLE", "UNREACHABLE", "REACHABLE"
            ]

            await asyncio.to_thread(publish, broker, messages)
            await eventually(
                lambda: metric(instance, "acknowledgements_total") == 2 * len(messages) + 2,
                worker_task,
            )
            assert sum(metric(instance, "duplicates_total", {"kind": k}) for k in FILES) == len(
                messages
            )
            assert await rows(mqtt_engine, SensorData) == 12
            events = await client.get("/api/v1/tasks/events")
            assert events.json()["meta"]["total"] == 9


async def test_invalid_messages_do_not_block_the_next_valid_message(mqtt_engine, broker):
    good = item("sensor")
    mismatch = item("sensor")
    mismatch[1]["zone"] = "B"
    invalid = item("sensor", temperature=999)
    messages = [
        ("tasks/events", b"not-json", False),
        mismatch,
        invalid,
        ("fog/FOG_D/predictions", b"{}", False),
        good,
    ]
    async with running(mqtt_engine, broker) as (instance, task):
        await asyncio.to_thread(publish, broker, messages)
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 5, task)
        assert await rows(mqtt_engine, SensorData) == 1
        for kind, code in [
            ("task_event", "INVALID_JSON"),
            ("sensor", "TOPIC_MISMATCH"),
            ("sensor", "VALIDATION_ERROR"),
            ("unknown", "UNKNOWN_TOPIC"),
        ]:
            assert metric(instance, "rejected_total", {"kind": kind, "code": code}) == 1


async def test_database_connection_failure_retries_without_ack(mqtt_engine, broker):
    # Un port reserve mais sans serveur produit une vraie erreur de connexion ; la base
    # de travail et son serveur PostgreSQL ne sont jamais arretes.
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
        unavailable = create_async_engine(
            mqtt_engine.url.set(port=port), connect_args={"timeout": 1}
        )
        try:
            async with running(mqtt_engine, broker) as (instance, task):
                instance.sessions = async_sessionmaker(unavailable)
                await asyncio.to_thread(publish, broker, [item("sensor")])
                await eventually(
                    lambda: metric(instance, "retries_total", {"stage": "database"}) >= 1, task
                )
                assert metric(instance, "acknowledgements_total") == 0
                assert await rows(mqtt_engine, SensorData) == 0
                instance.sessions = async_sessionmaker(mqtt_engine, expire_on_commit=False)
                await eventually(lambda: metric(instance, "acknowledgements_total") >= 1, task)
                assert await rows(mqtt_engine, SensorData) == 1
        finally:
            await unavailable.dispose()


async def test_disconnect_after_commit_before_ack_replays_without_second_row(
    mqtt_engine, broker, monkeypatch
):
    async with running(mqtt_engine, broker) as (instance, task):
        original = instance._ack
        interrupted = False

        def interrupt_first_ack(delivery):
            nonlocal interrupted
            if not interrupted:
                interrupted = True
                instance._disconnect()
            original(delivery)

        monkeypatch.setattr(instance, "_ack", interrupt_first_ack)
        await asyncio.to_thread(publish, broker, [item("sensor")])
        await eventually(
            lambda: metric(instance, "duplicates_total", {"kind": "sensor"}) >= 1, task
        )
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 1, task)
        assert metric(instance, "connections_total") >= 2
        assert metric(instance, "accepted_total", {"kind": "sensor"}) == 1
        assert await rows(mqtt_engine, SensorData) == 1


async def test_offline_session_retained_heartbeat_and_broker_restart(mqtt_engine, broker):
    settings = options(broker)
    async with running(mqtt_engine, broker, settings):
        pass
    messages = [item("sensor") for _ in range(3)] + [item("fog_status")]
    await asyncio.to_thread(publish, broker, messages)
    await asyncio.to_thread(broker.restart)
    settings = settings.model_copy(update={"mqtt_port": broker.port})
    async with running(mqtt_engine, broker, settings) as (instance, task):

        async def received_all():
            return await rows(mqtt_engine, SensorData) == 3

        await eventually(received_all, task)
        await eventually(
            lambda: metric(instance, "accepted_total", {"kind": "fog_status"}) == 1, task
        )
        assert await rows(mqtt_engine, MODEL_BY_KIND["fog_status"]) == 1
        async with AsyncSession(mqtt_engine) as reader:
            node = await reader.get(FogNode, messages[-1][1]["fog_id"])
            assert node.last_heartbeat is not None


async def test_small_queue_applies_backpressure_without_losing_qos_one(
    mqtt_engine, broker, monkeypatch
):
    gate = asyncio.Event()
    original = module.persist_batch

    async def held(*args):
        await gate.wait()
        return await original(*args)

    monkeypatch.setattr(module, "persist_batch", held)
    async with running(mqtt_engine, broker, options(broker, mqtt_queue_capacity=1)) as (
        instance,
        task,
    ):
        messages = [item("sensor") for _ in range(12)]
        await asyncio.to_thread(publish, broker, messages)
        await eventually(lambda: metric(instance, "backpressure_total") >= 1, task)
        assert instance._queue.qsize() <= 1
        assert metric(instance, "acknowledgements_total") == 0
        gate.set()
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 12, task)
        assert await rows(mqtt_engine, SensorData) == 12


async def test_worker_waits_for_catalogue_before_subscribing(committed_postgres_database, broker):
    engine = create_async_engine(committed_postgres_database.url)
    instance = MqttWorker(options(broker), async_sessionmaker(engine, expire_on_commit=False))
    stop = asyncio.Event()
    task = asyncio.create_task(instance.run(stop))
    try:
        await eventually(lambda: metric(instance, "retries_total", {"stage": "startup"}) >= 1, task)
        assert not instance.connected.is_set() and not instance.ready.is_set()
        async with AsyncSession(engine) as session, session.begin():
            await initialize_catalogue(session)
        await eventually(instance.ready.is_set, task)
        await asyncio.to_thread(publish, broker, [item("sensor")])
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 1, task)
        assert await rows(engine, SensorData) == 1
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=8)
        await engine.dispose()


async def test_metrics_endpoint_reports_readiness_and_committed_messages(mqtt_engine, broker):
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    async with running(mqtt_engine, broker, options(broker, mqtt_metrics_port=port)) as (
        instance,
        task,
    ):
        await asyncio.to_thread(publish, broker, [item("sensor")])
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 1, task)
        async with AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{port}/metrics")
            assert response.status_code == 200
            assert "fog_cloud_mqtt_ready 1.0" in response.text
            assert 'fog_cloud_mqtt_accepted_total{kind="sensor"} 1.0' in response.text


async def test_running_worker_reconnects_when_broker_restarts(mqtt_engine, broker):
    async with running(mqtt_engine, broker) as (instance, task):
        await asyncio.to_thread(broker.restart)
        # Docker peut reattribuer le port publie aleatoire du broker de test.
        instance.settings.mqtt_port = broker.port
        await eventually(
            lambda: instance.ready.is_set() and metric(instance, "connections_total") >= 2,
            task,
        )
        await asyncio.to_thread(publish, broker, [item("sensor")])
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 1, task)
        assert await rows(mqtt_engine, SensorData) == 1


async def test_fixture_cli_replays_same_message_id(mqtt_engine, broker):
    async with running(mqtt_engine, broker) as (instance, task):
        result = await asyncio.to_thread(
            subprocess.run,
            [
                sys.executable,
                "-m",
                "scripts.publish_mqtt",
                "--host",
                "127.0.0.1",
                "--port",
                str(broker.port),
                "--topic",
                "fog/A/sensor/M01",
                "--file",
                str(FIXTURES / "sensor_ok.json"),
                "--repeat",
                "3",
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stderr
        await eventually(lambda: metric(instance, "acknowledgements_total") >= 3, task)
        assert metric(instance, "accepted_total", {"kind": "sensor"}) == 1
        assert metric(instance, "duplicates_total", {"kind": "sensor"}) == 2
        assert await rows(mqtt_engine, SensorData) == 1
