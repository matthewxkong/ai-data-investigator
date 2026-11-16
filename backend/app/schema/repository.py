import json
import time
from uuid import UUID

from pydantic import TypeAdapter

from app.database import Database
from app.errors import ApiError
from app.schema.models import OverrideRequest, StoredOverrides, TypeOverride


class SchemaRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get(self, dataset_id: UUID, *, owner_id: str) -> StoredOverrides:
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT s.revision, s.overrides_json FROM dataset_schema_overrides s "
                "JOIN datasets d ON d.id = s.dataset_id WHERE d.id = ? AND d.session_id = ?",
                (str(dataset_id), owner_id),
            ).fetchone()
        if row is None:
            return StoredOverrides()
        return StoredOverrides(
            revision=row[0], overrides=TypeAdapter(dict[str, TypeOverride]).validate_json(row[1])
        )

    def replace(
        self, dataset_id: UUID, *, owner_id: str, request: OverrideRequest
    ) -> StoredOverrides:
        with self.database.connection(write=True) as connection:
            owned = connection.execute(
                "SELECT 1 FROM datasets d JOIN dataset_imports i ON i.dataset_id = d.id "
                "WHERE d.id = ? AND d.session_id = ?",
                (str(dataset_id), owner_id),
            ).fetchone()
            if owned is None:
                raise ApiError(404, "not_found", "Dataset not found.")
            if (
                connection.execute(
                    "SELECT 1 FROM upload_sessions WHERE id = ? AND expires_at > ?",
                    (owner_id, int(time.time())),
                ).fetchone()
                is None
            ):
                raise ApiError(
                    401, "session_required", "A valid upload session cookie is required."
                )
            current = connection.execute(
                "SELECT revision FROM dataset_schema_overrides WHERE dataset_id = ?",
                (str(dataset_id),),
            ).fetchone()
            revision = current[0] if current is not None else 0
            if revision != request.expected_revision:
                raise ApiError(
                    409, "schema_revision_conflict", "Schema changed. Read it again before editing."
                )
            updated = StoredOverrides(revision=revision + 1, overrides=request.overrides)
            connection.execute(
                "INSERT INTO dataset_schema_overrides VALUES (?, ?, ?) "
                "ON CONFLICT(dataset_id) DO UPDATE SET revision = excluded.revision, "
                "overrides_json = excluded.overrides_json",
                (
                    str(dataset_id),
                    updated.revision,
                    json.dumps(
                        {name: value.model_dump() for name, value in updated.overrides.items()}
                    ),
                ),
            )
        return updated
