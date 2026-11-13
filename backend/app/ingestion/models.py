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


class DatasetResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    version: UUID
    name: str
    byte_count: int
    row_count: int
    created_at: AwareDatetime
    sha256: str
    delimiter: Delimiter
    columns: tuple[CsvColumn, ...]


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
