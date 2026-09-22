import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import Settings
from app.database.session import create_engine
from app.main import create_app
from app.models import User


@pytest.mark.integration
@pytest.mark.skipif(os.environ.get("RUN_DB_TESTS") != "1", reason="requires migrated PostgreSQL")
def test_auth_on_migrated_postgres() -> None:
    settings = Settings()
    email = f"integration-{uuid4().hex}@example.com"
    headers = {"Origin": settings.frontend_origin, "X-RepoPilot-Request": "1"}
    password = "integration test passphrase"
    try:
        with TestClient(create_app(settings), base_url=settings.frontend_origin) as client:
            response = client.post(
                "/auth/register",
                json={"email": email, "password": password, "name": "Integration"},
                headers=headers,
            )
            assert response.status_code == 201, response.text
            assert client.get("/auth/me").json()["user"]["email"] == email
            csrf = response.json()["csrf_token"]
            assert (
                client.post(
                    "/auth/logout", json={}, headers={**headers, "X-CSRF-Token": csrf}
                ).status_code
                == 204
            )
            assert client.get("/auth/me").status_code == 401
            assert (
                client.post(
                    "/auth/login", json={"email": email, "password": password}, headers=headers
                ).status_code
                == 200
            )
    finally:

        async def cleanup() -> None:
            engine = create_engine(settings)
            try:
                async with engine.begin() as connection:
                    await connection.execute(delete(User).where(User.email == email))
            finally:
                await engine.dispose()

        asyncio.run(cleanup())
