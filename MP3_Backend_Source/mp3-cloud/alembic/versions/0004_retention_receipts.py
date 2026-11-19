"""Keep idempotency identities independently of raw sensor and prediction retention."""

import sqlalchemy as sa

from alembic import op

revision = "0004_retention_receipts"
down_revision = "0003_fog_supervision"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ingest_receipts",
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("message_id", sa.String(64), primary_key=True),
        sa.Column("payload_sha256", sa.LargeBinary(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("kind IN ('sensor','prediction')", name="ck_receipt_kind"),
        sa.CheckConstraint("length(message_id) BETWEEN 8 AND 64", name="ck_receipt_message_id"),
        sa.CheckConstraint("octet_length(payload_sha256)=32", name="ck_receipt_digest"),
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM ingest_receipts r WHERE "
            "(r.kind='sensor' AND NOT EXISTS(SELECT 1 FROM sensor_data s "
            "WHERE s.message_id=r.message_id)) "
            "OR (r.kind='prediction' AND NOT EXISTS(SELECT 1 FROM predictions p "
            "WHERE p.message_id=r.message_id))"
        )
    ):
        raise RuntimeError("Downgrade refused: receipts still protect purged observations")
    op.drop_table("ingest_receipts")
