"""Freeze bounded dialogue context at submission; old runs keep empty history."""

import sqlalchemy as sa
from alembic import op

revision = "0008_answer_history"
down_revision = "0007_answer_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "answer_runs", sa.Column("history", sa.JSON(), nullable=False, server_default="[]")
    )


def downgrade() -> None:
    op.drop_column("answer_runs", "history")
