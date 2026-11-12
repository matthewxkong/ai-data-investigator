import csv
import io
from collections.abc import Iterator
from dataclasses import dataclass

DEFAULT_SEED = 20261112
GENERATOR_VERSION = 1


@dataclass(frozen=True)
class FixtureTable:
    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        if not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("Fixture columns must be nonempty and unique.")
        if any(len(row) != len(self.columns) for row in self.rows):
            raise ValueError("Every fixture row must match its column count.")

    def records(self) -> Iterator[dict[str, str]]:
        for row in self.rows:
            yield dict(zip(self.columns, row, strict=True))

    def csv_bytes(self) -> bytes:
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(self.columns)
        writer.writerows(self.rows)
        return buffer.getvalue().encode("utf-8")
