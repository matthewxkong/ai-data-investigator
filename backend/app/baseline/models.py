from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr

ResultValue = StrictInt | StrictFloat | StrictStr | None
FixtureName = Literal["sales", "tickets", "inventory"]
MAX_RESULT_ROWS = 1_000


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class ResultColumn(Contract):
    name: str
    sql_type: str


class QueryResult(Contract):
    columns: list[ResultColumn]
    rows: list[list[ResultValue]]
    row_limit: int = Field(ge=1, le=MAX_RESULT_ROWS)
    truncated: bool


class QueryEvidence(Contract):
    dataset: FixtureName
    dataset_version: str
    source_sha256: str
    sql_sha256: str
    result_sha256: str


class Tolerance(Contract):
    absolute: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)
    relative: Decimal = Field(default=Decimal(0), ge=0, allow_inf_nan=False)


class CaseResult(Contract):
    case_id: str
    question: str
    evidence: QueryEvidence
    result: QueryResult
    expected_columns: list[str]
    expected_rows: list[list[ResultValue]]
    passed: bool
    mismatch: str | None


class BaselineReport(Contract):
    schema_version: Literal[1] = 1
    suite: Literal["development"] = "development"
    fixture_seed: int
    fixture_generator_version: int
    duckdb_version: str
    tolerance: Tolerance
    cases: list[CaseResult]
    passed: bool
