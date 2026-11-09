"""Preparation/profil SQL dans fog_lab seulement, execute dans le conteneur de laboratoire."""

import argparse
import asyncio
import json
import platform
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analytics.windows import HOUR, closed_hour
from app.config import get_settings
from app.models.tables import (
    Alert,
    FogNode,
    FogStatusHistory,
    IngestReceipt,
    KpiRecord,
    Machine,
    Prediction,
    SensorData,
    Task,
    TaskEvent,
)
from app.services.ingest import persist_batch
from app.services.receipts import FINALIZED_METRIC
from scripts.lab_common import distribution, prediction, require_run_id, sensor

TABLES = (Machine, FogNode, SensorData, Prediction, Alert, Task, TaskEvent,
          FogStatusHistory, KpiRecord, IngestReceipt)


async def prepare(factory, run_id):
    now = datetime.now(UTC)
    old = closed_hour(now - timedelta(days=8))
    recent = closed_hour(now) - HOUR
    async with factory() as session:
        # Une heure deja finalisee refuse de nouveaux identifiants. Choisir une heure libre.
        while await session.scalar(select(KpiRecord.id).where(
            KpiRecord.metric == FINALIZED_METRIC, KpiRecord.bucket_start == old
        ).limit(1)) is not None:
            old -= HOUR
    messages = []
    for number in range(1, 13):
        machine, zone = f"M{number:02d}", "ABC"[(number - 1) // 4]
        for label, timestamp in (("old1", old), ("old2", old + timedelta(seconds=1)),
                                 ("recent", recent)):
            messages.append({"kind": "sensor", "payload": sensor(
                f"{run_id}-{label}-s-{number}", machine, zone, timestamp
            )})
        for label, timestamp in (("old1", old), ("recent", recent)):
            messages.append({"kind": "prediction", "payload": prediction(
                f"{run_id}-{label}-p-{number}", machine, f"FOG_{zone}", timestamp
            )})
    async with factory() as session:
        result = await persist_batch(session, messages)
    if result.accepted != len(messages) or result.rejected:
        raise ValueError("Laboratory historical preparation failed")
    return {"inserted": len(messages), "old_candidates": 36, "old_hour": old.isoformat()}


async def inspect(factory, run_id=None):
    async with factory() as session:
        counts = {
            model.__tablename__: await session.scalar(select(func.count()).select_from(model))
            for model in TABLES
        }
        version = await session.scalar(text("SHOW server_version"))
        result = {"tables": counts, "postgres_version": version,
                  "container_python": platform.python_version()}
        if run_id:
            result["live_counts"] = {
                kind: await session.scalar(select(func.count()).select_from(model).where(
                    model.message_id.like(f"{run_id}-live-%")
                ))
                for kind, model in (("sensor", SensorData), ("prediction", Prediction),
                                    ("alert", Alert), ("fog_status", FogStatusHistory),
                                    ("task_event", TaskEvent))
            }
            result["old_remaining"] = sum([
                await session.scalar(select(func.count()).select_from(model).where(
                    model.message_id.like(f"{run_id}-old%")
                )) for model in (SensorData, Prediction)
            ])
            result["finalized_old_kpis"] = await session.scalar(
                select(func.count()).select_from(KpiRecord).where(
                    KpiRecord.metric == FINALIZED_METRIC
                )
            )
            delays = list((await session.execute(select(
                func.extract("epoch", SensorData.received_at - SensorData.timestamp)
            ).where(SensorData.message_id.like(f"{run_id}-live-%")))).scalars())
            result["producer_to_cloud_receipt"] = {
                **distribution([float(value) for value in delays if value >= 0]),
                "negative_delay_count": sum(value < 0 for value in delays),
                "basis": "sensor producer timestamp to Cloud recorded receipt; "
                         "different UTC clocks, before insert/commit, not exact commit latency",
            }
        # Profil diagnostique hors charge ; les temps SQL ne sont pas des temps HTTP.
        result["query_plans"] = {}
        if run_id is None:
            return result
        for name, statement in (
            ("measurement_page", "SELECT * FROM sensor_data WHERE machine_id='M01' "
             "ORDER BY timestamp DESC, id DESC LIMIT 50"),
            ("measurement_count", "SELECT count(*) FROM sensor_data WHERE machine_id='M01'"),
        ):
            plan = await session.scalar(
                text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement)
            )
            result["query_plans"][name] = json.loads(plan) if isinstance(plan, str) else plan
        return result


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "inspect"])
    parser.add_argument("--run-id")
    args = parser.parse_args()
    if args.run_id:
        require_run_id(args.run_id)
    if args.action == "prepare" and not args.run_id:
        parser.error("prepare requires --run-id")
    engine = create_async_engine(get_settings().database_url)
    if engine.url.database != "fog_lab":
        await engine.dispose()
        raise ValueError("This probe refuses any database other than fog_lab")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        result = await (prepare(factory, args.run_id) if args.action == "prepare"
                        else inspect(factory, args.run_id))
        print(json.dumps(result))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
