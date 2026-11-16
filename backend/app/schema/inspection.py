"""Fixed read-only scan, bounded by the accepted ingestion workload."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import BoundedSemaphore

import duckdb

from app.errors import ApiError
from app.ingestion.models import ImportedDataset
from app.schema.inference import ColumnEvidence

MAX_ROWS = 100_000
MAX_SOURCE_BYTES = 25_000_000


class SchemaInspector:
    def __init__(self) -> None:
        self.slots = BoundedSemaphore(2)

    @contextmanager
    def capacity(self) -> Iterator[None]:
        if not self.slots.acquire(blocking=False):
            raise ApiError(429, "schema_busy", "Two schema scans are active. Retry shortly.")
        try:
            yield
        finally:
            self.slots.release()

    def scan(self, database: Path, imported: ImportedDataset) -> tuple[ColumnEvidence, ...]:
        if not database.is_file():
            # Do not let connect create a replacement for a missing artifact.
            raise ApiError(503, "dataset_unavailable", "The dataset artifact is unavailable.")
        evidence = tuple(ColumnEvidence() for _ in imported.columns)
        try:
            with duckdb.connect(
                str(database),
                read_only=True,
                config={
                    "threads": "1",
                    "memory_limit": "128MB",
                    "autoload_known_extensions": "false",
                    "autoinstall_known_extensions": "false",
                    "allow_community_extensions": "false",
                },
            ) as connection:
                connection.execute("SET enable_external_access = false")
                connection.execute("SET lock_configuration = true")
                cursor = connection.execute("SELECT * FROM data LIMIT 100001")
                description = cursor.description
                if description is None or [(item[0], str(item[1])) for item in description] != [
                    (column.safe_name, "VARCHAR") for column in imported.columns
                ]:
                    raise ValueError("Artifact schema differs from import metadata.")
                rows = 0
                size = 0
                while batch := cursor.fetchmany(256):
                    for row in batch:
                        rows += 1
                        if rows > MAX_ROWS:
                            raise ValueError("Artifact row limit exceeded.")
                        for column, value in zip(evidence, row, strict=True):
                            if value is not None:
                                if not isinstance(value, str):
                                    raise ValueError("Artifact cell is not text.")
                                size += len(value.encode("utf-8"))
                                if size > MAX_SOURCE_BYTES:
                                    raise ValueError("Artifact text limit exceeded.")
                            column.observe(value)
                if rows != imported.metadata.row_count:
                    raise ValueError("Artifact row count differs from import metadata.")
        except (duckdb.Error, OSError, ValueError):
            raise ApiError(
                503, "dataset_unavailable", "The dataset artifact cannot be inspected."
            ) from None
        return evidence
