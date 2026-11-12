from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from app.fixtures.inventory import generate_inventory
from app.fixtures.references import (
    PROJECT_ROOT,
    ReferenceCase,
    development_answers,
    load_development_suite,
)
from app.fixtures.sales import generate_sales
from app.fixtures.tickets import generate_tickets

TABLE_TYPES = {
    "sales": {
        "order_id": "VARCHAR",
        "order_date": "DATE",
        "region": "VARCHAR",
        "product": "VARCHAR",
        "quantity": "INTEGER",
        "unit_price": "DECIMAL(18,2)",
    },
    "tickets": {
        "ticket_id": "VARCHAR",
        "created_at": "VARCHAR",
        "resolved_at": "VARCHAR",
        "status": "VARCHAR",
        "priority": "VARCHAR",
        "category": "VARCHAR",
        "assigned_team": "VARCHAR",
        "resolution_hours": "INTEGER",
        "customer_tier": "VARCHAR",
    },
    "inventory": {
        "snapshot_date": "DATE",
        "sku": "VARCHAR",
        "warehouse": "VARCHAR",
        "category": "VARCHAR",
        "on_hand": "INTEGER",
        "reserved": "INTEGER",
        "reorder_point": "INTEGER",
        "unit_cost": "DECIMAL(18,2)",
    },
}


@pytest.mark.parametrize("case", load_development_suite().cases, ids=lambda case: case.id)
def test_reference_sql_matches_fixed_answers_and_independent_decimal_oracle(
    case: ReferenceCase, tmp_path: Path
) -> None:
    suite = load_development_suite()
    tables = (
        generate_sales(suite.fixture_seed),
        generate_tickets(suite.fixture_seed),
        generate_inventory(suite.fixture_seed),
    )
    assert case.expected_rows == development_answers(tables)[case.id]
    table = next(table for table in tables if table.name == case.dataset)
    path = tmp_path / f"{table.name}.csv"
    path.write_bytes(table.csv_bytes())
    with duckdb.connect(":memory:") as connection:
        connection.read_csv(
            str(path), columns=TABLE_TYPES[table.name], header=True, auto_detect=False
        ).create_view(table.name)
        sql = (PROJECT_ROOT / "evaluation" / "development" / case.sql_file).read_text("utf-8")
        result = connection.execute(sql)
        assert result.description is not None
        assert [column[0] for column in result.description] == case.columns
        normalized = [
            [f"{value:.2f}" if isinstance(value, Decimal) else value for value in row]
            for row in result.fetchall()
        ]
        assert normalized == case.expected_rows


def test_development_suite_has_ten_cases_with_fixed_default_seed() -> None:
    suite = load_development_suite()
    assert suite.fixture_seed == 20261112
    assert len(suite.cases) == 10
    assert {case.dataset for case in suite.cases} == {"sales", "tickets", "inventory"}
