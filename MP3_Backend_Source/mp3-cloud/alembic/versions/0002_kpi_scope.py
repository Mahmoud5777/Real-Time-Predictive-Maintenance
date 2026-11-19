"""Allow full producer model versions in KPI scopes; preserve all existing records."""

import sqlalchemy as sa

from alembic import op

revision = "0002_kpi_scope"
down_revision = "0001_mp3_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("kpi_records", "scope_value", type_=sa.String(64))
    op.create_index("ix_task_event_received", "task_events", ["received_at"])
    op.create_index(
        "ix_alert_resolved",
        "alerts",
        ["resolved_at"],
        postgresql_where=sa.text("status='RESOLVED' AND severity='CRITICAL'"),
    )


def downgrade() -> None:
    # PostgreSQL rejects overlong values; no explicit cast that could truncate them.
    op.alter_column("kpi_records", "scope_value", type_=sa.String(16))
    op.drop_index("ix_task_event_received", table_name="task_events")
    op.drop_index("ix_alert_resolved", table_name="alerts")
