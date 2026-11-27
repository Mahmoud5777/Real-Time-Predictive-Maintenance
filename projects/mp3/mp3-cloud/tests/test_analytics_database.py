"""Known numeric results, cache atomicity and HTTP reads on disposable PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
import yaml
from httpx import ASGITransport, AsyncClient
from openapi_schema_validator import OAS30Validator
from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from test_integration_database import _alert, _event, _prediction, _sensor, _task
from test_read_database import expand_refs

from alembic import command
from app.analytics.aggregate import LOCK_ID, refresh
from app.analytics.aggregate import aggregate_rows as real_aggregate_rows
from app.analytics.catalogue import UNAVAILABLE
from app.config import Settings
from app.db.catalogue import initialize_catalogue
from app.db.session import get_session
from app.main import create_app
from app.models.tables import Alert, KpiRecord, Prediction, SensorData, Task, TaskEvent
from scripts.export_openapi import CONTRACT

pytestmark = pytest.mark.postgres
AT = datetime(2026, 11, 7, 10, tzinfo=UTC)
HOUR = timedelta(hours=1)
NOW = AT + HOUR + timedelta(minutes=10)
CONFIG = Settings(_env_file=None)


@pytest_asyncio.fixture
async def factory(committed_postgres_database):
    engine = create_async_engine(committed_postgres_database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await initialize_catalogue(session)
        await session.commit()
    try:
        yield factory
    finally:
        await engine.dispose()


async def calculate(factory, **kwargs):
    return await refresh(factory, CONFIG, AT, AT + HOUR, now=NOW, **kwargs)


async def records(factory):
    async with factory() as session:
        return {
            (r.metric, r.scope, r.scope_value): r
            for r in (await session.execute(select(KpiRecord))).scalars()
        }


async def test_numeric_results_scopes_boundaries_nulls_and_clock_skew(factory):
    async with factory() as session, session.begin():
        for i, temp, pressure, offset, delay in [
            (1, 60, 2, 0, 2),
            (2, 80, None, 10, -1),
            (3, 100, 4, 20, 4),
            (4, 250, 99, 3600, 1),
            (5, -40, 99, -1, 1),
        ]:
            ts = AT + timedelta(seconds=offset)
            await session.execute(
                insert(SensorData).values(
                    _sensor(
                        message_id=f"kpi-sensor-{i:04d}",
                        timestamp=ts,
                        temperature=temp,
                        pressure=pressure,
                        power=None,
                        frequency=None,
                        received_at=ts + timedelta(seconds=delay),
                    )
                )
            )
        for i, machine, fog, model, risk, anomaly in [
            (1, "M01", "FOG_B", "v" * 64, 0.9, True),
            (2, "M01", "FOG_B", "v" * 64, 0.5, False),
            (3, "M05", "FOG_A", "v2", 0.2, False),
        ]:
            await session.execute(
                insert(Prediction).values(
                    _prediction(
                        message_id=f"kpi-prediction-{i:04d}",
                        timestamp=AT,
                        machine_id=machine,
                        fog_id=fog,
                        model_version=model,
                        risk_score=risk,
                        anomaly=anomaly,
                        severity="CRITICAL" if i == 1 else "NORMAL",
                    )
                )
            )
    assert await calculate(factory) > 0
    rows = await records(factory)

    def row(metric, scope="plant", value="all"):
        return rows[metric, scope, value]

    assert row("measurement_count").value == 3
    assert row("mean_temperature").value == 80
    assert row("mean_pressure").value == 3 and row("mean_pressure").sample_size == 2
    assert row("mean_ingest_latency_s").value == 3
    assert row("mean_ingest_latency_s").sample_size == 2
    assert row("clock_skew_count").value == 1
    assert ("mean_power", "plant", "all") not in rows
    assert row("mean_risk_score").value == pytest.approx(1.6 / 3)
    assert row("anomaly_ratio").value == pytest.approx(1 / 3)
    assert row("critical_prediction_count").value == 1
    assert row("mean_risk_score", "model", "v" * 64).value == pytest.approx(0.7)
    assert row("prediction_count", "zone", "A").value == 2
    assert row("prediction_count", "fog", "FOG_B").value == 2
    assert row("measurement_count", "fog", "FOG_A").value == 3
    assert all(r.bucket_start == AT and r.bucket_end == AT + HOUR for r in rows.values())
    assert all(r.computed_at == NOW for r in rows.values())
    assert not any(r.metric in UNAVAILABLE for r in rows.values())


async def test_resolutions_use_resolution_hour_and_task_counts_use_receipt_hour(factory):
    async with factory() as session, session.begin():
        await session.execute(
            insert(Alert).values(
                _alert(
                    timestamp=AT - 2 * HOUR, resolved_at=AT, status="RESOLVED", severity="CRITICAL"
                )
            )
        )
        await session.execute(
            insert(Alert).values(
                _alert(
                    message_id="kpi-open-alert-0001",
                    alert_id="open",
                    timestamp=AT,
                    status="OPEN",
                    severity="CRITICAL",
                )
            )
        )
        await session.execute(
            insert(Task).values(
                _task(created_at=AT - HOUR, origin_fog_id="FOG_A", current_fog_id="FOG_B")
            )
        )
        for i, status in enumerate(["MIGRATED", "COMPLETED", "COMPLETED"], 1):
            await session.execute(
                insert(TaskEvent).values(
                    _event(
                        message_id=f"kpi-task-event-{i:04d}",
                        created_at=AT - HOUR,
                        occurred_at=None,
                        received_at=AT,
                        source_fog="FOG_B",
                        status=status,
                    )
                )
            )
    await calculate(factory)
    rows = await records(factory)
    assert rows["mttr_hours", "plant", "all"].value == 2
    assert rows["mttr_hours", "plant", "all"].sample_size == 1
    assert rows["critical_alert_count", "plant", "all"].value == 1
    assert rows["task_event_count", "plant", "all"].value == 3
    assert rows["tasks_migrated_total", "plant", "all"].value == 1
    assert rows["completed_task_reports", "plant", "all"].value == 1
    assert rows["task_event_count", "zone", "A"].value == 3
    assert rows["task_event_count", "fog", "FOG_B"].value == 3


async def test_unknown_task_origin_is_counted_only_in_known_scopes(factory):
    async with factory() as session, session.begin():
        await session.execute(
            insert(Task).values(_task(created_at=AT, origin_fog_id=None, machine_id=None))
        )
        await session.execute(insert(TaskEvent).values(_event(created_at=AT, received_at=AT)))
    await calculate(factory)
    rows = await records(factory)
    assert rows["task_event_count", "plant", "all"].value == 1
    assert rows["task_event_count", "fog", "FOG_A"].value == 1
    assert not any(r.scope in ("zone", "machine") for r in rows.values())


async def test_refresh_is_idempotent_and_includes_late_data_without_erasing_unowned(factory):
    async with factory() as session, session.begin():
        await session.execute(insert(SensorData).values(_sensor(timestamp=AT)))
        await session.execute(
            insert(KpiRecord).values(
                metric="future_metric",
                scope="plant",
                scope_value="all",
                bucket_start=AT,
                bucket_end=AT + HOUR,
                value=42,
                sample_size=1,
            )
        )
    first = await calculate(factory)
    assert await calculate(factory) == first
    async with factory() as session, session.begin():
        await session.execute(
            insert(SensorData).values(
                _sensor(
                    message_id="late-kpi-sensor-0001",
                    timestamp=AT,
                    temperature=90,
                )
            )
        )
    assert await calculate(factory) == first
    rows = await records(factory)
    assert rows["measurement_count", "plant", "all"].value == 2
    assert rows["mean_temperature", "plant", "all"].value == 80
    assert rows["future_metric", "plant", "all"].value == 42


async def test_empty_input_keeps_means_absent_and_http_explains_unsupported(factory):
    assert await calculate(factory) == 0
    # Unsupported manual/legacy rows must not become claimed measurements.
    async with factory() as session, session.begin():
        await session.execute(
            insert(KpiRecord).values(
                metric="model_precision",
                scope="plant",
                scope_value="all",
                bucket_start=AT,
                bucket_end=AT + HOUR,
                value=0.5,
                sample_size=1,
            )
        )
    app = create_app()

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        for path in ["kpis", "measurements", "model-comparison", "risk-ranking"]:
            response = await client.get(
                f"/api/v1/analytics/{path}",
                params={
                    "from": AT.isoformat(),
                    "to": (AT + HOUR).isoformat(),
                },
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["items"] == [] and body["meta"]["total"] == 0
            assert body["empty_reason"] and body["unavailable_metrics"] == UNAVAILABLE
        response = await client.get(
            "/api/v1/analytics/kpis",
            params={
                "from": AT.isoformat(),
                "to": (AT + HOUR).isoformat(),
                "metric": "model_precision",
            },
        )
        assert response.status_code == 200 and response.json()["items"] == []


async def test_concurrent_refresh_skips_and_releases_lock(factory):
    async with factory() as locker, locker.begin():
        await locker.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": LOCK_ID})
        assert await calculate(factory) is None
    assert await calculate(factory) == 0


async def test_failure_after_delete_and_cancellation_preserve_cache(factory):
    async with factory() as session, session.begin():
        await session.execute(insert(SensorData).values(_sensor(timestamp=AT)))
    await calculate(factory)
    before = {key: (r.id, r.value) for key, r in (await records(factory)).items()}
    for error in [DBAPIError("private", {}, Exception("fail")), asyncio.CancelledError()]:
        original = insert

        def failed_insert(*args, failure=error, real_insert=original, **kwargs):
            if args[0] is KpiRecord:
                raise failure
            return real_insert(*args, **kwargs)

        with patch("app.analytics.aggregate.insert", failed_insert), pytest.raises(type(error)):
            await calculate(factory)
        assert {key: (r.id, r.value) for key, r in (await records(factory)).items()} == before
    assert await calculate(factory) > 0  # failed/cancelled transaction released its lock


async def test_refresh_refuses_expired_data_before_opening_a_session(factory):
    with pytest.raises(ValueError, match="retention"):
        await refresh(factory, CONFIG, AT - 8 * 24 * HOUR, AT - 8 * 24 * HOUR + HOUR, now=NOW)


async def test_timeout_preserves_cache_and_releases_the_transaction_lock(factory):
    async with factory() as session, session.begin():
        await session.execute(insert(SensorData).values(_sensor(timestamp=AT)))
    await calculate(factory)
    before = {key: r.id for key, r in (await records(factory)).items()}
    config = CONFIG.model_copy(update={"kpi_database_timeout_seconds": 0.5})

    async def stalled(*_):
        await asyncio.Event().wait()

    with patch("app.analytics.aggregate.aggregate_rows", stalled), pytest.raises(TimeoutError):
        await refresh(factory, config, AT, AT + HOUR, now=NOW)
    assert {key: r.id for key, r in (await records(factory)).items()} == before
    assert await calculate(factory) > 0


async def test_one_snapshot_excludes_data_committed_during_refresh(factory):
    async with factory() as session, session.begin():
        await session.execute(insert(SensorData).values(_sensor(timestamp=AT)))

    async def concurrent_arrival(session, *args):
        async with factory() as writer, writer.begin():
            await writer.execute(insert(Prediction).values(_prediction(timestamp=AT)))
        return await real_aggregate_rows(session, *args)

    with patch("app.analytics.aggregate.aggregate_rows", concurrent_arrival):
        await calculate(factory)
    assert ("prediction_count", "plant", "all") not in await records(factory)
    await calculate(factory)
    assert (await records(factory))["prediction_count", "plant", "all"].value == 1


async def test_multi_hour_results_are_separate_and_earliest_partial_hour_is_skipped(factory):
    async with factory() as session, session.begin():
        for i in range(2):
            await session.execute(
                insert(SensorData).values(
                    _sensor(
                        message_id=f"multi-hour-sensor-{i:04d}",
                        timestamp=AT - i * HOUR,
                        temperature=60 + 20 * i,
                    )
                )
            )
    await refresh(factory, CONFIG, AT - HOUR, AT + HOUR, now=NOW)
    async with factory() as session:
        rows = (
            (
                await session.execute(
                    select(KpiRecord)
                    .where(KpiRecord.metric == "mean_temperature", KpiRecord.scope == "plant")
                    .order_by(KpiRecord.bucket_start)
                )
            )
            .scalars()
            .all()
        )
    assert [r.value for r in rows] == [80, 60]
    config = CONFIG.model_copy(update={"raw_retention_days": 1, "kpi_lookback_hours": 24})
    assert await refresh(factory, config, now=NOW) > 0


async def test_analytics_http_units_samples_filters_sort_and_pagination(factory):
    async with factory() as session, session.begin():
        for number, risk in [(1, 0.1), (5, 0.8)]:
            await session.execute(
                insert(Prediction).values(
                    _prediction(
                        message_id=f"http-kpi-pred-{number:04d}",
                        machine_id=f"M{number:02d}",
                        timestamp=AT,
                        risk_score=risk,
                        model_version="v1",
                    )
                )
            )
    await calculate(factory)
    app = create_app()

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    params = {"from": AT.isoformat(), "to": (AT + HOUR).isoformat()}
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get("/api/v1/analytics/risk-ranking", params={**params, "limit": 1})
        assert response.status_code == 200, response.text
        body = response.json()
        contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
        schema = contract["paths"]["/analytics/risk-ranking"]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        OAS30Validator(expand_refs(schema, contract)).validate(body)
        assert body["meta"]["total"] == 2 and len(body["items"]) == 1
        item = body["items"][0]
        assert item["scope_value"] == "M05" and item["value"] == 0.8
        assert item["quality"] == "LOW_SAMPLE" and item["unit"] == "ratio"
        assert item["time_basis"] == "prediction.timestamp" and item["sample_size"] == 1
        response = await client.get(
            "/api/v1/analytics/risk-ranking", params={**params, "limit": 1, "offset": 1}
        )
        assert response.json()["items"][0]["scope_value"] == "M01"
        response = await client.get(
            "/api/v1/analytics/model-comparison", params={**params, "model_version": "v1"}
        )
        assert response.status_code == 200, response.text
        assert len(response.json()["items"]) == 5
        assert "accuracy" in response.json()["note"]
        response = await client.get(
            "/api/v1/analytics/kpis",
            params={
                **params,
                "scope": "zone",
                "scope_value": "B",
                "metric": "prediction_count",
            },
        )
        assert response.json()["items"][0]["value"] == 1
        response = await client.get(
            "/api/v1/analytics/kpis",
            params={
                **params,
                "metric": "model_precision",
            },
        )
        assert response.json()["items"] == [] and response.json()["empty_reason"]


def test_scope_migration_roundtrip_and_no_truncation(committed_postgres_database):
    database = committed_postgres_database

    async def add_long():
        engine = create_async_engine(database.url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(KpiRecord).values(
                        metric="mean_risk_score",
                        scope="model",
                        scope_value="v" * 64,
                        bucket_start=AT,
                        bucket_end=AT + HOUR,
                        value=0.5,
                        sample_size=1,
                    )
                )
        finally:
            await engine.dispose()

    asyncio.run(add_long())
    config = database.alembic_config()
    with pytest.raises(DBAPIError):
        command.downgrade(config, "0001_mp3_schema")

    async def shorten():
        engine = create_async_engine(database.url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                assert (
                    await connection.execute(select(KpiRecord.scope_value))
                ).scalar_one() == "v" * 64
                await connection.execute(update(KpiRecord).values(scope_value="v1"))
        finally:
            await engine.dispose()

    asyncio.run(shorten())
    command.downgrade(config, "0001_mp3_schema")
    command.upgrade(config, "head")
    command.check(config)
