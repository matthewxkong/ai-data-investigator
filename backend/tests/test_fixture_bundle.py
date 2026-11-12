import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from app.fixtures.bundle import generate_bundle
from app.fixtures.common import DEFAULT_SEED
from app.fixtures.references import PROJECT_ROOT


def run_cli(
    output: Path, *arguments: str, hash_seed: str = "1"
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
    return subprocess.run(
        [sys.executable, "-m", "app.fixtures", "--output", str(output), *arguments],
        cwd=PROJECT_ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_manifest_hashes_counts_and_csv_fields_match_actual_bytes() -> None:
    files = generate_bundle()
    manifest = json.loads(files["manifest.json"])
    assert len(files) == 13
    assert manifest["seed"] == DEFAULT_SEED
    assert len(manifest["files"]) == 12
    assert len({entry["file"] for entry in manifest["files"]}) == 12
    for entry in manifest["files"]:
        content = files[entry["file"]]
        assert hashlib.sha256(content).hexdigest() == entry["sha256"]
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        assert reader.fieldnames == entry["columns"]
        rows = list(reader)
        assert len(rows) == entry["row_count"]
        assert all(None not in row and None not in row.values() for row in rows)
    other_seed = generate_bundle(7)
    assert all(
        files[f"{name}.csv"] != other_seed[f"{name}.csv"]
        for name in ("sales", "tickets", "inventory")
    )


def test_fresh_processes_and_different_output_paths_generate_identical_bytes(
    tmp_path: Path,
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    assert run_cli(first, hash_seed="1").returncode == 0
    assert run_cli(second, hash_seed="777").returncode == 0
    assert {path.name: path.read_bytes() for path in first.iterdir()} == {
        path.name: path.read_bytes() for path in second.iterdir()
    }


def test_check_detects_tampering_without_repair_and_generation_preserves_unrelated_files(
    tmp_path: Path,
) -> None:
    output = tmp_path / "fixtures"
    assert run_cli(output).returncode == 0
    assert run_cli(output, "--check").returncode == 0
    sales = output / "sales.csv"
    tampered = sales.read_bytes() + b"\n"
    sales.write_bytes(tampered)
    result = run_cli(output, "--check")
    assert result.returncode == 1
    assert "different: sales.csv" in result.stdout
    assert sales.read_bytes() == tampered
    unrelated = output / "keep.txt"
    unrelated.write_text("preserve", encoding="utf-8")
    assert run_cli(output).returncode == 0
    assert unrelated.read_text(encoding="utf-8") == "preserve"
    assert run_cli(output, "--check").returncode == 0


def test_check_missing_output_and_invalid_seed_never_create_files(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert run_cli(missing, "--check").returncode == 1
    assert not missing.exists()
    assert run_cli(missing, "--seed", "-1").returncode == 2
    assert not missing.exists()
    assert run_cli(missing, "--seed", "4294967296").returncode == 2
    assert not missing.exists()


def test_invalid_output_reports_error_without_replacing_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "occupied"
    output.write_text("preserve", encoding="utf-8")
    assert run_cli(output).returncode == 2
    assert output.read_text(encoding="utf-8") == "preserve"


def test_checked_in_bundle_matches_default_generator() -> None:
    output = PROJECT_ROOT / "fixtures" / "generated"
    assert run_cli(output, "--check").returncode == 0
