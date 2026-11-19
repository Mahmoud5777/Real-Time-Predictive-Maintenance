"""Periodic Fog heartbeat supervision; starts after schema/catalogue are ready."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.services.periodic import PeriodicWorker, serve
from app.supervision.service import check_nodes


class Worker(PeriodicWorker):
    def __init__(self, factory, config, *, check_fn=check_nodes):
        super().__init__(
            factory, config, check_fn, "fog_cloud_supervision", config.supervision_interval_seconds
        )


async def main():
    config = get_settings()
    engine = create_async_engine(config.database_url, pool_pre_ping=True)
    worker = Worker(async_sessionmaker(engine, expire_on_commit=False), config)
    await serve(worker, engine, config.supervision_metrics_host, config.supervision_metrics_port)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(main())
