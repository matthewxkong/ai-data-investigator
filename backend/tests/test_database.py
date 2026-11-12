from pathlib import Path

import pytest

from app import migrations
from app.database import Database, MetadataStartupError


def test_migrations_are_idempotent_across_database_instances(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "metadata.sqlite3"
    first = Database(path)
    assert not first.is_ready()
    assert not path.exists()
    first.initialize()
    with first.connection() as connection:
        applied = connection.execute("SELECT * FROM schema_migrations").fetchall()
    second = Database(path)
    second.initialize()
    assert second.is_ready()
    with second.connection() as connection:
        assert [tuple(row) for row in applied] == [
            tuple(row) for row in connection.execute("SELECT * FROM schema_migrations")
        ]


def test_failed_upgrade_rolls_back_ddl_and_preserves_existing_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path / "metadata.sqlite3")
    database.initialize()
    failed_upgrade = migrations.Migration(
        version=2,
        name="broken_upgrade",
        statements=(
            "CREATE TABLE rollback_probe(id INTEGER)",
            "INSERT INTO absent_table VALUES (1)",
        ),
    )
    monkeypatch.setattr(migrations, "MIGRATIONS", (*migrations.MIGRATIONS, failed_upgrade))
    with pytest.raises(MetadataStartupError, match="schema compatibility"):
        database.initialize()
    with database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'rollback_probe'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize("change", ["unknown_version", "changed_checksum"])
def test_incompatible_history_is_rejected_without_rewriting_it(tmp_path: Path, change: str) -> None:
    database = Database(tmp_path / "metadata.sqlite3")
    database.initialize()
    with database.connection(write=True) as connection:
        if change == "unknown_version":
            connection.execute(
                "INSERT INTO schema_migrations VALUES (2, 'future', 'unknown', '2026-11-10')"
            )
        else:
            connection.execute("UPDATE schema_migrations SET checksum = 'modified'")
    with pytest.raises(MetadataStartupError):
        database.initialize()
    assert not database.is_ready()


def test_unavailable_storage_does_not_get_recreated_by_readiness(tmp_path: Path) -> None:
    path = tmp_path / "metadata.sqlite3"
    database = Database(path)
    database.initialize()
    backup = tmp_path / "backup.sqlite3"
    path.rename(backup)
    assert not database.is_ready()
    assert not path.exists()
    backup.rename(path)
    assert database.is_ready()
