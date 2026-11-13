"""Validate CSV incrementally and produce a canonical, text-preserving import source."""

import csv
import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast
from urllib.parse import unquote_to_bytes

from app.errors import ApiError
from app.ingestion.models import CsvColumn, Delimiter

MAX_FIELD_CHARACTERS = 131_072
MAX_LINE_CHARACTERS = 1_048_576
RESERVED_NAMES = {"select", "from", "where", "table", "order", "group", "by", "limit", "null"}


@dataclass(frozen=True)
class ParsedCsv:
    columns: tuple[CsvColumn, ...]
    delimiter: Delimiter
    row_count: int


def validate_filename(value: str) -> str:
    try:
        name = unicodedata.normalize("NFC", unquote_to_bytes(value).decode("utf-8")).strip()
    except UnicodeDecodeError:
        raise ApiError(
            400, "invalid_filename", "X-Filename must be UTF-8 percent-encoded."
        ) from None
    if (
        not 1 <= len(name) <= 255
        or any(ord(character) < 32 for character in name)
        or "/" in name
        or "\\" in name
        or not name.lower().endswith(".csv")
    ):
        raise ApiError(400, "invalid_filename", "Use a CSV filename without directory components.")
    return name


def normalize_columns(headers: list[str]) -> tuple[CsvColumn, ...]:
    result = []
    used: set[str] = set()
    for index, original in enumerate(headers):
        if not original.strip() or len(original) > 256 or any(ord(char) < 32 for char in original):
            raise ApiError(
                400, "invalid_header", "Headers must be nonblank, at most 256 characters, and text."
            )
        ascii_name = unicodedata.normalize("NFKD", original).encode("ascii", "ignore").decode()
        base = re.sub(r"[^a-z0-9_]+", "_", ascii_name.lower()).strip("_")
        if not base:
            base = f"column_{index + 1}"
        if base[0].isdigit() or base in RESERVED_NAMES:
            base = f"col_{base}"
        base = base[:63]
        candidate, number = base, 2
        while candidate in used:
            suffix = f"_{number}"
            candidate = base[: 63 - len(suffix)] + suffix
            number += 1
        used.add(candidate)
        result.append(CsvColumn(position=index, original_name=original, safe_name=candidate))
    return tuple(result)


def bounded_lines(source: TextIO) -> Iterator[str]:
    while line := source.readline(MAX_LINE_CHARACTERS + 1):
        if len(line) > MAX_LINE_CHARACTERS:
            raise ApiError(
                413, "csv_line_too_long", "A CSV physical line exceeds 1048576 characters."
            )
        yield line


def parse_csv(
    source: Path,
    canonical: Path,
    *,
    max_rows: int,
    max_columns: int,
    delimiter: Delimiter | None = None,
) -> ParsedCsv:
    created = False
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as input_file:
            if delimiter is None:
                sample = input_file.read(65_536)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                    delimiter = cast(Delimiter, dialect.delimiter)
                except csv.Error:
                    delimiter = ","
                input_file.seek(0)
            reader = csv.reader(bounded_lines(input_file), delimiter=delimiter, strict=True)
            headers = next((row for row in reader if row), None)
            if headers is None:
                raise ApiError(
                    400, "empty_csv", "CSV must contain a header and at least one data row."
                )
            if len(headers) > max_columns:
                raise ApiError(
                    413, "too_many_columns", f"CSV exceeds the {max_columns}-column limit."
                )
            columns = normalize_columns(headers)
            with canonical.open("x", encoding="utf-8", newline="") as output:
                created = True
                writer = csv.writer(output, lineterminator="\n")
                writer.writerow([column.safe_name for column in columns])
                count = 0
                for row in reader:
                    if not row:
                        continue
                    if len(row) != len(columns):
                        raise ApiError(
                            400,
                            "inconsistent_columns",
                            "Every data row must match the header width.",
                        )
                    if any("\x00" in cell for cell in row):
                        raise ApiError(400, "invalid_csv", "CSV cannot contain NUL characters.")
                    if any(len(cell) > MAX_FIELD_CHARACTERS for cell in row):
                        raise ApiError(
                            413, "csv_field_too_long", "A CSV field exceeds 131072 characters."
                        )
                    if count >= max_rows:
                        raise ApiError(
                            413, "too_many_rows", f"CSV exceeds the {max_rows}-row limit."
                        )
                    writer.writerow(row)
                    count += 1
                if count == 0:
                    raise ApiError(400, "empty_csv", "CSV must contain at least one data row.")
            return ParsedCsv(columns=columns, delimiter=delimiter, row_count=count)
    except BaseException as error:
        if created:
            canonical.unlink(missing_ok=True)
        if isinstance(error, UnicodeDecodeError):
            raise ApiError(400, "invalid_encoding", "Only UTF-8 CSV files are supported.") from None
        if isinstance(error, csv.Error):
            if "field larger than field limit" in str(error):
                raise ApiError(
                    413, "csv_field_too_long", "A CSV field exceeds 131072 characters."
                ) from None
            raise ApiError(
                400, "invalid_csv", "CSV quoting or record structure is malformed."
            ) from None
        raise
