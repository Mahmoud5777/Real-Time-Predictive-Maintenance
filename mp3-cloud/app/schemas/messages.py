from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.common import MessageBase, UtcDatetime

Zone = Literal["A", "B", "C"]
FogId = Literal["FOG_A", "FOG_B", "FOG_C"]
MACHINE_PATTERN = r"^M(0[1-9]|1[0-2])$"
UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-4[0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12}$"
)


class MachineData(MessageBase):
    """Section 1 du contrat - mesure machine produite par MP1 via MP2."""

    machine_id: str = Field(pattern=MACHINE_PATTERN)
    zone: Zone
    timestamp: UtcDatetime
    temperature: float = Field(ge=-50, le=300)
    vibration: float = Field(ge=0, le=100)
    speed: float = Field(ge=0, le=20000)
    current: float = Field(ge=0, le=1000)
    pressure: float | None = Field(default=None, ge=0, le=100)
    power: float | None = Field(default=None, ge=0, le=1000)
    frequency: float | None = Field(default=None, ge=0, le=400)
    state: Literal["RUNNING", "IDLE", "STOPPED", "FAULT"]


class PredictionResult(MessageBase):
    """Section 2 - prediction emittee par un noeud Fog."""

    machine_id: str = Field(pattern=MACHINE_PATTERN)
    fog_id: FogId
    timestamp: UtcDatetime
    risk_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    anomaly: bool
    predicted_fault: Literal[
        "NONE", "BEARING_WEAR", "OVERHEATING", "IMBALANCE", "ELECTRICAL_OVERLOAD", "MISALIGNMENT"
    ]
    severity: Literal["NORMAL", "WARNING", "CRITICAL"]
    model_version: str = Field(min_length=1, max_length=64)


class AlertMessage(MessageBase):
    """Section 3 - alerte avec cycle de vie pilote par le Cloud."""

    alert_id: str = Field(min_length=1, max_length=64)
    machine_id: str = Field(pattern=MACHINE_PATTERN)
    fog_id: FogId
    timestamp: UtcDatetime
    type: Literal[
        "ANOMALY_DETECTED",
        "THRESHOLD_EXCEEDED",
        "PREDICTED_FAILURE",
        "SENSOR_LOST",
        "NODE_UNREACHABLE",
    ]
    severity: Literal["NORMAL", "WARNING", "CRITICAL"]
    message: str = Field(min_length=1, max_length=2000)
    recommended_action: str | None = None


class FogStatus(MessageBase):
    """Section 4 - heartbeat d un noeud Fog."""

    fog_id: FogId
    zone: Zone
    status: Literal["ONLINE", "OVERLOADED", "OFFLINE", "RECOVERING"]
    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)
    queued_tasks: int = Field(ge=0)
    active_tasks: int = Field(ge=0)
    last_heartbeat: UtcDatetime


class TaskEvent(MessageBase):
    """Section 5 - evenement de tache (creation, migration, achevement, reprise)."""

    task_id: str = Field(pattern=UUID_PATTERN)
    task_type: Literal[
        "ANOMALY_DETECTION",
        "FEATURE_EXTRACTION",
        "AGGREGATION",
        "REPORTING",
        "MODEL_RETRAIN",
    ]
    priority: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    critical: bool
    source_fog: FogId
    destination_fog: FogId | None = None
    status: Literal["CREATED", "QUEUED", "RUNNING", "MIGRATED", "COMPLETED", "FAILED", "RECOVERED"]
    created_at: UtcDatetime
    completed_at: UtcDatetime | None = None
    reason: str | None = None



