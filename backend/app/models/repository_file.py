from uuid import UUID, uuid4

from sqlalchemy import ForeignKeyConstraint, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RepositoryFile(Base):
    __tablename__ = "repository_files"
    __table_args__ = (
        ForeignKeyConstraint(
            ["import_job_id", "repository_id"],
            ["import_jobs.id", "import_jobs.repository_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("import_job_id", "path", name="uq_import_file_path"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    repository_id: Mapped[UUID]
    import_job_id: Mapped[UUID]
    path: Mapped[str] = mapped_column(String(512))
    language: Mapped[str] = mapped_column(String(30))
    size: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
