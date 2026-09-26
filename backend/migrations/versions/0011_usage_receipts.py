"""Independent call receipts; legacy run usage remains unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "0011_usage_receipts"
down_revision = "0010_answer_preview"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "answer_runs",
        sa.Column("receipt_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "usage_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id", sa.Uuid(), sa.ForeignKey("answer_runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("input_rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("output_rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Numeric(24, 12)),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("run_id", "kind", name="uq_receipt_run_kind"),
        sa.CheckConstraint("kind IN ('generation','query_embedding')", name="ck_receipt_kind"),
        sa.CheckConstraint("input_rate >= 0 AND output_rate >= 0", name="ck_receipt_rates"),
        sa.CheckConstraint(
            "(input_tokens IS NULL AND output_tokens IS NULL AND estimated_cost_usd IS NULL) "
            "OR (input_tokens >= 0 AND output_tokens >= 0 AND estimated_cost_usd >= 0 "
            "AND input_tokens IS NOT NULL AND output_tokens IS NOT NULL "
            "AND estimated_cost_usd IS NOT NULL)",
            name="ck_receipt_usage",
        ),
    )


def downgrade() -> None:
    op.drop_table("usage_receipts")
    op.drop_column("answer_runs", "receipt_version")
