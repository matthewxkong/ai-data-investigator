import json
import sqlite3
import time
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from app.database import Database
from app.ingestion.models import (
    CsvColumn,
    DatasetArtifact,
    DatasetList,
    DatasetSummary,
    Delimiter,
    ImportedDataset,
)
from app.models import DatasetMetadata
from app.sessions import SessionExpiredError, SessionGrant


class DatasetRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(
        self,
        *,
        session_id: str,
        name: str,
        byte_count: int = 0,
        row_count: int | None = None,
    ) -> DatasetMetadata:
        dataset = DatasetMetadata(
            id=uuid4(),
            version=uuid4(),
            session_id=session_id,
            name=name,
            byte_count=byte_count,
            row_count=row_count,
            created_at=datetime.now(UTC),
        )
        with self.database.connection(write=True) as connection:
            self._insert(connection, dataset)
        return dataset

    @staticmethod
    def _insert(connection: sqlite3.Connection, dataset: DatasetMetadata) -> None:
        connection.execute(
            """INSERT INTO datasets
                (id, version, session_id, name, byte_count, row_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(dataset.id),
                str(dataset.version),
                dataset.session_id,
                dataset.name,
                dataset.byte_count,
                dataset.row_count,
                dataset.created_at.isoformat(),
            ),
        )

    def register_import(self, imported: ImportedDataset, session: SessionGrant) -> None:
        if imported.metadata.session_id != session.owner_id:
            raise ValueError("Imported metadata must belong to its upload session.")
        with self.database.connection(write=True) as connection:
            if session.expires_at <= int(time.time()):
                raise SessionExpiredError()
            if session.is_new:
                connection.execute(
                    "INSERT INTO upload_sessions VALUES (?, ?, ?)",
                    (session.owner_id, session.created_at, session.expires_at),
                )
            elif (
                connection.execute(
                    "SELECT 1 FROM upload_sessions WHERE id = ? AND expires_at > ?",
                    (session.owner_id, int(time.time())),
                ).fetchone()
                is None
            ):
                raise SessionExpiredError()
            self._insert(connection, imported.metadata)
            connection.execute(
                "INSERT INTO dataset_imports VALUES (?, ?, ?, ?)",
                (
                    str(imported.metadata.id),
                    imported.sha256,
                    imported.delimiter,
                    json.dumps([column.model_dump() for column in imported.columns]),
                ),
            )

    def get_import(self, dataset_id: UUID | str, *, session_id: str) -> ImportedDataset | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT d.*, i.sha256 AS source_sha256, i.delimiter AS source_delimiter, "
                "i.columns_json FROM datasets d JOIN dataset_imports i ON i.dataset_id = d.id "
                "WHERE d.id = ? AND d.session_id = ?",
                (str(dataset_id), session_id),
            ).fetchone()
        if row is None:
            return None
        values = dict(row)
        sha256 = values.pop("source_sha256")
        raw_delimiter = values.pop("source_delimiter")
        if raw_delimiter not in (",", ";", "\t"):
            raise ValueError("Stored CSV delimiter is invalid.")
        delimiter = cast(Delimiter, raw_delimiter)
        columns = TypeAdapter(tuple[CsvColumn, ...]).validate_json(values.pop("columns_json"))
        return ImportedDataset(DatasetMetadata.model_validate(values), sha256, delimiter, columns)

    def list_imports(self, session_id: str, *, limit: int, offset: int) -> DatasetList:
        if not 1 <= limit <= 100 or not 0 <= offset <= 2**63 - 1:
            raise ValueError("Invalid dataset list window.")
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT d.id, d.version, d.name, d.byte_count, d.row_count, d.created_at, i.sha256 "
                "FROM datasets d JOIN dataset_imports i ON i.dataset_id = d.id "
                "WHERE d.session_id = ? ORDER BY d.created_at DESC, d.id DESC LIMIT ? OFFSET ?",
                (session_id, limit + 1, offset),
            ).fetchall()
        return DatasetList(
            datasets=[DatasetSummary.model_validate(dict(row)) for row in rows[:limit]],
            next_offset=offset + limit if len(rows) > limit else None,
        )

    def begin_deletion(self, dataset_id: UUID, *, session_id: str) -> DatasetArtifact | None:
        params = (str(dataset_id), session_id)
        with self.database.connection(write=True) as connection:
            row = connection.execute(
                "SELECT d.version FROM datasets d JOIN dataset_imports i ON i.dataset_id = d.id "
                "WHERE d.id = ? AND d.session_id = ?",
                params,
            ).fetchone()
            if row is None:
                pending = connection.execute(
                    "SELECT dataset_version FROM dataset_deletions "
                    "WHERE dataset_id = ? AND session_id = ?",
                    params,
                ).fetchone()
                return None if pending is None else DatasetArtifact(dataset_id, UUID(pending[0]))
            version = UUID(row[0])
            connection.execute(
                "INSERT INTO dataset_deletions VALUES (?, ?, ?)",
                (str(dataset_id), str(version), session_id),
            )
            connection.execute("DELETE FROM datasets WHERE id = ? AND session_id = ?", params)
            return DatasetArtifact(dataset_id, version)

    def pending_deletions(self) -> list[DatasetArtifact]:
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT dataset_id, dataset_version FROM dataset_deletions ORDER BY rowid LIMIT 100"
            ).fetchall()
        return [DatasetArtifact(UUID(row[0]), UUID(row[1])) for row in rows]

    def complete_deletion(self, artifact: DatasetArtifact) -> None:
        with self.database.connection(write=True) as connection:
            connection.execute(
                "DELETE FROM dataset_deletions WHERE dataset_id = ? AND dataset_version = ?",
                (str(artifact.dataset_id), str(artifact.version)),
            )

    def get(self, dataset_id: UUID | str, *, session_id: str) -> DatasetMetadata | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM datasets WHERE id = ? AND session_id = ?",
                (str(dataset_id), session_id),
            ).fetchone()
        return DatasetMetadata.model_validate(dict(row)) if row is not None else None

    def list_for_session(self, session_id: str, *, limit: int = 50) -> list[DatasetMetadata]:
        if not 1 <= limit <= 100:
            raise ValueError("Metadata list limit must be between 1 and 100.")
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM datasets WHERE session_id = ? ORDER BY created_at, id LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [DatasetMetadata.model_validate(dict(row)) for row in rows]
