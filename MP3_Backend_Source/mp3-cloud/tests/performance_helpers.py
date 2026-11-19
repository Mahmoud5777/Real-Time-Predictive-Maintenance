"""Charge synthetique et vrai serveur HTTP, exclusivement pour les bases jetables."""

import asyncio
import json
import math
import re
import socket
import statistics
import time
from contextlib import asynccontextmanager, suppress
from datetime import timedelta
from uuid import uuid4

import uvicorn
from httpx import AsyncClient, Limits
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_mqtt_integration import FILES, FIXTURES, eventually

from app.db.session import get_session
from app.main import create_app


def observations(ticks, start, *, predictions=True):
    """12 mesures/s et, si active, une prediction/10 s par machine."""
    bases = {
        kind: json.loads((FIXTURES / FILES[kind]).read_text(encoding="utf-8"))["payload"]
        for kind in ("sensor", "prediction")
    }
    prefix = uuid4().hex[:16]
    result = []
    for tick in range(ticks):
        for number in range(1, 13):
            zone = "ABC"[(number - 1) // 4]
            common = dict(
                machine_id=f"M{number:02d}",
                timestamp=(start + timedelta(seconds=tick)).isoformat(),
            )
            result.append({
                "kind": "sensor",
                "payload": {
                    **bases["sensor"], **common,
                    "message_id": f"perf-{prefix}-s-{tick:04d}-{number:02d}",
                    "zone": zone, "temperature": 60 + number + (tick % 20) / 10,
                },
            })
            if predictions and tick % 10 == 0:
                result.append({
                    "kind": "prediction",
                    "payload": {
                        **bases["prediction"], **common,
                        "message_id": f"perf-{prefix}-p-{tick:04d}-{number:02d}",
                        "fog_id": f"FOG_{zone}", "model_version": "benchmark-v1",
                    },
                })
    return result


def mqtt_message(item):
    kind, body = item["kind"], item["payload"]
    if kind == "sensor":
        topic = f"fog/{body['zone']}/sensor/{body['machine_id']}"
    elif kind == "task_event":
        topic = "tasks/events"
    else:
        suffix = {"prediction": "predictions", "alert": "alerts", "fog_status": "status"}[kind]
        topic = f"fog/{body['fog_id']}/{suffix}"
    return topic, body, kind == "fog_status"


def distribution(seconds):
    """Quantiles par rang ; pas de p95/p99 sur un effectif trop faible."""
    ordered = sorted(value * 1000 for value in seconds)
    if not ordered:
        return {"samples": 0}

    def percentile(fraction):
        return ordered[math.ceil(fraction * len(ordered)) - 1]

    return {
        "samples": len(ordered), "unit": "ms",
        "min": ordered[0], "mean": statistics.fmean(ordered),
        "p50": statistics.median(ordered), "max": ordered[-1],
        "p95": percentile(.95) if len(ordered) >= 100 else None,
        "p99": percentile(.99) if len(ordered) >= 1000 else None,
    }


@asynccontextmanager
async def api_server(engine):
    if re.fullmatch(r"mp3_test_[0-9a-f]{32}", engine.url.database or "") is None:
        raise ValueError("Performance HTTP requires a disposable test database")
    application = create_app()
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def isolated_session():
        async with factory() as session:
            yield session

    application.dependency_overrides[get_session] = isolated_session
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    server = uvicorn.Server(uvicorn.Config(
        application, log_level="error", access_log=False, lifespan="off"
    ))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        await eventually(lambda: server.started, task, timeout=10)
        port = listener.getsockname()[1]
        async with AsyncClient(
            base_url=f"http://127.0.0.1:{port}", timeout=60,
            limits=Limits(max_connections=20, max_keepalive_connections=20),
        ) as client:
            yield client, factory
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=10)
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            listener.close()


async def ingest(client, messages, batch_size=100, *, duplicates=False):
    durations = []
    started = time.perf_counter()
    for index in range(0, len(messages), batch_size):
        batch = messages[index:index + batch_size]
        at = time.perf_counter()
        response = await client.post(
            "/api/v1/ingest/batch", json={"messages": batch},
            headers={"Authorization": "Bearer test-token"},
        )
        body = response.json()
        assert response.status_code == 207, body
        assert body["rejected"] == 0 and body["errors"] == [], body
        assert body["duplicates" if duplicates else "accepted"] == len(batch), body
        assert body["accepted" if duplicates else "duplicates"] == 0, body
        durations.append(time.perf_counter() - at)
    elapsed = time.perf_counter() - started
    return {
        "messages": len(messages), "batch_size": batch_size, "elapsed_s": elapsed,
        "messages_per_second": len(messages) / elapsed,
        "requests": distribution(durations),
    }


READ_PATHS = (
    "/api/v1/machines?limit=12",
    "/api/v1/measurements?machine_id=M01&limit=50",
    "/api/v1/measurements?zone=B&limit=50",
    "/api/v1/predictions?fog_id=FOG_C&limit=50",
    "/api/v1/alerts?status=OPEN",
    "/api/v1/fog/nodes",
    "/api/v1/tasks/events?time_field=received_at",
    "/api/v1/analytics/kpis",
)


async def reads(client, *, repetitions=100, concurrency=6):
    semaphore = asyncio.Semaphore(concurrency)
    samples = {path: [] for path in READ_PATHS}

    async def read(path):
        async with semaphore:
            at = time.perf_counter()
            response = await client.get(path)
            body = response.json()
            assert response.status_code == 200, body
            assert body["meta"]["total"] > 0 and body["items"], (path, body)
            samples[path].append(time.perf_counter() - at)

    started = time.perf_counter()
    await asyncio.gather(*(read(path) for _ in range(repetitions) for path in READ_PATHS))
    elapsed = time.perf_counter() - started
    flat = [sample for values in samples.values() for sample in values]
    return {
        "concurrency": concurrency, "elapsed_s": elapsed,
        "requests_per_second": len(flat) / elapsed,
        "all_routes": distribution(flat),
        "routes": {path: distribution(values) for path, values in samples.items()},
    }
