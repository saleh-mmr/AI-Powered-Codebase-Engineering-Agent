from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def source_constraints(prefix: str) -> tuple[ForeignKeyConstraint, ForeignKeyConstraint]:
    return (
        ForeignKeyConstraint(
            ["index_id", "import_job_id"],
            ["repository_indexes.id", "repository_indexes.import_job_id"],
            ondelete="CASCADE",
            name=f"fk_{prefix}_index_source",
        ),
        ForeignKeyConstraint(
            ["file_id", "import_job_id"],
            ["repository_files.id", "repository_files.import_job_id"],
            ondelete="CASCADE",
            name=f"fk_{prefix}_file_source",
        ),
    )


class CodeSymbol(Base):
    __tablename__ = "code_symbols"
    __table_args__ = (
        *source_constraints("symbol"),
        ForeignKeyConstraint(
            ["index_id", "file_id", "parent_ordinal"],
            ["code_symbols.index_id", "code_symbols.file_id", "code_symbols.ordinal"],
            name="fk_symbol_parent",
        ),
        Index("ix_symbols_file_id", "file_id"),
        UniqueConstraint("index_id", "file_id", "ordinal", name="uq_symbol_ordinal"),
        CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_symbol_lines"),
        Index("ix_symbols_index_kind", "index_id", "kind"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    index_id: Mapped[UUID]
    import_job_id: Mapped[UUID]
    file_id: Mapped[UUID]
    ordinal: Mapped[int]
    name: Mapped[str] = mapped_column(Text)
    qualified_name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(20))
    signature: Mapped[str | None] = mapped_column(Text)
    docstring: Mapped[str | None] = mapped_column(Text)
    parent_ordinal: Mapped[int | None]
    start_line: Mapped[int]
    end_line: Mapped[int]


class CodeChunk(Base):
    __tablename__ = "code_chunks"
    __table_args__ = (
        *source_constraints("chunk"),
        UniqueConstraint("id", "index_id", name="uq_chunk_index"),
        ForeignKeyConstraint(
            ["index_id", "file_id", "symbol_ordinal"],
            ["code_symbols.index_id", "code_symbols.file_id", "code_symbols.ordinal"],
            name="fk_chunk_symbol",
        ),
        Index("ix_chunks_file_id", "file_id"),
        UniqueConstraint("index_id", "file_id", "ordinal", name="uq_chunk_ordinal"),
        CheckConstraint("start_line >= 1 AND end_line >= start_line", name="ck_chunk_lines"),
        CheckConstraint("start_offset >= 0 AND end_offset > start_offset", name="ck_chunk_offsets"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    index_id: Mapped[UUID]
    import_job_id: Mapped[UUID]
    file_id: Mapped[UUID]
    ordinal: Mapped[int]
    symbol_ordinal: Mapped[int | None]
    start_offset: Mapped[int]
    end_offset: Mapped[int]
    start_line: Mapped[int]
    end_line: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
