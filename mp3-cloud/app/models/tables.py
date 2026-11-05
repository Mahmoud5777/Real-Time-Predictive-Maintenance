"""Etape 2 : catalogues, etats observes et historiques du Cloud.

Les tables sont d'abord non partitionnees. Les contraintes uniques sur message_id
protegent chaque type de message contre les nouvelles livraisons MQTT QoS 1.
Le Cloud observe les taches ; leur execution et leur ordonnancement restent chez MP2.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


def _message_constraints(prefix: str) -> tuple[UniqueConstraint, CheckConstraint]:
    return (
        UniqueConstraint("message_id", name=f"uq_{prefix}_message_id"),
        CheckConstraint(
            "length(message_id) BETWEEN 8 AND 64", name=f"ck_{prefix}_message_id_length"
        ),
    )


def _load_constraints(prefix: str) -> tuple[CheckConstraint, ...]:
    # NULL passe le CHECK : dans le catalogue, une charge non observee reste inconnue.
    return (
        CheckConstraint("cpu_percent BETWEEN 0 AND 100", name=f"ck_{prefix}_cpu"),
        CheckConstraint("ram_percent BETWEEN 0 AND 100", name=f"ck_{prefix}_ram"),
        CheckConstraint("queued_tasks >= 0", name=f"ck_{prefix}_queued_tasks"),
        CheckConstraint("active_tasks >= 0", name=f"ck_{prefix}_active_tasks"),
        CheckConstraint(
            "status IN ('ONLINE', 'OVERLOADED', 'OFFLINE', 'RECOVERING')",
            name=f"ck_{prefix}_status",
        ),
    )


def _task_constraints(prefix: str) -> tuple[CheckConstraint, ...]:
    return (
        CheckConstraint(
            "task_type IN ('ANOMALY_DETECTION', 'FEATURE_EXTRACTION', 'AGGREGATION', "
            "'REPORTING', 'MODEL_RETRAIN')",
            name=f"ck_{prefix}_type",
        ),
        CheckConstraint(
            "priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')", name=f"ck_{prefix}_priority"
        ),
        CheckConstraint(
            "status IN ('CREATED', 'QUEUED', 'RUNNING', 'MIGRATED', 'COMPLETED', "
            "'FAILED', 'RECOVERED')",
            name=f"ck_{prefix}_status",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name=f"ck_{prefix}_completion_time",
        ),
    )


class FogNode(Base):
    """Catalogue des trois Fog et dernier etat observe, sans charge fictive."""

    __tablename__ = "fog_nodes"
    __table_args__ = (
        UniqueConstraint("fog_id", "zone", name="uq_fog_zone"),
        CheckConstraint("zone IN ('A', 'B', 'C')", name="ck_fog_zone"),
        CheckConstraint("fog_id = 'FOG_' || zone", name="ck_fog_id_zone"),
        *_load_constraints("fog"),
    )

    fog_id: Mapped[str] = mapped_column(String(5), primary_key=True)
    zone: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(12), server_default="OFFLINE")
    cpu_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    ram_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    queued_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_tasks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    environment_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    endpoint: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (
        UniqueConstraint("machine_id", "zone", name="uq_machine_zone"),
        ForeignKeyConstraint(
            ["fog_id", "zone"], ["fog_nodes.fog_id", "fog_nodes.zone"], name="fk_machine_fog_zone"
        ),
        CheckConstraint(
            "machine_id IN ('M01', 'M02', 'M03', 'M04', 'M05', 'M06', 'M07', 'M08', "
            "'M09', 'M10', 'M11', 'M12')",
            name="ck_machine_id",
        ),
        CheckConstraint("length(name) > 0", name="ck_machine_name"),
        CheckConstraint("length(machine_type) > 0", name="ck_machine_type"),
    )

    machine_id: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    machine_type: Mapped[str] = mapped_column(String(32), server_default="UNSPECIFIED")
    zone: Mapped[str] = mapped_column(String(1), index=True)
    fog_id: Mapped[str] = mapped_column(String(5), index=True)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SensorData(Base):
    """Historique des mesures, avec une zone conforme au catalogue de la machine."""

    __tablename__ = "sensor_data"
    __table_args__ = (
        *_message_constraints("sensor"),
        ForeignKeyConstraint(
            ["machine_id", "zone"],
            ["machines.machine_id", "machines.zone"],
            name="fk_sensor_machine_zone",
        ),
        CheckConstraint("temperature BETWEEN -50 AND 300", name="ck_sensor_temperature"),
        CheckConstraint("vibration BETWEEN 0 AND 100", name="ck_sensor_vibration"),
        CheckConstraint("speed BETWEEN 0 AND 20000", name="ck_sensor_speed"),
        CheckConstraint("current BETWEEN 0 AND 1000", name="ck_sensor_current"),
        CheckConstraint("pressure BETWEEN 0 AND 100", name="ck_sensor_pressure"),
        CheckConstraint("power BETWEEN 0 AND 1000", name="ck_sensor_power"),
        CheckConstraint("frequency BETWEEN 0 AND 400", name="ck_sensor_frequency"),
        CheckConstraint("state IN ('RUNNING', 'IDLE', 'STOPPED', 'FAULT')", name="ck_sensor_state"),
        Index("ix_sensor_machine_ts", "machine_id", "timestamp"),
        Index("ix_sensor_zone_ts", "zone", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(String(3))
    zone: Mapped[str] = mapped_column(String(1))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    temperature: Mapped[float] = mapped_column(Float)
    vibration: Mapped[float] = mapped_column(Float)
    speed: Mapped[float] = mapped_column(Float)
    current: Mapped[float] = mapped_column(Float)
    pressure: Mapped[float | None] = mapped_column(Float, nullable=True)
    power: Mapped[float | None] = mapped_column(Float, nullable=True)
    frequency: Mapped[float | None] = mapped_column(Float, nullable=True)
    state: Mapped[str] = mapped_column(String(8))


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        *_message_constraints("prediction"),
        CheckConstraint("risk_score BETWEEN 0 AND 1", name="ck_prediction_risk"),
        CheckConstraint(
            "predicted_fault IN ('NONE', 'BEARING_WEAR', 'OVERHEATING', 'IMBALANCE', "
            "'ELECTRICAL_OVERLOAD', 'MISALIGNMENT')",
            name="ck_prediction_fault",
        ),
        CheckConstraint(
            "severity IN ('NORMAL', 'WARNING', 'CRITICAL')", name="ck_prediction_severity"
        ),
        CheckConstraint("length(model_version) > 0", name="ck_prediction_model_version"),
        Index("ix_pred_machine_ts", "machine_id", "timestamp"),
        Index("ix_pred_fog_ts", "fog_id", "timestamp"),
        Index("ix_pred_risk", "risk_score"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"))
    fog_id: Mapped[str] = mapped_column(ForeignKey("fog_nodes.fog_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    risk_score: Mapped[Decimal] = mapped_column(Numeric())
    anomaly: Mapped[bool] = mapped_column(Boolean)
    predicted_fault: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    model_version: Mapped[str] = mapped_column(String(64), index=True)


class Alert(Base):
    """Une alerte a un cycle de vie : OPEN -> ACKNOWLEDGED -> RESOLVED."""

    __tablename__ = "alerts"
    __table_args__ = (
        *_message_constraints("alert"),
        UniqueConstraint("alert_id", name="uq_alert_alert_id"),
        CheckConstraint("length(alert_id) > 0", name="ck_alert_id"),
        CheckConstraint("length(message) BETWEEN 1 AND 2000", name="ck_alert_message"),
        CheckConstraint(
            "type IN ('ANOMALY_DETECTED', 'THRESHOLD_EXCEEDED', 'PREDICTED_FAILURE', "
            "'SENSOR_LOST', 'NODE_UNREACHABLE')",
            name="ck_alert_type",
        ),
        CheckConstraint("severity IN ('NORMAL', 'WARNING', 'CRITICAL')", name="ck_alert_severity"),
        CheckConstraint("status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')", name="ck_alert_status"),
        CheckConstraint(
            "acknowledged_at IS NULL OR acknowledged_at >= timestamp", name="ck_alert_ack_time"
        ),
        CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= timestamp", name="ck_alert_resolution_time"
        ),
        CheckConstraint(
            "resolved_at IS NULL OR acknowledged_at IS NULL OR resolved_at >= acknowledged_at",
            name="ck_alert_lifecycle_time",
        ),
        Index("ix_alert_status_severity", "status", "severity"),
        Index("ix_alert_machine_ts", "machine_id", "timestamp"),
        Index("ix_alert_fog_ts", "fog_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64))
    alert_id: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"))
    fog_id: Mapped[str] = mapped_column(ForeignKey("fog_nodes.fog_id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    message: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), server_default="OPEN")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FogStatusHistory(Base):
    """Observations conservees meme apres la mise a jour du dernier etat d'un Fog."""

    __tablename__ = "fog_status_history"
    __table_args__ = (
        *_message_constraints("fog_history"),
        *_load_constraints("fog_history"),
        ForeignKeyConstraint(
            ["fog_id", "zone"],
            ["fog_nodes.fog_id", "fog_nodes.zone"],
            name="fk_fog_history_fog_zone",
        ),
        Index("ix_fog_history_fog_observed", "fog_id", "observed_at", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64))
    fog_id: Mapped[str] = mapped_column(String(5))
    zone: Mapped[str] = mapped_column(String(1))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(12))
    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    queued_tasks: Mapped[int] = mapped_column(Integer)
    active_tasks: Mapped[int] = mapped_column(Integer)


