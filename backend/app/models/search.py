from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator, TypeEngine

from app.database.base import Base


class EmbeddingVector(TypeDecorator[list[float]]):
    """Native pgvector in production; JSON only for portable unit/API tests."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        return dialect.type_descriptor(Vector(1536) if dialect.name == "postgresql" else JSON())


class SearchDocument(Base):
    __tablename__ = "search_documents"
    __table_args__ = (
        UniqueConstraint("search_index_id", "chunk_id", name="uq_search_document_chunk"),
        ForeignKeyConstraint(
            ["search_index_id", "source_index_id"],
            ["search_indexes.id", "search_indexes.source_index_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["chunk_id", "source_index_id"],
            ["code_chunks.id", "code_chunks.index_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("token_count > 0", name="ck_document_tokens"),
        Index("ix_search_documents_chunk", "chunk_id"),
        Index(
            "ix_search_documents_lexical",
            text("to_tsvector('simple', search_text)"),
            postgresql_using="gin",
        ).ddl_if(dialect="postgresql"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    search_index_id: Mapped[UUID]
    source_index_id: Mapped[UUID]
    chunk_id: Mapped[UUID]
    search_text: Mapped[str] = mapped_column(Text)
    input_hash: Mapped[str] = mapped_column(String(64))
    token_count: Mapped[int]
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector())
