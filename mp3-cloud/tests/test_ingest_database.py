"""Etape 3 : ingestion reelle, transactions, projections et concurrence en base jetable."""

import asyncio
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, pool, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.catalogue import initialize_catalogue
from app.db.session import get_session
from app.main import app
from app.models.tables import Alert, FogNode, FogStatusHistory, SensorData, Task, TaskEvent
from app.services import ingest
from app.services.ingest import MODEL_BY_KIND, persist_batch

pytestmark = pytest.mark.postgres
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"
FIXTURE_NAMES = {
    "sensor": "sensor_ok.json",
    "prediction": "prediction_ok.json",
    "alert": "alert_ok.json",
    "fog_status": "fog_status_ok.json",
    "task_event": "task_event_ok.json",
}
HEADERS = {"Authorization": "Bearer test-token"}


def message(kind, **changes):
    item = json.loads((FIXTURES / FIXTURE_NAMES[kind]).read_text(encoding="utf-8"))
    item["payload"]["message_id"] = f"step3-{uuid4().hex}"
    if kind == "alert":
        item["payload"]["alert_id"] = f"alert-{uuid4().hex}"
    if kind == "task_event":
        item["payload"]["task_id"] = str(uuid4())
    item["payload"].update(changes)
    return item


@pytest_asyncio.fixture
async def initialized_session(populated_session):
    # Commit du savepoint de fixture uniquement ; la transaction externe reste annulee.
    await populated_session.commit()
    yield populated_session


async def send(session, messages):
    # Fermer les transactions de lecture entre deux appels independants du service.
    if session.in_transaction():
        await session.commit()
    return await persist_batch(session, messages)


async def count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize("kind", FIXTURE_NAMES)
async def test_all_message_types_persist_and_replay(initialized_session, kind):
    item = message(kind)
    report = await send(initialized_session, [item, item, item])
    assert (report.accepted, report.duplicates, report.rejected, report.total) == (1, 2, 0, 3)
    assert await count(initialized_session, MODEL_BY_KIND[kind]) == 1
    again = await send(initialized_session, [item])
    assert (again.accepted, again.duplicates, again.rejected) == (0, 1, 0)


@pytest.mark.parametrize(
    ("kind", "field", "value"),
    [
        ("sensor", "temperature", 99),
        ("prediction", "risk_score", 0.99),
        ("alert", "message", "Different alert content"),
        ("fog_status", "cpu_percent", 99),
        ("task_event", "reason", "Different task reason"),
    ],
)
async def test_reused_message_id_with_changed_content_is_rejected(
    initialized_session, kind, field, value
):
    original = message(kind)
    changed = copy.deepcopy(original)
    changed["payload"][field] = value
    report = await send(initialized_session, [original, changed])
    assert (report.accepted, report.duplicates, report.rejected) == (1, 0, 1)
    assert report.errors[0]["code"] == "MESSAGE_ID_CONFLICT"
    assert report.errors[0]["index"] == 1
    assert await count(initialized_session, MODEL_BY_KIND[kind]) == 1


async def test_task_id_collision_does_not_leave_an_orphan_task(initialized_session):
    original = message("task_event")
    changed = copy.deepcopy(original)
    changed["payload"]["task_id"] = str(uuid4())
    report = await send(initialized_session, [original, changed])
    assert (report.accepted, report.rejected) == (1, 1)
    assert report.errors[0]["code"] == "MESSAGE_ID_CONFLICT"
    assert await count(initialized_session, Task) == 1
    assert await count(initialized_session, TaskEvent) == 1


async def test_alert_replay_preserves_acknowledgement_and_business_id_conflicts(
    initialized_session,
):
    original = message("alert")
    await send(initialized_session, [original])
    await initialized_session.execute(
        update(Alert).values(
            status="ACKNOWLEDGED",
            acknowledged_by="test-operator",
            acknowledged_at=datetime(2026, 11, 2, tzinfo=UTC),
        )
    )
    changed = copy.deepcopy(original)
    changed["payload"]["message_id"] = f"step3-{uuid4().hex}"
    report = await send(initialized_session, [original, changed])
    assert (report.duplicates, report.rejected) == (1, 1)
    assert report.errors[0]["code"] == "IDENTIFIER_CONFLICT"
    alert = (await initialized_session.execute(select(Alert))).scalar_one()
    assert (alert.status, alert.acknowledged_by) == ("ACKNOWLEDGED", "test-operator")


