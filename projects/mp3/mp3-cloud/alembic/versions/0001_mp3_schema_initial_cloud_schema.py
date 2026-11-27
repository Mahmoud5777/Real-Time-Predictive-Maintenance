"""initial cloud schema

Revision ID: 0001_mp3_schema
Revises:
Create Date: 2026-11-02 00:49:26.295884
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_mp3_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Catalogues avant leurs references ; historiques sans partitionnement initial.
    op.create_table(
        "fog_nodes",
        sa.Column("fog_id", sa.String(length=5), nullable=False),
        sa.Column("zone", sa.String(length=1), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="OFFLINE", nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=True),
        sa.Column("ram_percent", sa.Float(), nullable=True),
        sa.Column("queued_tasks", sa.Integer(), nullable=True),
        sa.Column("active_tasks", sa.Integer(), nullable=True),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("offline_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("environment_ref", sa.String(length=128), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("fog_id = 'FOG_' || zone", name="ck_fog_id_zone"),
        sa.CheckConstraint(
            "status IN ('ONLINE', 'OVERLOADED', 'OFFLINE', 'RECOVERING')", name="ck_fog_status"
        ),
        sa.CheckConstraint("zone IN ('A', 'B', 'C')", name="ck_fog_zone"),
        sa.CheckConstraint("active_tasks >= 0", name="ck_fog_active_tasks"),
        sa.CheckConstraint("cpu_percent BETWEEN 0 AND 100", name="ck_fog_cpu"),
        sa.CheckConstraint("queued_tasks >= 0", name="ck_fog_queued_tasks"),
        sa.CheckConstraint("ram_percent BETWEEN 0 AND 100", name="ck_fog_ram"),
        sa.PrimaryKeyConstraint("fog_id"),
        sa.UniqueConstraint("fog_id", "zone", name="uq_fog_zone"),
    )
    op.create_table(
        "kpi_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("scope_value", sa.String(length=16), nullable=False),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bucket_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("sample_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "value > '-Infinity'::double precision AND value < 'Infinity'::double precision",
            name="ck_kpi_finite_value",
        ),
        sa.CheckConstraint("bucket_end > bucket_start", name="ck_kpi_window"),
        sa.CheckConstraint("length(metric) > 0", name="ck_kpi_metric"),
        sa.CheckConstraint("length(scope) > 0", name="ck_kpi_scope"),
        sa.CheckConstraint("length(scope_value) > 0", name="ck_kpi_scope_value"),
        sa.CheckConstraint("sample_size >= 0", name="ck_kpi_sample_size"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric", "scope", "scope_value", "bucket_start", name="uq_kpi_bucket"),
    )
    op.create_index("ix_kpi_metric_bucket", "kpi_records", ["metric", "bucket_start"], unique=False)
    op.create_table(
        "fog_status_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("fog_id", sa.String(length=5), nullable=False),
        sa.Column("zone", sa.String(length=1), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("ram_percent", sa.Float(), nullable=False),
        sa.Column("queued_tasks", sa.Integer(), nullable=False),
        sa.Column("active_tasks", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "status IN ('ONLINE', 'OVERLOADED', 'OFFLINE', 'RECOVERING')",
            name="ck_fog_history_status",
        ),
        sa.CheckConstraint("active_tasks >= 0", name="ck_fog_history_active_tasks"),
        sa.CheckConstraint("cpu_percent BETWEEN 0 AND 100", name="ck_fog_history_cpu"),
        sa.CheckConstraint(
            "length(message_id) BETWEEN 8 AND 64", name="ck_fog_history_message_id_length"
        ),
        sa.CheckConstraint("queued_tasks >= 0", name="ck_fog_history_queued_tasks"),
        sa.CheckConstraint("ram_percent BETWEEN 0 AND 100", name="ck_fog_history_ram"),
        sa.ForeignKeyConstraint(
            ["fog_id", "zone"],
            ["fog_nodes.fog_id", "fog_nodes.zone"],
            name="fk_fog_history_fog_zone",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_fog_history_message_id"),
    )
    op.create_index(
        "ix_fog_history_fog_observed",
        "fog_status_history",
        ["fog_id", "observed_at", "id"],
        unique=False,
    )
    op.create_table(
        "machines",
        sa.Column("machine_id", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "machine_type", sa.String(length=32), server_default="UNSPECIFIED", nullable=False
        ),
        sa.Column("zone", sa.String(length=1), nullable=False),
        sa.Column("fog_id", sa.String(length=5), nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "machine_id IN ('M01', 'M02', 'M03', 'M04', 'M05', 'M06', 'M07', 'M08', "
            "'M09', 'M10', 'M11', 'M12')",
            name="ck_machine_id",
        ),
        sa.CheckConstraint("length(machine_type) > 0", name="ck_machine_type"),
        sa.CheckConstraint("length(name) > 0", name="ck_machine_name"),
        sa.ForeignKeyConstraint(
            ["fog_id", "zone"], ["fog_nodes.fog_id", "fog_nodes.zone"], name="fk_machine_fog_zone"
        ),
        sa.PrimaryKeyConstraint("machine_id"),
        sa.UniqueConstraint("machine_id", "zone", name="uq_machine_zone"),
    )
    op.create_index(op.f("ix_machines_fog_id"), "machines", ["fog_id"], unique=False)
    op.create_index(op.f("ix_machines_zone"), "machines", ["zone"], unique=False)
    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("alert_id", sa.String(length=64), nullable=False),
        sa.Column("machine_id", sa.String(length=3), nullable=False),
        sa.Column("fog_id", sa.String(length=5), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="OPEN", nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=64), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "severity IN ('NORMAL', 'WARNING', 'CRITICAL')", name="ck_alert_severity"
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED')", name="ck_alert_status"
        ),
        sa.CheckConstraint(
            "type IN ('ANOMALY_DETECTED', 'THRESHOLD_EXCEEDED', 'PREDICTED_FAILURE', "
            "'SENSOR_LOST', 'NODE_UNREACHABLE')",
            name="ck_alert_type",
        ),
        sa.CheckConstraint(
            "acknowledged_at IS NULL OR acknowledged_at >= timestamp", name="ck_alert_ack_time"
        ),
        sa.CheckConstraint("length(alert_id) > 0", name="ck_alert_id"),
        sa.CheckConstraint("length(message) BETWEEN 1 AND 2000", name="ck_alert_message"),
        sa.CheckConstraint(
            "length(message_id) BETWEEN 8 AND 64", name="ck_alert_message_id_length"
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR acknowledged_at IS NULL OR resolved_at >= acknowledged_at",
            name="ck_alert_lifecycle_time",
        ),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= timestamp", name="ck_alert_resolution_time"
        ),
        sa.ForeignKeyConstraint(
            ["fog_id"],
            ["fog_nodes.fog_id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machines.machine_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("alert_id", name="uq_alert_alert_id"),
        sa.UniqueConstraint("message_id", name="uq_alert_message_id"),
    )
    op.create_index("ix_alert_fog_ts", "alerts", ["fog_id", "timestamp"], unique=False)
    op.create_index("ix_alert_machine_ts", "alerts", ["machine_id", "timestamp"], unique=False)
    op.create_index("ix_alert_status_severity", "alerts", ["status", "severity"], unique=False)
    op.create_index(op.f("ix_alerts_timestamp"), "alerts", ["timestamp"], unique=False)
    op.create_table(
        "predictions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("machine_id", sa.String(length=3), nullable=False),
        sa.Column("fog_id", sa.String(length=5), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("risk_score", sa.Numeric(), nullable=False),
        sa.Column("anomaly", sa.Boolean(), nullable=False),
        sa.Column("predicted_fault", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=8), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "predicted_fault IN ('NONE', 'BEARING_WEAR', 'OVERHEATING', 'IMBALANCE', "
            "'ELECTRICAL_OVERLOAD', 'MISALIGNMENT')",
            name="ck_prediction_fault",
        ),
        sa.CheckConstraint(
            "severity IN ('NORMAL', 'WARNING', 'CRITICAL')", name="ck_prediction_severity"
        ),
        sa.CheckConstraint(
            "length(message_id) BETWEEN 8 AND 64", name="ck_prediction_message_id_length"
        ),
        sa.CheckConstraint("length(model_version) > 0", name="ck_prediction_model_version"),
        sa.CheckConstraint("risk_score BETWEEN 0 AND 1", name="ck_prediction_risk"),
        sa.ForeignKeyConstraint(
            ["fog_id"],
            ["fog_nodes.fog_id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machines.machine_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_prediction_message_id"),
    )
    op.create_index("ix_pred_fog_ts", "predictions", ["fog_id", "timestamp"], unique=False)
    op.create_index("ix_pred_machine_ts", "predictions", ["machine_id", "timestamp"], unique=False)
    op.create_index("ix_pred_risk", "predictions", ["risk_score"], unique=False)
    op.create_index(
        op.f("ix_predictions_model_version"), "predictions", ["model_version"], unique=False
    )
    op.create_index(op.f("ix_predictions_timestamp"), "predictions", ["timestamp"], unique=False)
    op.create_table(
        "sensor_data",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("machine_id", sa.String(length=3), nullable=False),
        sa.Column("zone", sa.String(length=1), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("vibration", sa.Float(), nullable=False),
        sa.Column("speed", sa.Float(), nullable=False),
        sa.Column("current", sa.Float(), nullable=False),
        sa.Column("pressure", sa.Float(), nullable=True),
        sa.Column("power", sa.Float(), nullable=True),
        sa.Column("frequency", sa.Float(), nullable=True),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.CheckConstraint(
            "state IN ('RUNNING', 'IDLE', 'STOPPED', 'FAULT')", name="ck_sensor_state"
        ),
        sa.CheckConstraint("current BETWEEN 0 AND 1000", name="ck_sensor_current"),
        sa.CheckConstraint("frequency BETWEEN 0 AND 400", name="ck_sensor_frequency"),
        sa.CheckConstraint(
            "length(message_id) BETWEEN 8 AND 64", name="ck_sensor_message_id_length"
        ),
        sa.CheckConstraint("power BETWEEN 0 AND 1000", name="ck_sensor_power"),
        sa.CheckConstraint("pressure BETWEEN 0 AND 100", name="ck_sensor_pressure"),
        sa.CheckConstraint("speed BETWEEN 0 AND 20000", name="ck_sensor_speed"),
        sa.CheckConstraint("temperature BETWEEN -50 AND 300", name="ck_sensor_temperature"),
        sa.CheckConstraint("vibration BETWEEN 0 AND 100", name="ck_sensor_vibration"),
        sa.ForeignKeyConstraint(
            ["machine_id", "zone"],
            ["machines.machine_id", "machines.zone"],
            name="fk_sensor_machine_zone",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_sensor_message_id"),
    )
    op.create_index(op.f("ix_sensor_data_timestamp"), "sensor_data", ["timestamp"], unique=False)
    op.create_index(
        "ix_sensor_machine_ts", "sensor_data", ["machine_id", "timestamp"], unique=False
    )
    op.create_index("ix_sensor_zone_ts", "sensor_data", ["zone", "timestamp"], unique=False)
    op.create_table(
        "tasks",
        sa.Column("task_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=8), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("origin_fog_id", sa.String(length=5), nullable=True),
        sa.Column("current_fog_id", sa.String(length=5), nullable=True),
        sa.Column("machine_id", sa.String(length=3), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')", name="ck_task_priority"
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'QUEUED', 'RUNNING', 'MIGRATED', 'COMPLETED', "
            "'FAILED', 'RECOVERED')",
            name="ck_task_status",
        ),
        sa.CheckConstraint(
            "task_id::text ~ '^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
            "[0-9a-f]{12}$'",
            name="ck_task_uuid_v4",
        ),
        sa.CheckConstraint(
            "task_type IN ('ANOMALY_DETECTION', 'FEATURE_EXTRACTION', 'AGGREGATION', "
            "'REPORTING', 'MODEL_RETRAIN')",
            name="ck_task_type",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at", name="ck_task_completion_time"
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at",
            name="ck_task_execution_time",
        ),
        sa.CheckConstraint(
            "last_event_at IS NULL OR last_event_at >= created_at", name="ck_task_event_time"
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR started_at >= created_at", name="ck_task_start_time"
        ),
        sa.ForeignKeyConstraint(
            ["current_fog_id"],
            ["fog_nodes.fog_id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machines.machine_id"],
        ),
        sa.ForeignKeyConstraint(
            ["origin_fog_id"],
            ["fog_nodes.fog_id"],
        ),
        sa.PrimaryKeyConstraint("task_id"),
    )
    op.create_index(
        "ix_task_current_fog_status", "tasks", ["current_fog_id", "status"], unique=False
    )
    op.create_index("ix_task_machine_created", "tasks", ["machine_id", "created_at"], unique=False)
    op.create_index(
        "ix_task_origin_created", "tasks", ["origin_fog_id", "created_at"], unique=False
    )
    op.create_table(
        "task_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("task_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=8), nullable=False),
        sa.Column("critical", sa.Boolean(), nullable=False),
        sa.Column("source_fog", sa.String(length=5), nullable=False),
        sa.Column("destination_fog", sa.String(length=5), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')", name="ck_task_event_priority"
        ),
        sa.CheckConstraint(
            "status IN ('CREATED', 'QUEUED', 'RUNNING', 'MIGRATED', 'COMPLETED', "
            "'FAILED', 'RECOVERED')",
            name="ck_task_event_status",
        ),
        sa.CheckConstraint(
            "task_type IN ('ANOMALY_DETECTION', 'FEATURE_EXTRACTION', 'AGGREGATION', "
            "'REPORTING', 'MODEL_RETRAIN')",
            name="ck_task_event_type",
        ),
        sa.CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_task_event_completion_time",
        ),
        sa.CheckConstraint(
            "length(message_id) BETWEEN 8 AND 64", name="ck_task_event_message_id_length"
        ),
        sa.CheckConstraint(
            "occurred_at IS NULL OR occurred_at >= created_at", name="ck_task_event_occurrence"
        ),
        sa.ForeignKeyConstraint(
            ["destination_fog"],
            ["fog_nodes.fog_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_fog"],
            ["fog_nodes.fog_id"],
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.task_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", name="uq_task_event_message_id"),
    )
    op.create_index(
        "ix_task_event_destination_occurred",
        "task_events",
        ["destination_fog", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_event_source_created", "task_events", ["source_fog", "created_at"], unique=False
    )
    op.create_index(
        "ix_task_event_status_occurred", "task_events", ["status", "occurred_at"], unique=False
    )
    op.create_index(
        "ix_task_event_task_occurred", "task_events", ["task_id", "occurred_at", "id"], unique=False
    )
    op.create_index(
        "ix_task_event_task_received", "task_events", ["task_id", "received_at", "id"], unique=False
    )

    # Une origine manquante peut etre completee, mais une origine connue reste immuable.
    op.execute("""
        CREATE FUNCTION mp3_keep_task_origin() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.origin_fog_id IS NOT NULL
               AND NEW.origin_fog_id IS DISTINCT FROM OLD.origin_fog_id THEN
                RAISE EXCEPTION 'task origin cannot change once known'
                    USING ERRCODE = '23514', CONSTRAINT = 'ck_task_origin_immutable';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER tr_task_origin_immutable
        BEFORE UPDATE OF origin_fog_id ON tasks
        FOR EACH ROW EXECUTE FUNCTION mp3_keep_task_origin()
    """)


def downgrade() -> None:
    # Ordre inverse des dependances. Le rollback est verifie sur une base jetable.
    op.execute("DROP TRIGGER tr_task_origin_immutable ON tasks")
    op.execute("DROP FUNCTION mp3_keep_task_origin()")
    op.drop_index("ix_task_event_task_received", table_name="task_events")
    op.drop_index("ix_task_event_task_occurred", table_name="task_events")
    op.drop_index("ix_task_event_status_occurred", table_name="task_events")
    op.drop_index("ix_task_event_source_created", table_name="task_events")
    op.drop_index("ix_task_event_destination_occurred", table_name="task_events")
    op.drop_table("task_events")
    op.drop_index("ix_task_origin_created", table_name="tasks")
    op.drop_index("ix_task_machine_created", table_name="tasks")
    op.drop_index("ix_task_current_fog_status", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_sensor_zone_ts", table_name="sensor_data")
    op.drop_index("ix_sensor_machine_ts", table_name="sensor_data")
    op.drop_index(op.f("ix_sensor_data_timestamp"), table_name="sensor_data")
    op.drop_table("sensor_data")
    op.drop_index(op.f("ix_predictions_timestamp"), table_name="predictions")
    op.drop_index(op.f("ix_predictions_model_version"), table_name="predictions")
    op.drop_index("ix_pred_risk", table_name="predictions")
    op.drop_index("ix_pred_machine_ts", table_name="predictions")
    op.drop_index("ix_pred_fog_ts", table_name="predictions")
    op.drop_table("predictions")
    op.drop_index(op.f("ix_alerts_timestamp"), table_name="alerts")
    op.drop_index("ix_alert_status_severity", table_name="alerts")
    op.drop_index("ix_alert_machine_ts", table_name="alerts")
    op.drop_index("ix_alert_fog_ts", table_name="alerts")
    op.drop_table("alerts")
    op.drop_index(op.f("ix_machines_zone"), table_name="machines")
    op.drop_index(op.f("ix_machines_fog_id"), table_name="machines")
    op.drop_table("machines")
    op.drop_index("ix_fog_history_fog_observed", table_name="fog_status_history")
    op.drop_table("fog_status_history")
    op.drop_index("ix_kpi_metric_bucket", table_name="kpi_records")
    op.drop_table("kpi_records")
    op.drop_table("fog_nodes")
