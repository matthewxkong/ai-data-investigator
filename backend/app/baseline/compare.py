from decimal import Decimal, InvalidOperation, localcontext

from app.baseline.models import QueryResult, ResultColumn, ResultValue, Tolerance

APPROXIMATE_SQL_TYPES = {"FLOAT", "DOUBLE", "REAL"}


def matches_value(
    actual: ResultValue, expected: ResultValue, column: ResultColumn, tolerance: Tolerance
) -> bool:
    if type(actual) is type(expected) and actual == expected:
        return True
    if actual is None or expected is None or isinstance(actual, bool) or isinstance(expected, bool):
        return False
    if not (column.sql_type.startswith("DECIMAL(") or column.sql_type in APPROXIMATE_SQL_TYPES):
        return False
    try:
        actual_number = Decimal(str(actual))
        expected_number = Decimal(str(expected))
    except InvalidOperation:
        return False
    if not actual_number.is_finite() or not expected_number.is_finite():
        return False
    with localcontext() as context:
        context.prec = 80
        difference = abs(actual_number - expected_number)
        allowed = max(tolerance.absolute, abs(expected_number) * tolerance.relative)
        return difference <= allowed


def compare_result(
    result: QueryResult,
    expected_columns: list[str],
    expected_rows: list[list[ResultValue]],
    tolerance: Tolerance,
) -> str | None:
    if [column.name for column in result.columns] != expected_columns:
        return "Result column names or order differ."
    if not result.output_complete:
        return "Result exceeds the output row limit."
    if len(result.rows) != len(expected_rows):
        return f"Expected {len(expected_rows)} rows, received {len(result.rows)}."
    pairs = zip(result.rows, expected_rows, strict=True)
    for row_number, (actual, expected) in enumerate(pairs, 1):
        if len(actual) != len(result.columns) or len(expected) != len(result.columns):
            return f"Column count differs at row {row_number}."
        if any(
            not matches_value(value, target, column, tolerance)
            for value, target, column in zip(actual, expected, result.columns, strict=True)
        ):
            return f"Value differs at row {row_number}."
    return None
