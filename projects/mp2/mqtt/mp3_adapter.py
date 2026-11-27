"""MP2 adapter for the frozen MP3 MQTT contract.

The adapter is deliberately independent of MP3 Python sources: MP2 can still run on
its own, while the payload it emits matches MP3's published Pydantic contract.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from shared.models import FogState, FogStatus, TaskEvent

logger = logging.getLogger(__name__)

FOG_IDS = {"fog-a": "FOG_A", "fog-b": "FOG_B", "fog-c": "FOG_C"}
MP3_TASK_TYPES = {
    "ANOMALY_DETECTION",
    "FAILURE_PREDICTION",
    "FEATURE_EXTRACTION",
    "AGGREGATION",
    "REPORTING",
    "MODEL_RETRAIN",
}
MP3_EVENT_STATUSES = {
    "CREATED",
    "QUEUED",
    "RUNNING",
    "MIGRATED",
    "COMPLETED",
    "FAILED",
    "RECOVERED",
}


class MP3ContractError(ValueError):
    """Raised when MP2 data cannot be represented without inventing a mapping."""


def _uuid4(value: str) -> str:
    try:
        parsed = UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MP3ContractError("task_id must be a UUID v4") from exc
    if parsed.version != 4:
        raise MP3ContractError("task_id must be a UUID v4")
    return str(parsed)


def _fog_id(value: str | None, *, required: bool) -> str | None:
    if value is None:
        if required:
            raise MP3ContractError("source_fog is required by the MP3 contract")
        return None
    try:
        return FOG_IDS[value]
    except KeyError as exc:
        raise MP3ContractError(f"unsupported MP2 Fog identifier: {value}") from exc


def _message_id() -> str:
    return str(uuid4())


class MP3MQTTAdapter:
    """Build and publish MP3 contract messages without changing MP2 internal topics."""

    def __init__(self, mqtt_client) -> None:
        self.mqtt_client = mqtt_client
        self._event_message_ids: dict[tuple[str, str, str | None], str] = {}

    def heartbeat(self, status: FogStatus, *, zone: str, active_tasks: int) -> tuple[str, dict[str, Any]]:
        if zone not in {"A", "B", "C"}:
            raise MP3ContractError(f"unsupported zone: {zone}")
        state = {
            FogState.ONLINE: "ONLINE",
            FogState.DEGRADED: "OVERLOADED",
            FogState.OFFLINE: "OFFLINE",
        }.get(status.status)
        if state is None:
            raise MP3ContractError(f"unsupported Fog status: {status.status}")
        fog_id = _fog_id(status.fog_id, required=True)
        payload = {
            "message_id": _message_id(),
            "fog_id": fog_id,
            "zone": zone,
            "status": state,
            "cpu_percent": status.cpu_percent,
            "ram_percent": status.ram_percent,
            "queued_tasks": status.queued_tasks,
            "active_tasks": active_tasks,
            "last_heartbeat": status.last_heartbeat.isoformat(),
        }
        return f"fog/{fog_id}/status", payload

    def task_event(self, event: TaskEvent, *, cloud_status: str | None = None) -> tuple[str, dict[str, Any]]:
        task_type = event.task_type.upper()
        if task_type not in MP3_TASK_TYPES:
            raise MP3ContractError(
                f"task_type {task_type} has no approved MP3 enum mapping"
            )
        status = cloud_status or event.status.value
        if status not in MP3_EVENT_STATUSES:
            raise MP3ContractError(f"status {status} has no approved MP3 enum mapping")
        task_id = _uuid4(event.task_id)
        destination = _fog_id(event.destination_fog, required=False)
        message_key = (task_id, status, destination)
        message_id = self._event_message_ids.get(message_key)
        if message_id is None:
            message_id = _message_id()
            self._event_message_ids[message_key] = message_id
        occurred_at = max(event.event_at, event.created_at)
        completed_at = (
            max(event.completed_at, occurred_at)
            if event.completed_at is not None
            else None
        )
        payload = {
            "message_id": message_id,
            "task_id": task_id,
            "task_type": task_type,
            "priority": event.priority.value,
            "critical": event.critical,
            "source_fog": _fog_id(event.source_fog, required=True),
            "destination_fog": destination,
            "status": status,
            "created_at": event.created_at.isoformat(),
            "occurred_at": occurred_at.isoformat(),
            "completed_at": completed_at.isoformat() if completed_at else None,
            "reason": event.reason,
        }
        return "tasks/events", payload

    def publish_heartbeat(self, status: FogStatus, *, zone: str, active_tasks: int):
        topic, payload = self.heartbeat(status, zone=zone, active_tasks=active_tasks)
        return self.mqtt_client.publish(topic, payload, qos=1, retain=True)

    def publish_task_event(self, event: TaskEvent, *, cloud_status: str | None = None):
        topic, payload = self.task_event(event, cloud_status=cloud_status)
        return self.mqtt_client.publish(topic, payload, qos=1, retain=False)

    def prediction(self, *, machine_id: str, fog_id: str, timestamp: datetime,
                   risk_score: float, anomaly: bool, predicted_fault: str,
                   severity: str, model_version: str) -> tuple[str, dict[str, Any]]:
        fog = _fog_id(fog_id, required=True)
        if machine_id not in {f"M{i:02d}" for i in range(1, 13)}:
            raise MP3ContractError(f"unsupported MP3 machine identifier: {machine_id}")
        if predicted_fault not in {
            "NONE", "BEARING_WEAR", "OVERHEATING",
            "IMBALANCE", "ELECTRICAL_OVERLOAD", "MISALIGNMENT",
        }:
            raise MP3ContractError(f"unsupported MP3 predicted fault: {predicted_fault}")
        if severity not in {"NORMAL", "WARNING", "CRITICAL"}:
            raise MP3ContractError(f"unsupported MP3 prediction severity: {severity}")
        payload = {
            "message_id": _message_id(),
            "machine_id": machine_id,
            "fog_id": fog,
            "timestamp": timestamp.isoformat(),
            "risk_score": risk_score,
            "anomaly": anomaly,
            "predicted_fault": predicted_fault,
            "severity": severity,
            "model_version": model_version,
        }
        return f"fog/{fog}/predictions", payload

    def alert(self, *, machine_id: str, fog_id: str, timestamp: datetime,
              alert_type: str, severity: str, message: str,
              recommended_action: str | None) -> tuple[str, dict[str, Any]]:
        fog = _fog_id(fog_id, required=True)
        if machine_id not in {f"M{i:02d}" for i in range(1, 13)}:
            raise MP3ContractError(f"unsupported MP3 machine identifier: {machine_id}")
        if alert_type not in {
            "ANOMALY_DETECTED", "THRESHOLD_EXCEEDED",
            "PREDICTED_FAILURE", "SENSOR_LOST", "NODE_UNREACHABLE",
        }:
            raise MP3ContractError(f"unsupported MP3 alert type: {alert_type}")
        if severity not in {"NORMAL", "WARNING", "CRITICAL"}:
            raise MP3ContractError(f"unsupported MP3 alert severity: {severity}")
        payload = {
            "message_id": _message_id(),
            "alert_id": str(uuid4()),
            "machine_id": machine_id,
            "fog_id": fog,
            "timestamp": timestamp.isoformat(),
            "type": alert_type,
            "severity": severity,
            "message": message,
            "recommended_action": recommended_action,
        }
        return f"fog/{fog}/alerts", payload

    def publish_prediction(self, **kwargs):
        topic, payload = self.prediction(**kwargs)
        return self.mqtt_client.publish(topic, payload, qos=1, retain=False)

    def publish_alert(self, **kwargs):
        topic, payload = self.alert(**kwargs)
        return self.mqtt_client.publish(topic, payload, qos=1, retain=False)


def new_task_id() -> str:
    """Generate an MP3-compatible task identifier for a newly accepted MP2 task."""
    return str(uuid4())
