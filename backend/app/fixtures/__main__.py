import argparse
from collections.abc import Sequence
from pathlib import Path

from app.fixtures.bundle import check_bundle, generate_bundle, write_bundle
from app.fixtures.common import DEFAULT_SEED

DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "fixtures" / "generated"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate reproducible synthetic CSV fixtures.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Compare bytes without writing files.")
    options = parser.parse_args(argv)
    try:
        files = generate_bundle(options.seed)
        output = options.output.expanduser().resolve()
        if options.check:
            problems = check_bundle(output, files)
            if problems:
                print("Fixture check failed:\n" + "\n".join(problems))
                return 1
            print(f"Fixture checks passed: 12 CSV files, seed {options.seed}.")
        else:
            write_bundle(output, files)
            print(f"Generated 12 CSV files and manifest in {output} (seed {options.seed}).")
    except (OSError, ValueError) as error:
        parser.exit(2, f"Fixture generation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