class Task(Base):
    """Dernier etat connu d'une tache ; l'origine peut manquer dans un journal partiel."""

    __tablename__ = "tasks"
    __table_args__ = (
        *_task_constraints("task"),
        CheckConstraint(
            "task_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
            "[0-9a-f]{12}$'",
            name="ck_task_uuid_v4",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at", name="ck_task_start_time"
        ),
        CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_task_execution_time",
        ),
        CheckConstraint(
            "last_event_at IS NULL OR last_event_at >= created_at", name="ck_task_event_time"
        ),
        Index("ix_task_current_fog_status", "current_fog_id", "status"),
        Index("ix_task_origin_created", "origin_fog_id", "created_at"),
        Index("ix_task_machine_created", "machine_id", "created_at"),
    )

    task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(8))
    critical: Mapped[bool] = mapped_column(Boolean)
    origin_fog_id: Mapped[str | None] = mapped_column(ForeignKey("fog_nodes.fog_id"), nullable=True)
    current_fog_id: Mapped[str | None] = mapped_column(
        ForeignKey("fog_nodes.fog_id"), nullable=True
    )
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.machine_id"), nullable=True)
    status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TaskEvent(Base):
    """Un task_id stable produit plusieurs evenements, chacun avec son message_id."""

    __tablename__ = "task_events"
    __table_args__ = (
        *_message_constraints("task_event"),
        *_task_constraints("task_event"),
        CheckConstraint(
            "occurred_at IS NULL OR occurred_at >= created_at", name="ck_task_event_occurrence"
        ),
        Index("ix_task_event_task_occurred", "task_id", "occurred_at", "id"),
        Index("ix_task_event_task_received", "task_id", "received_at", "id"),
        Index("ix_task_event_status_occurred", "status", "occurred_at"),
        Index("ix_task_event_source_created", "source_fog", "created_at"),
        Index("ix_task_event_destination_occurred", "destination_fog", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.task_id"))
    task_type: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(8))
    critical: Mapped[bool] = mapped_column(Boolean)
    source_fog: Mapped[str] = mapped_column(ForeignKey("fog_nodes.fog_id"))
    destination_fog: Mapped[str | None] = mapped_column(
        ForeignKey("fog_nodes.fog_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class KpiRecord(Base):
    """Resultats de calcul pour une fenetre et un perimetre, recalculables sans doublon."""

    __tablename__ = "kpi_records"
    __table_args__ = (
        UniqueConstraint("metric", "scope", "scope_value", "bucket_start", name="uq_kpi_bucket"),
        CheckConstraint("length(metric) > 0", name="ck_kpi_metric"),
        CheckConstraint("length(scope) > 0", name="ck_kpi_scope"),
        CheckConstraint("length(scope_value) > 0", name="ck_kpi_scope_value"),
        CheckConstraint("bucket_end > bucket_start", name="ck_kpi_window"),
        CheckConstraint("sample_size >= 0", name="ck_kpi_sample_size"),
        CheckConstraint(
            "value > '-Infinity'::double precision AND value < 'Infinity'::double precision",
            name="ck_kpi_finite_value",
        ),
        Index("ix_kpi_metric_bucket", "metric", "bucket_start"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String(48))
    scope: Mapped[str] = mapped_column(String(16))
    scope_value: Mapped[str] = mapped_column(String(16))
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bucket_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer, server_default="0")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
