"""Owned public repositories, durable import jobs, and immutable imported files."""

import sqlalchemy as sa
from alembic import op

revision = "0003_repository_imports"
down_revision = "0002_users_and_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_key", sa.String(200), nullable=False),
        sa.Column("owner", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("github_repository_id", sa.BigInteger()),
        sa.Column("default_branch", sa.String(255)),
        sa.Column("last_commit_sha", sa.String(40)),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("user_id", "source_key", name="uq_repository_user_source"),
    )
    op.create_index("ix_repositories_user_id", "repositories", ["user_id"])
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "repository_id",
            sa.Uuid(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("id", "repository_id", name="uq_import_job_repository"),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','failed','cancelled')",
            name="ck_import_job_status",
        ),
    )
    op.create_index(
        "uq_current_repository_job",
        "import_jobs",
        ["repository_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
        sqlite_where=sa.text("is_current = 1"),
    )
    op.create_index("ix_import_jobs_dispatch", "import_jobs", ["status", "available_at"])
    op.create_table(
        "repository_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("import_job_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("language", sa.String(30), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_job_id", "repository_id"],
            ["import_jobs.id", "import_jobs.repository_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("import_job_id", "path", name="uq_import_file_path"),
    )


def downgrade() -> None:
    op.drop_table("repository_files")
    op.drop_table("import_jobs")
    op.drop_table("repositories")
