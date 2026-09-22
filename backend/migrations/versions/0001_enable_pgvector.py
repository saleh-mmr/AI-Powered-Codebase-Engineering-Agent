"""Enable pgvector; this revision does not create application tables."""

from alembic import op

revision = "0001_enable_pgvector"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    # The extension can be shared by other schemas; intentionally retain it.
    pass
