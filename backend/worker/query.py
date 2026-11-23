"""Fixed read-only operation for the W09 container boundary."""

import json
import sys

import duckdb


def count_rows() -> int:
    with duckdb.connect(
        "/input/data.duckdb",
        read_only=True,
        config={
            "threads": "1",
            "memory_limit": "128MB",
            "temp_directory": "/tmp/spill",
            "max_temp_directory_size": "32MB",
            "enable_external_access": "false",
            "allow_unsigned_extensions": "false",
            "allow_community_extensions": "false",
            "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false",
            "lock_configuration": "true",
        },
    ) as connection:
        row = connection.execute("SELECT count(*) FROM data").fetchone()
    if row is None:
        raise ValueError("Missing count result.")
    return int(row[0])


def main() -> int:
    try:
        sys.stdout.write(json.dumps({"schema_version": 1, "row_count": count_rows()}) + "\n")
        return 0
    except (duckdb.Error, OSError, ValueError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
