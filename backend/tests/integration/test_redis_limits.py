import asyncio
import os
from uuid import uuid4

import pytest
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limits import Limit, RedisRateLimiter


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="requires integration infrastructure"
)
def test_rate_limit_is_shared_and_atomic() -> None:
    async def scenario() -> None:
        redis = Redis.from_url(Settings().redis_url.get_secret_value(), socket_timeout=2)
        key = "test:" + uuid4().hex

        async def request(limiter: RedisRateLimiter) -> bool:
            try:
                await limiter.check([Limit(key, 5, 60)])
                return True
            except AppError as exc:
                assert exc.status == 429
                return False

        try:
            outcomes = await asyncio.gather(*(request(RedisRateLimiter(redis)) for _ in range(8)))
            assert sum(outcomes) == 5
        finally:
            await redis.delete("repopilot:limit:" + key)
            await redis.aclose()

    asyncio.run(scenario())
