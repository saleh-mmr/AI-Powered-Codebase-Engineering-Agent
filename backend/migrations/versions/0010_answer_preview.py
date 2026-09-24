"""Bounded provisional snapshot; lifecycle event IDs stay unchanged."""

import sqlalchemy as sa
from alembic import op

revision = "0010_answer_preview"
down_revision = "0009_run_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "answer_runs", sa.Column("preview_text", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "answer_runs",
        sa.Column("preview_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_run_preview_length", "answer_runs", "length(preview_text) <= 8000"
    )
    op.create_check_constraint(
        "ck_run_preview_revision",
        "answer_runs",
        "preview_revision >= 0 AND preview_revision <= 256",
    )


def downgrade() -> None:
    op.drop_constraint("ck_run_preview_revision", "answer_runs", type_="check")
    op.drop_constraint("ck_run_preview_length", "answer_runs", type_="check")
    op.drop_column("answer_runs", "preview_revision")
    op.drop_column("answer_runs", "preview_text")
