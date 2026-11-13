import json
import os
import subprocess
import sys
from pathlib import Path

from app.config import BACKEND_ROOT
from app.errors import ApiError
from app.ingestion.parser import ParsedCsv


def run_controlled_import(
    canonical: Path, database: Path, parsed: ParsedCsv, *, timeout_seconds: float
) -> None:
    specification = canonical.parent / "import.json"
    specification.write_text(
        json.dumps(
            {
                "columns": [column.safe_name for column in parsed.columns],
                "row_count": parsed.row_count,
            }
        ),
        encoding="utf-8",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "LANG", "LC_ALL"}
    }
    environment.update(PYTHONUTF8="1", PYTHONNOUSERSITE="1")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "app.ingestion.worker",
                str(canonical),
                str(database),
                str(specification),
            ],
            cwd=BACKEND_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ApiError(
            408, "import_timeout", "CSV import exceeded its time budget. Use a smaller file."
        ) from None
    except OSError:
        raise ApiError(
            503, "import_unavailable", "The CSV import process is unavailable."
        ) from None
    try:
        valid_result = json.loads(result.stdout) == {"ok": True, "row_count": parsed.row_count}
    except (ValueError, TypeError):
        valid_result = False
    if result.returncode != 0 or not valid_result or not database.is_file():
        raise ApiError(503, "import_failed", "CSV import failed within its resource budget.")
