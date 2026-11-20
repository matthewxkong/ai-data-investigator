# Trusted SQL baseline

From `backend`:

```sh
uv run --locked python -m app.baseline --check
```

The CLI validates the three clean synthetic fixture files against the development suite's seed, imports them through the same CSV service used by the app, and runs all ten checked-in SQL files on the resulting read-only DuckDB artifacts. The temporary workspace is removed when the run ends. Fixed temporary views cast fixture fields to the dates, integers, and decimals expected by the reference SQL.

The default comparison checks exact values, column names, row counts, and row order. Decimals serialize as strings to preserve precision, dates use ISO format, and missing values remain JSON `null`. To explore approximate comparisons, pass `--absolute-tolerance` or `--relative-tolerance`. Only decimal or floating-point columns use tolerances, with an allowed error of the greater of the absolute tolerance and the expected value's magnitude times the relative tolerance. Counts and labels still match exactly.

The runner reads one extra result row to detect truncation. `output_complete` means the full **SQL result** is in the report. For the authored top-three query, that means all three requested rows, not all products. The cap applies after SQL computes its aggregates, and truncated cases fail the baseline. To inspect that behavior, run the CLI with `--row-limit 1`.

The [versioned report](../evaluation/development/baseline.json) records the exact expected and actual rows, fixture generator and DuckDB versions, and source, SQL, and result hashes. The stable dataset version combines the generator version and source hash so importing the same bytes into a fresh temporary database produces the same report. SQL hashes use UTF-8 text with normalized line endings; result hashes include column types, ordered rows, and completeness flags. `--check` verifies the committed report byte for byte. Use `--write` when an intentional fixture, query, or engine change warrants updating it.

This benchmark covers the ten public development cases. Held-out cases, model behavior, and execution of user-supplied SQL are outside its scope.
