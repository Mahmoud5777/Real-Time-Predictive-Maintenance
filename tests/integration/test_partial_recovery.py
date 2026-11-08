import httpx
import pytest

from scheduler import main as scheduler_main
from scheduler.task_registry import TaskRegistry


def create_task(task_id, priority="MEDIUM"):
    return {
        "task_id": task_id,
        "task_type": "DATA_PREPROCESSING",
        "priority": priority,
        "payload": {},
    }


def test_partial_recovery_allows_retry_only_for_failed_task():
    registry = TaskRegistry()

    # Register three tasks on the failed Fog.
    for task_id in ("task-101", "task-102", "task-103"):
        registry.register_task(
            create_task(task_id),
            "fog-a",
            "fog-b",
        )

    registry.update_task_status("task-102", "RUNNING")
    registry.update_task_status("task-103", "ACCEPTED")

    # Reserve all three tasks for recovery.
    claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(claimed) == 3

    # Two tasks are successfully transferred to Fog C.
    assert registry.update_destination("task-101", "fog-c") is True
    assert registry.update_destination("task-102", "fog-c") is True

    # The third task fails and its previous status is restored.
    assert registry.release_recovery_claim("task-103") is True

    task_101 = registry.get_task("task-101")
    task_102 = registry.get_task("task-102")
    task_103 = registry.get_task("task-103")

    assert task_101["destination_fog"] == "fog-c"
    assert task_101["status"] == "RECOVERED"

    assert task_102["destination_fog"] == "fog-c"
    assert task_102["status"] == "RECOVERED"

    assert task_103["destination_fog"] == "fog-b"
    assert task_103["status"] == "ACCEPTED"

    # A new recovery attempt for Fog B must claim only task-103.
    retry_claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(retry_claimed) == 1
    assert retry_claimed[0]["task_id"] == "task-103"

@pytest.mark.asyncio
async def test_recovery_releases_claim_when_destination_is_unavailable(
    monkeypatch,
):
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-201"),
        "fog-a",
        "fog-b",
    )

    # Use an isolated registry for the scheduler.
    monkeypatch.setattr(
        scheduler_main,
        "task_registry",
        registry,
    )

    # Simulate Fog C as the selected replacement.
    monkeypatch.setattr(
        scheduler_main,
        "select_recovery_destination",
        lambda failed_fog_id, nodes: {"fog_id": "fog-c"},
    )

    monkeypatch.setattr(
        scheduler_main,
        "FOG_NODE_URLS",
        {"fog-c": "http://127.0.0.1:8003"},
    )

    # Simulate an unavailable destination.
    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            raise httpx.ConnectError("Fog C unavailable")

    monkeypatch.setattr(
        scheduler_main.httpx,
        "AsyncClient",
        FailingAsyncClient,
    )

    await scheduler_main.recover_tasks_from_failed_node("fog-b")

    task = registry.get_task("task-201")

    assert task["status"] == "PENDING"
    assert task["destination_fog"] == "fog-b"

    # The task must be claimable again.
    retry_claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(retry_claimed) == 1
    assert retry_claimed[0]["task_id"] == "task-201"

@pytest.mark.asyncio
async def test_recovery_releases_claim_when_destination_returns_500(
    monkeypatch,
):
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-202"),
        "fog-a",
        "fog-b",
    )

    monkeypatch.setattr(
        scheduler_main,
        "task_registry",
        registry,
    )

    monkeypatch.setattr(
        scheduler_main,
        "select_recovery_destination",
        lambda failed_fog_id, nodes: {"fog_id": "fog-c"},
    )

    monkeypatch.setattr(
        scheduler_main,
        "FOG_NODE_URLS",
        {"fog-c": "http://127.0.0.1:8003"},
    )

    class FailingAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", args[0])
            response = httpx.Response(500, request=request)
            return response

    monkeypatch.setattr(
        scheduler_main.httpx,
        "AsyncClient",
        FailingAsyncClient,
    )

    await scheduler_main.recover_tasks_from_failed_node("fog-b")

    task = registry.get_task("task-202")

    assert task["status"] == "PENDING"
    assert task["destination_fog"] == "fog-b"

    retry_claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(retry_claimed) == 1
    assert retry_claimed[0]["task_id"] == "task-202"

@pytest.mark.asyncio
async def test_mixed_recovery_continues_after_individual_failures(
    monkeypatch,
):
    registry = TaskRegistry()

    for task_id in ("task-301", "task-302", "task-303"):
        registry.register_task(
            create_task(task_id),
            "fog-a",
            "fog-b",
        )

    monkeypatch.setattr(
        scheduler_main,
        "task_registry",
        registry,
    )

    monkeypatch.setattr(
        scheduler_main,
        "select_recovery_destination",
        lambda failed_fog_id, nodes: {"fog_id": "fog-c"},
    )

    monkeypatch.setattr(
        scheduler_main,
        "FOG_NODE_URLS",
        {"fog-c": "http://127.0.0.1:8003"},
    )

    class MixedAsyncClient:
        def __init__(self, *args, **kwargs):
            self.call_count = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, *args, **kwargs):
            self.call_count += 1

            if self.call_count == 1:
                request = httpx.Request("POST", args[0])
                return httpx.Response(200, request=request)

            if self.call_count == 2:
                request = httpx.Request("POST", args[0])
                return httpx.Response(500, request=request)

            raise httpx.ConnectError("Fog C unavailable")

    monkeypatch.setattr(
        scheduler_main.httpx,
        "AsyncClient",
        MixedAsyncClient,
    )

    await scheduler_main.recover_tasks_from_failed_node("fog-b")

    task_301 = registry.get_task("task-301")
    task_302 = registry.get_task("task-302")
    task_303 = registry.get_task("task-303")

    # First task succeeds.
    assert task_301["status"] == "RECOVERED"
    assert task_301["destination_fog"] == "fog-c"

    # Second and third tasks fail and become retryable.
    assert task_302["status"] == "PENDING"
    assert task_302["destination_fog"] == "fog-b"

    assert task_303["status"] == "PENDING"
    assert task_303["destination_fog"] == "fog-b"

    retry_claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(retry_claimed) == 2
    assert {
        task["task_id"] for task in retry_claimed
    } == {"task-302", "task-303"}
