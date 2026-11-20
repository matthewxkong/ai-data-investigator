import math
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from app.baseline.models import (
    MAX_RESULT_ROWS,
    FixtureName,
    QueryResult,
    ResultColumn,
    ResultValue,
)
from app.config import Settings
from app.fixtures.references import PROJECT_ROOT, ReferenceCase
from app.ingestion.models import ImportedDataset
from app.schema.inspection import read_artifact
from app.services import Services, create_services

DEVELOPMENT_ROOT = PROJECT_ROOT / "evaluation" / "development"
FIXTURE_ROOT = PROJECT_ROOT / "fixtures" / "generated"

CASTS: dict[FixtureName, dict[str, str]] = {
    "sales": {"order_date": "DATE", "quantity": "INTEGER", "unit_price": "DECIMAL(18,2)"},
    "tickets": {"resolution_hours": "INTEGER"},
    "inventory": {
        "snapshot_date": "DATE",
        "on_hand": "INTEGER",
        "reserved": "INTEGER",
        "reorder_point": "INTEGER",
        "unit_cost": "DECIMAL(18,2)",
    },
}


def fixture_services(data_dir: Path) -> Services:
    services = create_services(Settings.model_construct(environment="test", data_dir=data_dir))
    services.database.initialize()
    return services


async def import_fixture(
    services: Services, dataset: FixtureName, fixture_bytes: bytes
) -> ImportedDataset:
    async def body() -> AsyncIterator[bytes]:
        yield fixture_bytes

    imported, _ = await services.ingestion.ingest(
        body(), filename=f"{dataset}.csv", token=None, declared_length=None, delimiter=","
    )
    return imported


def normalize_value(value: object) -> ResultValue:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal) and value.is_finite():
        return format(value, "f")
    if isinstance(value, float) and math.isfinite(value):
        return 0.0 if value == 0 else value
    if isinstance(value, datetime):
        timestamp = value.astimezone(UTC) if value.tzinfo is not None else value
        return timestamp.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    raise ValueError("Reference query returned an unsupported or non-finite value.")


def run_reference(
    database: Path, imported: ImportedDataset, case: ReferenceCase, *, row_limit: int
) -> tuple[bytes, QueryResult]:
    if not 1 <= row_limit <= MAX_RESULT_ROWS:
        raise ValueError("Reference query row limit is out of range.")
    sql = (DEVELOPMENT_ROOT / case.sql_file).read_text(encoding="utf-8")
    casts = CASTS[case.dataset]
    fields = [f"CAST({name} AS {sql_type}) AS {name}" for name, sql_type in casts.items()]
    replaced = ", ".join(fields)
    with read_artifact(database, imported) as connection:
        connection.execute(
            f"CREATE TEMP VIEW {case.dataset} AS SELECT * REPLACE ({replaced}) FROM data"
        )
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise ValueError("Reference query must return a relation.")
        columns = [
            ResultColumn(name=field[0], sql_type=str(field[1])) for field in cursor.description
        ]
        raw_rows = cursor.fetchmany(row_limit + 1)
    truncated = len(raw_rows) > row_limit
    return sql.encode("utf-8"), QueryResult(
        columns=columns,
        rows=[[normalize_value(value) for value in row] for row in raw_rows[:row_limit]],
        row_limit=row_limit,
        truncated=truncated,
        output_complete=not truncated,
    )
