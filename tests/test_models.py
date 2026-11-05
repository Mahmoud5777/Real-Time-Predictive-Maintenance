
from shared.models import (
    MachineData,
    FogStatus,
    TaskRequest,
    TaskEvent,
    FogState,
    TaskPriority,
    TaskStatus,
)


def test_machine_data():
    machine = MachineData(
        machine_id="M01",
        zone="A",
        temperature=65.5,
        vibration=1.2,
        speed=1480,
        current=10.5
    )

    assert machine.machine_id == "M01"
    assert machine.temperature == 65.5


def test_fog_status():
    fog = FogStatus(
        fog_id="fog-a",
        status=FogState.ONLINE,
        cpu_percent=35.5,
        ram_percent=42.0,
        queued_tasks=5
    )

    assert fog.status == FogState.ONLINE
    assert fog.queued_tasks == 5


def test_task_request():
    task = TaskRequest(
        task_id="task-001",
        task_type="ANOMALY_DETECTION",
        priority=TaskPriority.HIGH,
        machine_id="M01"
    )

    assert task.priority == TaskPriority.HIGH


def test_task_event():
    event = TaskEvent(
        task_id="task-001",
        source_fog="fog-a",
        destination_fog="fog-b",
        priority=TaskPriority.LOW,
        status=TaskStatus.MIGRATED,
        created_at=TaskRequest(
            task_id="task-001",
            task_type="STATISTICS",
            priority=TaskPriority.LOW
        ).created_at
    )

    assert event.status == TaskStatus.MIGRATED
    assert event.destination_fog == "fog-b"
