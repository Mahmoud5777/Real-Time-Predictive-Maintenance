
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
        destination_fog: str | None = None,
    ) -> bool:
        """Update a task status while protecting terminal states and destination."""

        with self._lock:
            task = self._tasks.get(task_id)

            if task is None:
                return False

            # Ignore events from a previous Fog destination.
            if (
                destination_fog is not None
                and destination_fog != task["destination_fog"]
            ):
                return False

            current_status = task["status"]

            # A completed or failed task cannot return to another state.
            terminal_statuses = {"COMPLETED", "FAILED"}

            if current_status in terminal_statuses:
                return current_status == status

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
        """Update the destination after successful task recovery."""

        with self._lock:
            task = self._tasks.get(task_id)

            if task is None:
                return False

            task["destination_fog"] = destination_fog

            # Change status only if the task is still being recovered.
            if task["status"] == "RECOVERING":
                task["status"] = "RECOVERED"

            task["attempts"] += 1
            task["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            task.pop("recovery_previous_status", None)

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
        statuses: tuple = ("PENDING", "ACCEPTED", "RUNNING"),
    ) -> list[dict]:
        """
        Return unfinished tasks assigned to a specific Fog node.
        These tasks may be candidates for fault recovery.
        """

        with self._lock:
            return [
                deepcopy(task)
                for task in self._tasks.values()
                if (
                    task["destination_fog"] == fog_id
                    and task["status"] in statuses
                )
            ]

    def claim_tasks_for_recovery(self, fog_id: str) -> list[dict]:
        """
        Atomically reserve unfinished tasks for fault recovery.
        Prevents the same task from being recovered multiple times.
        """

        recoverable_statuses = (
            "PENDING",
            "ACCEPTED",
            "RUNNING",
        )

        claimed_tasks = []

        with self._lock:
            for task in self._tasks.values():

                if (
                    task["destination_fog"] == fog_id
                    and task["status"] in recoverable_statuses
                ):
                    task["recovery_previous_status"] = task["status"]
                    task["status"] = "RECOVERING"
                    task["updated_at"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    claimed_tasks.append(deepcopy(task))

        return claimed_tasks

    def release_recovery_claim(self, task_id: str) -> bool:
        """
        Restore the previous status if task recovery fails.
        """

        with self._lock:
            task = self._tasks.get(task_id)

            if task is None or task["status"] != "RECOVERING":
                return False

            previous_status = task.pop(
                "recovery_previous_status",
                "PENDING",
            )

            task["status"] = previous_status
            task["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()

            return True