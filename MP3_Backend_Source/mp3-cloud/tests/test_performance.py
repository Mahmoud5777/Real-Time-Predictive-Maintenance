"""Baseline reproductible : vrai HTTP TCP, MQTT Docker et PostgreSQL jetables.

Commande : python -m pytest --mqtt --performance tests/test_performance.py -s
Les assertions portent sur la coherence ; aucun seuil de temps dependant du poste n'est impose.
"""

import asyncio
import json
import os
import platform
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from performance_helpers import (
    api_server,
    distribution,
    ingest,
    mqtt_message,
    observations,
    reads,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from test_mqtt_integration import (
    broker as broker_fixture,
)
from test_mqtt_integration import (
    eventually,
    item,
    metric,
    options,
    publish,
    rows,
    running,
)
from test_mqtt_integration import (
    mqtt_engine as engine_fixture,
)

from app.analytics.aggregate import refresh
from app.analytics.windows import HOUR, closed_hour
from app.config import Settings
from app.models.tables import IngestReceipt, KpiRecord, Prediction, SensorData
from app.retention.service import run_retention
from app.supervision.service import check_nodes

pytestmark = [pytest.mark.postgres, pytest.mark.performance]
ROOT = Path(__file__).resolve().parents[1]
CONFIG = Settings(_env_file=None)
# Reutiliser les fixtures existantes et leur nettoyage, sans ouvrir fog_cloud.
broker = broker_fixture
mqtt_engine = engine_fixture


@pytest.fixture(scope="module")
def report(request):
    started = datetime.now(UTC)
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5
    )
    result = {
        "started_at": started.isoformat(),
        "selected_tests": [
            node.name for node in request.session.items if node.path == request.node.path
        ],
        "environment": {
            "os": platform.platform(), "python": platform.python_version(),
            "logical_cpus": os.cpu_count(), "git_head": git.stdout.strip(),
            "code_state": "working tree; HEAD alone does not identify uncommitted code",
            "topology": "HTTP client and Uvicorn same Python process, TCP loopback; "
                        "PostgreSQL and MQTT in Docker Desktop",
            "database": "unique disposable mp3_test_<UUID> for each scenario",
            "other_services": "working Compose services remain running on this host",
        },
        "method": {
            "clock": "time.perf_counter; client start through parsed HTTP response",
            "read_queue": "client semaphore wait excluded from per-request latency",
            "quantiles": "p50 median; p95/p99 nearest rank; "
                         "p95 only >=100 samples, p99 only >=1000",
            "load": "synthetic burst, not paced real-time; 12 machines in zones A/B/C",
            "limitations": "small datasets, no WAN or physical Fog; not a capacity guarantee",
        },
        "scenarios": {},
    }
    yield result
    result["finished_at"] = datetime.now(UTC).isoformat()
    result["all_scenarios_recorded"] = len(result["scenarios"]) == len(result["selected_tests"])
    destination = ROOT / "data" / "benchmarks" / f"{started:%Y%m%dT%H%M%S%fZ}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nBenchmark report: {destination}")


async def postgres_version(engine):
    async with AsyncSession(engine) as session:
        return await session.scalar(text("SHOW server_version"))


@pytest.mark.parametrize("batch_size", [1, 100])
async def test_http_batch_baseline(mqtt_engine, batch_size, report):
    # Les deux essais ont une base neuve, les memes 2400 mesures et un warmup de 12.
    at = closed_hour(datetime.now(UTC)) - HOUR
    messages = observations(200, at, predictions=False)
    async with api_server(mqtt_engine) as (client, _factory):
        await ingest(client, observations(1, at, predictions=False))
        result = await ingest(client, messages, batch_size)
        await ingest(client, messages[:12], duplicates=True)
        assert await rows(mqtt_engine, SensorData) == 2412
        assert await rows(mqtt_engine, IngestReceipt) == 2412
    result["warmup_messages"] = 12
    result["writer_concurrency"] = 1
    result["postgres_version"] = await postgres_version(mqtt_engine)
    report["scenarios"][f"http_batch_{batch_size}"] = result
    print(f"HTTP batch {batch_size}: {result['messages_per_second']:.1f} messages/s")


