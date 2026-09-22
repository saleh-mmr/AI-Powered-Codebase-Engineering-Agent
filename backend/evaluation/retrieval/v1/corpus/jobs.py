from datetime import datetime


def claim_expired_job(expires_at: datetime, now: datetime, attempts: int) -> bool:
    """Recover abandoned background work after its lease expires, at most three attempts."""
    return expires_at < now and attempts < 3


def cancel_job(state: dict[str, str | None]) -> None:
    """Cancel a queued or running job by revoking its worker lease token."""
    state["status"] = "cancelled"
    state["lease_token"] = None
