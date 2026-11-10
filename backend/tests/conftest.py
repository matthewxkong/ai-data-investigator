"""Keep tests independent of a developer's environment and private data."""

import os
from pathlib import Path

import pytest

from app.config import Settings
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


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, environment="test", data_dir=tmp_path / "application-data")
