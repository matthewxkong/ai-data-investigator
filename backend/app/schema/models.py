from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

SchemaType = Literal["integer", "decimal", "boolean", "date", "datetime", "categorical", "text"]
DateOrder = Literal["mdy", "dmy"]
SafeName = Annotated[str, StringConstraints(pattern=r"^[a-z_][a-z0-9_]{0,62}$")]
WarningCode = Literal[
    "all_null",
    "mixed_types",
    "ambiguous_dates",
    "inconsistent_dates",
    "invalid_dates",
    "leading_zeros",
    "nonfinite_numbers",
    "long_values",
    "low_cardinality",
    "no_type_evidence",
    "timezone_unspecified",
]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SchemaWarning(Contract):
    code: WarningCode
    message: str


class TypeEvidence(Contract):
    integer_values: int = 0
    decimal_values: int = 0
    boolean_values: int = 0
    iso_date_values: int = 0
    mdy_date_values: int = 0
    dmy_date_values: int = 0
    datetime_values: int = 0


class TypeOverride(Contract):
    type: SchemaType
    date_order: DateOrder | None = None

    @model_validator(mode="after")
    def date_order_requires_date(self) -> Self:
        if self.date_order is not None and self.type != "date":
            raise ValueError("Date order is only valid for a date override.")
        return self


class OverrideRequest(Contract):
    expected_revision: Annotated[int, Field(strict=True, ge=0)]
    overrides: Annotated[dict[SafeName, TypeOverride], Field(max_length=256)]


class StoredOverrides(Contract):
    revision: int = 0
    overrides: dict[SafeName, TypeOverride] = Field(default_factory=dict)


class SchemaColumn(Contract):
    position: int
    original_name: str
    safe_name: str
    storage_type: Literal["VARCHAR"] = "VARCHAR"
    inferred_type: SchemaType
    effective_type: SchemaType
    type_source: Literal["inferred", "override"] = "inferred"
    date_order: DateOrder | None = None
    non_null_count: int
    null_count: int
    explanation: str
    evidence: TypeEvidence
    warnings: tuple[SchemaWarning, ...]
    override: TypeOverride | None = None


class SchemaResponse(Contract):
    dataset_id: UUID
    dataset_version: UUID
    source_sha256: str
    inference_version: Literal["1"] = "1"
    schema_revision: int
    rows_examined: int
    complete: Literal[True] = True
    columns: tuple[SchemaColumn, ...]
