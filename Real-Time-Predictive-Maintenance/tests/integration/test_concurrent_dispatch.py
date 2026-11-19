
import asyncio
import uuid

import httpx
import pytest


SCHEDULER_URL = "http://127.0.0.1:8000"

NUMBER_OF_TASKS = 50


@pytest.mark.asyncio
async def test_concurrent_task_dispatch():

    task_ids = [
        f"load-test-{uuid.uuid4().hex[:12]}"
        for _ in range(NUMBER_OF_TASKS)
    ]

    async with httpx.AsyncClient(
        timeout=30.0
    ) as client:

        async def dispatch_one(task_id):
            payload = {
                "source_fog_id": "fog-a",
                "task": {
                    "task_id": task_id,
                    "task_type": "ANOMALY_DETECTION",
                    "priority": "LOW",
                    "payload": {
                        "temperature": 95,
                        "vibration": 12
                    },
                    "source_fog": "fog-a",
                    "machine_id": "load-test-machine",
                    "created_at": "2026-11-06T21:00:00Z"
                }
            }

            try:
                response = await client.post(
                    f"{SCHEDULER_URL}/dispatch",
                    json=payload
                )

                return {
                    "task_id": task_id,
                    "status_code": response.status_code,
                    "body": response.json()
                }

            except Exception as error:
                return {
                    "task_id": task_id,
                    "error": str(error)
                }

        results = await asyncio.gather(
            *(dispatch_one(task_id) for task_id in task_ids)
        )

    successful = [
        result for result in results
        if result.get("status_code") == 200
    ]

    failed = [
        result for result in results
        if result.get("status_code") != 200
    ]

    print(f"\nTotal tasks: {NUMBER_OF_TASKS}")
    print(f"Successful dispatches: {len(successful)}")
    print(f"Failed dispatches: {len(failed)}")

    for failure in failed:
        print(failure)

    assert len(successful) == NUMBER_OF_TASKS
