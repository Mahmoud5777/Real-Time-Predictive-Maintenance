
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock


class TaskRegistry:
    """
    Central registry for tracking distributed Fog tasks.
    """

    def __init__(self):
        self._lock = Lock()
        self._tasks = {}

    def register_task(
        self,
        task: dict,
        source_fog: str,
        destination_fog: str,
    ) -> None:
        """Register a task after successful dispatch."""

        task_id = task["task_id"]

        with self._lock:
            now = datetime.now(timezone.utc).isoformat()

            self._tasks[task_id] = {
                "task_id": task_id,
                "task": deepcopy(task),
                "source_fog": source_fog,
                "destination_fog": destination_fog,
                "status": "PENDING",
                "attempts": 1,
                "created_at": now,
                "updated_at": now,
            }

    def update_task_status(
        self,
        task_id: str,
        status: str,
    ) -> bool:
        """Update the status of a registered task."""

        with self._lock:
            task = self._tasks.get(task_id)

            if task is None:
                return False

            task["status"] = status
            task["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return True

    def update_destination(
        self,
        task_id: str,
        destination_fog: str,
    ) -> bool:
        """Update the destination after task reassignment."""

        with self._lock:
            task = self._tasks.get(task_id)

            if task is None:
                return False

            task["destination_fog"] = destination_fog
            task["status"] = "RECOVERED"
            task["attempts"] += 1
            task["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return True

    def get_task(self, task_id: str):
        """Return one registered task."""

        with self._lock:
            task = self._tasks.get(task_id)

            return deepcopy(task) if task else None

    def get_all_tasks(self) -> list[dict]:
        """Return all registered tasks."""

        with self._lock:
            return deepcopy(list(self._tasks.values()))

    def get_node_tasks(
        self,
        fog_id: str,
        statuses: tuple = ("PENDING", "RUNNING"),
    ) -> list[dict]:
        """Return unfinished tasks assigned to a Fog node."""

        with self._lock:
            return [
                deepcopy(task)
                for task in self._tasks.values()
                if task["destination_fog"] == fog_id
                and task["status"] in statuses
            ]

    def get_tasks_by_status(self, status: str) -> list[dict]:
        """Return tasks matching a given status."""

        with self._lock:
            return [
                deepcopy(task)
                for task in self._tasks.values()
                if task["status"] == status
            ]
