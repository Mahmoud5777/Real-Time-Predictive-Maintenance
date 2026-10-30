"""T3 - Modeles des 7 tables du Cloud.

Choix de conception assumes :
- `sensor_data` partitionnee par jour + retention configurable (~1 M lignes/jour).
- `message_id` unique la ou un message peut etre re-emit (MQTT QoS 1) => dedup atomique en base.
- FK vers `machines` : une mesure d une machine inconnue est rejetee, pas stockee.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Machine(Base):
    __tablename__ = "machines"

    machine_id: Mapped[str] = mapped_column(String(4), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    machine_type: Mapped[str] = mapped_column(String(32))
    zone: Mapped[str] = mapped_column(String(1), index=True)
    fog_id: Mapped[str] = mapped_column(String(6), index=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SensorData(Base):
    """Mesures brutes. Table partitionnee par `timestamp` dans la migration SQL."""

    __tablename__ = "sensor_data"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_sensor_message_id"),
        Index("ix_sensor_machine_ts", "machine_id", "timestamp"),
        Index("ix_sensor_zone_ts", "zone", "timestamp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32))
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"))
    zone: Mapped[str] = mapped_column(String(1))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
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
        UniqueConstraint("message_id", name="uq_prediction_message_id"),
        Index("ix_pred_machine_ts", "machine_id", "timestamp"),
        Index("ix_pred_risk", "risk_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32))
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"))
    fog_id: Mapped[str] = mapped_column(String(6), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    risk_score: Mapped[float] = mapped_column(Numeric(4, 3))
    anomaly: Mapped[bool] = mapped_column(Boolean)
    predicted_fault: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    model_version: Mapped[str] = mapped_column(String(64), index=True)


class Alert(Base):
    """Une alerte a un cycle de vie : open -> acknowledged -> resolved."""

    __tablename__ = "alerts"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_alert_message_id"),
        UniqueConstraint("alert_id", name="uq_alert_alert_id"),
        Index("ix_alert_status_severity", "status", "severity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32))
    alert_id: Mapped[str] = mapped_column(String(64))
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.machine_id"))
    fog_id: Mapped[str] = mapped_column(String(6))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    type: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(8))
    message: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="OPEN")
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FogNode(Base):
    __tablename__ = "fog_nodes"

    fog_id: Mapped[str] = mapped_column(String(6), primary_key=True)
    zone: Mapped[str] = mapped_column(String(1))
    status: Mapped[str] = mapped_column(String(12), default="OFFLINE")
    cpu_percent: Mapped[float] = mapped_column(Float, default=0)
    ram_percent: Mapped[float] = mapped_column(Float, default=0)
    queued_tasks: Mapped[int] = mapped_column(Integer, default=0)
    active_tasks: Mapped[int] = mapped_column(Integer, default=0)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskEvent(Base):
    """Historique complet des taches : un task_id emet plusieurs evenements."""

    __tablename__ = "task_events"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_task_event_message_id"),
        Index("ix_task_status", "status"),
        Index("ix_task_source_created", "source_fog", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32))
    task_id: Mapped[str] = mapped_column(String(36), index=True)
    task_type: Mapped[str] = mapped_column(String(32))
    priority: Mapped[str] = mapped_column(String(8))
    critical: Mapped[bool] = mapped_column(Boolean)
    source_fog: Mapped[str] = mapped_column(String(6))
    destination_fog: Mapped[str | None] = mapped_column(String(6), nullable=True)
    status: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class KpiRecord(Base):
    """KPI pre-calculés par job periodique : le dashboard lit en O(1)."""

    __tablename__ = "kpi_records"
    __table_args__ = (
        UniqueConstraint("metric", "scope", "scope_value", "bucket_start", name="uq_kpi_bucket"),
        Index("ix_kpi_metric_bucket", "metric", "bucket_start"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric: Mapped[str] = mapped_column(String(48))
    scope: Mapped[str] = mapped_column(String(16))
    scope_value: Mapped[str] = mapped_column(String(16))
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bucket_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float] = mapped_column(Float)
    sample_size: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

