from decimal import Decimal

from app.fixtures.inventory import WAREHOUSES, generate_inventory


def test_inventory_is_seeded_with_unique_sku_warehouse_pairs() -> None:
    table = generate_inventory()
    records = list(table.records())
    assert table.csv_bytes() == generate_inventory().csv_bytes()
    assert table.csv_bytes() != generate_inventory(7).csv_bytes()
    assert len(records) == len({(row["sku"], row["warehouse"]) for row in records}) == 72
    assert {row["warehouse"] for row in records} == set(WAREHOUSES)
    assert {row["snapshot_date"] for row in records} == {"2026-06-30"}


def test_inventory_quantities_costs_and_reorder_examples_are_valid() -> None:
    records = list(generate_inventory().records())
    costs: dict[str, set[Decimal]] = {}
    for row in records:
        on_hand, reserved = int(row["on_hand"]), int(row["reserved"])
        assert 0 <= reserved <= on_hand
        assert int(row["reorder_point"]) > 0
        cost = Decimal(row["unit_cost"])
        assert cost > 0
        assert cost.as_tuple().exponent == -2
        costs.setdefault(row["sku"], set()).add(cost)
    assert all(len(values) == 1 for values in costs.values())
    for warehouse in WAREHOUSES:
        assert any(row["warehouse"] == warehouse and row["on_hand"] == "0" for row in records)
