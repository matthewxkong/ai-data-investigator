from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.models import DatasetMetadata

Delimiter = Literal[",", ";", "\t"]


class CsvColumn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    position: int
    original_name: str
    safe_name: str


class DatasetSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: UUID
    name: str
    byte_count: int
    row_count: int
    created_at: AwareDatetime
    sha256: str


class DatasetResponse(DatasetSummary):
    delimiter: Delimiter
    columns: tuple[CsvColumn, ...]


class DatasetList(BaseModel):
    datasets: list[DatasetSummary]
    next_offset: int | None


class PreviewCell(BaseModel):
    value: str | None
    truncated: bool


class DatasetPreview(BaseModel):
    dataset_id: UUID
    dataset_version: UUID
    columns: tuple[CsvColumn, ...]
    rows: list[list[PreviewCell]]
    offset: int
    next_offset: int | None
    row_count: int


@dataclass(frozen=True)
class DatasetArtifact:
    dataset_id: UUID
    version: UUID


@dataclass(frozen=True)
class ImportedDataset:
    metadata: DatasetMetadata
    sha256: str
    delimiter: Delimiter
    columns: tuple[CsvColumn, ...]

    def response(self) -> DatasetResponse:
        assert self.metadata.row_count is not None
        return DatasetResponse(
            **self.metadata.model_dump(exclude={"session_id", "row_count"}),
            row_count=self.metadata.row_count,
            sha256=self.sha256,
            delimiter=self.delimiter,
            columns=self.columns,
        )
