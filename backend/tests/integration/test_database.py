import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1", reason="set RUN_DB_TESTS=1 with migrated DB"
)
def test_migrated_database_is_ready() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/health/ready").status_code == 200
