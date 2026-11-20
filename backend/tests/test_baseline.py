import asyncio
import hashlib
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.baseline.compare import compare_result
from app.baseline.execution import DEVELOPMENT_ROOT, FIXTURE_ROOT, normalize_value
from app.baseline.models import QueryResult, ResultColumn, Tolerance
from app.baseline.runner import REPORT_PATH, report_text, run_baseline
from app.fixtures.references import load_development_suite


def test_report_reproduces_the_checked_in_answers_and_evidence() -> None:
    report = asyncio.run(run_baseline(Tolerance()))
    suite = load_development_suite()
    assert report.passed and len(report.cases) == 10
    assert report_text(report).encode("utf-8") == REPORT_PATH.read_bytes()
    for actual, case in zip(report.cases, suite.cases, strict=True):
        assert actual.case_id == case.id and actual.passed
        assert actual.result.rows == case.expected_rows
        assert actual.result.output_complete and not actual.result.truncated
        source = (FIXTURE_ROOT / f"{case.dataset}.csv").read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        assert actual.evidence.source_sha256 == digest
        assert actual.evidence.dataset_version == f"fixture-v1:{digest}"
        sql = (DEVELOPMENT_ROOT / case.sql_file).read_text(encoding="utf-8")
        assert actual.evidence.sql_sha256 == hashlib.sha256(sql.encode("utf-8")).hexdigest()
        assert (
            actual.evidence.result_sha256
            == hashlib.sha256(actual.result.model_dump_json().encode("utf-8")).hexdigest()
        )


def test_truncation_is_disclosed_and_fails_comparison() -> None:
    report = asyncio.run(run_baseline(Tolerance(), row_limit=1))
    cases = {case.case_id: case for case in report.cases}
    scalar = cases["dev_sales_count"]
    grouped = cases["dev_sales_regions"]
    assert not report.passed
    assert scalar.passed and scalar.result.output_complete
    assert not grouped.passed and not grouped.result.output_complete
    assert grouped.result.truncated and len(grouped.result.rows) == 1
    assert grouped.mismatch == "Result exceeds the output row limit."
    assert scalar.evidence.dataset_version == grouped.evidence.dataset_version


def test_normalization_preserves_decimal_precision_dates_nulls_and_text() -> None:
    assert normalize_value(Decimal("123456789012345678.10")) == "123456789012345678.10"
    assert normalize_value(date(2026, 11, 19)) == "2026-11-19"
    stamp = datetime(2026, 11, 19, 12, tzinfo=timezone(timedelta(hours=-5)))
    assert normalize_value(stamp) == datetime(2026, 11, 19, 17, tzinfo=UTC).isoformat()
    assert normalize_value(None) is None
    assert normalize_value("001") == "001"
    for value in (float("nan"), float("inf"), Decimal("NaN"), {"key": "value"}):
        with pytest.raises(ValueError, match="unsupported or non-finite"):
            normalize_value(value)


def test_tolerance_applies_only_to_decimal_and_float_columns() -> None:
    columns = [
        ResultColumn(name="total", sql_type="DECIMAL(18,2)"),
        ResultColumn(name="label", sql_type="VARCHAR"),
        ResultColumn(name="count", sql_type="BIGINT"),
        ResultColumn(name="sample", sql_type="DOUBLE"),
    ]
    result = QueryResult(
        columns=columns,
        rows=[["100.10", "001", 7, 0.001]],
        row_limit=1,
        truncated=False,
        output_complete=True,
    )
    names = [column.name for column in columns]
    assert compare_result(result, names, [["100.00", "001", 7, 0]], Tolerance()) is not None
    tolerance = Tolerance(absolute=Decimal("0.001"), relative=Decimal("0.001"))
    assert compare_result(result, names, [["100.00", "001", 7, 0]], tolerance) is None
    assert compare_result(result, names, [["100.00", "1", 7, 0]], tolerance) is not None
    assert compare_result(result, names, [["100.00", "001", 7.0, 0]], tolerance) is not None
    assert compare_result(result, names, [["100.00", "001", 7, None]], tolerance) is not None
    assert compare_result(result, names[::-1], result.rows, tolerance) is not None
