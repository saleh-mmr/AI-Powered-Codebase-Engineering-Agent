import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.models import ImportJob

AUTH = {"Origin": "http://localhost:3000", "X-RepoPilot-Request": "1"}


def sign_in(client: TestClient, email: str = "owner@example.com") -> dict[str, str]:
    client.cookies.clear()
    response = client.post(
        "/auth/register",
        json={"name": "Owner", "email": email, "password": "correct horse battery staple"},
        headers=AUTH,
    )
    assert response.status_code == 201
    return {**AUTH, "X-CSRF-Token": response.json()["csrf_token"]}


def connect(client: TestClient, headers: dict[str, str], name: str = "repo"):
    return client.post(
        "/repositories", json={"url": f"https://github.com/owner/{name}"}, headers=headers
    )


def test_job_is_durable_without_queue(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    response = connect(auth_client, headers)
    assert response.status_code == 202
    data = response.json()
    assert data["job"]["status"] == "queued"
    assert auth_client.get("/repositories").json()[0]["id"] == data["id"]

    async def verify():
        async with auth_client.app.state.test_factory() as db:
            assert await db.scalar(select(func.count()).select_from(ImportJob)) == 1

    asyncio.run(verify())
    assert connect(auth_client, headers).status_code == 409


def test_ownership_on_every_repository_endpoint(auth_client: TestClient) -> None:
    first = sign_in(auth_client)
    data = connect(auth_client, first).json()
    second = sign_in(auth_client, "other@example.com")
    assert auth_client.get("/repositories").json() == []
    rid = data["id"]
    for path in [
        f"/repositories/{rid}",
        f"/repositories/{rid}/files",
        f"/repositories/{rid}/files/{data['job']['id']}",
    ]:
        assert auth_client.get(path).status_code == 404
    for action in ["retry", "cancel"]:
        assert (
            auth_client.post(f"/repositories/{rid}/{action}", json={}, headers=second).status_code
            == 404
        )
    assert auth_client.delete(f"/repositories/{rid}", headers=second).status_code == 404


def test_csrf_cancel_retry_and_delete(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    assert (
        auth_client.post(
            "/repositories", json={"url": "https://github.com/o/r"}, headers=AUTH
        ).status_code
        == 403
    )
    data = connect(auth_client, headers).json()
    path = f"/repositories/{data['id']}"
    assert auth_client.post(path + "/retry", json={}, headers=headers).status_code == 409
    assert auth_client.post(path + "/cancel", json={}, headers=headers).status_code == 204
    assert auth_client.get(path).json()["job"]["status"] == "cancelled"
    retried = auth_client.post(path + "/retry", json={}, headers=headers)
    assert retried.status_code == 202
    assert retried.json()["job"]["id"] != data["job"]["id"]
    assert auth_client.delete(path, headers=headers).status_code == 204
    assert auth_client.get(path).status_code == 404

    async def verify():
        async with auth_client.app.state.test_factory() as db:
            assert await db.scalar(select(func.count()).select_from(ImportJob)) == 0

    asyncio.run(verify())


def test_import_quota_survives_repository_removal(auth_client: TestClient) -> None:
    headers = sign_in(auth_client)
    for index in range(5):
        response = connect(auth_client, headers, str(index))
        assert response.status_code == 202
        assert (
            auth_client.delete(
                f"/repositories/{response.json()['id']}", headers=headers
            ).status_code
            == 204
        )
    assert connect(auth_client, headers, "sixth").status_code == 429


def test_unsafe_urls_and_anonymous_requests(auth_client: TestClient) -> None:
    assert auth_client.get("/repositories").status_code == 401
    headers = sign_in(auth_client)
    assert (
        auth_client.post(
            "/repositories", json={"url": "http://127.0.0.1:8000/docs"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        auth_client.post(
            "/repositories",
            json={"url": "https://github.com/o/r", "user_id": "injected"},
            headers=headers,
        ).status_code
        == 422
    )
