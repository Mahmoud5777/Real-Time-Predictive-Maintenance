
import asyncio
from itertools import count

from shared.models import TaskRequest, TaskPriority


class QueueManager:
    """
    Manage tasks using a priority queue.

    HIGH tasks are processed before MEDIUM,
    and MEDIUM before LOW.
    Tasks with the same priority keep their
    arrival order.
    """

    PRIORITY_LEVELS = {
        TaskPriority.HIGH: 0,
        TaskPriority.MEDIUM: 1,
        TaskPriority.LOW: 2,
    }

    def __init__(self, config, max_size: int | None = None):
        self.config = config

        queue_size = (
            max_size
            if max_size is not None
            else self.config.max_queue_size
        )

        self._queue = asyncio.PriorityQueue(maxsize=queue_size)
        self._counter = count()

        # Track task IDs to prevent duplicate queued tasks
        self._queued_task_ids = set()
        # Track tasks already accepted by this Fog node
        self._known_task_ids = set()

    def add_task(self, task: TaskRequest) -> bool:
        """Add a task only if it has never been accepted before."""

        task_id = task.task_id

        if task_id in self._known_task_ids:
            return False

        priority = self.PRIORITY_LEVELS[task.priority]
        sequence = next(self._counter)

        self._queue.put_nowait((priority, sequence, task))

        self._queued_task_ids.add(task_id)
        self._known_task_ids.add(task_id)

        return True

    async def get_task(self) -> TaskRequest:
        """Retrieve the next task according to priority."""

        _, _, task = await self._queue.get()

        # The task is no longer waiting in the queue.
        self._queued_task_ids.discard(task.task_id)

        return task

    def task_done(self) -> None:
        """Mark a retrieved task as completed."""

        self._queue.task_done()

    async def wait_until_empty(self) -> None:
        """Wait until all queued tasks are processed."""

        await self._queue.join()

    def get_queue_size(self) -> int:
        return self._queue.qsize()

    def is_empty(self) -> bool:
        return self._queue.empty()

    def is_full(self) -> bool:
        return self._queue.full()
