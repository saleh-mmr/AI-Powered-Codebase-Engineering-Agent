import json
from uuid import UUID

from sqlalchemy import Text, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession


class PostgresCandidates:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def lexical(self, index_id: UUID, terms: list[str]) -> list[UUID]:
        if not terms:
            return []
        statement = text("""
            SELECT d.chunk_id FROM search_documents d
            JOIN code_chunks c ON c.id = d.chunk_id
            JOIN repository_files f ON f.id = c.file_id
            WHERE search_index_id = :index_id
              AND to_tsvector('simple', search_text) @@ to_tsquery('simple', :query)
            ORDER BY ts_rank_cd(to_tsvector('simple', search_text),
                     to_tsquery('simple', :query)) DESC,
                     f.path, c.ordinal LIMIT 30
        """)
        return list(
            (
                await self.db.scalars(statement, {"index_id": index_id, "query": " | ".join(terms)})
            ).all()
        )

    async def symbols(self, index_id: UUID, terms: list[str]) -> list[UUID]:
        if not terms:
            return []
        statement = text("""
            SELECT DISTINCT d.chunk_id, f.path, c.ordinal FROM search_documents d
            JOIN code_chunks c ON c.id = d.chunk_id
            JOIN repository_files f ON f.id = c.file_id
            JOIN code_symbols s ON s.index_id = c.index_id AND s.file_id = c.file_id
              AND (s.ordinal = c.symbol_ordinal OR s.start_line BETWEEN c.start_line AND c.end_line)
            WHERE d.search_index_id = :index_id
              AND (lower(s.name) = ANY(:terms) OR lower(s.qualified_name) = ANY(:terms))
            ORDER BY f.path, c.ordinal LIMIT 30
        """).bindparams(bindparam("terms", type_=ARRAY(Text())))
        return list(
            (await self.db.scalars(statement, {"index_id": index_id, "terms": terms})).all()
        )

    async def vector(self, index_id: UUID, vector: list[float]) -> list[UUID]:
        # Exact filtered search. No ANN recall loss or cross-generation candidates.
        statement = text("""
            SELECT d.chunk_id FROM search_documents d
            JOIN code_chunks c ON c.id = d.chunk_id
            JOIN repository_files f ON f.id = c.file_id
            WHERE search_index_id = :index_id AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:vector AS vector), f.path, c.ordinal LIMIT 30
        """)
        return list(
            (
                await self.db.scalars(
                    statement, {"index_id": index_id, "vector": json.dumps(vector, allow_nan=False)}
                )
            ).all()
        )
