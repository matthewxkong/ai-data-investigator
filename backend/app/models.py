"""Validated metadata records; raw CSV contents are not stored here."""

from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

SessionId = Annotated[str, Field(min_length=1, max_length=128)]
DatasetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class DatasetMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: UUID
    session_id: SessionId
    name: DatasetName
    byte_count: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)
    created_at: AwareDatetime


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class InvestigationMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    session_id: SessionId
    dataset_id: UUID
    question: Question
    status: InvestigationStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime
