"""Versioned search preparation, lexical GIN index and native pgvector storage."""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0005_hybrid_search"
down_revision = "0004_source_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_source_index_repository", "repository_indexes", ["id", "repository_id"]
    )
    op.create_unique_constraint("uq_chunk_index", "code_chunks", ["id", "index_id"])
    op.create_table(
        "search_indexes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("source_index_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("pipeline_version", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("provider_profile", sa.String(120), nullable=False),
        sa.Column("documents_stored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_budget", sa.Integer(), nullable=False),
        sa.Column("price_per_million", sa.Float(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.String(300)),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_dispatched_at", sa.DateTime(timezone=True)),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(
            ["source_index_id", "repository_id"],
            ["repository_indexes.id", "repository_indexes.repository_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "source_index_id", name="uq_search_index_source"),
        sa.CheckConstraint("mode IN ('keyword','hybrid')", name="ck_search_mode"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_search_index_status",
        ),
    )
    op.create_index(
        "uq_current_search_index",
        "search_indexes",
        ["repository_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current = 1"),
    )
    op.create_index("ix_search_indexes_dispatch", "search_indexes", ["status", "available_at"])
    op.create_table(
        "search_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("search_index_id", sa.Uuid(), nullable=False),
        sa.Column("source_index_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(1536)),
        sa.UniqueConstraint("search_index_id", "chunk_id", name="uq_search_document_chunk"),
        sa.ForeignKeyConstraint(
            ["search_index_id", "source_index_id"],
            ["search_indexes.id", "search_indexes.source_index_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id", "source_index_id"],
            ["code_chunks.id", "code_chunks.index_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("token_count > 0", name="ck_document_tokens"),
    )
    op.create_index("ix_search_documents_chunk", "search_documents", ["chunk_id"])
    op.create_index(
        "ix_search_documents_lexical",
        "search_documents",
        [sa.text("to_tsvector('simple', search_text)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("search_documents")
    op.drop_table("search_indexes")
    op.drop_constraint("uq_chunk_index", "code_chunks", type_="unique")
    op.drop_constraint("uq_source_index_repository", "repository_indexes", type_="unique")
