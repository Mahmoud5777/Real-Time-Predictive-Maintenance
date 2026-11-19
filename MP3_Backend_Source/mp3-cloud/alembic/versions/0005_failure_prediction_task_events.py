"""Accept MP2 failure prediction tasks and preserve per-event timestamps."""

import sqlalchemy as sa

from alembic import op

revision = "0005_failure_prediction_events"
down_revision = "0004_retention_receipts"
branch_labels = None
depends_on = None

TASK_TYPES = (
    "'ANOMALY_DETECTION', 'FEATURE_EXTRACTION', 'AGGREGATION', "
    "'REPORTING', 'MODEL_RETRAIN', 'FAILURE_PREDICTION'"
)


def upgrade():
    for table, constraint in (
        ("tasks", "ck_task_type"),
        ("task_events", "ck_task_event_type"),
    ):
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(
            constraint,
            table,
            sa.text(f"task_type IN ({TASK_TYPES})"),
        )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM tasks WHERE task_type='FAILURE_PREDICTION') + "
            "(SELECT count(*) FROM task_events WHERE task_type='FAILURE_PREDICTION')"
        )
    ):
        raise RuntimeError(
            "Downgrade refused: failure prediction task events are already stored"
        )

    old_types = (
        "'ANOMALY_DETECTION', 'FEATURE_EXTRACTION', 'AGGREGATION', "
        "'REPORTING', 'MODEL_RETRAIN'"
    )
    for table, constraint in (
        ("task_events", "ck_task_event_type"),
        ("tasks", "ck_task_type"),
    ):
        op.drop_constraint(constraint, table, type_="check")
        op.create_check_constraint(
            constraint,
            table,
            sa.text(f"task_type IN ({old_types})"),
        )
