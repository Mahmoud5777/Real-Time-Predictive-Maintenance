"""Separate persistent Cloud supervision from reported Fog status in existing tables."""

import sqlalchemy as sa

from alembic import op

revision = "0003_fog_supervision"
down_revision = "0002_kpi_scope"
branch_labels = None
depends_on = None

NODE_COLUMNS = {
    "supervision_status": sa.String(16),
    "supervision_reason": sa.String(32),
    "supervision_since": sa.DateTime(timezone=True),
    "supervision_checked_at": sa.DateTime(timezone=True),
}
HISTORY_COLUMNS = {
    "record_type": sa.String(16),
    "supervision_status": sa.String(16),
    "previous_supervision_status": sa.String(16),
    "supervision_reason": sa.String(32),
    "evidence_heartbeat_at": sa.DateTime(timezone=True),
    "evidence_received_at": sa.DateTime(timezone=True),
    "timeout_seconds": sa.Integer(),
    "gap_start": sa.DateTime(timezone=True),
    "gap_end": sa.DateTime(timezone=True),
}
LOAD_COLUMNS = ["status", "cpu_percent", "ram_percent", "queued_tasks", "active_tasks"]
STATES = "'UNKNOWN', 'REACHABLE', 'UNREACHABLE'"
REASONS = (
    "'NO_HEARTBEAT', 'FRESH_HEARTBEAT', 'HEARTBEAT_TIMEOUT', 'REPORTED_OFFLINE', "
    "'CLOCK_SKEW', 'MONITOR_GAP'"
)
RECORD_CHECK = (
    "(record_type='HEARTBEAT' AND status IS NOT NULL AND cpu_percent IS NOT NULL "
    "AND ram_percent IS NOT NULL AND queued_tasks IS NOT NULL AND active_tasks IS NOT NULL "
    "AND supervision_status IS NULL AND supervision_reason IS NULL "
    "AND previous_supervision_status IS NULL AND evidence_heartbeat_at IS NULL "
    "AND evidence_received_at IS NULL AND timeout_seconds IS NULL "
    "AND gap_start IS NULL AND gap_end IS NULL) OR "
    "(record_type='SUPERVISION' AND status IS NULL AND cpu_percent IS NULL "
    "AND ram_percent IS NULL AND queued_tasks IS NULL AND active_tasks IS NULL "
    "AND supervision_status IS NOT NULL AND supervision_reason IS NOT NULL "
    "AND previous_supervision_status IS NOT NULL AND timeout_seconds > 0 "
    "AND timeout_seconds IS NOT NULL AND "
    "((supervision_reason='MONITOR_GAP' AND gap_start IS NOT NULL "
    "AND gap_end IS NOT NULL AND gap_end > gap_start AND gap_end=observed_at) OR "
    "(supervision_reason<>'MONITOR_GAP' AND gap_start IS NULL AND gap_end IS NULL)))"
)


def upgrade():
    for name, column_type in NODE_COLUMNS.items():
        default = {"supervision_status": "UNKNOWN", "supervision_reason": "NO_HEARTBEAT"}.get(name)
        op.add_column(
            "fog_nodes",
            sa.Column(name, column_type, nullable=default is None, server_default=default),
        )
    for name, column_type in HISTORY_COLUMNS.items():
        op.add_column(
            "fog_status_history",
            sa.Column(
                name,
                column_type,
                nullable=name != "record_type",
                server_default="HEARTBEAT" if name == "record_type" else None,
            ),
        )
    for name in LOAD_COLUMNS:
        op.alter_column("fog_status_history", name, nullable=True)
    for prefix, table in [("fog", "fog_nodes"), ("fog_history", "fog_status_history")]:
        op.create_check_constraint(
            f"ck_{prefix}_supervision_status", table, f"supervision_status IN ({STATES})"
        )
        op.create_check_constraint(
            f"ck_{prefix}_supervision_reason", table, f"supervision_reason IN ({REASONS})"
        )
        op.create_check_constraint(
            f"ck_{prefix}_supervision_consistency",
            table,
            "(supervision_status='UNKNOWN' AND supervision_reason IN "
            "('NO_HEARTBEAT','CLOCK_SKEW','MONITOR_GAP')) OR "
            "(supervision_status='REACHABLE' AND supervision_reason='FRESH_HEARTBEAT') OR "
            "(supervision_status='UNREACHABLE' AND supervision_reason IN "
            "('HEARTBEAT_TIMEOUT','REPORTED_OFFLINE'))",
        )
    op.create_check_constraint("ck_fog_history_record_type", "fog_status_history", RECORD_CHECK)
    op.create_check_constraint(
        "ck_fog_history_previous_supervision",
        "fog_status_history",
        f"previous_supervision_status IN ({STATES})",
    )
    op.create_index(
        "ix_fog_supervision_observed",
        "fog_status_history",
        ["observed_at", "id"],
        postgresql_where=sa.text("record_type='SUPERVISION'"),
    )


def downgrade():
    # The old schema cannot represent Cloud events; refuse to silently delete their evidence.
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM fog_status_history WHERE record_type='SUPERVISION'")
    ):
        raise RuntimeError("Downgrade refused: preserve/export Cloud supervision history first")
    op.drop_index("ix_fog_supervision_observed", table_name="fog_status_history")
    for prefix, table in [("fog", "fog_nodes"), ("fog_history", "fog_status_history")]:
        for suffix in ["status", "reason", "consistency"]:
            op.drop_constraint(f"ck_{prefix}_supervision_{suffix}", table, type_="check")
    for name in ["ck_fog_history_record_type", "ck_fog_history_previous_supervision"]:
        op.drop_constraint(name, "fog_status_history", type_="check")
    for name in LOAD_COLUMNS:
        op.alter_column("fog_status_history", name, nullable=False)
    for name in reversed(HISTORY_COLUMNS):
        op.drop_column("fog_status_history", name)
    for name in reversed(NODE_COLUMNS):
        op.drop_column("fog_nodes", name)
