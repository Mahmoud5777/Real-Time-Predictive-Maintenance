"""Independent KPI refresher using the shared bounded worker lifecycle."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.analytics.aggregate import refresh
from app.config import get_settings
from app.services.periodic import PeriodicWorker, serve


class Worker(PeriodicWorker):
    def __init__(self, factory, config, *, refresh_fn=refresh):
        super().__init__(factory, config, refresh_fn, "fog_cloud_kpi", config.kpi_refresh_seconds)


async def main():
    config = get_settings()
    engine = create_async_engine(config.database_url, pool_pre_ping=True)
    worker = Worker(async_sessionmaker(engine, expire_on_commit=False), config)
    await serve(worker, engine, config.kpi_metrics_host, config.kpi_metrics_port)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(main())
