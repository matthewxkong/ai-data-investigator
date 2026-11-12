from decimal import Decimal
from random import Random

from app.fixtures.common import DEFAULT_SEED, FixtureTable

WAREHOUSES = ("North Hub", "Central Hub", "West Hub")


def generate_inventory(seed: int = DEFAULT_SEED) -> FixtureTable:
    rng = Random(seed + 2)
    rows: list[tuple[str, ...]] = []
    for index in range(24):
        cost = Decimal(rng.randint(250, 25000)) / 100
        reorder = rng.randint(5, 30)
        category = ("hardware", "accessories", "office")[index % 3]
        for warehouse in WAREHOUSES:
            on_hand = 0 if index == 0 else rng.randint(0, 120)
            reserved = rng.randint(0, min(on_hand, 15))
            rows.append(
                (
                    "2026-06-30",
                    f"SKU-{index + 1:03d}",
                    warehouse,
                    category,
                    str(on_hand),
                    str(reserved),
                    str(reorder),
                    f"{cost:.2f}",
                )
            )
    return FixtureTable(
        name="inventory",
        columns=(
            "snapshot_date",
            "sku",
            "warehouse",
            "category",
            "on_hand",
            "reserved",
            "reorder_point",
            "unit_cost",
        ),
        rows=tuple(rows),
    )
