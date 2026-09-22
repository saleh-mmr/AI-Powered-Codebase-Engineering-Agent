import asyncio
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.auth.tokens import token_hash
from app.models import Session, User

HEADERS = {"Origin": "http://localhost:3000", "X-RepoPilot-Request": "1"}
PASSWORD = "correct horse battery staple"


def register(client: TestClient, email: str = "saleh@example.com"):
    return client.post(
        "/auth/register",
        json={"name": "Saleh", "email": email, "password": PASSWORD},
        headers=HEADERS,
    )


def test_registration_persistence_and_logout(auth_client: TestClient) -> None:
    response = register(auth_client)
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "saleh@example.com"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/" in cookie
    token = auth_client.cookies["repopilot_session"]

    async def inspect_storage() -> None:
        async with auth_client.app.state.test_factory() as db:
            user = await db.scalar(select(User))
            session = await db.scalar(select(Session))
            assert user.password_hash.startswith("$argon2id$")
            assert PASSWORD not in user.password_hash
            assert session.token_hash == token_hash(token)
            assert token not in session.token_hash

    asyncio.run(inspect_storage())
    current = auth_client.get("/auth/me")
    assert current.status_code == 200
    assert current.json()["user"]["id"] == response.json()["user"]["id"]
    assert "password" not in current.text and token not in current.text
    logout = auth_client.post(
        "/auth/logout", json={}, headers={**HEADERS, "X-CSRF-Token": current.json()["csrf_token"]}
    )
    assert logout.status_code == 204 and not logout.content
    auth_client.cookies.set("repopilot_session", token)
    assert auth_client.get("/auth/me").status_code == 401


def test_login_rotates_and_revokes_old_cookie(auth_client: TestClient) -> None:
    assert register(auth_client).status_code == 201
    old = auth_client.cookies["repopilot_session"]
    response = auth_client.post(
        "/auth/login", json={"email": "Saleh@EXAMPLE.COM", "password": PASSWORD}, headers=HEADERS
    )
    assert response.status_code == 200
    new = auth_client.cookies["repopilot_session"]
    assert old != new
    auth_client.cookies.clear()
    auth_client.cookies.set("repopilot_session", old)
    assert auth_client.get("/auth/me").status_code == 401
    auth_client.cookies.set("repopilot_session", new)
    assert auth_client.get("/auth/me").status_code == 200


def test_login_errors_do_not_reveal_account_existence(auth_client: TestClient) -> None:
    register(auth_client)
    responses = [
        auth_client.post(
            "/auth/login", json={"email": email, "password": "wrong password"}, headers=HEADERS
        )
        for email in ["saleh@example.com", "absent@example.com"]
    ]
    assert all(response.status_code == 401 for response in responses)
    assert responses[0].json()["error"]["message"] == responses[1].json()["error"]["message"]


def test_duplicate_email_is_case_insensitive(auth_client: TestClient) -> None:
    assert register(auth_client, "Saleh@Example.com").status_code == 201
    assert register(auth_client, "saleh@example.com").status_code == 409


def test_csrf_and_origin_protection(auth_client: TestClient) -> None:
    payload = {"name": "Saleh", "email": "saleh@example.com", "password": PASSWORD}
    for headers in [
        {},
        {**HEADERS, "Origin": "https://evil.example"},
        {"Origin": "http://localhost:3000"},
    ]:
        assert auth_client.post("/auth/register", json=payload, headers=headers).status_code == 403
    session = register(auth_client).json()
    assert auth_client.post("/auth/logout", json={}, headers=HEADERS).status_code == 403
    assert (
        auth_client.post(
            "/auth/logout", json={}, headers={**HEADERS, "X-CSRF-Token": "0" * 64}
        ).status_code
        == 403
    )
    assert (
        auth_client.post(
            "/auth/logout",
            json={},
            headers={
                **HEADERS,
                "Origin": "https://evil.example",
                "X-CSRF-Token": session["csrf_token"],
            },
        ).status_code
        == 403
    )
    assert auth_client.get("/auth/me").status_code == 200


def test_two_users_cannot_substitute_identity_or_csrf(auth_client: TestClient) -> None:
    first = register(auth_client, "first@example.com").json()
    auth_client.cookies.clear()
    second = register(auth_client, "second@example.com").json()
    assert first["user"]["id"] != second["user"]["id"]
    current = auth_client.get(
        "/auth/me",
        params={"user_id": first["user"]["id"]},
        headers={"X-User-ID": first["user"]["id"]},
    )
    assert current.json()["user"]["id"] == second["user"]["id"]
    assert (
        auth_client.post(
            "/auth/logout", json={}, headers={**HEADERS, "X-CSRF-Token": first["csrf_token"]}
        ).status_code
        == 403
    )


def test_expired_sessions_are_rejected(auth_client: TestClient) -> None:
    register(auth_client)

    async def expire() -> None:
        async with auth_client.app.state.test_factory() as db:
            await db.execute(
                update(Session).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
            await db.commit()

    asyncio.run(expire())
    assert auth_client.get("/auth/me").status_code == 401


def test_missing_and_malformed_cookies_are_rejected(auth_client: TestClient) -> None:
    assert auth_client.get("/auth/me").status_code == 401
    auth_client.cookies.set("repopilot_session", "not-a-session")
    assert auth_client.get("/auth/me").status_code == 401


def test_validation_does_not_echo_passwords(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/auth/register",
        json={"name": "Saleh", "email": "not-an-email", "password": "secret"},
        headers=HEADERS,
    )
    assert response.status_code == 422
    assert "secret" not in response.text and "not-an-email" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


def test_password_policy_and_json_only(auth_client: TestClient) -> None:
    assert (
        auth_client.post(
            "/auth/register",
            json={"name": "Saleh", "email": "saleh@example.com", "password": "short"},
            headers=HEADERS,
        ).status_code
        == 422
    )
    assert (
        auth_client.post(
            "/auth/login", content="{}", headers={**HEADERS, "Content-Type": "text/plain"}
        ).status_code
        == 415
    )


def test_login_rate_limit(auth_client: TestClient) -> None:
    for _ in range(5):
        assert (
            auth_client.post(
                "/auth/login",
                json={"email": "absent@example.com", "password": "incorrect"},
                headers=HEADERS,
            ).status_code
            == 401
        )
    response = auth_client.post(
        "/auth/login",
        json={"email": "absent@example.com", "password": "incorrect"},
        headers=HEADERS,
    )
    assert response.status_code == 429 and response.headers["retry-after"] == "60"


def test_secure_cookie_configuration(auth_client: TestClient) -> None:
    auth_client.app.state.settings.cookie_secure = True
    response = register(auth_client)
    assert response.status_code == 201
    assert "; Secure" in response.headers["set-cookie"]
