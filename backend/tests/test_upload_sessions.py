import hashlib
from pathlib import Path

import pytest

from app import migrations
from app.database import Database
from app.repositories.datasets import DatasetRepository
from app.sessions import SessionStore


def test_candidate_tokens_are_not_live_until_persisted_and_only_hashes_are_stored(
    database: Database,
) -> None:
    store = SessionStore(database)
    grant = store.candidate()
    assert grant.token not in repr(grant)
    assert grant.owner_id == hashlib.sha256(grant.token.encode()).hexdigest()
    assert store.resolve(grant.token) is None
    with database.connection(write=True) as connection:
        connection.execute(
            "INSERT INTO upload_sessions VALUES (?, ?, ?)",
            (grant.owner_id, grant.created_at, grant.expires_at),
        )
    resolved = store.resolve(grant.token)
    assert resolved is not None and resolved.owner_id == grant.owner_id and not resolved.is_new
    assert store.resolve(grant.owner_id) is None
    assert store.resolve("x" * 43) is None


def test_expired_tokens_are_rejected(database: Database) -> None:
    store = SessionStore(database)
    grant = store.candidate()
    with database.connection(write=True) as connection:
        connection.execute("INSERT INTO upload_sessions VALUES (?, 0, 1)", (grant.owner_id,))
    assert store.resolve(grant.token) is None


def test_version_one_metadata_upgrades_without_losing_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path / "metadata.sqlite3")
    with monkeypatch.context() as legacy:
        legacy.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS[:1])
        with database.connection(write=True, create=True) as connection:
            migrations.apply_migrations(connection)
        original = DatasetRepository(database).create(session_id="legacy-owner", name="Original")
    database.initialize()
    assert DatasetRepository(database).get(original.id, session_id="legacy-owner") == original
    assert database.is_ready()
