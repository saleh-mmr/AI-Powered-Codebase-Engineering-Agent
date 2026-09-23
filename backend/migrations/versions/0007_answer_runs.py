"""Durable answer submissions, single active run and explicit uncertain usage."""

import sqlalchemy as sa
from alembic import op

revision = "0007_answer_runs"
down_revision = "0006_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("source_index_id", sa.Uuid(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("usage_state", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Float()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.String(300)),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_dispatched_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("conversation_id", "request_key", name="uq_answer_run_request"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_answer_run_status",
        ),
        sa.CheckConstraint("mode IN ('keyword','hybrid')", name="ck_answer_run_mode"),
        sa.CheckConstraint(
            "usage_state IN ('not_started','unknown','recorded')", name="ck_answer_run_usage"
        ),
        sa.CheckConstraint("input_tokens IS NULL OR input_tokens >= 0", name="ck_answer_run_input"),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0", name="ck_answer_run_output"
        ),
        sa.CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0", name="ck_answer_run_cost"
        ),
    )
    op.create_index(
        "uq_answer_run_active",
        "answer_runs",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','running')"),
        sqlite_where=sa.text("status IN ('queued','running')"),
    )
    op.create_index("ix_answer_runs_dispatch", "answer_runs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_table("answer_runs")
