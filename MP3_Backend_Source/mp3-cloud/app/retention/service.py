"""Whole expired hours, durable receipts and an atomic finalization/deletion transaction."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert

from app.analytics.aggregate import aggregate_rows
from app.analytics.catalogue import MEASUREMENTS, PREDICTION_METRICS
from app.analytics.windows import HOUR, closed_hour
from app.models.tables import IngestReceipt, KpiRecord, Prediction, SensorData
from app.services.receipts import FINALIZED_METRIC, RETENTION_LOCK, digest, stored_payload

OWNED_METRICS = (
    set(PREDICTION_METRICS)
    | {f"mean_{name}" for name in MEASUREMENTS}
    | {
        "measurement_count",
        "mean_ingest_latency_s",
        "clock_skew_count",
    }
)
MODELS = {"sensor": SensorData, "prediction": Prediction}


@dataclass(frozen=True)
class RetentionResult:
    cutoff: datetime
    hour: datetime | None
    candidates: dict[str, int]
    deleted: dict[str, int]
    dry_run: bool


def eligible(model, cutoff):
    query = select(model).where(model.timestamp < cutoff)
    if model is SensorData:
        latest = (
            select(SensorData.id)
            .distinct(SensorData.machine_id)
            .order_by(
                SensorData.machine_id,
                SensorData.timestamp.desc(),
                SensorData.id.desc(),
            )
        )
        query = query.where(SensorData.id.not_in(latest))
    return query


async def run_retention(factory, config, *, now=None, dry_run=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware retention time is required")
    now = now.astimezone(UTC)
    # Preserve the oldest partially retained hour and all newer data.
    cutoff = closed_hour(now - timedelta(days=config.raw_retention_days))
    dry_run = config.retention_dry_run if dry_run is None else dry_run
    async with asyncio.timeout(config.retention_database_timeout_seconds):
        async with factory() as session, session.begin():
            await session.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": str(int(config.retention_database_timeout_seconds * 1000))},
            )
            if not (
                await session.execute(
                    text("SELECT pg_try_advisory_xact_lock(:lock)"), {"lock": RETENTION_LOCK}
                )
            ).scalar_one():
                return None
            # Touch the ledger even when no candidates exist: migration must be ready.
            await session.execute(select(IngestReceipt.message_id).limit(1))
            minima = []
            for model in MODELS.values():
                minimum = await session.scalar(
                    select(func.min(model.timestamp)).where(
                        model.id.in_(eligible(model, cutoff).with_only_columns(model.id))
                    )
                )
                if minimum is not None:
                    minima.append(minimum)
            hour = closed_hour(min(minima)) if minima else None
            candidates = {kind: 0 for kind in MODELS}
            deleted = candidates.copy()
            if hour is None:
                return RetentionResult(cutoff, None, candidates, deleted, dry_run)
            selected = {}
            for kind, model in MODELS.items():
                rows = (
                    (
                        await session.execute(
                            eligible(model, cutoff)
                            .where(
                                model.timestamp >= hour,
                                model.timestamp < hour + HOUR,
                            )
                            .order_by(model.timestamp, model.id)
                            .limit(config.retention_batch_size)
                        )
                    )
                    .scalars()
                    .all()
                )
                selected[kind] = rows
                candidates[kind] = len(rows)
            if dry_run:
                return RetentionResult(cutoff, hour, candidates, deleted, True)
            finalized = await session.scalar(
                select(KpiRecord.id).where(
                    KpiRecord.metric == FINALIZED_METRIC,
                    KpiRecord.scope == "plant",
                    KpiRecord.scope_value == "all",
                    KpiRecord.bucket_start == hour,
                )
            )
            if finalized is None:
                # App ingress holds a shared lock for its whole transaction; all source facts
                # remain stable here under READ COMMITTED while this exclusive gate is held.
                aggregates = await aggregate_rows(
                    session, hour, hour + HOUR, now, metric_filter=OWNED_METRICS
                )
                await session.execute(
                    delete(KpiRecord).where(
                        KpiRecord.metric.in_(OWNED_METRICS),
                        KpiRecord.bucket_start == hour,
                    )
                )
                for i in range(0, len(aggregates), 500):
                    await session.execute(insert(KpiRecord), aggregates[i : i + 500])
                await session.execute(
                    insert(KpiRecord).values(
                        metric=FINALIZED_METRIC,
                        scope="plant",
                        scope_value="all",
                        bucket_start=hour,
                        bucket_end=hour + HOUR,
                        value=1,
                        sample_size=0,
                        computed_at=now,
                    )
                )
            for kind, model in MODELS.items():
                rows = selected[kind]
                if not rows:
                    continue
                receipts = []
                for row in rows:
                    payload = stored_payload(
                        kind,
                        {
                            column.name: getattr(row, column.name)
                            for column in model.__table__.columns
                        },
                    )
                    receipts.append(
                        dict(
                            kind=kind,
                            message_id=row.message_id,
                            payload_sha256=digest(kind, payload),
                        )
                    )
                await session.execute(
                    insert(IngestReceipt)
                    .values(receipts)
                    .on_conflict_do_nothing(index_elements=["kind", "message_id"])
                )
                known = dict(
                    (
                        await session.execute(
                            select(IngestReceipt.message_id, IngestReceipt.payload_sha256).where(
                                IngestReceipt.kind == kind,
                                IngestReceipt.message_id.in_([r.message_id for r in rows]),
                            )
                        )
                    ).all()
                )
                if any(known[r["message_id"]] != r["payload_sha256"] for r in receipts):
                    raise ValueError("Receipt does not match stored observation; purge refused")
                await session.execute(delete(model).where(model.id.in_([row.id for row in rows])))
                deleted[kind] = len(rows)
    return RetentionResult(cutoff, hour, candidates, deleted, False)
