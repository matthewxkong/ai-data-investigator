import asyncio
from collections.abc import AsyncIterator

import duckdb
import pytest

from app import migrations
from app.config import Settings
from app.database import Database
from app.errors import ApiError
from app.ingestion.service import IngestionService
from app.repositories.datasets import DatasetRepository
from app.schema.inspection import SchemaInspector
from app.schema.models import OverrideRequest
from app.schema.repository import SchemaRepository
from app.sessions import SessionStore


async def body() -> AsyncIterator[bytes]:
    yield b"Column Name,Column Name\n1,001\n2,002\n"


def imported_data(settings: Settings):
    database = Database(settings.database_path)
    database.initialize()
    ingestion = IngestionService(settings, DatasetRepository(database), SessionStore(database))
    imported, grant = asyncio.run(
        ingestion.ingest(
            body(),
            filename="sample.csv",
            token=None,
            declared_length=None,
            delimiter=None,
        )
    )
    return database, ingestion, imported, grant


def test_version_two_upgrade_preserves_import_sessions_and_history(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(settings.database_path)
    settings.data_dir.mkdir(parents=True)
    with monkeypatch.context() as legacy:
        legacy.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS[:2])
        with database.connection(write=True, create=True) as connection:
            migrations.apply_migrations(connection)
        ingestion = IngestionService(settings, DatasetRepository(database), SessionStore(database))
        imported, grant = asyncio.run(
            ingestion.ingest(
                body(),
                filename="legacy.csv",
                token=None,
                declared_length=None,
                delimiter=None,
            )
        )
        with database.connection() as connection:
            before = [tuple(row) for row in connection.execute("SELECT * FROM schema_migrations")]
    database.initialize()
    with database.connection() as connection:
        after = [tuple(row) for row in connection.execute("SELECT * FROM schema_migrations")]
    assert after[:2] == before
    assert len(after) == 3 and database.is_ready()
    assert SessionStore(database).resolve(grant.token) is not None
    assert (
        DatasetRepository(database).get_import(imported.metadata.id, session_id=grant.owner_id)
        == imported
    )
    assert (
        SchemaRepository(database).get(imported.metadata.id, owner_id=grant.owner_id).revision == 0
    )


def test_repository_checks_owner_expiry_and_cascades_on_dataset_delete(settings: Settings) -> None:
    database, _, imported, grant = imported_data(settings)
    repository = SchemaRepository(database)
    request = OverrideRequest(expected_revision=0, overrides={})
    with pytest.raises(ApiError) as wrong_owner:
        repository.replace(imported.metadata.id, owner_id="someone-else", request=request)
    assert wrong_owner.value.status_code == 404
    assert (
        repository.replace(imported.metadata.id, owner_id=grant.owner_id, request=request).revision
        == 1
    )
    assert repository.get(imported.metadata.id, owner_id="someone-else").revision == 0
    with database.connection(write=True) as connection:
        connection.execute("UPDATE upload_sessions SET expires_at = 1")
    with pytest.raises(ApiError) as expired:
        repository.replace(imported.metadata.id, owner_id=grant.owner_id, request=request)
    assert expired.value.status_code == 401
    with database.connection(write=True) as connection:
        connection.execute("DELETE FROM datasets WHERE id = ?", (str(imported.metadata.id),))
        assert (
            connection.execute("SELECT COUNT(*) FROM dataset_schema_overrides").fetchone()[0] == 0
        )


@pytest.mark.parametrize(
    "damage", ["renamed_column", "nontext_column", "extra_row", "missing_table", "corrupt_file"]
)
def test_incompatible_artifacts_fail_safely_and_release_capacity(
    settings: Settings, damage: str
) -> None:
    _, ingestion, imported, _ = imported_data(settings)
    path = ingestion.artifact_path(imported.metadata) / "data.duckdb"
    if damage == "corrupt_file":
        path.write_bytes(b"PRIVATE CORRUPTION")
    else:
        with duckdb.connect(str(path)) as connection:
            if damage == "renamed_column":
                connection.execute("ALTER TABLE data RENAME column_name TO unexpected")
            elif damage == "nontext_column":
                connection.execute("ALTER TABLE data ALTER column_name SET DATA TYPE INTEGER")
            elif damage == "extra_row":
                connection.execute("INSERT INTO data VALUES ('3','003')")
            else:
                connection.execute("DROP TABLE data")
    inspector = SchemaInspector()
    for _ in range(3):
        with pytest.raises(ApiError) as failure, inspector.capacity():
            inspector.scan(path, imported)
        assert failure.value.status_code == 503
        assert str(path) not in failure.value.message
        assert "PRIVATE" not in failure.value.message
    with inspector.capacity(), inspector.capacity():
        pass


def test_full_maximum_workload_and_artifact_bounds(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, ingestion, imported, _ = imported_data(settings)
    path = ingestion.artifact_path(imported.metadata) / "data.duckdb"
    with duckdb.connect(str(path)) as connection:
        connection.execute("DELETE FROM data")
        connection.execute("INSERT INTO data SELECT i::VARCHAR, '001' FROM range(100000) t(i)")
    imported = type(imported)(
        imported.metadata.model_copy(update={"row_count": 100_000}),
        imported.sha256,
        imported.delimiter,
        imported.columns,
    )
    inspector = SchemaInspector()
    evidence = inspector.scan(path, imported)
    assert evidence[0].integers == evidence[1].leading_zeros == 100_000
    with duckdb.connect(str(path)) as connection:
        connection.execute("INSERT INTO data VALUES ('late','001')")
    with pytest.raises(ApiError):
        inspector.scan(path, imported)


def test_source_text_byte_boundary_is_enforced_during_inspection(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.schema import inspection

    _, ingestion, imported, _ = imported_data(settings)
    path = ingestion.artifact_path(imported.metadata) / "data.duckdb"
    monkeypatch.setattr(inspection, "MAX_SOURCE_BYTES", 7)
    with pytest.raises(ApiError) as failure:
        SchemaInspector().scan(path, imported)
    assert failure.value.status_code == 503
