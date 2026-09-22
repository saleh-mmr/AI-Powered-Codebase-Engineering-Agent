import asyncio
import os

import pytest

from app.core.config import Settings
from app.evaluation.retrieval import benchmark


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="requires migrated isolated PostgreSQL/pgvector"
)
def test_real_postgres_keyword_retrieval_benchmark() -> None:
    report = asyncio.run(benchmark(Settings()))
    assert report["semantic_api_called"] is False
    assert report["case_count"] == 14
    # Small development-fixture regression gate, not a general quality claim.
    assert report["metrics"]["keyword"]["recall@5"] >= 0.5
    assert report["metrics"]["symbol"]["recall@5"] > 0


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="requires PostgreSQL/pgvector")
def test_pgvector_storage_and_generation_filtering() -> None:
    from uuid import uuid4

    from sqlalchemy import delete, select, text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.core.rate_limits import MemoryRateLimiter
    from app.database.session import create_engine
    from app.embeddings.provider import DIMENSIONS, PROFILE, EmbeddingBatch
    from app.evaluation.fixtures import seed
    from app.evaluation.retrieval import DATASET
    from app.jobs.prepare_search import run_preparation
    from app.models import SearchDocument, User
    from app.retrieval.postgres import PostgresCandidates
    from app.services.search_preparation import PreparationService

    class Provider:
        profile = PROFILE

        def tokenize(self, text):
            from app.embeddings.tokens import token_parts

            return token_parts(text)

        async def embed(self, inputs):
            return EmbeddingBatch(
                [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in inputs], sum(map(len, inputs))
            )

    async def scenario():
        settings = Settings()
        assert settings.database_url.get_secret_value().split("?")[0].endswith("_test")
        settings.embeddings_enabled = True
        engine = create_engine(settings)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        users = [uuid4(), uuid4()]
        indexes = []
        try:
            for user in users:
                repo_id, _ = await seed(factory, DATASET / "corpus", user)
                async with factory() as db:
                    job, _ = await PreparationService(db, MemoryRateLimiter(), settings).start(
                        user, repo_id, "hybrid"
                    )
                indexes.append(job.id)
                await run_preparation(factory, job.id, Provider())
            async with factory() as db:
                first = set(
                    (
                        await db.scalars(
                            select(SearchDocument.chunk_id).where(
                                SearchDocument.search_index_id == indexes[0]
                            )
                        )
                    ).all()
                )
                second = set(
                    (
                        await db.scalars(
                            select(SearchDocument.chunk_id).where(
                                SearchDocument.search_index_id == indexes[1]
                            )
                        )
                    ).all()
                )
                hits = await PostgresCandidates(db).vector(
                    indexes[0], [1.0] + [0.0] * (DIMENSIONS - 1)
                )
                assert hits and set(hits) <= first and not set(hits) & second
                dimensions = await db.scalar(
                    text(
                        "SELECT vector_dims(embedding) FROM search_documents "
                        "WHERE search_index_id = :id LIMIT 1"
                    ),
                    {"id": indexes[0]},
                )
                assert dimensions == DIMENSIONS
        finally:
            async with engine.begin() as connection:
                await connection.execute(delete(User).where(User.id.in_(users)))
            await engine.dispose()

    asyncio.run(scenario())
