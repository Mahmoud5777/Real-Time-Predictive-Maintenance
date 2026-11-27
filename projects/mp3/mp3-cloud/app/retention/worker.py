"""Bounded cleanup worker; default dry-run reports candidates without deleting data."""

import asyncio
import logging

from prometheus_client import Gauge
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.retention.service import run_retention
from app.services.periodic import PeriodicWorker, serve


class Worker(PeriodicWorker):
    def __init__(self, factory, config):
        super().__init__(
            factory, config, self.cycle, "fog_cloud_retention", config.retention_interval_seconds
        )
        self.candidates = Gauge(
            "fog_cloud_retention_last_candidates",
            "Candidates in latest batch",
            registry=self.registry,
        )
        self.dry_run = Gauge(
            "fog_cloud_retention_dry_run", "1 means no data deletion", registry=self.registry
        )
        self.dry_run.set(int(config.retention_dry_run))

    async def cycle(self, factory, config):
        result = await run_retention(factory, config)
        if result is None:
            return None
        self.candidates.set(sum(result.candidates.values()))
        return sum(result.deleted.values())


async def main():
    config = get_settings()
    engine = create_async_engine(config.database_url, pool_pre_ping=True)
    worker = Worker(async_sessionmaker(engine, expire_on_commit=False), config)
    await serve(worker, engine, config.retention_metrics_host, config.retention_metrics_port)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(main())
