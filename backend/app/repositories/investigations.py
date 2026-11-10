from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.database import Database
from app.models import InvestigationMetadata, InvestigationStatus
from app.repositories import MetadataNotFoundError


class InvestigationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, *, session_id: str, dataset_id: UUID, question: str) -> InvestigationMetadata:
        now = datetime.now(UTC)
        investigation = InvestigationMetadata(
            id=uuid4(),
            session_id=session_id,
            dataset_id=dataset_id,
            question=question,
            status=InvestigationStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        with self.database.connection(write=True) as connection:
            result = connection.execute(
                """INSERT INTO investigations
                    (id, session_id, dataset_id, question, status, created_at, updated_at)
                    SELECT ?, ?, id, ?, ?, ?, ? FROM datasets WHERE id = ? AND session_id = ?""",
                (
                    str(investigation.id),
                    session_id,
                    investigation.question,
                    investigation.status.value,
                    now.isoformat(),
                    now.isoformat(),
                    str(dataset_id),
                    session_id,
                ),
            )
            if result.rowcount != 1:
                raise MetadataNotFoundError("Dataset not found.")
        return investigation

    def get(self, investigation_id: UUID | str, *, session_id: str) -> InvestigationMetadata | None:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM investigations WHERE id = ? AND session_id = ?",
                (str(investigation_id), session_id),
            ).fetchone()
        return InvestigationMetadata.model_validate(dict(row)) if row is not None else None

    def list_for_session(self, session_id: str, *, limit: int = 50) -> list[InvestigationMetadata]:
        if not 1 <= limit <= 100:
            raise ValueError("Metadata list limit must be between 1 and 100.")
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM investigations WHERE session_id = ? ORDER BY created_at, id LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [InvestigationMetadata.model_validate(dict(row)) for row in rows]

    def update_status(
        self, investigation_id: UUID | str, *, session_id: str, status: InvestigationStatus
    ) -> InvestigationMetadata | None:
        """Persist a status; orchestration and transition policy belong to the future agent loop."""
        validated_status = InvestigationStatus(status)
        with self.database.connection(write=True) as connection:
            connection.execute(
                "UPDATE investigations SET status = ?, updated_at = ? "
                "WHERE id = ? AND session_id = ?",
                (
                    validated_status.value,
                    datetime.now(UTC).isoformat(),
                    str(investigation_id),
                    session_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM investigations WHERE id = ? AND session_id = ?",
                (str(investigation_id), session_id),
            ).fetchone()
        return InvestigationMetadata.model_validate(dict(row)) if row is not None else None
