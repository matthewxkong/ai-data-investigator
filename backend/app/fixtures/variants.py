from dataclasses import dataclass
from typing import Literal

from app.fixtures.common import FixtureTable

VariantKind = Literal["nulls", "duplicates", "mixed_types"]


@dataclass(frozen=True)
class CellChange:
    data_row: int
    column: str
    before: str
    after: str


@dataclass(frozen=True)
class FixtureVariant:
    table: FixtureTable
    source_dataset: str
    kind: VariantKind
    changes: tuple[CellChange, ...] = ()
    duplicate_source_rows: tuple[int, ...] = ()


NULL_COLUMNS = {
    "sales": ("quantity", "unit_price", "order_date"),
    "tickets": ("category", "priority", "created_at"),
    "inventory": ("unit_cost", "warehouse", "reorder_point"),
}
MIXED_VALUES = {
    "sales": (("quantity", "many"), ("unit_price", "$19.95"), ("order_date", "03/04/2026")),
    "tickets": (
        ("resolution_hours", "unknown"),
        ("resolution_hours", "48 hours"),
        ("created_at", "04/05/2026 10:00"),
    ),
    "inventory": (
        ("on_hand", "many"),
        ("unit_cost", "$12.50"),
        ("snapshot_date", "06/07/2026"),
    ),
}


def _edited_variant(
    source: FixtureTable,
    kind: VariantKind,
    replacements: tuple[tuple[int, str, str], ...],
) -> FixtureVariant:
    rows = [list(row) for row in source.rows]
    changes = []
    for index, column, value in replacements:
        column_index = source.columns.index(column)
        changes.append(CellChange(index + 1, column, rows[index][column_index], value))
        rows[index][column_index] = value
    return FixtureVariant(
        table=FixtureTable(
            name=f"{source.name}_{kind}",
            columns=source.columns,
            rows=tuple(tuple(row) for row in rows),
        ),
        source_dataset=source.name,
        kind=kind,
        changes=tuple(changes),
    )


def generate_variants(source: FixtureTable) -> tuple[FixtureVariant, ...]:
    if source.name not in NULL_COLUMNS or len(source.rows) < 18:
        raise ValueError("Variants require a known clean dataset with at least 18 rows.")
    nulls = _edited_variant(
        source,
        "nulls",
        tuple(
            (index, column, "")
            for index, column in zip((3, 11, 17), NULL_COLUMNS[source.name], strict=True)
        ),
    )
    duplicates = FixtureVariant(
        table=FixtureTable(
            name=f"{source.name}_duplicates",
            columns=source.columns,
            rows=(*source.rows, source.rows[0], source.rows[7]),
        ),
        source_dataset=source.name,
        kind="duplicates",
        duplicate_source_rows=(1, 8),
    )
    mixed = _edited_variant(
        source,
        "mixed_types",
        tuple(
            (index, column, value)
            for index, (column, value) in zip((2, 10, 16), MIXED_VALUES[source.name], strict=True)
        ),
    )
    return nulls, duplicates, mixed
