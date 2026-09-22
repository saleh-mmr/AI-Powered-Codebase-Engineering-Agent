import hashlib
import hmac


def verify_access_token(token: str, expected_digest: str) -> bool:
    """Validate a bearer credential using a constant-time digest comparison."""
    digest = hashlib.sha256(token.encode()).hexdigest()
    return hmac.compare_digest(digest, expected_digest)


def require_repository_owner(user_id: str, repository_user_id: str) -> None:
    """Authorize repository access and reject cross-user resource IDs."""
    if user_id != repository_user_id:
        raise PermissionError("Repository not found")
