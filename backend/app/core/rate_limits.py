from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.errors import AppError


@dataclass(frozen=True)
class Limit:
    key: str
    count: int
    seconds: int


class RateLimiter(Protocol):
    async def check(self, limits: list[Limit]) -> None: ...


SCRIPT = """
for i, key in ipairs(KEYS) do
  if tonumber(redis.call('GET', key) or '0') >= tonumber(ARGV[(i-1)*2+1]) then
    return 0
  end
end
for i, key in ipairs(KEYS) do
  local count = redis.call('INCR', key)
  if count == 1 then redis.call('EXPIRE', key, tonumber(ARGV[(i-1)*2+2])) end
end
return 1
"""


class RedisRateLimiter:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def check(self, limits: list[Limit]) -> None:
        args: list[str | int] = ["repopilot:limit:" + limit.key for limit in limits]
        for limit in limits:
            args.extend([limit.count, limit.seconds])
        try:
            # redis-py does not type its generic command bridge; validate the result below.
            result: object = await self.redis.execute_command(  # type: ignore[no-untyped-call]
                "EVAL", SCRIPT, len(limits), *args
            )
        except RedisError as exc:
            raise AppError(
                "rate_limit_unavailable",
                "Request protection is unavailable. Try again shortly.",
                503,
            ) from exc
        if result != 1:
            code = (
                "import_rate_limited"
                if any(limit.seconds > 60 for limit in limits)
                else "rate_limited"
            )
            raise AppError(code, "Too many attempts. Please try again later.", 429)


class MemoryRateLimiter:
    """Deterministic local test double; production uses RedisRateLimiter."""

    def __init__(self) -> None:
        self.values: dict[str, tuple[float, int]] = {}

    async def check(self, limits: list[Limit]) -> None:
        now = monotonic()
        for limit in limits:
            expires, count = self.values.get(limit.key, (now + limit.seconds, 0))
            if expires <= now:
                expires, count = now + limit.seconds, 0
            if count >= limit.count:
                raise AppError("rate_limited", "Too many attempts.", 429)
            self.values[limit.key] = (expires, count + 1)
