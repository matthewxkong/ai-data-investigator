"""Short-lived SQLite connections; transactions and file handles have explicit owners."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app import migrations


class MetadataStartupError(RuntimeError):
    """Actionable startup failure without exposing configuration values."""


def validate_schema(connection: sqlite3.Connection) -> None:
    if migrations.schema_version(connection) != len(migrations.MIGRATIONS):
        raise migrations.MigrationError("The metadata schema is not fully migrated.")
    connection.execute(
        "SELECT id, version, session_id, name, byte_count, row_count, created_at "
        "FROM datasets LIMIT 0"
    )
    connection.execute(
        "SELECT id, dataset_id, session_id, question, status, created_at, updated_at "
        "FROM investigations LIMIT 0"
    )
    connection.execute("SELECT id, created_at, expires_at FROM upload_sessions LIMIT 0")
    connection.execute(
        "SELECT dataset_id, sha256, delimiter, columns_json FROM dataset_imports LIMIT 0"
    )


class Database:
    def __init__(self, path: Path, *, timeout_seconds: float = 5.0) -> None:
        self.path = path.resolve()
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def connection(
        self, *, write: bool = False, create: bool = False
    ) -> Iterator[sqlite3.Connection]:
        mode = "rwc" if create else "rw"
        connection = sqlite3.connect(
            f"{self.path.as_uri()}?mode={mode}",
            uri=True,
            timeout=self.timeout_seconds,
            autocommit=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection(write=True, create=True) as connection:
                migrations.apply_migrations(connection)
                validate_schema(connection)
        except (OSError, sqlite3.Error, migrations.MigrationError) as error:
            raise MetadataStartupError(
                "Metadata initialization failed. Check ADI_DATA_DIR permissions and schema "
                "compatibility; restore a compatible backup instead of deleting existing data."
            ) from error

    def is_ready(self) -> bool:
        try:
            with self.connection() as connection:
                validate_schema(connection)
            return True
        except (OSError, sqlite3.Error, migrations.MigrationError):
            return False
