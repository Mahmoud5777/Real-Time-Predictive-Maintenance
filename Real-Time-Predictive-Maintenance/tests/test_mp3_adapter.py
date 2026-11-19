from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
from uuid import uuid4
from types import SimpleNamespace

import pytest

from fog_nodes.common.processor import TaskProcessor
from fog_nodes.common.queue_manager import QueueManager
from mqtt.mp3_adapter import MP3ContractError, MP3MQTTAdapter
from shared.models import FogState, FogStatus, TaskEvent, TaskPriority, TaskRequest, TaskStatus


# Validate output against the real frozen MP3 Pydantic models, without making MP2
# depend on MP3 at runtime.
MP3_ROOT = Path(__file__).resolve().parents[2] / "MP3_Backend_Source" / "mp3-cloud"
sys.path.insert(0, str(MP3_ROOT))
from app.schemas.messages import (
    AlertMessage as MP3Alert,
    FogStatus as MP3FogStatus,
    PredictionResult as MP3Prediction,
    TaskEvent as MP3TaskEvent,
)  # noqa: E402


class RecordingMqttClient:
    def __init__(self):
        self.calls = []

    def publish(self, topic, message, *, qos=0, retain=False):
        self.calls.append((topic, message, qos, retain))
        return 0


def test_heartbeat_is_accepted_by_real_mp3_model_and_is_retained_qos_1():
    client = RecordingMqttClient()
    adapter = MP3MQTTAdapter(client)
    status = FogStatus(
        fog_id="fog-a",
        status=FogState.DEGRADED,
        cpu_percent=91.0,
        ram_percent=80.0,
        queued_tasks=2,
        last_heartbeat=datetime.now(timezone.utc),
    )

    adapter.publish_heartbeat(status, zone="A", active_tasks=1)

    topic, payload, qos, retain = client.calls[-1]
    assert topic == "fog/FOG_A/status"
    assert qos == 1
    assert retain is True
    assert payload["status"] == "OVERLOADED"
    assert MP3FogStatus.model_validate(payload).active_tasks == 1


def test_task_event_is_accepted_by_real_mp3_model_and_retransmission_keeps_message_id():
    client = RecordingMqttClient()
    adapter = MP3MQTTAdapter(client)
    task_id = str(uuid4())
    event = TaskEvent(
        task_id=task_id,
        task_type="ANOMALY_DETECTION",
        priority=TaskPriority.HIGH,
        critical=False,
        source_fog="fog-a",
        destination_fog="fog-b",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
    )

    adapter.publish_task_event(event)
    adapter.publish_task_event(event)

    first_topic, first_payload, first_qos, first_retain = client.calls[0]
    second_topic, second_payload, second_qos, second_retain = client.calls[1]
    assert first_topic == second_topic == "tasks/events"
    assert first_qos == second_qos == 1
    assert first_retain is second_retain is False
    assert first_payload["message_id"] == second_payload["message_id"]
    assert MP3TaskEvent.model_validate(first_payload).task_id == task_id


def test_unsupported_task_type_is_not_approximated_to_an_mp3_enum():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    event = TaskEvent(
        task_id=str(uuid4()),
        task_type="DATA_PREPROCESSING",
        priority=TaskPriority.HIGH,
        source_fog="fog-a",
        destination_fog="fog-a",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
    )

    with pytest.raises(MP3ContractError, match="no approved MP3 enum mapping"):
        adapter.task_event(event)


def test_task_id_is_normalized_once_before_dispatch():
    task = TaskRequest(
        task_id="legacy-task-id",
        task_type="ANOMALY_DETECTION",
        priority=TaskPriority.HIGH,
    )
    first = task.ensure_mp3_task_id()
    second = task.ensure_mp3_task_id()

    assert first == second
    assert uuid4().__class__(first).version == 4


def _fog_config():
    return SimpleNamespace(
        fog_id="fog-a",
        max_queue_size=10,
        temperature_threshold=80.0,
        vibration_threshold=5.0,
    )


