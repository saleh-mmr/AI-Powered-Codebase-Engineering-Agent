from fastapi.testclient import TestClient

from app.api.routes.health import get_readiness_probe
from app.core.config import Settings
from app.main import create_app


class HealthyProbe:
    async def check(self) -> None:
        return None


class FailedProbe:
    async def check(self) -> None:
        raise ConnectionError("postgresql://user:secret@internal/db")


def test_liveness_does_not_require_database() -> None:
    app = create_app(Settings(database_url="postgresql+asyncpg://user:secret@localhost/db"))
    with TestClient(app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "repopilot-api"}
    assert response.headers["x-request-id"]


def test_readiness_success() -> None:
    app = create_app(Settings(database_url="postgresql+asyncpg://user:secret@localhost/db"))
    app.dependency_overrides[get_readiness_probe] = HealthyProbe
    with TestClient(app) as client:
        assert client.get("/health/ready").status_code == 200


def test_readiness_failure_is_safe() -> None:
    app = create_app(Settings(database_url="postgresql+asyncpg://user:secret@localhost/db"))
    app.dependency_overrides[get_readiness_probe] = FailedProbe
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "dependency_unavailable"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "secret" not in response.text
    assert "internal/db" not in response.text
