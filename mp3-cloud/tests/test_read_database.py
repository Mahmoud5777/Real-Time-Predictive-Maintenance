"""Du stockage PostgreSQL aux reponses MP4, exclusivement dans des bases jetables."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
import yaml
from httpx import ASGITransport, AsyncClient
from openapi_schema_validator import OAS30Validator
from sqlalchemy import pool, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api import fog as fog_api
from app.db.catalogue import initialize_catalogue
from app.db.session import get_session
from app.main import create_app
from app.models.tables import Alert, FogNode, Task, TaskEvent
from app.services.ingest import persist_batch
from scripts.export_openapi import CONTRACT

pytestmark = pytest.mark.postgres
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"
FILES = {
    "sensor": "sensor_ok.json",
    "prediction": "prediction_ok.json",
    "alert": "alert_ok.json",
    "fog_status": "fog_status_ok.json",
    "task_event": "task_event_ok.json",
}
AT = datetime(2026, 11, 7, 10, tzinfo=UTC)
FIRST = "11111111-1111-4111-8111-111111111111"
SECOND = "22222222-2222-4222-8222-222222222222"
PARTIAL = "33333333-3333-4333-8333-333333333333"


def wire(kind, message_id, **changes):
    item = json.loads((FIXTURES / FILES[kind]).read_text(encoding="utf-8"))
    item["payload"].update(message_id=message_id, **changes)
    return item


def iso(seconds=0):
    return (AT + timedelta(seconds=seconds)).isoformat()


def expand_refs(schema, contract):
    if isinstance(schema, list):
        return [expand_refs(item, contract) for item in schema]
    if not isinstance(schema, dict):
        return schema
    if "$ref" in schema:
        target = contract
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return expand_refs(target, contract)
    return {key: expand_refs(value, contract) for key, value in schema.items()}


async def get(client, path, **params):
    response = await client.get("/api/v1" + path, params=params)
    assert response.status_code == 200, response.text
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    schema_path = path
    if path.startswith("/machines/"):
        schema_path = "/machines/{machine_id}" + ("/latest" if path.endswith("/latest") else "")
    elif path.startswith("/tasks/") and path != "/tasks/events":
        schema_path = "/tasks/{task_id}"
    elif path.startswith("/alerts/"):
        schema_path = "/alerts/{alert_id}"
    elif path.startswith("/fog/nodes/"):
        schema_path = "/fog/nodes/{fog_id}"
    schema = contract["paths"][schema_path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    OAS30Validator(expand_refs(schema, contract)).validate(response.json())
    return response.json()


@pytest_asyncio.fixture
async def reader(populated_session):
    application = create_app()

    async def isolated_database():
        yield populated_session

    application.dependency_overrides[get_session] = isolated_database
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client


@pytest_asyncio.fixture
async def observations(populated_session):
    session = populated_session
    await session.commit()  # savepoint seulement, la transaction externe sera annulee
    messages = [
        wire("sensor", "read-sensor-0001", timestamp=iso()),
        wire(
            "sensor", "read-sensor-0002", timestamp=iso(), pressure=None, power=None, frequency=None
        ),
        wire("sensor", "read-sensor-0003", timestamp=iso(10), machine_id="M05", zone="B"),
        wire("sensor", "read-sensor-0004", timestamp=iso(20), machine_id="M09", zone="C"),
        wire(
            "prediction",
            "read-pred-0001",
            timestamp=iso(),
            fog_id="FOG_B",
            model_version="v1",
            risk_score=0.91,
        ),
        wire(
            "prediction",
            "read-pred-0002",
            timestamp=iso(5),
            fog_id="FOG_A",
            model_version="v2",
            risk_score=0.2,
            anomaly=False,
        ),
        wire(
            "prediction",
            "read-pred-0003",
            timestamp=iso(10),
            machine_id="M05",
            fog_id="FOG_B",
            model_version="v1",
        ),
        wire(
            "prediction",
            "read-pred-0004",
            timestamp=iso(20),
            machine_id="M09",
            fog_id="FOG_C",
            model_version="v1",
            anomaly=False,
        ),
        wire("alert", "read-alert-0001", timestamp=iso(), alert_id="A-OPEN", fog_id="FOG_B"),
        wire(
            "alert",
            "read-alert-0002",
            timestamp=iso(10),
            alert_id="A-ACK",
            machine_id="M05",
            severity="WARNING",
        ),
        wire(
            "alert",
            "read-alert-0003",
            timestamp=iso(20),
            alert_id="A-RES",
            machine_id="M09",
            fog_id="FOG_C",
        ),
        wire("fog_status", "read-status-0001", last_heartbeat=iso()),
        wire(
            "fog_status",
            "read-status-0002",
            fog_id="FOG_B",
            zone="B",
            status="OVERLOADED",
            last_heartbeat=iso(5),
        ),
        wire(
            "fog_status",
            "read-status-0003",
            fog_id="FOG_C",
            zone="C",
            status="RECOVERING",
            last_heartbeat=iso(10),
        ),
        wire(
            "task_event",
            "read-task-created",
            task_id=FIRST,
            status="CREATED",
            created_at=iso(),
            destination_fog=None,
        ),
        wire(
            "task_event", "read-task-migrated", task_id=FIRST, status="MIGRATED", created_at=iso()
        ),
        wire(
            "task_event",
            "read-task-completed",
            task_id=FIRST,
            status="COMPLETED",
            source_fog="FOG_B",
            destination_fog=None,
            created_at=iso(),
            completed_at=iso(50),
        ),
        wire(
            "task_event",
            "read-task-critical",
            task_id=SECOND,
            status="CREATED",
            source_fog="FOG_C",
            destination_fog=None,
            created_at=iso(1),
            critical=True,
            priority="CRITICAL",
        ),
        wire(
            "task_event",
            "read-task-running",
            task_id=SECOND,
            status="RUNNING",
            source_fog="FOG_C",
            destination_fog=None,
            created_at=iso(1),
            critical=True,
            priority="CRITICAL",
        ),
        wire(
            "task_event",
            "read-task-partial",
            task_id=PARTIAL,
            status="MIGRATED",
            source_fog="FOG_B",
            destination_fog="FOG_C",
            created_at=iso(2),
        ),
    ]
    report = await persist_batch(session, messages)
    assert report.accepted == len(messages) and report.rejected == 0, report.errors
    await session.execute(
        update(Alert)
        .where(Alert.alert_id == "A-ACK")
        .values(
            status="ACKNOWLEDGED",
            acknowledged_at=AT + timedelta(seconds=30),
            acknowledged_by="test-user",
        )
    )
    await session.execute(
        update(Alert)
        .where(Alert.alert_id == "A-RES")
        .values(
            status="RESOLVED",
            resolved_at=AT + timedelta(seconds=40),
        )
    )
    # Une date d'evenement connue dans le scenario, pas un nouveau champ producteur.
    await session.execute(
        update(TaskEvent)
        .where(TaskEvent.message_id == "read-task-migrated")
        .values(
            occurred_at=AT + timedelta(seconds=10),
            received_at=AT + timedelta(seconds=101),
        )
    )
    return session


async def test_empty_histories_and_unobserved_catalogue_are_honest(reader):
    assert (await get(reader, "/machines"))["meta"]["total"] == 12
    for path in (
        "/measurements",
        "/predictions",
        "/alerts",
        "/tasks",
        "/tasks/events",
        "/fog/status-history",
    ):
        result = await get(reader, path)
        assert result == {"items": [], "meta": {"limit": 50, "offset": 0, "total": 0}}
    nodes = await get(reader, "/fog/nodes")
    assert nodes["meta"]["total"] == 3
    for node in nodes["items"]:
        assert node["status"] == "OFFLINE"
        assert node["cpu_percent"] is None and node["heartbeat_stale"] is None
        assert node["last_heartbeat"] is None


@pytest.mark.parametrize(
    "path,total",
    [
        ("/machines", 12),
        ("/measurements", 4),
        ("/predictions", 4),
        ("/alerts", 3),
        ("/fog/nodes", 3),
        ("/fog/status-history", 3),
        ("/tasks", 3),
        ("/tasks/events", 6),
    ],
)
async def test_all_collections_serialize_real_postgres_and_paginate(
    reader, observations, path, total
):
    page = await get(reader, path, limit=2, offset=1)
    assert page["meta"] == {"limit": 2, "offset": 1, "total": total}
    assert len(page["items"]) == 2
    beyond = await get(reader, path, offset=total + 10)
    assert beyond["items"] == [] and beyond["meta"]["total"] == total


async def test_measurement_filters_timezones_and_equal_timestamp_order(reader, observations):
    params = {"machine_id": "M01", "zone": "A", "from": "2026-11-07T11:00:00+01:00", "to": iso()}
    full = await get(reader, "/measurements", **params)
    assert [row["message_id"] for row in full["items"]] == ["read-sensor-0002", "read-sensor-0001"]
    first = await get(reader, "/measurements", **params, limit=1)
    second = await get(reader, "/measurements", **params, limit=1, offset=1)
    assert first["items"][0]["id"] != second["items"][0]["id"]
    asc = await get(reader, "/measurements", **params, sort="timestamp")
    assert asc["items"] == list(reversed(full["items"]))
    latest = await get(reader, "/machines/M01/latest")
    assert latest["message_id"] == "read-sensor-0002"
    assert latest["pressure"] is None and latest["timestamp"].endswith("Z")
    assert (await get(reader, "/machines", zone="B", sort="-machine_id"))["items"][0][
        "machine_id"
    ] == "M08"


async def test_predictions_filter_machine_zone_separately_from_executor(reader, observations):
    result = await get(
        reader, "/predictions", zone="A", fog_id="FOG_B", anomaly=True, model_version="v1"
    )
    assert result["meta"]["total"] == 1
    assert result["items"][0]["machine_id"] == "M01"
    assert result["items"][0]["risk_score"] == 0.91
    ordinary = await get(reader, "/predictions", anomaly=False)
    assert ordinary["meta"]["total"] == 2 and all(not row["anomaly"] for row in ordinary["items"])
    ranked = await get(reader, "/predictions", sort="-risk_score")
    assert ranked["items"][0]["message_id"] == "read-pred-0001"
    assert (
        await get(reader, "/predictions", machine_id="M05", **{"from": iso(10), "to": iso(10)})
    )["meta"]["total"] == 1


async def test_alert_filters_and_detail_include_existing_lifecycle(reader, observations):
    result = await get(reader, "/alerts", zone="B", status="ACKNOWLEDGED", severity="WARNING")
    assert result["meta"]["total"] == 1
    assert result["items"][0]["acknowledged_by"] == "test-user"
    detail = await get(reader, "/alerts/A-RES")
    assert detail["status"] == "RESOLVED" and detail["resolved_at"] is not None
    assert (await get(reader, "/alerts", machine_id="M01", fog_id="FOG_B"))["meta"]["total"] == 1


async def test_fog_staleness_is_metadata_and_history_uses_observation_time(
    reader, observations, monkeypatch
):
    class Clock:
        @staticmethod
        def now(_timezone):
            return AT + timedelta(seconds=16)

    monkeypatch.setattr(fog_api, "datetime", Clock)
    nodes = await get(reader, "/fog/nodes")
    first, second, _third = nodes["items"]
    assert first["status"] == "ONLINE" and first["heartbeat_stale"] is True
    assert first["heartbeat_age_seconds"] == 16
    assert second["heartbeat_stale"] is False
    assert "endpoint" not in first and "environment_ref" not in first
    assert (await observations.get(FogNode, "FOG_A")).status == "ONLINE"
    assert (await get(reader, "/fog/nodes/FOG_A"))["heartbeat_stale"] is True
    history = await get(
        reader, "/fog/status-history", fog_id="FOG_B", zone="B", **{"from": iso(5), "to": iso(5)}
    )
    assert history["meta"]["total"] == 1 and history["items"][0]["status"] == "OVERLOADED"


async def test_task_filters_preserve_origin_and_unknown_projection_fields(reader, observations):
    result = await get(
        reader, "/tasks", zone="A", current_fog_id="FOG_B", status="COMPLETED", critical=False
    )
    assert result["meta"]["total"] == 1 and result["items"][0]["task_id"] == FIRST
    first = await get(reader, "/tasks/" + FIRST)
    assert first["origin_fog_id"] == "FOG_A" and first["current_fog_id"] == "FOG_B"
    assert first["started_at"] is None and first["last_event_at"] is None
    assert first["machine_id"] is None and first["completed_at"] is not None
    partial = await get(reader, "/tasks/" + PARTIAL)
    assert partial["origin_fog_id"] is None and partial["current_fog_id"] == "FOG_C"
    assert (await get(reader, "/tasks", priority="CRITICAL", critical=True))["meta"]["total"] == 1
    assert (await get(reader, "/tasks", machine_id="M01"))["meta"]["total"] == 0


async def test_event_filters_distinguish_creation_occurrence_and_reception(reader, observations):
    migrated = await get(
        reader,
        "/tasks/events",
        task_id=FIRST.upper(),
        source_fog="FOG_A",
        destination_fog="FOG_B",
        status="MIGRATED",
    )
    assert migrated["meta"]["total"] == 1
    assert migrated["items"][0]["occurred_at"] == "2026-11-07T10:00:10Z"
    observed = await get(
        reader,
        "/tasks/events",
        task_id=FIRST,
        time_field="occurred_at",
        **{"from": iso(), "to": iso(20)},
    )
    assert observed["meta"]["total"] == 1  # NULL n'est pas remplace par une autre date
    arrived = await get(
        reader,
        "/tasks/events",
        task_id=FIRST,
        time_field="received_at",
        **{"from": iso(101), "to": iso(101)},
    )
    assert arrived["meta"]["total"] == 1
    created = await get(
        reader, "/tasks/events", task_id=FIRST, **{"from": iso(101), "to": iso(101)}
    )
    assert created["meta"]["total"] == 0
    ordered = await get(reader, "/tasks/events", task_id=FIRST, sort="occurred_at")
    assert ordered["items"][0]["message_id"] == "read-task-migrated"
    assert ordered["items"][-1]["occurred_at"] is None
    assert (await get(reader, "/tasks/events", zone="A"))["meta"]["total"] == 3


@pytest.mark.parametrize(
    "path",
    [
        "/machines/M99",
        "/machines/M01/latest",
        "/alerts/unknown",
        "/tasks/" + FIRST,
    ],
)
async def test_missing_resource_is_top_level_404(reader, path):
    response = await reader.get("/api/v1" + path)
    assert response.status_code == 404
    assert response.json()["status"] == 404 and response.json()["instance"] == "/api/v1" + path
    assert isinstance(response.json()["detail"], str)


async def test_committed_http_ingestion_is_readable_from_another_connection(
    committed_postgres_database,
):
    engine = create_async_engine(committed_postgres_database.url, poolclass=pool.NullPool)
    application = create_app()

    async def independent_sessions():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    application.dependency_overrides[get_session] = independent_sessions
    try:
        async with AsyncSession(engine) as session:
            await initialize_catalogue(session)
            await session.commit()
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/ingest/batch",
                headers={"Authorization": "Bearer test-token"},
                json={
                    "messages": [wire("sensor", "step5-committed-sensor", timestamp=iso())],
                },
            )
            assert response.status_code == 207 and response.json()["accepted"] == 1
            readings = await get(client, "/measurements", machine_id="M01")
            assert readings["items"][0]["message_id"] == "step5-committed-sensor"
            await get(client, "/machines/M01")
        async with AsyncSession(engine) as session:
            assert (await session.execute(select(Task))).scalars().all() == []
    finally:
        await engine.dispose()