def _task_event(task_id, status, *, critical=True, completed_at=None, reason=None):
    return TaskEvent(
        task_id=task_id,
        task_type="ANOMALY_DETECTION",
        priority=TaskPriority.HIGH,
        critical=critical,
        source_fog="fog-a",
        destination_fog="fog-b",
        status=status,
        created_at=datetime.now(timezone.utc),
        completed_at=completed_at,
        reason=reason,
    )


def test_all_cloud_lifecycle_payloads_validate_with_critical_preserved():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    task_id = str(uuid4())
    completed_at = datetime.now(timezone.utc)
    lifecycle = [
        (_task_event(task_id, TaskStatus.PENDING), "CREATED"),
        (_task_event(task_id, TaskStatus.PENDING), "QUEUED"),
        (_task_event(task_id, TaskStatus.RUNNING), None),
        (_task_event(task_id, TaskStatus.COMPLETED, completed_at=completed_at), None),
        (_task_event(task_id, TaskStatus.FAILED, completed_at=completed_at, reason="processor error"), None),
    ]

    payloads = []
    for event, cloud_status in lifecycle:
        topic, payload = adapter.task_event(event, cloud_status=cloud_status)
        validated = MP3TaskEvent.model_validate(payload)
        assert topic == "tasks/events"
        assert validated.critical is True
        payloads.append(payload)

    assert [payload["status"] for payload in payloads] == [
        "CREATED", "QUEUED", "RUNNING", "COMPLETED", "FAILED"
    ]
    assert len({payload["message_id"] for payload in payloads}) == len(payloads)


def test_failure_prediction_event_includes_occurrence_time():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    occurred_at = datetime.now(timezone.utc)
    event = TaskEvent(
        task_id=str(uuid4()),
        task_type="FAILURE_PREDICTION",
        priority=TaskPriority.MEDIUM,
        critical=False,
        source_fog="fog-a",
        destination_fog="fog-a",
        status=TaskStatus.RUNNING,
        created_at=occurred_at,
        event_at=occurred_at,
    )

    topic, payload = adapter.task_event(event)

    assert topic == "tasks/events"
    validated = MP3TaskEvent.model_validate(payload)
    assert validated.task_type == "FAILURE_PREDICTION"
    assert validated.occurred_at == occurred_at


def test_task_event_timestamps_cannot_precede_task_creation():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    created_at = datetime.now(timezone.utc)
    event = TaskEvent(
        task_id=str(uuid4()),
        task_type="FAILURE_PREDICTION",
        priority=TaskPriority.MEDIUM,
        source_fog="fog-a",
        destination_fog="fog-a",
        status=TaskStatus.COMPLETED,
        created_at=created_at,
        event_at=created_at - timedelta(milliseconds=1),
        completed_at=created_at - timedelta(milliseconds=1),
    )

    _, payload = adapter.task_event(event)

    validated = MP3TaskEvent.model_validate(payload)
    assert validated.occurred_at == created_at
    assert validated.completed_at == created_at


@pytest.mark.asyncio
async def test_active_task_count_tracks_queue_lifecycle():
    queue = QueueManager(_fog_config())
    task = TaskRequest(
        task_id=str(uuid4()),
        task_type="ANOMALY_DETECTION",
        priority=TaskPriority.HIGH,
    )

    assert queue.get_active_task_count() == 0
    assert queue.add_task(task) is True
    assert queue.get_active_task_count() == 0

    active_task = await queue.get_task()
    assert active_task.task_id == task.task_id
    assert queue.get_active_task_count() == 1

    queue.task_done(task.task_id)
    assert queue.get_active_task_count() == 0