async def test_mixed_batch_isolates_validation_and_database_errors(initialized_session):
    items = [
        message("sensor"),
        message("sensor", machine_id="M99"),
        message("sensor", zone="B"),
        message("task_event", completed_at="2020-01-01T00:00:00Z"),
        message("prediction", fog_id="FOG_B"),
        {"kind": "unknown", "payload": {}},
    ]
    report = await send(initialized_session, items)
    assert (report.accepted, report.duplicates, report.rejected, report.total) == (2, 0, 4, 6)
    assert [(x["index"], x["code"]) for x in report.errors] == [
        (1, "VALIDATION_ERROR"),
        (2, "REFERENCE_ERROR"),
        (3, "DATA_INTEGRITY_ERROR"),
        (5, "UNKNOWN_KIND"),
    ]
    assert await count(initialized_session, SensorData) == 1
    assert await count(initialized_session, Task) == 0
    assert await count(initialized_session, TaskEvent) == 0


async def test_missing_catalogue_is_rejected(db_session):
    report = await persist_batch(db_session, [message("sensor"), message("fog_status")])
    assert (report.accepted, report.rejected) == (0, 2)
    assert all(error["code"] == "REFERENCE_ERROR" for error in report.errors)


async def test_projection_failure_rolls_back_history_but_preserves_other_messages(
    initialized_session,
):
    # Injecter une vraie erreur PostgreSQL apres l'insertion d'historique, en base de test.
    await initialized_session.execute(text("""
        CREATE FUNCTION reject_test_fog_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'test projection failure' USING ERRCODE = '23514';
        END; $$
    """))
    await initialized_session.execute(text("""
        CREATE TRIGGER reject_test_fog_update BEFORE UPDATE ON fog_nodes
        FOR EACH ROW EXECUTE FUNCTION reject_test_fog_update()
    """))
    report = await send(initialized_session, [message("fog_status"), message("sensor")])
    assert (report.accepted, report.rejected) == (1, 1)
    assert report.errors[0]["code"] == "DATA_INTEGRITY_ERROR"
    assert await count(initialized_session, FogStatusHistory) == 0
    node = await initialized_session.get(FogNode, "FOG_A")
    assert node.status == "OFFLINE" and node.last_heartbeat is None
    assert await count(initialized_session, SensorData) == 1


async def test_fog_history_keeps_old_and_equal_dates_without_regressing_state(initialized_session):
    first = message("fog_status", last_heartbeat="2026-11-02T08:00:00Z", cpu_percent=40)
    newer = message("fog_status", last_heartbeat="2026-11-02T08:00:10Z", cpu_percent=90)
    old = message(
        "fog_status", last_heartbeat="2026-11-02T08:00:05Z", cpu_percent=55, status="OFFLINE"
    )
    equal = message("fog_status", last_heartbeat="2026-11-02T08:00:10Z", cpu_percent=5)
    report = await send(initialized_session, [first, newer, old, equal, first])
    assert (report.accepted, report.duplicates) == (4, 1)
    node = await initialized_session.get(FogNode, first["payload"]["fog_id"])
    assert node.cpu_percent == 90
    assert node.status == newer["payload"]["status"]
    assert node.offline_since is None and node.recovered_at is None
    assert await count(initialized_session, FogStatusHistory) == 4


async def test_observed_offline_and_recovery_are_distinct_from_catalogue_state(initialized_session):
    items = [
        message("fog_status", status="ONLINE", last_heartbeat="2026-11-02T08:00:00Z"),
        message("fog_status", status="OFFLINE", last_heartbeat="2026-11-02T08:00:10Z"),
        message("fog_status", status="RECOVERING", last_heartbeat="2026-11-02T08:00:20Z"),
    ]
    await send(initialized_session, items[:2])
    node = await initialized_session.get(FogNode, items[0]["payload"]["fog_id"])
    assert node.offline_since == datetime(2026, 11, 2, 8, 0, 10, tzinfo=UTC)
    assert node.recovered_at is None
    await send(initialized_session, items[2:])
    await initialized_session.refresh(node)
    assert node.status == "RECOVERING" and node.offline_since is None
    assert node.recovered_at == datetime(2026, 11, 2, 8, 0, 20, tzinfo=UTC)


