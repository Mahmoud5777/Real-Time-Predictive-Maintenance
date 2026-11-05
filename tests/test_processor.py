
import asyncio

from fog_nodes.common.queue_manager import QueueManager
from fog_nodes.common.processor import TaskProcessor
from fog_nodes.fog_a.config import config

from shared.models import (
    TaskRequest,
    TaskPriority,
    TaskStatus
)


def create_task(task_id, task_type, payload):
    return TaskRequest(
        task_id=task_id,
        task_type=task_type,
        priority=TaskPriority.HIGH,
        payload=payload
    )


def test_anomaly_detection():

    queue = QueueManager(config)
    processor = TaskProcessor(queue, config)

    task = create_task(
        "task-001",
        "ANOMALY_DETECTION",
        {
            "temperature": 95,
            "vibration": 7.2
        }
    )

    result = processor.execute(task)

    assert result["anomaly_detected"] is True
    assert "HIGH_TEMPERATURE" in result["anomalies"]
    assert "HIGH_VIBRATION" in result["anomalies"]


def test_failure_prediction():

    queue = QueueManager(config)
    processor = TaskProcessor(queue, config)

    task = create_task(
        "task-002",
        "FAILURE_PREDICTION",
        {
            "temperature": 95,
            "vibration": 7.2
        }
    )

    result = processor.execute(task)

    assert result["risk_level"] == "HIGH"
    assert result["method"] == "RULE_BASED"


def test_data_preprocessing():

    queue = QueueManager(config)
    processor = TaskProcessor(queue, config)

    task = create_task(
        "task-003",
        "DATA_PREPROCESSING",
        {
            "temperature": 65,
            "vibration": 2.1
        }
    )

    result = processor.execute(task)

    assert result["data_ready"] is True
    assert result["field_count"] == 2


def test_process_next():

    async def run_test():

        queue = QueueManager(config)
        processor = TaskProcessor(queue, config)

        task = create_task(
            "task-004",
            "ANOMALY_DETECTION",
            {
                "temperature": 95,
                "vibration": 7.2
            }
        )

        queue.add_task(task)

        event = await processor.process_next()

        assert event.task_id == "task-004"
        assert event.status == TaskStatus.COMPLETED
        assert event.result["anomaly_detected"] is True

        assert queue.is_empty()

    asyncio.run(run_test())


def test_unsupported_task():

    queue = QueueManager(config)
    processor = TaskProcessor(queue, config)

    task = create_task(
        "task-005",
        "UNKNOWN_TASK",
        {}
    )

    try:
        processor.execute(task)
        assert False, "An unsupported task should raise ValueError"

    except ValueError as error:
        assert "Unsupported task type" in str(error)
