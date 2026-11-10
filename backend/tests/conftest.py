"""Keep tests independent of a developer's environment and private data."""

import os
from pathlib import Path

import pytest

from app.database import Database


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in os.environ:
        if name.startswith("ADI_"):
            monkeypatch.delenv(name)


@pytest.fixture
def database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "metadata.sqlite3")
    database.initialize()
    return database