def task_message(task_id, status, source="FOG_A", destination=None, **changes):
    return message(
        "task_event", task_id=task_id, status=status, source_fog=source,
        destination_fog=destination, **changes
    )


async def test_task_journey_keeps_origin_and_has_no_invented_event_times(initialized_session):
    task_id = str(uuid4())
    events = [
        task_message(task_id.upper(), "CREATED"),
        task_message(task_id, "QUEUED"),
        task_message(task_id, "RUNNING"),
        task_message(task_id, "MIGRATED", destination="FOG_B"),
        task_message(task_id, "RUNNING", source="FOG_B"),
        task_message(task_id, "COMPLETED", source="FOG_B", completed_at="2026-11-02T08:00:00Z"),
    ]
    report = await send(initialized_session, events)
    assert (report.accepted, report.rejected) == (6, 0)
    task = await initialized_session.get(Task, task_id)
    assert (task.origin_fog_id, task.current_fog_id, task.status) == ("FOG_A", "FOG_B", "COMPLETED")
    assert task.started_at is None and task.last_event_at is None and task.machine_id is None
    stored = (await initialized_session.execute(select(TaskEvent))).scalars().all()
    assert len(stored) == 6 and all(x.occurred_at is None for x in stored)
    replay = await send(initialized_session, events)
    assert (replay.accepted, replay.duplicates, replay.rejected) == (0, 6, 0)


async def test_partial_journal_and_late_creation_preserve_observed_assignment(initialized_session):
    task_id = str(uuid4())
    await send(initialized_session, [task_message(task_id, "MIGRATED", "FOG_B", "FOG_C")])
    task = await initialized_session.get(Task, task_id)
    assert task.origin_fog_id is None and task.current_fog_id == "FOG_C"
    await send(initialized_session, [task_message(task_id, "CREATED")])
    await initialized_session.refresh(task)
    assert (task.origin_fog_id, task.current_fog_id, task.status) == ("FOG_A", "FOG_C", "MIGRATED")
    report = await send(initialized_session, [task_message(task_id, "CREATED", source="FOG_B")])
    assert report.errors[0]["code"] == "TASK_CONFLICT"
    assert await count(initialized_session, TaskEvent) == 2


async def test_missing_transfer_destination_remains_unknown(initialized_session):
    task_id = str(uuid4())
    report = await send(initialized_session, [task_message(task_id, "MIGRATED")])
    assert report.accepted == 1
    task = await initialized_session.get(Task, task_id)
    assert task.current_fog_id is None and task.origin_fog_id is None


async def test_changed_task_creation_date_is_rejected_without_overwriting_task(initialized_session):
    task_id = str(uuid4())
    created = task_message(task_id, "CREATED")
    changed = task_message(task_id, "RUNNING", created_at="2020-01-01T00:00:00Z")
    report = await send(initialized_session, [created, changed])
    assert (report.accepted, report.rejected) == (1, 1)
    assert report.errors[0]["code"] == "TASK_CONFLICT"
    task = await initialized_session.get(Task, task_id)
    assert task.status == "CREATED"
    assert await count(initialized_session, TaskEvent) == 1


async def test_completion_is_not_overwritten_by_a_late_running_event(initialized_session):
    task_id = str(uuid4())
    events = [
        task_message(task_id, "CREATED"),
        task_message(task_id, "COMPLETED", completed_at="2026-11-02T08:00:00Z"),
        task_message(task_id, "RUNNING", source="FOG_B"),
    ]
    report = await send(initialized_session, events)
    assert report.accepted == 3
    task = await initialized_session.get(Task, task_id)
    assert (task.status, task.current_fog_id) == ("COMPLETED", "FOG_A")
    assert await count(initialized_session, TaskEvent) == 3


async def test_critical_task_recovery_can_be_observed_on_another_fog(initialized_session):
    task_id = str(uuid4())
    events = [
        task_message(task_id, "CREATED", critical=True, priority="CRITICAL"),
        task_message(task_id, "FAILED", critical=True, priority="CRITICAL"),
        task_message(task_id, "RECOVERED", destination="FOG_C", critical=True, priority="CRITICAL"),
        task_message(task_id, "RUNNING", source="FOG_C", critical=True, priority="CRITICAL"),
    ]
    report = await send(initialized_session, events)
    assert report.accepted == 4
    task = await initialized_session.get(Task, task_id)
    assert (task.origin_fog_id, task.current_fog_id, task.status) == ("FOG_A", "FOG_C", "RUNNING")


