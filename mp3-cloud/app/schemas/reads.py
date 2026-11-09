"""Reponses publiques de lecture ; les champs absents restent NULL."""

from typing import Annotated, Literal

from pydantic import UUID4, BaseModel, ConfigDict, Field

from app.schemas.common import UtcDatetime
from app.schemas.messages import MACHINE_PATTERN, FogId, Zone

MachineId = Annotated[str, Field(pattern=MACHINE_PATTERN)]
Severity = Literal["NORMAL", "WARNING", "CRITICAL"]
AlertStatus = Literal["OPEN", "ACKNOWLEDGED", "RESOLVED"]
NodeStatus = Literal["ONLINE", "OVERLOADED", "OFFLINE", "RECOVERING"]
SupervisionStatus = Literal["UNKNOWN", "REACHABLE", "UNREACHABLE"]
SupervisionReason = Literal[
    "NO_HEARTBEAT",
    "FRESH_HEARTBEAT",
    "HEARTBEAT_TIMEOUT",
    "REPORTED_OFFLINE",
    "CLOCK_SKEW",
    "MONITOR_GAP",
]
TaskStatus = Literal["CREATED", "QUEUED", "RUNNING", "MIGRATED", "COMPLETED", "FAILED", "RECOVERED"]
TaskType = Literal[
    "ANOMALY_DETECTION", "FEATURE_EXTRACTION", "AGGREGATION", "REPORTING", "MODEL_RETRAIN"
]
Priority = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
MachineSort = Literal["machine_id", "-machine_id", "name", "-name", "zone", "-zone"]
MeasurementSort = Literal["timestamp", "-timestamp", "received_at", "-received_at", "id", "-id"]
PredictionSort = Literal[
    "timestamp",
    "-timestamp",
    "received_at",
    "-received_at",
    "risk_score",
    "-risk_score",
    "id",
    "-id",
]
NodeSort = Literal["fog_id", "-fog_id", "zone", "-zone", "last_heartbeat", "-last_heartbeat"]
HistorySort = Literal["observed_at", "-observed_at", "received_at", "-received_at", "id", "-id"]
TaskSort = Literal["created_at", "-created_at", "last_received_at", "-last_received_at"]
EventSort = Literal[
    "created_at",
    "-created_at",
    "received_at",
    "-received_at",
    "occurred_at",
    "-occurred_at",
    "id",
    "-id",
]


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ReadProblem(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str


class PageMeta(BaseModel):
    limit: int
    offset: int
    total: int


class Page[T](BaseModel):
    items: list[T]
    meta: PageMeta


class MachineRead(ReadModel):
    machine_id: str
    name: str
    machine_type: str
    zone: Zone
    fog_id: FogId


class MeasurementRead(ReadModel):
    id: int
    message_id: str
    machine_id: str
    zone: Zone
    timestamp: UtcDatetime
    received_at: UtcDatetime
    temperature: float
    vibration: float
    speed: float
    current: float
    pressure: float | None
    power: float | None
    frequency: float | None
    state: Literal["RUNNING", "IDLE", "STOPPED", "FAULT"]


class PredictionRead(ReadModel):
    id: int
    message_id: str
    machine_id: str
    fog_id: FogId
    timestamp: UtcDatetime
    received_at: UtcDatetime
    risk_score: float = Field(ge=0, le=1)
    anomaly: bool
    predicted_fault: str
    severity: Severity
    model_version: str


class AlertRead(ReadModel):
    id: int
    message_id: str
    alert_id: str
    machine_id: str
    fog_id: FogId
    timestamp: UtcDatetime
    received_at: UtcDatetime
    type: str
    severity: Severity
    message: str
    recommended_action: str | None
    status: AlertStatus
    acknowledged_at: UtcDatetime | None
    acknowledged_by: str | None
    resolved_at: UtcDatetime | None


class FogNodeRead(ReadModel):
    fog_id: FogId
    zone: Zone
    status: NodeStatus
    cpu_percent: float | None
    ram_percent: float | None
    queued_tasks: int | None
    active_tasks: int | None
    last_heartbeat: UtcDatetime | None
    last_received_at: UtcDatetime | None
    offline_since: UtcDatetime | None
    recovered_at: UtcDatetime | None
    heartbeat_age_seconds: float | None = None
    heartbeat_stale: bool | None = None
    heartbeat_received_age_seconds: float | None = None
    supervision_status: SupervisionStatus = "UNKNOWN"
    supervision_reason: SupervisionReason = "NO_HEARTBEAT"
    supervision_since: UtcDatetime | None = None
    supervision_checked_at: UtcDatetime | None = None
    supervision_stale: bool = True
    effective_supervision_status: SupervisionStatus = "UNKNOWN"


class FogNodePage(Page[FogNodeRead]):
    as_of: UtcDatetime
    heartbeat_timeout_seconds: int
    supervision_gap_seconds: int = 30


class FogHistoryRead(ReadModel):
    id: int
    message_id: str
    fog_id: FogId
    zone: Zone
    observed_at: UtcDatetime
    received_at: UtcDatetime
    status: NodeStatus
    cpu_percent: float
    ram_percent: float
    queued_tasks: int
    active_tasks: int
    record_type: Literal["HEARTBEAT"] = "HEARTBEAT"


class FogSupervisionRead(ReadModel):
    id: int
    message_id: str
    fog_id: FogId
    zone: Zone
    record_type: Literal["SUPERVISION"]
    observed_at: UtcDatetime
    received_at: UtcDatetime
    supervision_status: SupervisionStatus
    previous_supervision_status: SupervisionStatus
    supervision_reason: SupervisionReason
    evidence_heartbeat_at: UtcDatetime | None
    evidence_received_at: UtcDatetime | None
    timeout_seconds: int
    gap_start: UtcDatetime | None
    gap_end: UtcDatetime | None


class TaskRead(ReadModel):
    task_id: UUID4
    task_type: TaskType
    priority: Priority
    critical: bool
    origin_fog_id: FogId | None
    current_fog_id: FogId | None
    machine_id: str | None
    status: TaskStatus
    created_at: UtcDatetime
    started_at: UtcDatetime | None
    completed_at: UtcDatetime | None
    last_event_at: UtcDatetime | None
    last_received_at: UtcDatetime


class TaskEventRead(ReadModel):
    id: int
    message_id: str
    task_id: UUID4
    task_type: TaskType
    priority: Priority
    critical: bool
    source_fog: FogId
    destination_fog: FogId | None
    status: TaskStatus
    created_at: UtcDatetime
    occurred_at: UtcDatetime | None
    received_at: UtcDatetime
    completed_at: UtcDatetime | None
    reason: str | None
