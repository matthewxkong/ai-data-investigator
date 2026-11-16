import pytest

from app.ingestion.models import CsvColumn
from app.schema.inference import ColumnEvidence
from app.schema.models import TypeOverride


def observed(values: list[str | None]) -> ColumnEvidence:
    evidence = ColumnEvidence()
    for value in values:
        evidence.observe(value)
    return evidence


@pytest.mark.parametrize(
    ("values", "kind", "warning", "order"),
    [
        (["1", "-2", "+3", None], "integer", None, None),
        (["0", "1"], "integer", None, None),
        (["1", "1.20", "-2.5e2", ".5"], "decimal", None, None),
        (["true", "FALSE", "yes", "No"], "boolean", None, None),
        (["001", "002"], "text", "leading_zeros", None),
        (["1", "many"], "text", "mixed_types", None),
        (["true", "1"], "text", "mixed_types", None),
        (["1.1", "NaN"], "text", "nonfinite_numbers", None),
        (["Infinity", "-inf"], "text", "nonfinite_numbers", None),
        (["1,000", "$5.00"], "text", "no_type_evidence", None),
        ([" 1", "2"], "text", "mixed_types", None),
        (["１２", "٣"], "text", "no_type_evidence", None),
        ([None, None], "text", "all_null", None),
        (["A", "B"] * 5, "categorical", "low_cardinality", None),
        (["A", "B"] * 4, "text", "no_type_evidence", None),
        ([str(i) + "x" for i in range(21)] * 5, "text", "no_type_evidence", None),
        (["2024-02-29", "2026-11-16"], "date", None, None),
        (["2026-02-29", "2026-11-16"], "text", "invalid_dates", None),
        (["03/04/2026", "04/05/2026"], "text", "ambiguous_dates", None),
        (["2026-11-16", "03/04/2026"], "text", "ambiguous_dates", None),
        (["13/04/2026", "03/04/2026"], "date", None, "dmy"),
        (["04/13/2026", "2026-11-16"], "date", None, "mdy"),
        (["13/04/2026", "04/13/2026"], "text", "inconsistent_dates", None),
        (["31/02/2026"], "text", "invalid_dates", None),
        (["20261116", "20260101"], "integer", None, None),
        (["2026-11-16T10:00:00Z", "2026-11-16T12:00:00+02:00"], "datetime", None, None),
        (["2026-11-16 10:00:00.123456"], "datetime", "timezone_unspecified", None),
        (["2026-02-30T10:00:00Z"], "text", "invalid_dates", None),
        (["2026-11-16T25:00:00Z"], "text", "invalid_dates", None),
        (["2026-11-16", "2026-11-16T10:00:00Z"], "text", "mixed_types", None),
        (["1" * 257], "text", "long_values", None),
    ],
)
def test_conservative_types_and_explanations(values, kind, warning, order) -> None:
    evidence = observed(values)
    inferred, date_order, explanation, warnings = evidence.infer()
    assert inferred == kind and date_order == order and explanation
    assert warning is None or warning in {item.code for item in warnings}
    assert evidence.present + evidence.nulls == len(values)


@pytest.mark.parametrize(
    ("values", "override", "accepted"),
    [
        (["001", "002"], {"type": "integer"}, True),
        (["1", "1.5"], {"type": "integer"}, False),
        (["1", "1.5"], {"type": "decimal"}, True),
        (["NaN"], {"type": "decimal"}, False),
        (["yes", "0", "1"], {"type": "boolean"}, True),
        (["2"], {"type": "boolean"}, False),
        (["03/04/2026"], {"type": "date"}, False),
        (["03/04/2026"], {"type": "date", "date_order": "dmy"}, True),
        (["13/04/2026"], {"type": "date", "date_order": "mdy"}, False),
        (["13/04/2026"], {"type": "date"}, True),
        (["2026-02-30"], {"type": "date"}, False),
        (["2026-11-16T10:00:00Z"], {"type": "datetime"}, True),
        (["2026-11-16"], {"type": "datetime"}, False),
        ([None], {"type": "integer"}, True),
        (["anything"], {"type": "categorical"}, True),
        (["anything"], {"type": "text"}, True),
    ],
)
def test_overrides_validate_every_non_null_value(values, override, accepted) -> None:
    assert observed(values).accepts(TypeOverride.model_validate(override)) is accepted


def test_evidence_is_order_independent_and_retains_no_raw_cells() -> None:
    values = ["PRIVATE CELL " + str(i) for i in range(30)] + [None]
    forward = observed(values)
    backward = observed(list(reversed(values)))
    # Distinct storage is capped, so only the size (not which digests) affects inference.
    assert len(forward.distinct) == len(backward.distinct) == 21
    assert forward.infer() == backward.infer()
    assert "PRIVATE CELL" not in repr(forward)
    column = forward.column(CsvColumn(position=0, original_name="Label", safe_name="label"), None)
    assert "PRIVATE CELL" not in column.model_dump_json()
    assert (column.original_name, column.safe_name, column.storage_type) == (
        "Label",
        "label",
        "VARCHAR",
    )
