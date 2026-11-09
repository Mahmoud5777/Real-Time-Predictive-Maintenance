"""SQL aggregates; one atomic, bounded refresh protected by a transaction try-lock."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, insert, select, text

from app.analytics.catalogue import MEASUREMENTS, METRICS
from app.analytics.windows import HOUR, closed_hour, validate_window
from app.models.tables import KpiRecord
from app.services.receipts import FINALIZED_METRIC

LOCK_ID = 6030006


def grouped_sql(source, time_column, dimensions, aggregates):
    # All identifiers/expressions originate here, never from HTTP/CLI input.
    names = list(dimensions)
    dim_select = ", ".join(f"{value} AS {name}" for name, value in dimensions.items())
    grouping = ", ".join(["()"] + [f"({name})" for name in names])
    fields = ", ".join(f"{expression} AS {name}" for name, expression in aggregates.items())
    return text(f"""
        WITH source AS (
            SELECT s.*, {dim_select},
                   date_trunc('hour', {time_column} AT TIME ZONE 'UTC')
                       AT TIME ZONE 'UTC' AS bucket
            FROM {source}
            WHERE {time_column} >= :start AND {time_column} < :end
        )
        SELECT bucket, {', '.join(names)}, grouping({', '.join(names)}) AS mask, {fields}
        FROM source GROUP BY bucket, GROUPING SETS ({grouping})
    """)


def count_if(condition):
    return f"count(*) FILTER (WHERE {condition})"


def query_specs():
    common = {"zone_scope": "m.zone", "machine_scope": "s.machine_id"}
    sensor_dims = {**common, "fog_scope": "m.fog_id"}
    sensor = {
        "measurement_count": "count(*)",
        "clock_skew_count": count_if("received_at < timestamp"),
        "mean_ingest_latency_s": (
            "avg(extract(epoch FROM received_at - timestamp)) "
            "FILTER (WHERE received_at >= timestamp)"
        ),
        **{f"mean_{name}": f"avg({name})" for name in MEASUREMENTS},
    }
    sensor_samples = {f"mean_{name}": f"count({name})" for name in MEASUREMENTS}
    sensor_samples["mean_ingest_latency_s"] = count_if("received_at >= timestamp")
    pred_dims = {**common, "fog_scope": "s.fog_id", "model_scope": "s.model_version"}
    pred = {
        "prediction_count": "count(*)",
        "anomaly_count": count_if("anomaly"),
        "anomaly_ratio": "avg(anomaly::int)",
        "mean_risk_score": "avg(risk_score)",
        "critical_prediction_count": count_if("severity = 'CRITICAL'"),
    }
    alert_dims = {**common, "fog_scope": "s.fog_id"}
    alert = {"alert_count": "count(*)", "critical_alert_count": count_if("severity = 'CRITICAL'")}
    repair = {"mttr_hours": "avg(extract(epoch FROM resolved_at - timestamp) / 3600)"}
    task_dims = {
        "zone_scope": "f.zone",
        "machine_scope": "t.machine_id",
        "fog_scope": "s.source_fog",
    }
    task = {
        "task_event_count": "count(*)",
        "tasks_migrated_total": count_if("status='MIGRATED'"),
        "completed_task_reports": "count(DISTINCT task_id) FILTER (WHERE status='COMPLETED')",
    }
    sources = [
        (
            "sensor_data s JOIN machines m ON m.machine_id=s.machine_id",
            "s.timestamp",
            sensor_dims,
            sensor,
            sensor_samples,
        ),
        (
            "predictions s JOIN machines m ON m.machine_id=s.machine_id",
            "s.timestamp",
            pred_dims,
            pred,
            {},
        ),
        (
            "alerts s JOIN machines m ON m.machine_id=s.machine_id",
            "s.timestamp",
            alert_dims,
            alert,
            {},
        ),
        (
            "alerts s JOIN machines m ON m.machine_id=s.machine_id AND s.status='RESOLVED' "
            "AND s.severity='CRITICAL'",
            "s.resolved_at",
            alert_dims,
            repair,
            {},
        ),
        (
            "task_events s JOIN tasks t ON t.task_id=s.task_id "
            "LEFT JOIN fog_nodes f ON f.fog_id=t.origin_fog_id",
            "s.received_at",
            task_dims,
            task,
            {},
        ),
    ]
    return [
        (
            grouped_sql(
                source,
                time,
                dims,
                {
                    **metrics,
                    "samples": "count(*)",
                    **{f"n_{name}": expr for name, expr in samples.items()},
                },
            ),
            list(dims),
            list(metrics),
            samples,
        )
        for source, time, dims, metrics, samples in sources
    ]


async def aggregate_rows(session, start, end, computed_at, *, metric_filter=None):
    records = []
    for query, dimensions, metrics, samples in query_specs():
        if metric_filter is not None and not set(metrics) & metric_filter:
            continue
        rows = (await session.execute(query, {"start": start, "end": end})).mappings()
        for row in rows:
            mask = row["mask"]
            scope, value = "plant", "all"
            for i, dimension in enumerate(dimensions):
                if not mask & (1 << (len(dimensions) - i - 1)):
                    scope, value = dimension.removesuffix("_scope"), row[dimension]
                    break
            if value is None:  # Unknown machine/origin does not become a fake dimension.
                continue
            for metric in metrics:
                if row[metric] is None:
                    continue
                records.append(
                    dict(
                        metric=metric,
                        scope=scope,
                        scope_value=value,
                        bucket_start=row["bucket"],
                        bucket_end=row["bucket"] + HOUR,
                        value=float(row[metric]),
                        sample_size=int(
                            row[f"n_{metric}"] if metric in samples else row["samples"]
                        ),
                        computed_at=computed_at,
                    )
                )
    return records


async def refresh(session_factory, config, start=None, end=None, *, now=None):
    """Return written row count, or None if another refresher owns the lock.

    Caller supplies a fresh session factory. Cache writes and deletion share one transaction.
    A failed/cancelled transaction never replaces the previous usable cache.
    """
    now = now or datetime.now(UTC)
    end = end or closed_hour(now)
    cutoff = now - timedelta(days=config.raw_retention_days)
    earliest = closed_hour(cutoff)
    if earliest < cutoff:
        earliest += HOUR
    start = start or max(end - timedelta(hours=config.kpi_lookback_hours), earliest)
    start, end = validate_window(start, end, now)
    # Retention can remove a partial oldest hour; refresh only fully retained hours.
    if start < cutoff:
        raise ValueError("Refresh starts outside the raw retention horizon")
    async with asyncio.timeout(config.kpi_database_timeout_seconds):
        async with session_factory() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            await session.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": str(int(config.kpi_database_timeout_seconds * 1000))},
            )
            width = (
                await session.execute(
                    text(
                        "SELECT character_maximum_length FROM information_schema.columns "
                        "WHERE table_schema=current_schema() AND table_name='kpi_records' "
                        "AND column_name='scope_value'"
                    )
                )
            ).scalar_one_or_none()
            if width is None or width < 64:
                raise ValueError("KPI schema is not migrated; run alembic upgrade head")
            if not (
                await session.execute(
                    text("SELECT pg_try_advisory_xact_lock(:lock)"), {"lock": LOCK_ID}
                )
            ).scalar_one():
                return None
            if (
                await session.scalar(
                    select(KpiRecord.id)
                    .where(
                        KpiRecord.metric == FINALIZED_METRIC,
                        KpiRecord.bucket_start >= start,
                        KpiRecord.bucket_start < end,
                    )
                    .limit(1)
                )
                is not None
            ):
                raise ValueError("Refresh includes finalized hours whose raw data has expired")
            rows = await aggregate_rows(session, start, end, now)
            await session.execute(
                delete(KpiRecord).where(
                    KpiRecord.metric.in_(METRICS),
                    KpiRecord.bucket_start >= start,
                    KpiRecord.bucket_start < end,
                )
            )
            # Bound executemany parameter batches even for large lookbacks/model counts.
            for i in range(0, len(rows), 500):
                await session.execute(insert(KpiRecord), rows[i : i + 500])
    return len(rows)
