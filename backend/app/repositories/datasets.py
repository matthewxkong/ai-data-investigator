from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.database import Database
from app.models import DatasetMetadata


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
        return dataset

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
