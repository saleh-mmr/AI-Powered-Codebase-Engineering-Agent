"""Owned conversations and atomic question/answer transcript pairs."""

import sqlalchemy as sa
from alembic import op

revision = "0006_conversations"
down_revision = "0005_hybrid_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_repository_id_owner", "repositories", ["id", "user_id"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["repository_id", "user_id"],
            ["repositories.id", "repositories.user_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "message_count >= 0 AND message_count <= 200", name="ck_conversation_message_count"
        ),
    )
    op.create_index(
        "ix_conversations_repository_updated", "conversations", ["repository_id", "updated_at"]
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("turn_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer()),
        sa.Column("answer", sa.JSON(none_as_null=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("conversation_id", "position", name="uq_message_position"),
        sa.UniqueConstraint("turn_id", "role", name="uq_message_turn_role"),
        sa.CheckConstraint("role IN ('user', 'assistant', 'tool')", name="ck_message_role"),
        sa.CheckConstraint("position > 0", name="ck_message_position"),
        sa.CheckConstraint("token_count IS NULL OR token_count >= 0", name="ck_message_tokens"),
        sa.CheckConstraint(
            "(role = 'assistant' AND answer IS NOT NULL) OR "
            "(role != 'assistant' AND answer IS NULL)",
            name="ck_message_answer",
        ),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_constraint("uq_repository_id_owner", "repositories", type_="unique")
