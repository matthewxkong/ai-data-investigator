from collections.abc import Callable

import pytest

from app.fixtures.common import FixtureTable
from app.fixtures.inventory import generate_inventory
from app.fixtures.sales import generate_sales
from app.fixtures.tickets import generate_tickets
from app.fixtures.variants import generate_variants


@pytest.mark.parametrize("generator", [generate_sales, generate_tickets, generate_inventory])
def test_quality_variants_are_precise_and_do_not_mutate_clean_data(
    generator: Callable[[], FixtureTable],
) -> None:
    clean = generator()
    original = clean.csv_bytes()
    variants = generate_variants(clean)
    assert {variant.kind for variant in variants} == {"nulls", "duplicates", "mixed_types"}
    for variant in variants:
        assert variant.table.columns == clean.columns
        if variant.kind == "duplicates":
            assert variant.table.rows[: len(clean.rows)] == clean.rows
            assert variant.table.rows[-2:] == (clean.rows[0], clean.rows[7])
            assert variant.duplicate_source_rows == (1, 8)
        else:
            assert len(variant.table.rows) == len(clean.rows)
            actual_changes = {
                (index + 1, column, before, after)
                for index, (old_row, new_row) in enumerate(
                    zip(clean.rows, variant.table.rows, strict=True)
                )
                for column, before, after in zip(clean.columns, old_row, new_row, strict=True)
                if before != after
            }
            assert len(actual_changes) == 3
            assert actual_changes == {
                (change.data_row, change.column, change.before, change.after)
                for change in variant.changes
            }
            assert all(change.before for change in variant.changes)
            if variant.kind == "nulls":
                assert all(change.after == "" for change in variant.changes)
    assert clean.csv_bytes() == original
