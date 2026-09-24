import importlib

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text


def test_upgrade_backfills_only_current_state_and_downgrade_preserves_runs(monkeypatch):
    migration = importlib.import_module("migrations.versions.0009_run_events")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("""CREATE TABLE answer_runs (
            id CHAR(32) PRIMARY KEY, status TEXT, created_at DATETIME,
            started_at DATETIME, finished_at DATETIME
        )""")
        )
        for number, status in enumerate(["queued", "running", "completed", "cancelled", "failed"]):
            connection.execute(
                text("""INSERT INTO answer_runs VALUES
                (:id, :status, '2026-01-01 00:00:00', NULL, NULL)
            """),
                {"id": str(number) * 32, "status": status},
            )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        rows = connection.execute(
            text("SELECT sequence, status FROM answer_run_events ORDER BY run_id")
        ).all()
        assert rows == [
            (1, state) for state in ["queued", "running", "completed", "cancelled", "failed"]
        ]
        migration.downgrade()
        assert connection.scalar(text("SELECT count(*) FROM answer_runs")) == 5
    engine.dispose()