@pytest.mark.asyncio
async def test_processor_keeps_internal_event_and_publishes_mp3_event():
    client = RecordingMqttClient()
    config = _fog_config()
    queue = QueueManager(config)
    processor = TaskProcessor(queue, config, mqtt_client=client)
    task = TaskRequest(
        task_id=str(uuid4()),
        task_type="ANOMALY_DETECTION",
        priority=TaskPriority.HIGH,
        critical=True,
        source_fog="fog-a",
        payload={"temperature": 90.0, "vibration": 1.0},
    )

    assert queue.add_task(task) is True
    processor.publish_queued_task(task)
    final_event = await processor.process_next()

    topics = [topic for topic, _payload, _qos, _retain in client.calls]
    assert topics == [
        "tasks/events",
        "fog/fog-a/tasks/events",
        "tasks/events",
        "fog/fog-a/tasks/events",
        "tasks/events",
    ]
    cloud_calls = [call for call in client.calls if call[0] == "tasks/events"]
    assert [call[1]["status"] for call in cloud_calls] == ["QUEUED", "RUNNING", "COMPLETED"]
    assert all(call[2:] == (1, False) for call in cloud_calls)
    assert all(MP3TaskEvent.model_validate(call[1]).critical is True for call in cloud_calls)
    internal_calls = [call for call in client.calls if call[0] == "fog/fog-a/tasks/events"]
    assert len(internal_calls) == 2
    assert all(call[2:] == (0, False) for call in internal_calls)
    assert final_event.status is TaskStatus.COMPLETED
    assert queue.get_active_task_count() == 0


def test_non_mp3_task_still_publishes_internal_event_without_cloud_conversion():
    client = RecordingMqttClient()
    processor = TaskProcessor(QueueManager(_fog_config()), _fog_config(), mqtt_client=client)
    event = TaskEvent(
        task_id=str(uuid4()),
        task_type="DATA_PREPROCESSING",
        priority=TaskPriority.LOW,
        source_fog="fog-a",
        destination_fog="fog-a",
        status=TaskStatus.RUNNING,
        created_at=datetime.now(timezone.utc),
    )

    processor._publish_task_event(event)

    assert len(client.calls) == 1
    topic, payload, qos, retain = client.calls[0]
    assert topic == "fog/fog-a/tasks/events"
    assert payload["task_type"] == "DATA_PREPROCESSING"
    assert (qos, retain) == (0, False)


def test_each_lifecycle_republication_keeps_its_message_id():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    task_id = str(uuid4())
    events = [
        (_task_event(task_id, TaskStatus.PENDING), "CREATED"),
        (_task_event(task_id, TaskStatus.PENDING), "QUEUED"),
        (_task_event(task_id, TaskStatus.RUNNING), None),
        (_task_event(task_id, TaskStatus.COMPLETED, completed_at=datetime.now(timezone.utc)), None),
        (_task_event(task_id, TaskStatus.FAILED, completed_at=datetime.now(timezone.utc)), None),
    ]

    for event, cloud_status in events:
        _topic, first = adapter.task_event(event, cloud_status=cloud_status)
        _topic, second = adapter.task_event(event, cloud_status=cloud_status)
        assert first["message_id"] == second["message_id"]


def test_prediction_payload_is_accepted_by_real_mp3_model():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    timestamp = datetime.now(timezone.utc)

    topic, payload = adapter.prediction(
        machine_id="M01",
        fog_id="fog-a",
        timestamp=timestamp,
        risk_score=0.85,
        anomaly=True,
        predicted_fault="OVERHEATING",
        severity="CRITICAL",
        model_version="mp2-rule-v1",
    )

    assert topic == "fog/FOG_A/predictions"
    assert MP3Prediction.model_validate(payload).risk_score == Decimal("0.85")


def test_alert_payload_is_accepted_by_real_mp3_model():
    adapter = MP3MQTTAdapter(RecordingMqttClient())
    timestamp = datetime.now(timezone.utc)

    topic, payload = adapter.alert(
        machine_id="M01",
        fog_id="fog-a",
        timestamp=timestamp,
        alert_type="PREDICTED_FAILURE",
        severity="CRITICAL",
        message="HIGH_TEMPERATURE",
        recommended_action="Inspect the affected machine.",
    )

    assert topic == "fog/FOG_A/alerts"
    assert MP3Alert.model_validate(payload).severity == "CRITICAL"
