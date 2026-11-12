"""Development case contracts and an independent Python/Decimal answer oracle."""

from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from app.fixtures.common import FixtureTable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ReferenceScalar = StrictInt | StrictStr


class ReferenceCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^dev_[a-z_]+$")]
    dataset: Literal["sales", "tickets", "inventory"]
    question: str
    sql_file: Annotated[str, Field(pattern=r"^sql/dev_[a-z_]+[.]sql$")]
    columns: list[str] = Field(min_length=1)
    expected_rows: list[list[ReferenceScalar]]

    @model_validator(mode="after")
    def rectangular_result(self) -> "ReferenceCase":
        if any(len(row) != len(self.columns) for row in self.expected_rows):
            raise ValueError("Expected rows must match the result column count.")
        return self


class DevelopmentSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    generator_version: Literal[1]
    fixture_seed: int = Field(ge=0, le=2**32 - 1)
    split: Literal["development"]
    cases: list[ReferenceCase] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "DevelopmentSuite":
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Development case IDs must be unique.")
        return self


def load_development_suite() -> DevelopmentSuite:
    return DevelopmentSuite.model_validate_json(
        (PROJECT_ROOT / "evaluation" / "development" / "cases.json").read_text(encoding="utf-8")
    )


def development_answers(tables: tuple[FixtureTable, ...]) -> dict[str, list[list[ReferenceScalar]]]:
    """Calculate from generated records, independently of the checked-in SQL expressions."""
    records = {table.name: list(table.records()) for table in tables}
    sales = records["sales"]
    revenue_by_region: dict[str, Decimal] = defaultdict(Decimal)
    revenue_by_month: dict[str, Decimal] = defaultdict(Decimal)
    units: Counter[str] = Counter()
    for row in sales:
        revenue = int(row["quantity"]) * Decimal(row["unit_price"])
        revenue_by_region[row["region"]] += revenue
        revenue_by_month[row["order_date"][:7]] += revenue
        units[row["product"]] += int(row["quantity"])

    tickets = records["tickets"]
    priorities = Counter(row["priority"] for row in tickets)
    resolution_hours: Counter[str] = Counter()
    for row in tickets:
        if row["status"] == "resolved":
            resolution_hours[row["category"]] += int(row["resolution_hours"])

    reorder_counts: Counter[str] = Counter()
    stock_values: dict[str, Decimal] = defaultdict(Decimal)
    for row in records["inventory"]:
        if int(row["on_hand"]) - int(row["reserved"]) < int(row["reorder_point"]):
            reorder_counts[row["warehouse"]] += 1
        stock_values[row["warehouse"]] += int(row["on_hand"]) * Decimal(row["unit_cost"])

    return {
        "dev_sales_count": [[len(sales)]],
        "dev_sales_revenue": [[f"{sum(revenue_by_region.values(), Decimal()):.2f}"]],
        "dev_sales_regions": [
            [key, f"{value:.2f}"] for key, value in sorted(revenue_by_region.items())
        ],
        "dev_sales_months": [
            [key, f"{value:.2f}"] for key, value in sorted(revenue_by_month.items())
        ],
        "dev_sales_products": [
            [key, value]
            for key, value in sorted(units.items(), key=lambda item: (-item[1], item[0]))[:3]
        ],
        "dev_ticket_priorities": [[key, value] for key, value in sorted(priorities.items())],
        "dev_ticket_unresolved": [[sum(row["status"] != "resolved" for row in tickets)]],
        "dev_ticket_resolution_hours": [
            [key, value] for key, value in sorted(resolution_hours.items())
        ],
        "dev_inventory_reorder": [[key, value] for key, value in sorted(reorder_counts.items())],
        "dev_inventory_value": [
            [key, f"{value:.2f}"] for key, value in sorted(stock_values.items())
        ],
    }
