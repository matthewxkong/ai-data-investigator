"""Build the complete fixture bundle in memory without accessing external data."""

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.fixtures.common import DEFAULT_SEED, GENERATOR_VERSION
from app.fixtures.inventory import generate_inventory
from app.fixtures.sales import generate_sales
from app.fixtures.tickets import generate_tickets
from app.fixtures.variants import CellChange, generate_variants


@dataclass(frozen=True)
class FileEntry:
    file: str
    source_dataset: str
    variant: str
    row_count: int
    columns: tuple[str, ...]
    sha256: str
    changes: tuple[CellChange, ...] = ()
    duplicate_source_rows: tuple[int, ...] = ()


def generate_bundle(seed: int = DEFAULT_SEED) -> dict[str, bytes]:
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("Seed must be between 0 and 4294967295.")
    files: dict[str, bytes] = {}
    entries: list[FileEntry] = []
    for clean in (generate_sales(seed), generate_tickets(seed), generate_inventory(seed)):
        clean_bytes = clean.csv_bytes()
        filename = f"{clean.name}.csv"
        files[filename] = clean_bytes
        entries.append(
            FileEntry(
                file=filename,
                source_dataset=clean.name,
                variant="clean",
                row_count=len(clean.rows),
                columns=clean.columns,
                sha256=hashlib.sha256(clean_bytes).hexdigest(),
            )
        )
        for variant in generate_variants(clean):
            content = variant.table.csv_bytes()
            filename = f"{variant.table.name}.csv"
            files[filename] = content
            entries.append(
                FileEntry(
                    file=filename,
                    source_dataset=clean.name,
                    variant=variant.kind,
                    row_count=len(variant.table.rows),
                    columns=variant.table.columns,
                    sha256=hashlib.sha256(content).hexdigest(),
                    changes=variant.changes,
                    duplicate_source_rows=variant.duplicate_source_rows,
                )
            )
    manifest = {
        "schema_version": 1,
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "reference_python": "3.13",
        "origin": "synthetic_builtin_distributions",
        "encoding": "utf-8",
        "newline": "LF",
        "null_representation": "empty_field",
        "files": [asdict(entry) for entry in sorted(entries, key=lambda entry: entry.file)],
    }
    files["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return files


def check_bundle(output: Path, files: dict[str, bytes]) -> list[str]:
    problems = []
    for name, expected in sorted(files.items()):
        path = output / name
        if not path.exists():
            problems.append(f"missing: {name}")
        elif path.read_bytes() != expected:
            problems.append(f"different: {name}")
    return problems


def write_bundle(output: Path, files: dict[str, bytes]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    # Write the manifest last. An interrupted write is detectable with --check.
    for name in sorted(name for name in files if name != "manifest.json"):
        (output / name).write_bytes(files[name])
    (output / "manifest.json").write_bytes(files["manifest.json"])
