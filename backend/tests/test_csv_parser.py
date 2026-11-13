import csv
from pathlib import Path

import pytest

from app.errors import ApiError
from app.fixtures.references import PROJECT_ROOT
from app.ingestion.parser import normalize_columns, parse_csv, validate_filename


def test_header_normalization_preserves_labels_and_resolves_collisions() -> None:
    originals = [" Café ", "cafe", "123", "名字", "select", "A" * 80, "a" * 80]
    columns = normalize_columns(originals)
    assert [column.original_name for column in columns] == originals
    assert [column.safe_name for column in columns[:5]] == [
        "cafe",
        "cafe_2",
        "col_123",
        "column_4",
        "col_select",
    ]
    assert len({column.safe_name for column in columns}) == len(columns)
    assert all(len(column.safe_name) <= 63 for column in columns)


@pytest.mark.parametrize("name", ["../source.csv", "C:\\source.csv", "source.txt", "%00.csv"])
def test_filenames_cannot_supply_paths_or_non_csv_extensions(name: str) -> None:
    with pytest.raises(ApiError):
        validate_filename(name)


def test_percent_encoded_filename_is_decoded_without_using_it_as_a_path() -> None:
    assert validate_filename("caf%C3%A9.csv") == "café.csv"


@pytest.mark.parametrize("source", sorted((PROJECT_ROOT / "fixtures" / "generated").glob("*.csv")))
def test_all_clean_and_quality_fixtures_parse_without_coercion(
    source: Path, tmp_path: Path
) -> None:
    canonical = tmp_path / "canonical.csv"
    result = parse_csv(source, canonical, max_rows=100_000, max_columns=256)
    with source.open(encoding="utf-8", newline="") as original:
        rows = list(csv.reader(original))
    with canonical.open(encoding="utf-8", newline="") as normalized:
        converted = list(csv.reader(normalized))
    assert result.row_count == len(rows) - 1
    assert converted[1:] == rows[1:]


def test_bom_semicolon_quoted_newline_and_blank_records(tmp_path: Path) -> None:
    source, canonical = tmp_path / "source.csv", tmp_path / "canonical.csv"
    source.write_bytes('\ufeffName;Note\r\n\r\n"A;B";"line 1\nline 2"\r\n'.encode())
    result = parse_csv(source, canonical, max_rows=10, max_columns=2, delimiter=";")
    assert result.row_count == 1
    with canonical.open(encoding="utf-8", newline="") as output:
        assert list(csv.reader(output)) == [["name", "note"], ["A;B", "line 1\nline 2"]]


@pytest.mark.parametrize(
    ("content", "rows", "columns", "code"),
    [
        (b"", 10, 10, "empty_csv"),
        (b"name\n", 10, 10, "empty_csv"),
        (b"a,b\n1\n", 10, 10, "inconsistent_columns"),
        (b'a,b\n"unclosed,2\n', 10, 10, "invalid_csv"),
        (b"a,b\n1,2\n", 10, 1, "too_many_columns"),
        (b"a\n1\n2\n", 1, 10, "too_many_rows"),
        (b"a\n\xff\n", 10, 10, "invalid_encoding"),
        (b"a\na\x00b\n", 10, 10, "invalid_csv"),
        (b" ,b\n1,2\n", 10, 10, "invalid_header"),
    ],
)
def test_invalid_inputs_leave_no_canonical_file(
    tmp_path: Path, content: bytes, rows: int, columns: int, code: str
) -> None:
    source, canonical = tmp_path / "source.csv", tmp_path / "canonical.csv"
    source.write_bytes(content)
    with pytest.raises(ApiError) as failure:
        parse_csv(source, canonical, max_rows=rows, max_columns=columns)
    assert failure.value.code == code
    assert not canonical.exists()
