"""Execute only parsed, compiled operations in the Linux worker."""

import json
import math
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import duckdb

from worker.policy import MAX_CELL, MAX_OUTPUT, MAX_ROWS, MAX_SQL, parse_select


@contextmanager
def connect() -> Iterator[duckdb.DuckDBPyConnection]:
    config: dict[str, str | bool | int | float | list[str]] = {
        "threads": "1",
        "memory_limit": "128MB",
        "allow_unsigned_extensions": "false",
        "allow_community_extensions": "false",
        "autoinstall_known_extensions": "false",
        "autoload_known_extensions": "false",
    }
    with duckdb.connect("/input/data.duckdb", read_only=True, config=config) as connection:
        connection.execute("SET temp_directory = '/tmp/spill'")
        connection.execute("SET max_temp_directory_size = '32MB'")
        connection.execute("SET enable_external_access = false")
        connection.execute("SET lock_configuration = true")
        yield connection


def count_rows() -> int:
    with connect() as connection:
        row = connection.execute("SELECT count(*) FROM data").fetchone()
    if row is None:
        raise ValueError("Missing count result.")
    return int(row[0])


def cell(value: object) -> tuple[object, bool]:
    if value is None or isinstance(value, (bool, int)):
        return value, False
    if isinstance(value, float):
        return (value, False) if math.isfinite(value) else (None, True)
    if isinstance(value, (date, datetime)):
        return value.isoformat(), False
    if isinstance(value, Decimal):
        return format(value, "f"), False
    if isinstance(value, str):
        return value[:MAX_CELL], len(value) > MAX_CELL
    raise ValueError("Unsupported result value.")


def encode(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode("ascii")


def select_rows(sql: str) -> bytes:
    with connect() as connection:
        columns = {
            field[0] for field in connection.execute("SELECT * FROM data LIMIT 0").description
        }
        statement, parameters = parse_select(sql, columns).compile()
        result = connection.execute(statement, parameters)
        names = [field[0] for field in result.description]
        envelope: dict[str, object] = {
            "schema_version": 1,
            "columns": [name[:MAX_CELL] for name in names],
            "rows": [],
            "truncated": any(len(name) > MAX_CELL for name in names),
        }
        rows: list[list[object]] = []
        size = len(encode(envelope)) + 8
        truncated = bool(envelope["truncated"])
        for index, row in enumerate(result.fetchmany(MAX_ROWS + 1)):
            converted = [cell(value) for value in row]
            values = [value for value, _ in converted]
            size += len(encode(values)) + 1
            if index == MAX_ROWS or size > MAX_OUTPUT:
                truncated = True
                break
            rows.append(values)
            truncated = truncated or any(clipped for _, clipped in converted)
        envelope.update(rows=rows, truncated=truncated)
        return encode(envelope)


def main() -> int:
    try:
        if sys.argv[1:] == ["select"]:
            header = sys.stdin.buffer.read(4)
            size = int.from_bytes(header, "big")
            if len(header) != 4 or not 1 <= size <= MAX_SQL * 4:
                return 1
            request = sys.stdin.buffer.read(size)
            if len(request) != size:
                return 1
            sys.stdout.buffer.write(select_rows(request.decode("utf-8")))
        elif not sys.argv[1:]:
            sys.stdout.buffer.write(encode({"schema_version": 1, "row_count": count_rows()}))
        else:
            return 1
        return 0
    except (duckdb.Error, OSError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
