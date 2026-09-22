from hashlib import sha256

from app.core.rate_limits import Limit, RateLimiter


class AuthThrottle:
    def __init__(self, limiter: RateLimiter) -> None:
        self.limiter = limiter

    async def check(self, email: str, peer: str) -> None:
        await self.limiter.check(
            [
                Limit("auth:email:" + sha256(email.encode()).hexdigest(), 5, 60),
                Limit("auth:peer:" + sha256(peer.encode()).hexdigest(), 40, 60),
            ]
        )