@pytest.mark.mqtt
async def test_reads_mqtt_workers_and_retention_baseline(mqtt_engine, broker, report):
    at = closed_hour(datetime.now(UTC)) - HOUR
    old = at - timedelta(days=CONFIG.raw_retention_days + 1)
    setup = observations(300, at)
    expired = observations(20, old)
    task_ids = [str(uuid4()) for _ in range(3)]
    for index, zone in enumerate("ABC"):
        fog = f"FOG_{zone}"
        setup.append({"kind": "alert", "payload": item(
            "alert", machine_id=f"M{1 + index * 4:02d}", fog_id=fog,
            timestamp=at.isoformat(),
        )[1]})
        common = dict(task_id=task_ids[index], created_at=at.isoformat(),
                      destination_fog=None, source_fog=fog)
        for status in ("CREATED", "RUNNING", "COMPLETED"):
            changes = dict(status=status)
            if status == "COMPLETED":
                changes["completed_at"] = (at + timedelta(seconds=1)).isoformat()
            setup.append({"kind": "task_event", "payload": item(
                "task_event", **common, **changes
            )[1]})
    async with api_server(mqtt_engine) as (client, factory):
        await ingest(client, setup + expired)
        await refresh(factory, CONFIG, at, at + HOUR)
        await reads(client, repetitions=2)  # HTTP / DB / connexions deja chauds
        baseline = await reads(client)
        http_messages = observations(100, at + timedelta(seconds=600))
        mqtt_items = observations(20, at + timedelta(seconds=900))
        groups = {zone: [] for zone in "ABC"}
        for message in mqtt_items:
            body = message["payload"]
            zone = body.get("zone", body.get("fog_id", "")[-1:])
            groups[zone].append(mqtt_message(message))
        for zone in "ABC":
            groups[zone].append(item(
                "fog_status", fog_id=f"FOG_{zone}", zone=zone,
                last_heartbeat=datetime.now(UTC).isoformat(),
            ))
        jobs = {"kpi": [], "supervision": [], "retention_preview": []}
        skipped = {"kpi": 0, "retention_preview": 0}
        stop = asyncio.Event()
        cycles = 0

        async def background_jobs():
            nonlocal cycles
            while not stop.is_set():
                for name, operation in (
                    ("kpi", lambda: refresh(factory, CONFIG, at, at + HOUR)),
                    ("supervision", lambda: check_nodes(factory, CONFIG)),
                    ("retention_preview", lambda: run_retention(factory, CONFIG, dry_run=True)),
                ):
                    started = time.perf_counter()
                    outcome = await operation()
                    jobs[name].append(time.perf_counter() - started)
                    if outcome is None:
                        skipped[name] += 1
                cycles += 1
                try:
                    await asyncio.wait_for(stop.wait(), timeout=.2)
                except TimeoutError:
                    pass

        async with running(mqtt_engine, broker, options(
            broker, mqtt_database_timeout_seconds=10
        )) as (instance, worker_task):
            async def mqtt_load():
                started = time.perf_counter()
                await asyncio.gather(*(
                    asyncio.to_thread(publish, broker, group) for group in groups.values()
                ))
                broker_done = time.perf_counter() - started
                expected = sum(map(len, groups.values()))
                await eventually(
                    lambda: metric(instance, "acknowledgements_total") == expected,
                    worker_task, timeout=90,
                )
                elapsed = time.perf_counter() - started
                assert metric(instance, "accepted_total", {"kind": "sensor"}) == 240
                assert metric(instance, "accepted_total", {"kind": "prediction"}) == 24
                assert metric(instance, "accepted_total", {"kind": "fog_status"}) == 3
                processing_count = instance.metrics.registry.get_sample_value(
                    "fog_cloud_mqtt_processing_seconds_count"
                )
                processing_sum = instance.metrics.registry.get_sample_value(
                    "fog_cloud_mqtt_processing_seconds_sum"
                )
                return {
                    "messages": expected, "publishers": 3,
                    "broker_publish_complete_s": broker_done,
                    "cloud_ack_complete_s": elapsed,
                    "messages_per_second": expected / elapsed,
                    "mean_worker_receipt_to_decision_ms": 1000 * processing_sum / processing_count,
                    "backpressure_episodes": metric(instance, "backpressure_total"),
                    "note": "burst throughput includes QoS1 publisher pacing; not server capacity",
                }

            worker_jobs = asyncio.create_task(background_jobs())
            loads = [asyncio.create_task(operation) for operation in (
                reads(client), ingest(client, http_messages), mqtt_load()
            )]
            try:
                read_result, http_result, mqtt_result = await asyncio.gather(*loads)
            finally:
                for load in loads:
                    if not load.done():
                        load.cancel()
                await asyncio.gather(*loads, return_exceptions=True)
                stop.set()
                await worker_jobs
            assert cycles > 0
        # Le dernier recalcul doit inclure toutes les ecritures de l'heure.
        await refresh(factory, CONFIG, at, at + HOUR)
        async with factory() as session:
            cached_count = await session.scalar(select(KpiRecord.value).where(
                KpiRecord.metric == "measurement_count", KpiRecord.scope == "plant",
                KpiRecord.bucket_start == at,
            ))
        assert cached_count == 3600 + 1200 + 240
        expected_sensors = 3600 + 240 + 1200 + 240
        assert await rows(mqtt_engine, SensorData) == expected_sensors
        assert await rows(mqtt_engine, Prediction) == 360 + 24 + 120 + 24

        started = time.perf_counter()
        preview = await run_retention(factory, CONFIG, dry_run=True)
        preview_time = time.perf_counter() - started
        assert preview.candidates == {"sensor": 240, "prediction": 24}
        started = time.perf_counter()
        retained = await run_retention(factory, CONFIG, dry_run=False)
        purge_time = time.perf_counter() - started
        assert retained.deleted == preview.candidates
        await ingest(client, expired, duplicates=True)
        assert await rows(mqtt_engine, SensorData) == expected_sensors - 240
        async with factory() as session:
            saved_count = await session.scalar(select(KpiRecord.value).where(
                KpiRecord.metric == "measurement_count", KpiRecord.scope == "plant",
                KpiRecord.bucket_start == old,
            ))
            assert saved_count == 240
            ledger = await session.scalar(select(func.count()).select_from(IngestReceipt))
        assert ledger == expected_sensors + 528

        async with mqtt_engine.begin() as connection:
            await connection.execute(text("ANALYZE sensor_data"))
            plan = await connection.scalar(text(
                "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT * FROM sensor_data "
                "WHERE machine_id='M01' ORDER BY timestamp DESC, id DESC LIMIT 50"
            ))
        if isinstance(plan, str):
            plan = json.loads(plan)
    result = {
        "postgres_version": await postgres_version(mqtt_engine),
        "dataset_before_purge": {"sensors": expected_sensors, "predictions": 528,
                                 "alerts": 3, "task_events": 9},
        "reads_only": baseline, "reads_with_ingestion_and_jobs": read_result,
        "http_with_contention": http_result, "mqtt_with_contention": mqtt_result,
        "jobs": {name: distribution(values) for name, values in jobs.items()},
        "job_cycles": cycles, "job_lock_skips": skipped,
        "job_schedule": "services called sequentially per cycle, 0.2 s pause; "
                        "overlap with concurrent HTTP/MQTT/reads",
        "retention": {"preview_ms": preview_time * 1000, "apply_ms": purge_time * 1000,
                      "deleted": retained.deleted, "known_replay_duplicates": len(expired)},
        "sensor_latest_query_plan": plan,
    }
    report["scenarios"]["mixed"] = result
    print(f"Reads p95: {baseline['all_routes']['p95']:.1f} ms; "
          f"with contention: {read_result['all_routes']['p95']:.1f} ms")
