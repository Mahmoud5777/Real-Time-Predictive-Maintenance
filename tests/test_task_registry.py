
from scheduler.task_registry import TaskRegistry


def create_task(task_id, priority="MEDIUM"):
    return {
        "task_id": task_id,
        "task_type": "DATA_PREPROCESSING",
        "priority": priority,
        "payload": {},
    }


def test_claim_tasks_for_recovery():
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-001"),
        "fog-a",
        "fog-b",
    )

    registry.register_task(
        create_task("task-002"),
        "fog-a",
        "fog-b",
    )

    registry.register_task(
        create_task("task-003"),
        "fog-a",
        "fog-c",
    )

    claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(claimed) == 2

    assert all(
        task["status"] == "RECOVERING"
        for task in claimed
    )

    assert all(
        task["destination_fog"] == "fog-b"
        for task in claimed
    )


def test_prevent_duplicate_recovery_claims():
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-004"),
        "fog-a",
        "fog-b",
    )

    first_claim = registry.claim_tasks_for_recovery("fog-b")
    second_claim = registry.claim_tasks_for_recovery("fog-b")

    assert len(first_claim) == 1
    assert len(second_claim) == 0


def test_claim_only_unfinished_tasks():
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-005"),
        "fog-a",
        "fog-b",
    )

    registry.register_task(
        create_task("task-006"),
        "fog-a",
        "fog-b",
    )

    registry.update_task_status("task-006", "COMPLETED")

    claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(claimed) == 1
    assert claimed[0]["task_id"] == "task-005"


def test_release_recovery_claim_restores_previous_status():
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-007"),
        "fog-a",
        "fog-b",
    )

    registry.update_task_status("task-007", "RUNNING")

    claimed = registry.claim_tasks_for_recovery("fog-b")

    assert len(claimed) == 1
    assert claimed[0]["status"] == "RECOVERING"

    released = registry.release_recovery_claim("task-007")

    assert released is True

    task = registry.get_task("task-007")

    assert task["status"] == "RUNNING"
    assert "recovery_previous_status" not in task


def test_release_recovery_claim_only_once():
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-008"),
        "fog-a",
        "fog-b",
    )

    registry.claim_tasks_for_recovery("fog-b")

    assert registry.release_recovery_claim("task-008") is True
    assert registry.release_recovery_claim("task-008") is False


def test_update_destination_clears_recovery_metadata():
    registry = TaskRegistry()

    registry.register_task(
        create_task("task-009"),
        "fog-a",
        "fog-b",
    )

    registry.claim_tasks_for_recovery("fog-b")

    updated = registry.update_destination(
        "task-009",
        "fog-c",
    )

    assert updated is True

    task = registry.get_task("task-009")

    assert task["destination_fog"] == "fog-c"
    assert task["status"] == "RECOVERED"
    assert task["attempts"] == 2
    assert "recovery_previous_status" not in task
    
