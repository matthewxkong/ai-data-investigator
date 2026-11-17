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
