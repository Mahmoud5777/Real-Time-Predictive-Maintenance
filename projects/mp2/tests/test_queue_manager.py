
import asyncio
import pytest

from fog_nodes.common.queue_manager import QueueManager
from fog_nodes.fog_a.config import config
from shared.models import TaskRequest, TaskPriority


def create_task(task_id, priority):
    return TaskRequest(
        task_id=task_id,
        task_type="TEST",
        priority=priority
    )


def test_priority_order():

    async def run_test():

        manager = QueueManager(config, max_size=10)

        manager.add_task(create_task("task-1", TaskPriority.LOW))
        manager.add_task(create_task("task-2", TaskPriority.HIGH))
        manager.add_task(create_task("task-3", TaskPriority.MEDIUM))

        first = await manager.get_task()
        manager.task_done()

        second = await manager.get_task()
        manager.task_done()

        third = await manager.get_task()
        manager.task_done()

        assert first.task_id == "task-2"
        assert second.task_id == "task-3"
        assert third.task_id == "task-1"

    asyncio.run(run_test())


def test_same_priority_keeps_arrival_order():

    async def run_test():

        manager = QueueManager(config, max_size=10)

        manager.add_task(create_task("task-1", TaskPriority.HIGH))
        manager.add_task(create_task("task-2", TaskPriority.HIGH))
        manager.add_task(create_task("task-3", TaskPriority.HIGH))

        first = await manager.get_task()
        manager.task_done()

        second = await manager.get_task()
        manager.task_done()

        third = await manager.get_task()
        manager.task_done()

        assert first.task_id == "task-1"
        assert second.task_id == "task-2"
        assert third.task_id == "task-3"

    asyncio.run(run_test())


def test_queue_capacity():

    manager = QueueManager(config, max_size=2)

    manager.add_task(create_task("task-1", TaskPriority.HIGH))
    manager.add_task(create_task("task-2", TaskPriority.LOW))

    with pytest.raises(asyncio.QueueFull):
        manager.add_task(create_task("task-3", TaskPriority.MEDIUM))


def test_queue_size():

    manager = QueueManager(config, max_size=10)

    manager.add_task(create_task("task-1", TaskPriority.HIGH))
    manager.add_task(create_task("task-2", TaskPriority.LOW))

    assert manager.get_queue_size() == 2
    assert manager.is_empty() is False


def test_duplicate_task_is_rejected_while_queued():

    manager = QueueManager(config, max_size=10)

    task = create_task("task-duplicate-1", TaskPriority.HIGH)

    assert manager.add_task(task) is True
    assert manager.add_task(task) is False

    assert manager.get_queue_size() == 1


def test_duplicate_task_is_rejected_after_dequeue():

    async def run_test():

        manager = QueueManager(config, max_size=10)

        task = create_task("task-duplicate-2", TaskPriority.HIGH)

        assert manager.add_task(task) is True

        retrieved = await manager.get_task()
        manager.task_done()

        assert retrieved.task_id == task.task_id

        # The task must remain known after leaving the queue.
        assert manager.add_task(task) is False

        assert manager.get_queue_size() == 0

    asyncio.run(run_test())


def test_different_tasks_are_accepted():

    manager = QueueManager(config, max_size=10)

    task_1 = create_task("task-unique-1", TaskPriority.HIGH)
    task_2 = create_task("task-unique-2", TaskPriority.MEDIUM)

    assert manager.add_task(task_1) is True
    assert manager.add_task(task_2) is True

    assert manager.get_queue_size() == 2
