import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Database, MetadataStartupError
from app.main import create_app
from app.models import InvestigationStatus
from app.services import Services


def test_metadata_survives_full_application_recreation(settings: Settings) -> None:
    first = create_app(settings)
    with TestClient(first) as client:
        services = cast(Services, first.state.services)
        dataset = services.datasets.create(session_id="owner", name="Sales", row_count=12)
        investigation = services.investigations.create(
            session_id="owner", dataset_id=dataset.id, question="Count sales"
        )
        services.investigations.update_status(
            investigation.id, session_id="owner", status=InvestigationStatus.COMPLETED
        )
        assert client.get("/api/ready").status_code == 200

    second = create_app(settings)
    with TestClient(second) as client:
        restarted = cast(Services, second.state.services)
        assert restarted.datasets.get(dataset.id, session_id="owner") == dataset
        restored = restarted.investigations.get(investigation.id, session_id="owner")
        assert restored is not None
        assert restored.status == InvestigationStatus.COMPLETED
        assert restored.dataset_id == dataset.id
        assert restarted.datasets.get(dataset.id, session_id="other") is None
        assert client.get("/api/ready").json()["metadata_schema_version"] == 2


def test_liveness_survives_lost_storage_and_readiness_recovers(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        backup = settings.database_path.with_suffix(".backup")
        settings.database_path.rename(backup)
        assert client.get("/api/health").status_code == 200
        response = client.get("/api/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "metadata_unavailable"
        assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
        assert not settings.database_path.exists()
        backup.rename(settings.database_path)
        assert client.get("/api/ready").status_code == 200


def test_exclusive_database_lock_returns_not_ready_without_breaking_liveness(
    settings: Settings,
) -> None:
    limited = settings.model_copy(update={"sqlite_timeout_seconds": 0.05})
    with TestClient(create_app(limited)) as client:
        with closing(sqlite3.connect(settings.database_path, autocommit=True)) as lock:
            try:
                lock.execute("BEGIN EXCLUSIVE")
                assert client.get("/api/ready").status_code == 503
                assert client.get("/api/health").status_code == 200
            finally:
                lock.execute("ROLLBACK")
        assert client.get("/api/ready").status_code == 200


def test_file_instead_of_data_directory_fails_with_actionable_message(tmp_path: Path) -> None:
    data_path = tmp_path / "occupied"
    data_path.write_text("preserve this file", encoding="utf-8")
    settings = Settings(_env_file=None, data_dir=data_path)
    with pytest.raises(MetadataStartupError, match="ADI_DATA_DIR permissions"):
        with TestClient(create_app(settings)):
            pytest.fail("Application must not start with unusable metadata storage.")
    assert data_path.read_text(encoding="utf-8") == "preserve this file"


def test_corrupt_database_is_preserved_and_startup_fails(settings: Settings) -> None:
    settings.data_dir.mkdir()
    original = b"not a SQLite database: retain for diagnosis"
    settings.database_path.write_bytes(original)
    with pytest.raises(MetadataStartupError, match="compatible backup"):
        with TestClient(create_app(settings)):
            pytest.fail("Application must not start with a corrupt database.")
    assert settings.database_path.read_bytes() == original


def test_missing_schema_table_makes_a_running_application_not_ready(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        database = Database(settings.database_path)
        with database.connection(write=True) as connection:
            connection.execute("DROP TABLE investigations")
        assert client.get("/api/ready").status_code == 503
        assert client.get("/api/health").status_code == 200


def test_incomplete_persisted_schema_fails_startup_without_recreating_tables(
    settings: Settings,
) -> None:
    database = Database(settings.database_path)
    database.initialize()
    with database.connection(write=True) as connection:
        connection.execute("DROP TABLE investigations")
    with pytest.raises(MetadataStartupError):
        with TestClient(create_app(settings)):
            pytest.fail("Application must not start with an incomplete persisted schema.")
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'investigations'"
            ).fetchone()
            is None
        )
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2


def test_concurrent_startup_serializes_migrations_once(tmp_path: Path) -> None:
    path = tmp_path / "metadata.sqlite3"
    databases = [Database(path), Database(path)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda database: database.initialize(), databases))
    with databases[0].connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 2
    assert all(database.is_ready() for database in databases)


def test_storage_path_with_spaces_unicode_and_uri_characters(tmp_path: Path) -> None:
    database = Database(tmp_path / "metadata # café" / "metadata.sqlite3")
    database.initialize()
    assert database.is_ready()
