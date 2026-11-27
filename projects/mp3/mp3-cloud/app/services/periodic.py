"""Shared bounded retry and signal lifecycle for independent database workers."""

import asyncio
import logging
import signal
import time

from prometheus_client import CollectorRegistry, Counter, Gauge, start_http_server
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class PeriodicWorker:
    def __init__(self, factory, config, operation, prefix, interval):
        self.factory, self.config, self.refresh_fn = factory, config, operation
        self.prefix, self.interval = prefix, interval
        self.registry = CollectorRegistry()
        self.ready = Gauge(
            f"{prefix}_ready", "Latest cycle committed successfully", registry=self.registry
        )
        self.last_success = Gauge(
            f"{prefix}_last_success_timestamp_seconds",
            "Unix time of latest committed cycle",
            registry=self.registry,
        )
        self.cycles = Counter(
            f"{prefix}_refresh_total", "Cycle outcomes", ["outcome"], registry=self.registry
        )
        self.rows = Gauge(
            f"{prefix}_last_written_rows", "Rows written in latest cycle", registry=self.registry
        )

    async def run_once(self):
        try:
            written = await self.refresh_fn(self.factory, self.config)
        except (SQLAlchemyError, OSError, TimeoutError, ValueError) as exc:
            self.ready.set(0)
            self.cycles.labels("error").inc()
            logger.warning(
                "%s cycle failed (%s); transaction rolled back, retry scheduled",
                self.prefix,
                type(exc).__name__,
            )
            return False
        if written is None:
            self.cycles.labels("busy").inc()
            return False
        self.rows.set(written)
        self.last_success.set(time.time())
        self.ready.set(1)
        self.cycles.labels("success").inc()
        return True

    async def run(self, stop):
        delay = 1
        while not stop.is_set():
            success = await self.run_once()
            delay = 1 if success else min(delay * 2, self.interval)
            try:
                await asyncio.wait_for(stop.wait(), timeout=self.interval if success else delay)
            except TimeoutError:
                pass
        self.ready.set(0)


async def serve(worker, engine, host, port):
    server, thread = start_http_server(port, addr=host, registry=worker.registry)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous[sig] = signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    task = asyncio.create_task(worker.run(stop))
    stopping = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait([task, stopping], return_when=asyncio.FIRST_COMPLETED)
        if not task.done():
            task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        stopping.cancel()
        worker.ready.set(0)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        await engine.dispose()
