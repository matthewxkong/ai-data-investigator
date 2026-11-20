import argparse
import asyncio
import sys

from app.baseline.models import MAX_RESULT_ROWS, Tolerance
from app.baseline.runner import DEFAULT_ROW_LIMIT, REPORT_PATH, report_text, run_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the checked-in development SQL baseline.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify the committed report")
    mode.add_argument("--write", action="store_true", help="replace the committed report")
    parser.add_argument("--absolute-tolerance", default="0")
    parser.add_argument("--relative-tolerance", default="0")
    parser.add_argument("--row-limit", type=int, default=DEFAULT_ROW_LIMIT)
    options = parser.parse_args()
    if not 1 <= options.row_limit <= MAX_RESULT_ROWS:
        parser.error(f"--row-limit must be between 1 and {MAX_RESULT_ROWS}")
    if (options.check or options.write) and (
        options.row_limit != DEFAULT_ROW_LIMIT
        or (options.absolute_tolerance, options.relative_tolerance) != ("0", "0")
    ):
        parser.error("--check and --write require the default row limit and exact comparison")
    try:
        tolerance = Tolerance.model_validate(
            {"absolute": options.absolute_tolerance, "relative": options.relative_tolerance}
        )
    except ValueError:
        parser.error(
            "tolerances must be finite and nonnegative; relative tolerance cannot exceed 1"
        )
    report = asyncio.run(run_baseline(tolerance, row_limit=options.row_limit))
    rendered = report_text(report)
    if not report.passed:
        print(rendered, end="")
        return 1
    if options.check:
        if not REPORT_PATH.is_file() or REPORT_PATH.read_bytes() != rendered.encode("utf-8"):
            print(
                "Development baseline report differs. Review the output before using --write.",
                file=sys.stderr,
            )
            return 1
        print(f"Development SQL baseline matched: {len(report.cases)} cases.")
    elif options.write:
        REPORT_PATH.write_bytes(rendered.encode("utf-8"))
        print(f"Wrote {len(report.cases)} passing cases to {REPORT_PATH.name}.")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
