"""Keep tests independent of a developer's environment and private data."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in os.environ:
        if name.startswith("ADI_"):
            monkeypatch.delenv(name)
