"""Purge real expired raw rows only after preserving aggregates and replay identities."""

import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from alembic import command
from app.analytics.aggregate import refresh
from app.config import Settings
from app.db.catalogue import initialize_catalogue
from app.models.tables import (
    Alert,
    FogStatusHistory,
    IngestReceipt,
    KpiRecord,
    Prediction,
    SensorData,
)
from app.retention.service import run_retention
from app.services.ingest import persist_batch
from app.services.receipts import RETENTION_LOCK

pytestmark = pytest.mark.postgres
NOW = datetime(2026, 11, 7, 12, 30, tzinfo=UTC)
OLD = datetime(2026, 10, 30, 10, tzinfo=UTC)
CONFIG = Settings(_env_file=None)
FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"


@pytest_asyncio.fixture
async def factory(committed_postgres_database):
    engine = create_async_engine(committed_postgres_database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session, session.begin():
        await initialize_catalogue(session)
    try:
        yield factory
    finally:
        await engine.dispose()


def wire(kind, identity, timestamp=OLD, **changes):
    name = "sensor_ok.json" if kind == "sensor" else "prediction_ok.json"
    item = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    item["payload"].update(message_id=identity, timestamp=timestamp.isoformat(), **changes)
    return item


async def send(factory, *items):
    async with factory() as session:
        return await persist_batch(session, list(items))


async def count(factory, model):
    async with factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def purge(factory, *, config=CONFIG, dry_run=False):
    return await run_retention(factory, config, now=NOW, dry_run=dry_run)


async def test_preview_is_read_only_and_cutoff_preserves_partial_oldest_hour(factory):
    await send(
        factory, wire("sensor", "retain-old-sensor"), wire("sensor", "retain-new-sensor", NOW)
    )
    result = await purge(factory, dry_run=True)
    assert result.cutoff == datetime(2026, 10, 31, 12, tzinfo=UTC)
    assert result.candidates == {"sensor": 1, "prediction": 0}
    assert sum(result.deleted.values()) == 0
    assert await count(factory, SensorData) == 2
    assert await count(factory, KpiRecord) == 0
    assert await count(factory, IngestReceipt) == 2


async def test_aggregates_survive_purge_replays_remain_duplicates_and_conflicts_rejected(factory):
    sensor = wire("sensor", "retain-old-sensor", temperature=60)
    pred = wire("prediction", "retain-old-prediction", risk_score=0.8)
    await send(factory, sensor, pred, wire("sensor", "retain-new-sensor", NOW, temperature=80))
    result = await purge(factory)
    assert result.deleted == {"sensor": 1, "prediction": 1}
    assert await count(factory, SensorData) == 1 and await count(factory, Prediction) == 0
    async with factory() as session:
        mean = await session.scalar(
            select(KpiRecord.value).where(
                KpiRecord.metric == "mean_temperature",
                KpiRecord.scope == "plant",
                KpiRecord.bucket_start == OLD,
            )
        )
        assert mean == 60
        assert (
            await session.scalar(
                select(KpiRecord.value).where(
                    KpiRecord.metric == "mean_risk_score", KpiRecord.scope == "plant"
                )
            )
            == 0.8
        )
    report = await send(factory, sensor, pred)
    assert report.duplicates == 2 and report.accepted == report.rejected == 0
    changed = copy.deepcopy(pred)
    changed["payload"]["risk_score"] = 0.2
    report = await send(factory, changed)
    assert report.rejected == 1 and report.errors[0]["code"] == "MESSAGE_ID_CONFLICT"
    assert await count(factory, Prediction) == 0


async def test_finalized_hour_rejects_unknown_late_ids_without_orphan_receipts(factory):
    await send(factory, wire("prediction", "retain-prediction-old"))
    await purge(factory)
    report = await send(factory, wire("prediction", "late-new-prediction"))
    assert report.errors[0]["code"] == "EXPIRED_WINDOW" and report.rejected == 1
    assert await count(factory, IngestReceipt) == 1 and await count(factory, Prediction) == 0
    # Increasing retention later must not permit destructive cache recomputation of purged raw.
    extended = CONFIG.model_copy(update={"raw_retention_days": 14})
    with pytest.raises(ValueError, match="finalized hours"):
        await refresh(factory, extended, OLD, OLD + timedelta(hours=1), now=NOW)
    async with factory() as session:
        assert (
            await session.scalar(
                select(KpiRecord.value).where(
                    KpiRecord.metric == "prediction_count", KpiRecord.scope == "plant"
                )
            )
            == 1
        )


async def test_batch_bound_keeps_complete_hour_aggregate_and_never_recomputes_partial_source(
    factory,
):
    for i in range(3):
        await send(factory, wire("prediction", f"retain-batch-pred-{i}", risk_score=(i + 1) / 10))
    config = CONFIG.model_copy(update={"retention_batch_size": 1})
    for remaining in [2, 1, 0]:
        assert (await purge(factory, config=config)).deleted["prediction"] == 1
        assert await count(factory, Prediction) == remaining
        async with factory() as session:
            row = (
                await session.execute(
                    select(KpiRecord).where(
                        KpiRecord.metric == "prediction_count", KpiRecord.scope == "plant"
                    )
                )
            ).scalar_one()
            assert row.value == 3 and row.sample_size == 3
    assert sum((await purge(factory)).deleted.values()) == 0


async def test_legacy_rows_get_receipts_and_retained_latest_still_replays(factory):
    latest = wire("sensor", "legacy-latest-sensor")
    old = wire("sensor", "legacy-old-sensor", OLD - timedelta(seconds=1))
    async with factory() as session, session.begin():
        for item in [old, latest]:
            payload = {
                **item["payload"],
                "timestamp": datetime.fromisoformat(item["payload"]["timestamp"]),
            }
            await session.execute(insert(SensorData).values(**payload))
    await purge(factory)  # closes 09h, preserves latest at 10h
    # A prediction closes the hour containing the retained legacy latest sensor.
    await send(factory, wire("prediction", "close-latest-hour-pred"))
    await purge(factory)
    assert (await send(factory, latest, old)).duplicates == 2
    assert await count(factory, SensorData) == 1
    await send(factory, wire("sensor", "new-latest-after-retention", NOW))
    assert (await purge(factory)).deleted["sensor"] == 1
    async with factory() as session:
        assert (
            await session.scalar(
                select(KpiRecord.value).where(
                    KpiRecord.metric == "measurement_count",
                    KpiRecord.scope == "plant",
                    KpiRecord.bucket_start == OLD,
                )
            )
            == 1
        )


async def test_receipt_keys_keep_message_types_independent_after_purge(factory):
    sensor = wire("sensor", "same-identity-both-types")
    prediction = wire("prediction", "same-identity-both-types")
    await send(factory, sensor, prediction, wire("sensor", "current-sensor-identity", NOW))
    await purge(factory)
    assert (await send(factory, sensor, prediction)).duplicates == 2


async def test_expiry_is_by_whole_hour_and_latest_measurement_is_retained(factory):
    cutoff = datetime(2026, 10, 31, 12, tzinfo=UTC)
    await send(
        factory,
        wire("prediction", "old-pred-before-edge", cutoff - timedelta(seconds=1)),
        wire("prediction", "old-pred-on-edge", cutoff),
        wire("sensor", "only-old-measurement"),
    )
    assert (await purge(factory)).deleted["prediction"] == 1
    assert await count(factory, Prediction) == 1 and await count(factory, SensorData) == 1


async def test_alerts_and_supervision_proofs_are_not_purged(factory):
    await send(factory, wire("prediction", "proof-retention-pred"))
    alert = json.loads((FIXTURES / "alert_ok.json").read_text(encoding="utf-8"))
    fog = json.loads((FIXTURES / "fog_status_ok.json").read_text(encoding="utf-8"))
    await send(factory, alert, fog)
    await purge(factory)
    assert await count(factory, Alert) == 1 and await count(factory, FogStatusHistory) == 1


@pytest.mark.parametrize(
    "failure", [DBAPIError("SQL", {}, Exception("fail")), asyncio.CancelledError()]
)
async def test_error_after_finalization_rolls_back_cache_receipts_and_deletion(factory, failure):
    await send(factory, wire("prediction", "rollback-retention-pred"))
    # Legacy mode to prove receipts added by the purge also roll back.
    async with factory() as session, session.begin():
        await session.execute(delete(IngestReceipt))
    original = delete

    def fail_raw(model):
        if model is Prediction:
            raise failure
        return original(model)

    with patch("app.retention.service.delete", fail_raw), pytest.raises(type(failure)):
        await purge(factory)
    assert await count(factory, Prediction) == 1
    assert await count(factory, IngestReceipt) == await count(factory, KpiRecord) == 0
    assert (await purge(factory)).deleted["prediction"] == 1


async def test_receipt_mismatch_blocks_cleanup(factory):
    await send(factory, wire("prediction", "mismatched-receipt-pred"))
    async with factory() as session, session.begin():
        await session.execute(update(IngestReceipt).values(payload_sha256=b"x" * 32))
    with pytest.raises(ValueError, match="does not match"):
        await purge(factory)
    assert await count(factory, Prediction) == 1 and await count(factory, KpiRecord) == 0


async def test_shared_ingestion_gate_makes_cleanup_busy_and_releases_after_commit(factory):
    await send(factory, wire("prediction", "busy-gate-prediction"))
    async with factory() as writer, writer.begin():
        await writer.execute(
            text("SELECT pg_advisory_xact_lock_shared(:lock)"), {"lock": RETENTION_LOCK}
        )
        assert await purge(factory) is None
    assert (await purge(factory)).deleted["prediction"] == 1


async def test_replay_waits_for_finalization_and_cannot_resurrect_deleted_data(factory):
    item = wire("prediction", "gate-replay-prediction")
    await send(factory, item)
    original = delete
    replay = None

    def replay_during_purge(model):
        nonlocal replay
        if model is Prediction:
            replay = asyncio.create_task(send(factory, item))
        return original(model)

    with patch("app.retention.service.delete", replay_during_purge):
        await purge(factory)
    assert (await replay).duplicates == 1
    assert await count(factory, Prediction) == 0


def test_downgrade_cannot_drop_dedup_evidence_of_purged_rows(committed_postgres_database):
    async def cleanup():
        engine = create_async_engine(committed_postgres_database.url, poolclass=NullPool)
        factory = async_sessionmaker(engine)
        try:
            async with factory() as session, session.begin():
                await initialize_catalogue(session)
            await send(factory, wire("prediction", "downgrade-purged-pred"))
            await purge(factory)
        finally:
            await engine.dispose()

    asyncio.run(cleanup())
    config = committed_postgres_database.alembic_config()
    with pytest.raises(RuntimeError, match="receipts still protect"):
        command.downgrade(config, "0003_fog_supervision")
    command.check(config)
