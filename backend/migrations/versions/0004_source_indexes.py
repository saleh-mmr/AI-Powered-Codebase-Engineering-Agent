"""Versioned static indexes and immutable, source-linked symbols/chunks."""

import sqlalchemy as sa
from alembic import op

revision = "0004_source_indexes"
down_revision = "0003_repository_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_repository_file_source", "repository_files", ["id", "import_job_id"]
    )
    op.create_table(
        "repository_indexes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("pipeline_version", sa.String(100), nullable=False),
        sa.Column("diagnostics", sa.JSON(), nullable=False),
        sa.Column("symbol_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(40), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_stored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("files_skipped", sa.Integer(), nullable=False, server_default="0"),
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
            ["import_job_id", "repository_id"],
            ["import_jobs.id", "import_jobs.repository_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "import_job_id", name="uq_repository_index_source"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_repository_index_status",
        ),
    )
    op.create_index(
        "uq_current_repository_index",
        "repository_indexes",
        ["repository_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current = 1"),
    )
    op.create_index(
        "ix_repository_indexes_dispatch", "repository_indexes", ["status", "available_at"]
    )
    op.create_table(
        "code_symbols",
        *source_columns(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("parent_ordinal", sa.Integer()),
        sa.Column("signature", sa.Text()),
        sa.Column("docstring", sa.Text()),
        *source_constraints("symbol"),
        sa.ForeignKeyConstraint(
            ["index_id", "file_id", "parent_ordinal"],
            ["code_symbols.index_id", "code_symbols.file_id", "code_symbols.ordinal"],
            name="fk_symbol_parent",
        ),
        sa.UniqueConstraint("index_id", "file_id", "ordinal", name="uq_symbol_ordinal"),
        sa.CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_symbol_lines"),
    )
    op.create_index("ix_symbols_file_id", "code_symbols", ["file_id"])
    op.create_index("ix_symbols_index_kind", "code_symbols", ["index_id", "kind"])
    op.create_table(
        "code_chunks",
        *source_columns(),
        sa.Column("symbol_ordinal", sa.Integer()),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        *source_constraints("chunk"),
        sa.ForeignKeyConstraint(
            ["index_id", "file_id", "symbol_ordinal"],
            ["code_symbols.index_id", "code_symbols.file_id", "code_symbols.ordinal"],
            name="fk_chunk_symbol",
        ),
        sa.UniqueConstraint("index_id", "file_id", "ordinal", name="uq_chunk_ordinal"),
        sa.CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_chunk_lines"),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset", name="ck_chunk_offsets"
        ),
    )

    op.create_index("ix_chunks_file_id", "code_chunks", ["file_id"])


def source_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("index_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
    ]


def source_constraints(prefix: str) -> list[sa.ForeignKeyConstraint]:
    return [
        sa.ForeignKeyConstraint(
            ["index_id", "import_job_id"],
            ["repository_indexes.id", "repository_indexes.import_job_id"],
            ondelete="CASCADE",
            name=f"fk_{prefix}_index_source",
        ),
        sa.ForeignKeyConstraint(
            ["file_id", "import_job_id"],
            ["repository_files.id", "repository_files.import_job_id"],
            ondelete="CASCADE",
            name=f"fk_{prefix}_file_source",
        ),
    ]


def downgrade() -> None:
    op.drop_table("code_chunks")
    op.drop_table("code_symbols")
    op.drop_table("repository_indexes")
    op.drop_constraint("uq_repository_file_source", "repository_files", type_="unique")
