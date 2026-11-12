import csv
import io
import random
from datetime import date
from decimal import Decimal

from app.fixtures.sales import PRODUCTS, REGIONS, generate_sales


def test_sales_are_reproducible_without_changing_global_random_state() -> None:
    state = random.getstate()
    first = generate_sales()
    assert first.csv_bytes() == generate_sales().csv_bytes()
    assert first.csv_bytes() != generate_sales(7).csv_bytes()
    assert random.getstate() == state


def test_sales_cover_months_regions_and_valid_catalog_values() -> None:
    records = list(generate_sales().records())
    assert len(records) == 120
    assert len({row["order_id"] for row in records}) == 120
    assert {row["order_date"][:7] for row in records} == {
        f"2026-{month:02d}" for month in range(1, 7)
    }
    assert {row["region"] for row in records} == set(REGIONS)
    catalog = dict(PRODUCTS)
    for row in records:
        assert date.fromisoformat(row["order_date"]).year == 2026
        assert 1 <= int(row["quantity"]) <= 6
        assert Decimal(row["unit_price"]) == catalog[row["product"]]


def test_csv_round_trip_preserves_quoted_product_names_and_lf_bytes() -> None:
    table = generate_sales()
    content = table.csv_bytes()
    assert b"\r" not in content
    assert content.endswith(b"\n")
    records = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    assert records == list(table.records())
    assert any("," in row["product"] for row in records)
    assert any('"' in row["product"] for row in records)
