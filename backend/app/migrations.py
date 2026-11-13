"""Ordered, checksummed metadata migrations applied inside one transaction."""

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


class MigrationError(RuntimeError):
    """The persisted schema cannot safely be used by this application version."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        return hashlib.sha256("\n".join(self.statements).encode()).hexdigest()


MIGRATIONS = (
    Migration(
        version=1,
        name="initial_metadata",
        statements=(
            """CREATE TABLE datasets (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                session_id TEXT NOT NULL CHECK(length(session_id) > 0),
                name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 255),
                byte_count INTEGER NOT NULL CHECK(byte_count >= 0),
                row_count INTEGER CHECK(row_count >= 0),
                created_at TEXT NOT NULL,
                UNIQUE(id, session_id)
            )""",
            """CREATE INDEX datasets_session_created_idx
                ON datasets(session_id, created_at, id)""",
            """CREATE TABLE investigations (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                question TEXT NOT NULL CHECK(length(trim(question)) BETWEEN 1 AND 4000),
                status TEXT NOT NULL CHECK(status IN
                    ('queued', 'running', 'completed', 'failed', 'cancelled')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(dataset_id, session_id)
                    REFERENCES datasets(id, session_id) ON DELETE CASCADE
            )""",
            """CREATE INDEX investigations_session_created_idx
                ON investigations(session_id, created_at, id)""",
        ),
    ),
    Migration(
        version=2,
        name="csv_imports_and_upload_sessions",
        statements=(
            """CREATE TABLE upload_sessions (
                id TEXT PRIMARY KEY,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )""",
            """CREATE TABLE dataset_imports (
                dataset_id TEXT PRIMARY KEY REFERENCES datasets(id) ON DELETE CASCADE,
                sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
                delimiter TEXT NOT NULL,
                columns_json TEXT NOT NULL
            )""",
        ),
    ),
)


def schema_version(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
    ).fetchall()
    if len(rows) > len(MIGRATIONS):
        raise MigrationError("The database requires a newer application version.")
    for index, row in enumerate(rows):
        expected = MIGRATIONS[index]
        if (row[0], row[1], row[2]) != (expected.version, expected.name, expected.checksum):
            raise MigrationError("Migration history does not match the application.")
    return len(rows)


def apply_migrations(connection: sqlite3.Connection) -> None:
    if not connection.in_transaction:
        raise MigrationError("Migrations require an explicit transaction.")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )"""
    )
    applied = schema_version(connection)
    for migration in MIGRATIONS[applied:]:
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, checksum, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (migration.version, migration.name, migration.checksum, datetime.now(UTC).isoformat()),
        )
