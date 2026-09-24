"""Durable lifecycle events; existing runs get an honest current-state baseline."""

import sqlalchemy as sa
from alembic import op

revision = "0009_run_events"
down_revision = "0008_answer_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_run_events",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("answer_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("sequence >= 1 AND sequence <= 3", name="ck_run_event_sequence"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_run_event_status",
        ),
    )
    # Prior transitions were not recorded. Do not invent a historical timeline.
    op.execute(
        sa.text("""
        INSERT INTO answer_run_events (run_id, sequence, status, occurred_at)
        SELECT id, 1, status, COALESCE(finished_at, started_at, created_at) FROM answer_runs
    """)
    )


def downgrade() -> None:
    op.drop_table("answer_run_events")
