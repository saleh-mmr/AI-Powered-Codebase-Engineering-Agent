from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CodeChunk, CodeSymbol, RepositoryFile, SearchIndex
from app.retrieval.contracts import SourceChunk
from app.retrieval.text import VERSION


class SearchStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def latest(self, repository_id: UUID) -> SearchIndex | None:
        return (
            await self.db.scalars(
                select(SearchIndex).where(
                    SearchIndex.repository_id == repository_id, SearchIndex.is_current.is_(True)
                )
            )
        ).one_or_none()

    async def active(
        self, repository_id: UUID, source_index_id: UUID, mode: str
    ) -> SearchIndex | None:
        return (
            await self.db.scalars(
                select(SearchIndex)
                .where(
                    SearchIndex.repository_id == repository_id,
                    SearchIndex.source_index_id == source_index_id,
                    SearchIndex.status == "completed",
                    SearchIndex.mode == mode,
                    SearchIndex.pipeline_version == VERSION,
                )
                .order_by(SearchIndex.created_at.desc(), SearchIndex.id)
                .limit(1)
            )
        ).one_or_none()

    async def chunks(
        self, source_index_id: UUID, ids: list[UUID] | None = None
    ) -> list[SourceChunk]:
        statement = (
            select(CodeChunk, RepositoryFile, CodeSymbol)
            .join(RepositoryFile, RepositoryFile.id == CodeChunk.file_id)
            .outerjoin(
                CodeSymbol,
                and_(
                    CodeSymbol.index_id == CodeChunk.index_id,
                    CodeSymbol.file_id == CodeChunk.file_id,
                    CodeSymbol.ordinal == CodeChunk.symbol_ordinal,
                ),
            )
            .where(CodeChunk.index_id == source_index_id)
        )
        if ids is not None:
            statement = statement.where(CodeChunk.id.in_(ids))
        rows = (
            await self.db.execute(statement.order_by(RepositoryFile.path, CodeChunk.ordinal))
        ).all()
        return [
            SourceChunk(
                c.id,
                f.id,
                f.path,
                f.language,
                s.qualified_name if s else None,
                s.signature if s else None,
                c.content,
                c.start_line,
                c.end_line,
                c.start_offset,
                c.end_offset,
            )
            for c, f, s in rows
        ]
