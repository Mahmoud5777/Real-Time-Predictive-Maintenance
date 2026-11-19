
from datetime import datetime, timezone
import logging
from typing import Any

from shared.models import (
    TaskRequest,
    TaskEvent,
    TaskStatus,
)
from shared.metrics import metrics
from mqtt.mp3_adapter import MP3ContractError, MP3MQTTAdapter

from .queue_manager import QueueManager

logger = logging.getLogger(__name__)


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
        self.mp3_adapter = MP3MQTTAdapter(mqtt_client) if mqtt_client is not None else None

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

        try:
            self.mp3_adapter.publish_task_event(event)
        except MP3ContractError as exc:
            # Do not invent an MP3 enum translation for an internal MP2 task.
            logger.warning("Task event not published to MP3: %s", exc)

    def publish_queued_task(self, task: TaskRequest) -> None:
        """Emit the MP3 QUEUED lifecycle event after this Fog accepted a task."""
        if self.mp3_adapter is None:
            return
        event = TaskEvent(
            task_id=task.task_id,
            task_type=task.task_type,
            source_fog=task.source_fog,
            destination_fog=self.config.fog_id,
            priority=task.priority,
            status=TaskStatus.PENDING,
            created_at=task.created_at,
            critical=task.critical,
        )
        try:
            self.mp3_adapter.publish_task_event(event, cloud_status="QUEUED")
        except MP3ContractError as exc:
            logger.warning("Queued task not published to MP3: %s", exc)

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
        """Estimate a failure risk using a simple rule-based approach."""

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
        """Retrieve, execute and report one task with performance metrics."""

        task = await self.queue_manager.get_task()

        started_at = datetime.now(timezone.utc)

        queue_wait_ms = max(
            (started_at - task.created_at).total_seconds() * 1000,
            0,
        )

        running_event = TaskEvent(
            task_id=task.task_id,
            task_type=task.task_type,
            source_fog=task.source_fog,
            destination_fog=self.config.fog_id,
            priority=task.priority,
            status=TaskStatus.RUNNING,
            created_at=task.created_at,
            started_at=started_at,
            queue_wait_ms=queue_wait_ms,
            critical=task.critical,
        )

        self._publish_task_event(running_event)

        try:
            result = self.execute(task)
            status = TaskStatus.COMPLETED

        except Exception as error:
            result = {"error": str(error)}
            status = TaskStatus.FAILED

        finally:
            self.queue_manager.task_done(task.task_id)

        completed_at = datetime.now(timezone.utc)

        processing_time_ms = max(
            (completed_at - started_at).total_seconds() * 1000,
            0,
        )

        end_to_end_ms = max(
            (completed_at - task.created_at).total_seconds() * 1000,
            0,
        )

        final_event = TaskEvent(
            task_id=task.task_id,
            task_type=task.task_type,
            source_fog=task.source_fog,
            destination_fog=self.config.fog_id,
            priority=task.priority,
            status=status,
            created_at=task.created_at,
            started_at=started_at,
            queue_wait_ms=queue_wait_ms,
            processing_time_ms=processing_time_ms,
            completed_at=completed_at,
            result=result,
            critical=task.critical,
            reason=result.get("error") if isinstance(result, dict) else None,
        )

        if task.task_type.upper() == "FAILURE_PREDICTION" and isinstance(result, dict):
            machine_id = task.machine_id or task.payload.get("machine_id")
            timestamp_value = task.payload.get("timestamp")
            try:
                timestamp = datetime.fromisoformat(
                    str(timestamp_value).replace("Z", "+00:00")
                )
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                timestamp = started_at

            risk_level = result.get("risk_level")
            risk_score = {"LOW": 0.25, "MEDIUM": 0.55, "HIGH": 0.85}.get(
                risk_level, 0.25
            )
            anomalies = result.get("anomalies", [])
            anomaly = bool(anomalies)
            if "HIGH_VIBRATION" in anomalies:
                predicted_fault = "BEARING_WEAR"
            elif "HIGH_TEMPERATURE" in anomalies:
                predicted_fault = "OVERHEATING"
            else:
                predicted_fault = "NONE"
            severity = {"LOW": "NORMAL", "MEDIUM": "WARNING", "HIGH": "CRITICAL"}.get(
                risk_level, "NORMAL"
            )

            if machine_id and self.mp3_adapter is not None:
                try:
                    self.mp3_adapter.publish_prediction(
                        machine_id=machine_id,
                        fog_id=self.config.fog_id,
                        timestamp=timestamp,
                        risk_score=risk_score,
                        anomaly=anomaly,
                        predicted_fault=predicted_fault,
                        severity=severity,
                        model_version="mp2-rule-v1",
                    )
                    if anomaly:
                        alert_type = (
                            "PREDICTED_FAILURE"
                            if risk_level == "HIGH"
                            else "ANOMALY_DETECTED"
                        )
                        self.mp3_adapter.publish_alert(
                            machine_id=machine_id,
                            fog_id=self.config.fog_id,
                            timestamp=timestamp,
                            alert_type=alert_type,
                            severity=severity,
                            message="; ".join(anomalies),
                            recommended_action="Inspect the affected machine and sensor readings.",
                        )
                except MP3ContractError as exc:
                    logger.warning("Prediction or alert not published to MP3: %s", exc)

        metrics.record_task_completion(
            fog_id=self.config.fog_id,
            task_type=task.task_type.upper(),
            status=status.value,
            queue_wait_ms=queue_wait_ms,
            processing_time_ms=processing_time_ms,
            end_to_end_ms=end_to_end_ms,
        )

        self._publish_task_event(final_event)

        return final_event