async def test_connection_failure_rolls_back_previously_accepted_items(
    initialized_session, monkeypatch,
):
    original = ingest._write_message
    calls = 0

    async def disconnected(session, kind, parsed):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ConnectionResetError("test disconnection")
        return await original(session, kind, parsed)

    monkeypatch.setattr(ingest, "_write_message", disconnected)
    with pytest.raises(ConnectionResetError):
        await send(initialized_session, [message("sensor"), message("sensor")])
    assert await count(initialized_session, SensorData) == 0


async def test_failure_at_outer_commit_does_not_confirm_saved_items(initialized_session):
    def fail_outer_commit(session):
        if not session.in_nested_transaction():
            raise ConnectionResetError("test commit failure")

    event.listen(initialized_session.sync_session, "before_commit", fail_outer_commit)
    try:
        with pytest.raises(ConnectionResetError):
            await persist_batch(initialized_session, [message("sensor")])
    finally:
        event.remove(initialized_session.sync_session, "before_commit", fail_outer_commit)
    assert await count(initialized_session, SensorData) == 0


@pytest_asyncio.fixture
async def committed_engine(committed_postgres_database):
    engine = create_async_engine(committed_postgres_database.url, poolclass=pool.NullPool)
    async with AsyncSession(engine) as session, session.begin():
        await initialize_catalogue(session)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.mark.parametrize("kind", ["sensor", "fog_status", "task_event"])
async def test_concurrent_deliveries_have_one_committed_message(committed_engine, kind):
    item = message(kind)

    async def deliver():
        async with AsyncSession(committed_engine) as session:
            return await persist_batch(session, [item])

    reports = await asyncio.wait_for(asyncio.gather(deliver(), deliver()), timeout=15)
    assert sum(x.accepted for x in reports) == 1
    assert sum(x.duplicates for x in reports) == 1
    assert sum(x.rejected for x in reports) == 0
    async with AsyncSession(committed_engine) as session:
        assert await count(session, MODEL_BY_KIND[kind]) == 1


async def test_http_commits_all_types_visible_on_a_separate_connection(committed_engine):
    async def test_session():
        async with AsyncSession(committed_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = test_session
    items = [message(kind) for kind in FIXTURE_NAMES]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ingest/batch", json={"messages": items}, headers=HEADERS
            )
            assert response.status_code == 207
            assert response.json() == {"accepted": 5, "duplicates": 0, "rejected": 0, "errors": []}
            async with AsyncSession(committed_engine) as reader:
                for model in MODEL_BY_KIND.values():
                    assert await count(reader, model) == 1
            response = await client.post(
                "/api/v1/ingest/batch", json={"messages": items}, headers=HEADERS
            )
            assert response.status_code == 207 and response.json()["duplicates"] == 5
            latest = await client.get("/api/v1/machines/M01/latest")
            assert latest.status_code == 200
            assert latest.json()["temperature"] == items[0]["payload"]["temperature"]
    finally:
        app.dependency_overrides.pop(get_session, None)


async def test_http_failure_returns_503_and_same_ids_can_be_retried(committed_engine, monkeypatch):
    async def test_session():
        async with AsyncSession(committed_engine) as session:
            yield session

    original = ingest._write_message
    calls = 0

    async def disconnected(session, kind, parsed):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ConnectionResetError("private test connection failure")
        return await original(session, kind, parsed)

    monkeypatch.setattr(ingest, "_write_message", disconnected)
    app.dependency_overrides[get_session] = test_session
    items = [message("sensor"), message("sensor")]
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ingest/batch", json={"messages": items}, headers=HEADERS
            )
            assert response.status_code == 503
            assert "accepted" not in response.json() and "private" not in response.text
            async with AsyncSession(committed_engine) as reader:
                assert await count(reader, SensorData) == 0
            monkeypatch.setattr(ingest, "_write_message", original)
            response = await client.post(
                "/api/v1/ingest/batch", json={"messages": items}, headers=HEADERS
            )
            assert response.status_code == 207 and response.json()["accepted"] == 2
    finally:
        app.dependency_overrides.pop(get_session, None)
