"""Etape 2 : migrations et integrite sur PostgreSQL reel, activees par --postgres.

Les scenarios inserent des observations de test. Ils ne simulent pas des VM et
ne constituent pas encore un service d'ingestion ou un ordonnanceur de taches.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.db.catalogue import initialize_catalogue
from app.models.base import Base
from app.models.tables import (
    Alert,
    FogNode,
    FogStatusHistory,
    KpiRecord,
    Machine,
    Prediction,
    SensorData,
    Task,
    TaskEvent,
)
from app.services.ingest import parse_message

pytestmark = pytest.mark.postgres
AT = datetime(2026, 11, 2, 8, tzinfo=UTC)
TASK_ID = "b3f1c2d4-6a11-4f3a-9c2e-7d5b1a0e9f42"
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"


def _task(**changes) -> dict:
    return {
        "task_id": TASK_ID,
        "task_type": "AGGREGATION",
        "priority": "MEDIUM",
        "critical": False,
        "origin_fog_id": "FOG_A",
        "current_fog_id": "FOG_A",
        "machine_id": "M01",
        "status": "CREATED",
        "created_at": AT,
        **changes,
    }


def _event(message_id="task-event-test-0001", **changes) -> dict:
    return {
        "message_id": message_id,
        "task_id": TASK_ID,
        "task_type": "AGGREGATION",
        "priority": "MEDIUM",
        "critical": False,
        "source_fog": "FOG_A",
        "destination_fog": None,
        "status": "CREATED",
        "created_at": AT,
        "occurred_at": None,
        "completed_at": None,
        **changes,
    }


def _history(message_id="fog-status-test-0001", **changes) -> dict:
    return {
        "message_id": message_id,
        "fog_id": "FOG_A",
        "zone": "A",
        "observed_at": AT,
        "status": "ONLINE",
        "cpu_percent": 30.0,
        "ram_percent": 40.0,
        "queued_tasks": 1,
        "active_tasks": 2,
        **changes,
    }


def _sensor(message_id="sensor-test-0001", **changes) -> dict:
    return {
        "message_id": message_id,
        "machine_id": "M01",
        "zone": "A",
        "timestamp": AT,
        "temperature": 70.0,
        "vibration": 4.0,
        "speed": 1480.0,
        "current": 12.0,
        "state": "RUNNING",
        **changes,
    }


def _prediction(message_id="prediction-test-0001", **changes) -> dict:
    return {
        "message_id": message_id,
        "machine_id": "M01",
        "fog_id": "FOG_A",
        "timestamp": AT,
        "risk_score": Decimal("0.4"),
        "anomaly": False,
        "predicted_fault": "NONE",
        "severity": "NORMAL",
        "model_version": "iforest-test",
        **changes,
    }


def _alert(message_id="alert-test-0001", **changes) -> dict:
    return {
        "message_id": message_id,
        "alert_id": "alert-test-0001",
        "machine_id": "M01",
        "fog_id": "FOG_A",
        "timestamp": AT,
        "type": "ANOMALY_DETECTED",
        "severity": "WARNING",
        "message": "Vibration elevee",
        **changes,
    }


def _kpi(**changes) -> dict:
    return {
        "metric": "tasks_migrated_total",
        "scope": "fog",
        "scope_value": "FOG_A",
        "bucket_start": AT,
        "bucket_end": AT + timedelta(hours=1),
        "value": 1.0,
        "sample_size": 1,
        **changes,
    }


async def _table_names(database) -> set[str]:
    url = database.url.set(drivername="postgresql").render_as_string(hide_password=False)
    connection = await asyncpg.connect(url, timeout=10)
    try:
        rows = await connection.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return {row["tablename"] for row in rows}
    finally:
        await connection.close()


def test_migration_replay_and_round_trip(postgres_database):
    config = postgres_database.alembic_config()
    expected = set(Base.metadata.tables) | {"alembic_version"}
    assert len(Base.metadata.tables) == 9
    assert asyncio.run(_table_names(postgres_database)) == expected
    command.upgrade(config, "head")
    assert asyncio.run(_table_names(postgres_database)) == expected
    command.check(config)

    # Ce nom vient exclusivement de la fixture de base jetable, jamais de fog_cloud.
    command.downgrade(config, "base")
    assert asyncio.run(_table_names(postgres_database)) == {"alembic_version"}
    command.upgrade(config, "head")
    assert asyncio.run(_table_names(postgres_database)) == expected
    command.check(config)


async def test_catalogue_is_idempotent_and_preserves_observations(db_session: AsyncSession):
    first = await initialize_catalogue(db_session)
    second = await initialize_catalogue(db_session)
    assert (first.fog_inserted, first.machines_inserted) == (3, 12)
    assert (second.fog_inserted, second.machines_inserted) == (0, 0)
    assert (second.fog_total, second.machines_total) == (3, 12)

    machines = (await db_session.execute(select(Machine).order_by(Machine.machine_id))).scalars()
    for number, machine in enumerate(machines, start=1):
        zone = ("A", "B", "C")[(number - 1) // 4]
        assert (machine.machine_id, machine.zone, machine.fog_id) == (
            f"M{number:02d}",
            zone,
            f"FOG_{zone}",
        )
        assert machine.machine_type == "UNSPECIFIED"
        assert machine.installed_at is None
        assert machine.registered_at.utcoffset() == timedelta(0)
    nodes = (await db_session.execute(select(FogNode))).scalars().all()
    assert all(node.status == "OFFLINE" and node.last_heartbeat is None for node in nodes)
    assert all(
        node.cpu_percent is None
        and node.ram_percent is None
        and node.queued_tasks is None
        and node.active_tasks is None
        for node in nodes
    )
    await db_session.execute(
        update(FogNode)
        .where(FogNode.fog_id == "FOG_A")
        .values(status="ONLINE", cpu_percent=25.0, last_heartbeat=AT, environment_ref="test-vm-A")
    )
    await db_session.execute(
        update(Machine)
        .where(Machine.machine_id == "M01")
        .values(name="Pompe de test", machine_type="PUMP", installed_at=AT)
    )
    third = await initialize_catalogue(db_session)
    assert (third.fog_inserted, third.machines_inserted) == (0, 0)
    db_session.expire_all()
    node = await db_session.get(FogNode, "FOG_A")
    machine = await db_session.get(Machine, "M01")
    assert (node.status, node.cpu_percent, node.last_heartbeat) == ("ONLINE", 25.0, AT)
    assert node.environment_ref == "test-vm-A"
    assert (machine.name, machine.machine_type, machine.installed_at) == (
        "Pompe de test",
        "PUMP",
        AT,
    )


async def test_existing_wire_fixtures_fit_database(populated_session: AsyncSession):
    session = populated_session
    for filename, model in (
        ("sensor_ok.json", SensorData),
        ("prediction_ok.json", Prediction),
        ("alert_ok.json", Alert),
    ):
        raw = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
        payload = parse_message(raw["kind"], raw["payload"]).model_dump()
        await session.execute(insert(model).values(payload))
    raw = json.loads((FIXTURES / "fog_status_ok.json").read_text(encoding="utf-8"))
    payload = parse_message(raw["kind"], raw["payload"]).model_dump()
    payload["observed_at"] = payload.pop("last_heartbeat")
    await session.execute(insert(FogStatusHistory).values(payload))

    raw = json.loads((FIXTURES / "task_event_ok.json").read_text(encoding="utf-8"))
    payload = parse_message(raw["kind"], raw["payload"]).model_dump()
    await session.execute(
        insert(Task).values(
            _task(
                task_id=payload["task_id"],
                created_at=payload["created_at"],
                status="MIGRATED",
                origin_fog_id=None,
                current_fog_id=payload["destination_fog"],
            )
        )
    )
    await session.execute(insert(TaskEvent).values(payload))
    task = await session.get(Task, payload["task_id"])
    event = (await session.execute(select(TaskEvent))).scalar_one()
    assert task.origin_fog_id is None
    assert task.last_event_at is None and event.occurred_at is None
    assert event.created_at == payload["created_at"]
    assert event.received_at.utcoffset() == timedelta(0)


MESSAGE_MODELS = [
    (SensorData, _sensor),
    (Prediction, _prediction),
    (Alert, _alert),
    (FogStatusHistory, _history),
    (TaskEvent, _event),
]


@pytest.mark.parametrize("model,factory", MESSAGE_MODELS, ids=lambda value: value.__name__)
async def test_message_ids_allow_64_characters(populated_session, model, factory):
    if model is TaskEvent:
        await populated_session.execute(insert(Task).values(_task()))
    message_id = "m" * 64
    await populated_session.execute(insert(model).values(factory(message_id=message_id)))
    row = (await populated_session.execute(select(model))).scalar_one()
    assert row.message_id == message_id


@pytest.mark.parametrize("model,factory", MESSAGE_MODELS, ids=lambda value: value.__name__)
async def test_reemitted_message_cannot_create_a_duplicate(populated_session, model, factory):
    session = populated_session
    if model is TaskEvent:
        await session.execute(insert(Task).values(_task()))
    payload = factory()
    await session.execute(insert(model).values(payload))
    with pytest.raises(IntegrityError) as error:
        async with session.begin_nested():
            await session.execute(insert(model).values(payload))
    assert error.value.orig.sqlstate == "23505"  # unique_violation
    assert (await session.execute(select(func.count()).select_from(model))).scalar_one() == 1


@pytest.mark.parametrize(
    "model,factory,changes",
    [
        (SensorData, _sensor, {"machine_id": "M99"}),
        (SensorData, _sensor, {"zone": "B"}),
        (Prediction, _prediction, {"fog_id": "FOG_D"}),
        (Alert, _alert, {"machine_id": "M99"}),
        (FogStatusHistory, _history, {"zone": "B"}),
        (Task, _task, {"current_fog_id": "FOG_D"}),
        (TaskEvent, _event, {"destination_fog": "FOG_D"}),
        (TaskEvent, _event, {"task_id": str(uuid4())}),
    ],
)
async def test_unknown_or_inconsistent_references_are_rejected(
    populated_session, model, factory, changes
):
    session = populated_session
    if model is TaskEvent:
        await session.execute(insert(Task).values(_task()))
    with pytest.raises(IntegrityError) as error:
        async with session.begin_nested():
            await session.execute(insert(model).values(factory(**changes)))
    assert error.value.orig.sqlstate == "23503"  # foreign_key_violation


@pytest.mark.parametrize(
    "model,factory,changes",
    [
        (SensorData, _sensor, {"temperature": 301.0}),
        (SensorData, _sensor, {"vibration": -0.1}),
        (SensorData, _sensor, {"speed": 20001.0}),
        (SensorData, _sensor, {"current": 1001.0}),
        (SensorData, _sensor, {"pressure": -0.1}),
        (SensorData, _sensor, {"power": 1001.0}),
        (SensorData, _sensor, {"frequency": 401.0}),
        (SensorData, _sensor, {"temperature": float("nan")}),
        (SensorData, _sensor, {"state": "UNKNOWN"}),
        (Prediction, _prediction, {"risk_score": Decimal("1.00001")}),
        (Prediction, _prediction, {"risk_score": Decimal("-0.00001")}),
        (Prediction, _prediction, {"severity": "UNKNOWN"}),
        (FogStatusHistory, _history, {"cpu_percent": 100.1}),
        (FogStatusHistory, _history, {"ram_percent": -0.1}),
        (FogStatusHistory, _history, {"queued_tasks": -1}),
        (FogStatusHistory, _history, {"active_tasks": -1}),
        (FogStatusHistory, _history, {"status": "UNKNOWN"}),
        (Alert, _alert, {"message": ""}),
        (Task, _task, {"task_id": "b3f1c2d4-6a11-1f3a-9c2e-7d5b1a0e9f42"}),
    ],
)
async def test_database_bounds_apply_without_pydantic(populated_session, model, factory, changes):
    with pytest.raises(IntegrityError) as error:
        async with populated_session.begin_nested():
            await populated_session.execute(insert(model).values(factory(**changes)))
    assert error.value.orig.sqlstate == "23514"  # check_violation


@pytest.mark.parametrize(
    "model,factory,changes",
    [
        (Task, _task, {"started_at": AT - timedelta(seconds=1)}),
        (Task, _task, {"completed_at": AT - timedelta(seconds=1)}),
        (Task, _task, {"started_at": AT + timedelta(seconds=5), "completed_at": AT}),
        (TaskEvent, _event, {"occurred_at": AT - timedelta(seconds=1)}),
        (Alert, _alert, {"resolved_at": AT - timedelta(seconds=1)}),
        (Alert, _alert, {"acknowledged_at": AT + timedelta(seconds=5), "resolved_at": AT}),
    ],
)
async def test_known_dates_cannot_have_impossible_order(populated_session, model, factory, changes):
    if model is TaskEvent:
        await populated_session.execute(insert(Task).values(_task()))
    with pytest.raises(IntegrityError) as error:
        async with populated_session.begin_nested():
            await populated_session.execute(insert(model).values(factory(**changes)))
    assert error.value.orig.sqlstate == "23514"


@pytest.mark.parametrize(
    "message_id,sqlstate",
    [
        ("short", "23514"),
        ("m" * 65, "22001"),
    ],
)
async def test_message_id_limits_apply_in_database(populated_session, message_id, sqlstate):
    with pytest.raises(DBAPIError) as error:
        async with populated_session.begin_nested():
            await populated_session.execute(
                insert(SensorData).values(_sensor(message_id=message_id))
            )
    assert error.value.orig.sqlstate == sqlstate


async def test_risk_score_is_not_rounded(populated_session):
    score = Decimal("0.1234567890123456789")
    await populated_session.execute(insert(Prediction).values(_prediction(risk_score=score)))
    row = (await populated_session.execute(select(Prediction))).scalar_one()
    assert row.risk_score == score


@pytest.mark.parametrize("new_origin", ["FOG_B", None])
async def test_known_task_origin_is_immutable(populated_session, new_origin):
    session = populated_session
    await session.execute(insert(Task).values(_task()))
    with pytest.raises(IntegrityError) as error:
        async with session.begin_nested():
            await session.execute(
                update(Task).where(Task.task_id == TASK_ID).values(origin_fog_id=new_origin)
            )
    assert error.value.orig.sqlstate == "23514"
    await session.execute(
        update(Task).where(Task.task_id == TASK_ID).values(current_fog_id="FOG_B")
    )
    task = await session.get(Task, TASK_ID)
    assert (task.origin_fog_id, task.current_fog_id) == ("FOG_A", "FOG_B")


async def test_unknown_origin_and_assignment_can_be_completed(populated_session):
    session = populated_session
    await session.execute(insert(Task).values(_task(origin_fog_id=None, current_fog_id=None)))
    task = await session.get(Task, TASK_ID)
    assert task.origin_fog_id is None and task.current_fog_id is None
    await session.execute(
        update(Task)
        .where(Task.task_id == TASK_ID)
        .values(origin_fog_id="FOG_C", current_fog_id="FOG_B")
    )
    await session.refresh(task)
    assert (task.origin_fog_id, task.current_fog_id) == ("FOG_C", "FOG_B")


async def test_collaboration_keeps_task_origin_events_and_load_history(populated_session):
    session = populated_session
    for zone in ("A", "B", "C"):
        await session.execute(
            insert(FogStatusHistory).values(
                _history(
                    message_id=f"normal-fog-{zone}-0001",
                    fog_id=f"FOG_{zone}",
                    zone=zone,
                )
            )
        )
        await session.execute(
            update(FogNode)
            .where(FogNode.fog_id == f"FOG_{zone}")
            .values(
                status="ONLINE",
                cpu_percent=30.0,
                ram_percent=40.0,
                queued_tasks=1,
                active_tasks=2,
                last_heartbeat=AT,
            )
        )
    await session.execute(
        insert(FogStatusHistory).values(
            _history(
                message_id="overloaded-fog-A-0002",
                status="OVERLOADED",
                cpu_percent=92.0,
                queued_tasks=12,
                observed_at=AT + timedelta(seconds=10),
            )
        )
    )
    await session.execute(
        insert(FogStatusHistory).values(
            _history(
                message_id="after-share-fog-A-0003",
                cpu_percent=60.0,
                queued_tasks=4,
                observed_at=AT + timedelta(seconds=20),
            )
        )
    )
    await session.execute(
        update(FogNode)
        .where(FogNode.fog_id == "FOG_A")
        .values(
            cpu_percent=60.0,
            queued_tasks=4,
            last_heartbeat=AT + timedelta(seconds=20),
        )
    )

    await session.execute(insert(Task).values(_task()))
    timeline = [
        (0, "CREATED", "FOG_A", None),
        (1, "QUEUED", "FOG_A", None),
        (10, "MIGRATED", "FOG_A", "FOG_B"),
        (12, "RUNNING", "FOG_B", None),
        (18, "COMPLETED", "FOG_B", None),
    ]
    for offset, status, source, destination in timeline:
        at = AT + timedelta(seconds=offset)
        await session.execute(
            insert(TaskEvent).values(
                _event(
                    message_id=f"sharing-task-event-{offset:04d}",
                    status=status,
                    source_fog=source,
                    destination_fog=destination,
                    occurred_at=at,
                    completed_at=at if status == "COMPLETED" else None,
                )
            )
        )
    await session.execute(
        update(Task)
        .where(Task.task_id == TASK_ID)
        .values(
            current_fog_id="FOG_B",
            status="COMPLETED",
            started_at=AT + timedelta(seconds=12),
            completed_at=AT + timedelta(seconds=18),
            last_event_at=AT + timedelta(seconds=18),
        )
    )
    task = await session.get(Task, TASK_ID)
    assert (task.origin_fog_id, task.current_fog_id, task.status) == ("FOG_A", "FOG_B", "COMPLETED")
    events = (
        (
            await session.execute(
                select(TaskEvent)
                .where(TaskEvent.task_id == TASK_ID)
                .order_by(TaskEvent.occurred_at)
            )
        )
        .scalars()
        .all()
    )
    assert [event.status for event in events] == [item[1] for item in timeline]
    assert len({event.message_id for event in events}) == 5
    assert (events[2].source_fog, events[2].destination_fog) == ("FOG_A", "FOG_B")
    history = (
        (
            await session.execute(
                select(FogStatusHistory)
                .where(FogStatusHistory.fog_id == "FOG_A")
                .order_by(FogStatusHistory.observed_at)
            )
        )
        .scalars()
        .all()
    )
    assert [row.cpu_percent for row in history] == [30.0, 92.0, 60.0]
    assert [row.queued_tasks for row in history] == [1, 12, 4]
    assert (await session.get(FogNode, "FOG_A")).cpu_percent == 60.0


async def test_critical_task_can_stay_local_or_recover_after_failure(populated_session):
    session = populated_session
    await session.execute(
        insert(Task).values(
            _task(
                critical=True,
                priority="CRITICAL",
                task_type="ANOMALY_DETECTION",
                status="RUNNING",
            )
        )
    )
    await session.execute(
        insert(TaskEvent).values(
            _event(
                critical=True,
                priority="CRITICAL",
                task_type="ANOMALY_DETECTION",
                status="RUNNING",
                occurred_at=AT + timedelta(seconds=1),
            )
        )
    )
    task = await session.get(Task, TASK_ID)
    assert task.current_fog_id == task.origin_fog_id == "FOG_A"

    await session.execute(
        insert(TaskEvent).values(
            _event(
                message_id="critical-task-failed-0002",
                critical=True,
                priority="CRITICAL",
                task_type="ANOMALY_DETECTION",
                status="FAILED",
                occurred_at=AT + timedelta(seconds=10),
                reason="Panne FOG_A dans le scenario de test",
            )
        )
    )
    await session.execute(
        insert(TaskEvent).values(
            _event(
                message_id="critical-task-recovered-0003",
                critical=True,
                priority="CRITICAL",
                task_type="ANOMALY_DETECTION",
                status="RECOVERED",
                destination_fog="FOG_C",
                occurred_at=AT + timedelta(seconds=11),
                reason="Reprise autorisee par la politique MP2",
            )
        )
    )
    await session.execute(
        insert(TaskEvent).values(
            _event(
                message_id="critical-task-resumed-0004",
                critical=True,
                priority="CRITICAL",
                task_type="ANOMALY_DETECTION",
                status="RUNNING",
                source_fog="FOG_C",
                occurred_at=AT + timedelta(seconds=12),
            )
        )
    )
    await session.execute(
        update(Task)
        .where(Task.task_id == TASK_ID)
        .values(
            current_fog_id="FOG_C",
            status="RUNNING",
            last_event_at=AT + timedelta(seconds=12),
        )
    )
    await session.refresh(task)
    assert (task.origin_fog_id, task.current_fog_id) == ("FOG_A", "FOG_C")
    events = (
        (await session.execute(select(TaskEvent).order_by(TaskEvent.occurred_at))).scalars().all()
    )
    assert [event.status for event in events] == ["RUNNING", "FAILED", "RECOVERED", "RUNNING"]


@pytest.mark.parametrize(
    "changes",
    [
        {"bucket_end": AT},
        {"sample_size": -1},
        {"value": float("inf")},
        {"value": float("nan")},
    ],
)
async def test_invalid_kpi_windows_or_values_are_rejected(db_session, changes):
    with pytest.raises(IntegrityError) as error:
        async with db_session.begin_nested():
            await db_session.execute(insert(KpiRecord).values(_kpi(**changes)))
    assert error.value.orig.sqlstate == "23514"


async def test_kpi_bucket_is_unique(db_session):
    await db_session.execute(insert(KpiRecord).values(_kpi()))
    with pytest.raises(IntegrityError) as error:
        async with db_session.begin_nested():
            await db_session.execute(insert(KpiRecord).values(_kpi(value=2.0)))
    assert error.value.orig.sqlstate == "23505"
