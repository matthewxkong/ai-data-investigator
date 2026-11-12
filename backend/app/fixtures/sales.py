from datetime import date
from decimal import Decimal
from random import Random

from app.fixtures.common import DEFAULT_SEED, FixtureTable

REGIONS = ("North", "South", "East", "West")
PRODUCTS = (
    ("Notebook, A5", Decimal("19.95")),
    ("Monitor", Decimal("229.00")),
    ('Keyboard "Pro"', Decimal("79.50")),
    ("Mouse", Decimal("24.99")),
)


def generate_sales(seed: int = DEFAULT_SEED) -> FixtureTable:
    rng = Random(seed)
    rows: list[tuple[str, ...]] = []
    for month in range(1, 7):
        for region in REGIONS:
            for _ in range(5):
                product, unit_price = rng.choice(PRODUCTS)
                rows.append(
                    (
                        f"S{len(rows) + 1:04d}",
                        date(2026, month, rng.randint(1, 28)).isoformat(),
                        region,
                        product,
                        str(rng.randint(1, 6)),
                        f"{unit_price:.2f}",
                    )
                )
    return FixtureTable(
        name="sales",
        columns=("order_id", "order_date", "region", "product", "quantity", "unit_price"),
        rows=tuple(rows),
    )
