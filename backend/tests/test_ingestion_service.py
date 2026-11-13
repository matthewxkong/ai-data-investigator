import asyncio
import hashlib
import sqlite3
from collections.abc import AsyncIterator
from typing import cast

import duckdb
import pytest

from app.config import Settings
from app.ingestion.service import IngestionService
from app.main import create_app
from app.repositories.datasets import DatasetRepository
from app.services import Services
from app.sessions import SessionStore


async def body(content: bytes) -> AsyncIterator[bytes]:
    yield content


def setup_service(settings: Settings) -> IngestionService:
    services = cast(Services, create_app(settings).state.services)
    services.database.initialize()
    return IngestionService(settings, services.datasets, SessionStore(services.database))


def test_immutable_imports_have_exact_sources_and_recoverable_metadata(settings: Settings) -> None:
    service = setup_service(settings)
    content = b"Name,Count\nA,001\n"
    first, grant = asyncio.run(
        service.ingest(
            body(content), filename="sales.csv", token=None, declared_length=None, delimiter=None
        )
    )
    second, _ = asyncio.run(
        service.ingest(
            body(content),
            filename="sales.csv",
            token=grant.token,
            declared_length=None,
            delimiter=None,
        )
    )
    assert first.sha256 == second.sha256 == hashlib.sha256(content).hexdigest()
    assert first.metadata.id != second.metadata.id
    assert first.metadata.version != second.metadata.version
    assert first.metadata.session_id == second.metadata.session_id
    assert service.artifact_path(first.metadata).joinpath("source.csv").read_bytes() == content
    with duckdb.connect(
        str(service.artifact_path(first.metadata) / "data.duckdb"), read_only=True
    ) as c:
        assert c.execute("SELECT * FROM data").fetchall() == [("A", "001")]
    stored = service.datasets.get_import(first.metadata.id, session_id=grant.owner_id)
    assert stored is not None and stored.response() == first.response()
    assert not list((settings.data_dir / "staging").iterdir())


def test_metadata_failure_removes_published_artifacts_and_leaves_no_session(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = setup_service(settings)

    def fail(*args: object) -> None:
        raise sqlite3.OperationalError("simulated failure")

    monkeypatch.setattr(DatasetRepository, "register_import", fail)
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(
            service.ingest(
                body(b"a\n1\n"),
                filename="sales.csv",
                token=None,
                declared_length=None,
                delimiter=None,
            )
        )
    assert not list(service.artifact_root.iterdir())
    assert not list((settings.data_dir / "staging").iterdir())
    with service.datasets.database.connection() as connection:
        assert connection.execute("SELECT COUNT(*) FROM upload_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 0
