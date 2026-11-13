import subprocess
from pathlib import Path

import duckdb
import pytest

from app.errors import ApiError
from app.ingestion.importer import run_controlled_import
from app.ingestion.parser import parse_csv
from app.ingestion.worker import restricted_connection


def test_controlled_process_preserves_text_nulls_and_literal_sql_cells(tmp_path: Path) -> None:
    source, canonical, database = (
        tmp_path / name for name in ("source.csv", "canonical.csv", "data.duckdb")
    )
    source.write_text('Identifier,Note\n001,"x\'); DROP TABLE data; --"\n002,\n', encoding="utf-8")
    parsed = parse_csv(source, canonical, max_rows=10, max_columns=2)
    run_controlled_import(canonical, database, parsed, timeout_seconds=30)
    with duckdb.connect(str(database), read_only=True) as connection:
        assert connection.execute("SELECT * FROM data ORDER BY identifier").fetchall() == [
            ("001", "x'); DROP TABLE data; --"),
            ("002", None),
        ]
        assert [row[1] for row in connection.execute("DESCRIBE data").fetchall()] == [
            "VARCHAR",
            "VARCHAR",
        ]


def test_import_connection_denies_unrelated_files_and_configuration_changes(tmp_path: Path) -> None:
    canonical, other = tmp_path / "canonical.csv", tmp_path / "unrelated.csv"
    canonical.write_text("value\n1\n", encoding="utf-8")
    other.write_text("secret\nprivate\n", encoding="utf-8")
    with restricted_connection(tmp_path / "data.duckdb", canonical) as connection:
        with pytest.raises(duckdb.Error):
            connection.execute("SELECT * FROM read_csv(?)", [str(other)])
        with pytest.raises(duckdb.Error):
            connection.execute("SET enable_external_access = true")


def test_existing_databases_are_not_overwritten(tmp_path: Path) -> None:
    source, canonical, database = (
        tmp_path / name for name in ("source.csv", "canonical.csv", "data.duckdb")
    )
    source.write_text("value\n1\n", encoding="utf-8")
    parsed = parse_csv(source, canonical, max_rows=10, max_columns=2)
    database.write_bytes(b"preserve")
    with pytest.raises(ApiError):
        run_controlled_import(canonical, database, parsed, timeout_seconds=30)
    assert database.read_bytes() == b"preserve"


def test_timeout_is_actionable_and_child_does_not_inherit_provider_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, canonical = tmp_path / "source.csv", tmp_path / "canonical.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    parsed = parse_csv(source, canonical, max_rows=10, max_columns=2)
    monkeypatch.setenv("ADI_MODEL_API_KEY", "private-provider-key")

    def timeout(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        assert "ADI_MODEL_API_KEY" not in environment
        raise subprocess.TimeoutExpired("worker", 0.01)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(ApiError) as failure:
        run_controlled_import(canonical, tmp_path / "data.duckdb", parsed, timeout_seconds=0.01)
    assert failure.value.code == "import_timeout"
