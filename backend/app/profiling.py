"""Fixed read-only profiling queries; no user SQL or expressions."""

import math
import re
from uuid import UUID

import duckdb
from pydantic import BaseModel

from app.errors import ApiError
from app.ingestion.models import ImportedDataset
from app.schema.service import SchemaService


class NumericSummary(BaseModel):
    count: int
    excluded_count: int
    minimum: float | None
    maximum: float | None
    mean: float | None
    q25: float | None
    median: float | None
    q75: float | None


class Frequency(BaseModel):
    value: str
    count: int
    truncated: bool


class ColumnProfile(BaseModel):
    original_name: str
    safe_name: str
    effective_type: str
    null_count: int
    distinct_count: int
    numeric: NumericSummary | None = None
    frequencies: tuple[Frequency, ...] = ()
    frequencies_complete: bool = False
    warnings: tuple[str, ...] = ()


class ProfileResponse(BaseModel):
    dataset_id: UUID
    dataset_version: UUID
    schema_revision: int
    profile_version: str = "1"
    row_count: int
    duplicate_row_count: int
    columns: tuple[ColumnProfile, ...]
    warnings: tuple[str, ...]


class Profiler:
    def __init__(self, schema: SchemaService) -> None:
        self.schema = schema

    @staticmethod
    def numeric(connection: duckdb.DuckDBPyConnection, name: str) -> NumericSummary:
        result = connection.execute(
            f"WITH parsed AS (SELECT TRY_CAST({name} AS DOUBLE) AS n FROM data "
            f"WHERE {name} IS NOT NULL), valid AS (SELECT n FROM parsed WHERE isfinite(n)) "
            "SELECT COUNT(*), (SELECT COUNT(*) FROM parsed) - COUNT(*), "
            "MIN(n), MAX(n), AVG(n), quantile_cont(n, 0.25), "
            "quantile_cont(n, 0.5), quantile_cont(n, 0.75) FROM valid"
        ).fetchone()
        assert result is not None
        # Very large finite inputs can overflow an aggregate. Never emit JSON NaN/Infinity.
        values = [
            float(value) if value is not None and math.isfinite(float(value)) else None
            for value in result[2:]
        ]
        return NumericSummary(
            count=int(result[0]),
            excluded_count=int(result[1]),
            **dict(
                zip(("minimum", "maximum", "mean", "q25", "median", "q75"), values, strict=True)
            ),
        )

    @staticmethod
    def identifier(name: str) -> str:
        if re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", name) is None:
            raise ValueError("Invalid stored identifier.")
        return '"' + name + '"'

    def inspect(self, imported: ImportedDataset) -> ProfileResponse:
        with self.schema.inspector.capacity():
            path = self.schema.ingestion.artifact_path(imported.metadata) / "data.duckdb"
            evidence = self.schema.inspector.scan(path, imported)
            stored = self.schema.repository.get(
                imported.metadata.id, owner_id=imported.metadata.session_id
            )
            schema = self.schema.response(imported, evidence, stored)
            try:
                with duckdb.connect(
                    str(path),
                    read_only=True,
                    config={
                        "threads": "1",
                        "memory_limit": "128MB",
                        "enable_external_access": "false",
                        "lock_configuration": "true",
                        "autoload_known_extensions": "false",
                        "autoinstall_known_extensions": "false",
                        "allow_community_extensions": "false",
                    },
                ) as connection:
                    counts = connection.execute(
                        "SELECT (SELECT COUNT(*) FROM data), "
                        "(SELECT COUNT(*) FROM (SELECT DISTINCT * FROM data))"
                    ).fetchone()
                    assert counts is not None
                    rows, unique_rows = int(counts[0]), int(counts[1])
                    columns = []
                    for column in schema.columns:
                        name = self.identifier(column.safe_name)
                        count = connection.execute(
                            f"SELECT COUNT(*) - COUNT({name}), COUNT(DISTINCT {name}) FROM data"
                        ).fetchone()
                        assert count is not None
                        columns.append(
                            ColumnProfile(
                                original_name=column.original_name,
                                safe_name=column.safe_name,
                                effective_type=column.effective_type,
                                null_count=int(count[0]),
                                distinct_count=int(count[1]),
                                warnings=tuple(warning.code for warning in column.warnings),
                            )
                        )
                        if column.effective_type in {"integer", "decimal"}:
                            summary = self.numeric(connection, name)
                            columns[-1].numeric = summary
                            columns[-1].warnings += ("binary_float_summary",)
                            if summary.excluded_count:
                                columns[-1].warnings += ("numeric_values_excluded",)
                            if summary.count and any(
                                value is None
                                for value in (
                                    summary.minimum,
                                    summary.maximum,
                                    summary.mean,
                                    summary.q25,
                                    summary.median,
                                    summary.q75,
                                )
                            ):
                                columns[-1].warnings += ("numeric_aggregate_overflow",)
                        if column.effective_type in {"categorical", "boolean"}:
                            frequencies = connection.execute(
                                f"SELECT LEFT({name}, 256), COUNT(*), LENGTH({name}) > 256 "
                                f"FROM data WHERE {name} IS NOT NULL GROUP BY {name} "
                                f"ORDER BY COUNT(*) DESC, {name} ASC LIMIT 10"
                            ).fetchall()
                            columns[-1].frequencies = tuple(
                                Frequency(value=value, count=count, truncated=truncated)
                                for value, count, truncated in frequencies
                            )
                            columns[-1].frequencies_complete = int(count[1]) <= 10
                    return ProfileResponse(
                        dataset_id=imported.metadata.id,
                        dataset_version=imported.metadata.version,
                        schema_revision=stored.revision,
                        row_count=rows,
                        duplicate_row_count=rows - unique_rows,
                        columns=tuple(columns),
                        warnings=("duplicate_rows",) if rows != unique_rows else (),
                    )
            except (duckdb.Error, OSError, ValueError):
                raise ApiError(
                    503, "profile_unavailable", "The dataset cannot be profiled."
                ) from None
