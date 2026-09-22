from hashlib import sha256
from time import monotonic

from app.core.errors import AppError


class AuthThrottle:
    """Bounded single-process protection; replace with Redis before scaling out."""

    def __init__(self) -> None:
        self.buckets: dict[str, tuple[float, int]] = {}

    def check(self, email: str, peer: str) -> None:
        now = monotonic()
        self.buckets = {key: value for key, value in self.buckets.items() if value[0] > now}
        keys = [("email:" + sha256(email.encode()).hexdigest(), 5), ("peer:" + peer, 40)]
        if len(self.buckets) + sum(key not in self.buckets for key, _ in keys) > 4096:
            raise AppError("rate_limited", "Too many attempts. Try again in one minute.", 429)
        for key, limit in keys:
            end, count = self.buckets.get(key, (now + 60, 0))
            if count >= limit:
                raise AppError("rate_limited", "Too many attempts. Try again in one minute.", 429)
            self.buckets[key] = (end, count + 1)
