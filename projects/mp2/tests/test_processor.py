import asyncio

from fog_nodes.common.queue_manager import QueueManager
from fog_nodes.common.processor import TaskProcessor
from fog_nodes.fog_a.config import config
from shared.models import TaskRequest, TaskPriority, TaskStatus


def create_task(task_id, task_type, payload):
    return TaskRequest(task_id=task_id, task_type=task_type,
                       priority=TaskPriority.HIGH, payload=payload)


def test_anomaly_detection():
    processor = TaskProcessor(QueueManager(config), config)
    task = create_task("task-001", "ANOMALY_DETECTION",
                       {"temperature": 95, "vibration": 7.2})
    result = processor.execute(task)
    assert result["anomaly_detected"] is True
    assert "HIGH_TEMPERATURE" in result["anomalies"]
    assert "HIGH_VIBRATION" in result["anomalies"]


def test_incomplete_failure_prediction_uses_explicit_legacy_fallback():
    processor = TaskProcessor(QueueManager(config), config)
    task = create_task("task-002", "FAILURE_PREDICTION",
                       {"temperature": 95, "vibration": 7.2})
    result = processor.execute(task)
    assert result["risk_level"] == "HIGH"
    assert result["method"] == "RULE_BASED_FALLBACK"
    assert result["model_version"] == "mp2-rule-fallback-v1"


def test_complete_sensor_payload_uses_mp1_predictor():
    class FakeMP1Predictor:
        def __init__(self):
            self.received = None

        def predict(self, payload):
            self.received = payload
            return {
                "machine_id": "M01",
                "timestamp": payload["timestamp"],
                "risk_score": 0.91,
                "anomaly": True,
                "predicted_fault": "OVERHEATING",
                "severity": "CRITICAL",
                "model_version": "hybrid-test-model",
            }

    predictor = FakeMP1Predictor()
    processor = TaskProcessor(QueueManager(config), config, predictor=predictor)
    payload = {
        "message_id": "01J00000000000000000000000",
        "machine_id": "M01",
        "zone": "A",
        "timestamp": "2026-11-25T10:00:00Z",
        "temperature": 95.0,
        "vibration": 7.2,
        "speed": 1480.0,
        "current": 12.4,
        "state": "FAULT",
    }
    task = create_task("task-ml-001", "FAILURE_PREDICTION", payload)

    result = processor.execute(task)

    # Pydantic normalizes/copies input dictionaries when constructing TaskRequest.
    # The processor must pass the exact payload object held by the task to MP1.
    assert predictor.received is task.payload
    assert predictor.received == payload
    assert result["method"] == "MP1_ML"
    assert result["model_version"] == "hybrid-test-model"
    assert result["risk_score"] == 0.91
    assert result["anomaly"] is True
    assert result["predicted_fault"] == "OVERHEATING"
    assert result["severity"] == "CRITICAL"


def test_data_preprocessing():
    processor = TaskProcessor(QueueManager(config), config)
    task = create_task("task-003", "DATA_PREPROCESSING",
                       {"temperature": 65, "vibration": 2.1})
    result = processor.execute(task)
    assert result["data_ready"] is True
    assert result["field_count"] == 2


def test_process_next():
    async def run_test():
        queue = QueueManager(config)
        processor = TaskProcessor(queue, config)
        task = create_task("task-004", "ANOMALY_DETECTION",
                           {"temperature": 95, "vibration": 7.2})
        queue.add_task(task)
        event = await processor.process_next()
        assert event.task_id == "task-004"
        assert event.status == TaskStatus.COMPLETED
        assert event.result["anomaly_detected"] is True
        assert queue.is_empty()
    asyncio.run(run_test())


def test_unsupported_task():
    processor = TaskProcessor(QueueManager(config), config)
    task = create_task("task-005", "UNKNOWN_TASK", {})
    try:
        processor.execute(task)
        assert False, "An unsupported task should raise ValueError"
    except ValueError as error:
        assert "Unsupported task type" in str(error)
