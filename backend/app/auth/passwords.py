from threading import BoundedSemaphore

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from starlette.concurrency import run_in_threadpool

# Argon2id. Explicit settings avoid silently changing cost after a dependency update.
_hash_slots = BoundedSemaphore(2)
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)


async def hash_password(password: str) -> str:
    def hash_value() -> str:
        with _hash_slots:
            return _hasher.hash(password)

    return await run_in_threadpool(hash_value)


async def verify_password(stored_hash: str, password: str) -> bool:
    def verify() -> bool:
        try:
            with _hash_slots:
                return _hasher.verify(stored_hash, password)
        except VerificationError:
            return False

    return await run_in_threadpool(verify)


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)
