
from datetime import datetime, timezone
from typing import Any

from shared.models import (
    TaskRequest,
    TaskEvent,
    TaskStatus,
)

from .queue_manager import QueueManager


class TaskProcessor:
    """
    Execute industrial tasks locally on a Fog Node
    and publish task lifecycle events through MQTT.
    """

    def __init__(
        self,
        queue_manager: QueueManager,
        config,
        mqtt_client=None,
    ):
        self.queue_manager = queue_manager
        self.config = config
        self.mqtt_client = mqtt_client

    def _publish_task_event(self, event: TaskEvent) -> None:
        """Publish a task lifecycle event through MQTT."""

        if self.mqtt_client is None:
            return

        topic = f"fog/{self.config.fog_id}/tasks/events"

        payload = event.model_dump(mode="json")

        self.mqtt_client.publish(
            topic,
            payload,
        )

    def _detect_anomalies(
        self,
        payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Detect abnormal temperature and vibration values."""

        if "temperature" not in payload and "vibration" not in payload:
            raise ValueError(
                "Temperature or vibration data is required."
            )

        anomalies = []

        temperature = payload.get("temperature")
        vibration = payload.get("vibration")

        if temperature is not None:
            if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
                raise ValueError("Invalid temperature value.")

            if temperature > self.config.temperature_threshold:
                anomalies.append("HIGH_TEMPERATURE")

        if vibration is not None:
            if not isinstance(vibration, (int, float)) or isinstance(vibration, bool):
                raise ValueError("Invalid vibration value.")

            if vibration > self.config.vibration_threshold:
                anomalies.append("HIGH_VIBRATION")

        return {
            "anomaly_detected": len(anomalies) > 0,
            "anomalies": anomalies,
            "temperature": temperature,
            "vibration": vibration
        }

    def _predict_failure(
        self,
        payload: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Estimate a failure risk using a simple rule-based approach.
        """

        detection = self._detect_anomalies(payload)

        anomaly_count = len(detection["anomalies"])

        if anomaly_count == 0:
            risk_level = "LOW"
        elif anomaly_count == 1:
            risk_level = "MEDIUM"
        else:
            risk_level = "HIGH"

        return {
            "risk_level": risk_level,
            "anomaly_count": anomaly_count,
            "anomalies": detection["anomalies"],
            "method": "RULE_BASED"
        }

    def _preprocess_data(
        self,
        payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Prepare data for subsequent processing."""

        if not payload:
            raise ValueError("The payload cannot be empty.")

        return {
            "received_fields": list(payload.keys()),
            "field_count": len(payload),
            "data_ready": True
        }

    def execute(self, task: TaskRequest) -> dict[str, Any]:
        """Select and execute the appropriate task handler."""

        task_type = task.task_type.upper()

        if task_type == "ANOMALY_DETECTION":
            return self._detect_anomalies(task.payload)

        elif task_type == "FAILURE_PREDICTION":
            return self._predict_failure(task.payload)

        elif task_type == "DATA_PREPROCESSING":
            return self._preprocess_data(task.payload)

        else:
            raise ValueError(
                f"Unsupported task type: {task_type}"
            )

    async def process_next(self) -> TaskEvent:
        """Retrieve, execute and report one task."""

        task = await self.queue_manager.get_task()

        started_at = datetime.now(timezone.utc)

        running_event = TaskEvent(
            task_id=task.task_id,
            source_fog=task.source_fog,
            destination_fog=self.config.fog_id,
            priority=task.priority,
            status=TaskStatus.RUNNING,
            created_at=task.created_at,
        )

        self._publish_task_event(running_event)

        try:
            result = self.execute(task)
            status = TaskStatus.COMPLETED

        except Exception as error:
            result = {"error": str(error)}
            status = TaskStatus.FAILED

        finally:
            self.queue_manager.task_done()

        completed_at = datetime.now(timezone.utc)

        final_event = TaskEvent(
            task_id=task.task_id,
            source_fog=task.source_fog,
            destination_fog=self.config.fog_id,
            priority=task.priority,
            status=status,
            created_at=task.created_at,
            completed_at=completed_at,
            result=result,
        )

        self._publish_task_event(final_event)

        return final_event
