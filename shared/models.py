from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict

# ==========================================
# ENUMERATIONS
# ==========================================

class FogState(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"


class TaskPriority(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    MIGRATED = "MIGRATED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERED = "RECOVERED"


# ==========================================
# MACHINE DATA
# ==========================================

class MachineData(BaseModel):
    """Sensor measurements received from an industrial machine."""

    model_config = ConfigDict(extra="forbid")

    machine_id: str
    zone: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    temperature: float = Field(ge=0)
    vibration: float = Field(ge=0)  
    speed: float = Field(ge=0)
    current: float = Field(ge=0)

    pressure: Optional[float] = Field(default=None, ge=0)
    power: Optional[float] = Field(default=None, ge=0)


# ==========================================
# FOG NODE STATUS
# ==========================================

class FogStatus(BaseModel):
    """Current health and resource information of a Fog node."""

    model_config = ConfigDict(extra="forbid")

    fog_id: str
    status: FogState = FogState.ONLINE

    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)

    queued_tasks: int = Field(ge=0, default=0)

    last_heartbeat: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ==========================================
# TASK REQUEST
# ==========================================

class TaskRequest(BaseModel):
    """A task submitted to a Fog node for execution."""

    task_id: str
    task_type: str
    priority: TaskPriority

    payload: dict[str, Any] = Field(default_factory=dict)

    source_fog: Optional[str] = None
    machine_id: Optional[str] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ==========================================
# TASK EVENT
# ==========================================

class TaskEvent(BaseModel):
    """A record of task execution, migration or recovery."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_type: str = "UNKNOWN"

    source_fog: Optional[str] = None
    destination_fog: Optional[str] = None

    priority: TaskPriority
    status: TaskStatus

    created_at: datetime
    event_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: Optional[datetime] = None

    result: Optional[dict[str, Any]] = None
    started_at: Optional[datetime] = None
    queue_wait_ms: Optional[float] = None
    processing_time_ms: Optional[float] = None
