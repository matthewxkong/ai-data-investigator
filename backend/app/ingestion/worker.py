"""Fixed-operation CSV importer. This is not the future arbitrary-query sandbox."""

import argparse
import json
import re
from pathlib import Path

import duckdb


def restricted_connection(database: Path, canonical: Path) -> duckdb.DuckDBPyConnection:
    if database.exists() or database.parent.resolve() != canonical.parent.resolve():
        raise ValueError("Importer requires a fresh database in its private staging directory.")
    connection = duckdb.connect(
        str(database),
        config={
            "threads": "1",
            "memory_limit": "256MB",
            "max_temp_directory_size": "256MB",
            "temp_directory": str(database.parent / "spill"),
            "autoload_known_extensions": "false",
            "autoinstall_known_extensions": "false",
            "allow_community_extensions": "false",
        },
    )
    try:
        connection.execute("SET enable_progress_bar = false")
        connection.execute("SET allowed_paths = ?", [[str(canonical.resolve())]])
        connection.execute("SET enable_external_access = false")
        connection.execute("SET lock_configuration = true")
    except BaseException:
        connection.close()
        raise
    return connection


def import_csv(canonical: Path, database: Path, columns: list[str], expected_rows: int) -> int:
    if not 1 <= len(columns) <= 256 or any(
        re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", column) is None for column in columns
    ):
        raise ValueError("Importer column identifiers are invalid.")
    with restricted_connection(database, canonical) as connection:
        connection.execute(
            "CREATE TABLE data AS SELECT * FROM read_csv(?, columns = ?, header = true, "
            "auto_detect = false, delim = ',', nullstr = '', encoding = 'utf-8', "
            "strict_mode = true, parallel = false)",
            [str(canonical), dict.fromkeys(columns, "VARCHAR")],
        )
        row = connection.execute("SELECT COUNT(*) FROM data").fetchone()
        if row is None or row[0] != expected_rows:
            raise ValueError("Imported row count differs from validated CSV.")
        return int(row[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical", type=Path)
    parser.add_argument("database", type=Path)
    parser.add_argument("specification", type=Path)
    options = parser.parse_args()
    try:
        specification = json.loads(options.specification.read_text(encoding="utf-8"))
        count = import_csv(
            options.canonical,
            options.database,
            specification["columns"],
            specification["row_count"],
        )
        print(json.dumps({"ok": True, "row_count": count}))
        return 0
    except Exception:
        # Do not echo DuckDB/parser exceptions: they can contain raw cells or private paths.
        print(json.dumps({"ok": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
