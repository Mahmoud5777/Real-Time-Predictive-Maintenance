
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
