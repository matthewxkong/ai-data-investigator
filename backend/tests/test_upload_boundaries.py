import asyncio
import csv
from collections import Counter
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import duckdb
import pytest
from fastapi.testclient import TestClient
from starlette.requests import ClientDisconnect

from app.config import Settings
from app.errors import ApiError
from app.fixtures.references import PROJECT_ROOT
from app.ingestion.service import remove_owned_directory
from app.main import create_app
from app.services import Services
from app.sessions import SESSION_COOKIE

FIXTURES = sorted((PROJECT_ROOT / "fixtures" / "generated").glob("*.csv"))


def assert_no_import_state(services: Services) -> None:
    for name in ("staging", "datasets"):
        directory = services.settings.data_dir / name
        assert not directory.exists() or not list(directory.iterdir())
    with services.database.connection() as connection:
        for table in ("datasets", "dataset_imports", "upload_sessions"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


@pytest.mark.parametrize("source", FIXTURES, ids=lambda path: path.name)
def test_fixture_uploads_preserve_source_bytes_and_every_text_value(
    settings: Settings, source: Path
) -> None:
    application = create_app(settings)
    content = source.read_bytes()
    with source.open(encoding="utf-8", newline="") as input_file:
        records = list(csv.reader(input_file))[1:]
    with TestClient(application) as client:
        response = client.post(
            "/api/datasets",
            content=content,
            headers={"Content-Type": "application/octet-stream", "X-Filename": source.name},
        )
        assert response.status_code == 201, response.text
        metadata = response.json()
        assert metadata["row_count"] == len(records)
        services = cast(Services, application.state.services)
        grant = services.sessions.resolve(client.cookies.get(SESSION_COOKIE))
        assert grant is not None
        imported = services.datasets.get_import(metadata["id"], session_id=grant.owner_id)
        assert imported is not None
        folder = services.ingestion.artifact_path(imported.metadata)
        assert (folder / "source.csv").read_bytes() == content
        with duckdb.connect(str(folder / "data.duckdb"), read_only=True) as connection:
            values = connection.execute("SELECT * FROM data").fetchall()
        assert Counter(values) == Counter(tuple(value or None for value in row) for row in records)


@pytest.mark.parametrize(
    ("content", "overrides", "status", "code"),
    [
        (b"a\n1\n", {"upload_max_bytes": 3}, 413, "upload_too_large"),
        (b"a\n1\n2\n", {"upload_max_rows": 1}, 413, "too_many_rows"),
        (b"a,b\n1,2\n", {"upload_max_columns": 1}, 413, "too_many_columns"),
        (b"a\n", {}, 400, "empty_csv"),
        (b'a\n"unclosed', {}, 400, "invalid_csv"),
        (b"a,b\n1\n", {}, 400, "inconsistent_columns"),
        (b"a\n\xff\n", {}, 400, "invalid_encoding"),
        (b"a\n" + b"x" * 131_073, {}, 413, "csv_field_too_long"),
        (b"a," + b"," * 1_048_577, {}, 413, "csv_line_too_long"),
    ],
)
def test_rejected_uploads_leave_no_files_metadata_or_sessions(
    settings: Settings, content: bytes, overrides: dict[str, int], status: int, code: str
) -> None:
    configured = settings.model_copy(update=overrides)
    application = create_app(configured)
    with TestClient(application) as client:
        response = client.post(
            "/api/datasets", content=content, headers={"Content-Type": "text/csv"}
        )
        assert response.status_code == status, response.text
        assert response.json()["error"]["code"] == code
        assert "set-cookie" not in response.headers
        assert_no_import_state(cast(Services, application.state.services))


def test_byte_and_row_limits_accept_the_boundary_and_reject_the_next_row(
    settings: Settings,
) -> None:
    limited = settings.model_copy(update={"upload_max_bytes": 8, "upload_max_rows": 1})
    with TestClient(create_app(limited)) as client:
        result = client.post(
            "/api/datasets", content=b"a,b\n1,2\n", headers={"Content-Type": "text/csv"}
        )
        assert result.status_code == 201
        assert result.json()["byte_count"] == 8 and result.json()["row_count"] == 1


def test_actual_hundred_thousand_row_boundary(settings: Settings) -> None:
    application = create_app(settings)
    with TestClient(application) as client:
        result = client.post(
            "/api/datasets",
            content=b"value\n" + b"1\n" * 100_000,
            headers={"Content-Type": "text/csv"},
        )
        assert result.status_code == 201, result.text
        assert result.json()["row_count"] == 100_000
        rejected = client.post(
            "/api/datasets",
            content=b"value\n" + b"1\n" * 100_001,
            headers={"Content-Type": "text/csv"},
        )
        assert rejected.status_code == 413
        services = cast(Services, application.state.services)
        assert not list((settings.data_dir / "staging").iterdir())
        assert len(list(services.ingestion.artifact_root.iterdir())) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "multipart/form-data; boundary=test"},
        {"Content-Type": "application/json"},
        {"Content-Type": "text/csv", "Content-Encoding": "gzip"},
        {"Content-Type": "text/csv", "X-Filename": "../secret.csv"},
        {"Content-Type": "text/csv", "Origin": "https://evil.invalid"},
        {"Content-Type": "text/csv", "Host": "evil.invalid"},
    ],
)
def test_protocol_and_origin_failures_do_not_create_import_state(
    settings: Settings, headers: dict[str, str]
) -> None:
    application = create_app(settings)
    with TestClient(application) as client:
        result = client.post("/api/datasets", content=b"a\n1\n", headers=headers)
        assert result.status_code in {400, 403, 415}
        assert_no_import_state(cast(Services, application.state.services))


def test_production_mode_and_disabled_uploads_are_enforced(settings: Settings) -> None:
    for configured in (
        settings.model_copy(update={"environment": "production"}),
        settings.model_copy(update={"uploads_enabled": False}),
    ):
        application = create_app(configured)
        with TestClient(application) as client:
            result = client.post(
                "/api/datasets", content=b"a\n1\n", headers={"Content-Type": "text/csv"}
            )
            assert result.status_code == 403
            assert_no_import_state(cast(Services, application.state.services))


def test_worker_failure_is_clean_and_does_not_echo_private_cells(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args: object, **kwargs: object) -> None:
        raise ApiError(408, "import_timeout", "CSV import exceeded its time budget.")

    monkeypatch.setattr("app.ingestion.service.run_controlled_import", timeout)
    application = create_app(settings)
    with TestClient(application) as client:
        result = client.post(
            "/api/datasets", content=b"a\nprivate-cell\n", headers={"Content-Type": "text/csv"}
        )
        assert result.status_code == 408
        assert "private-cell" not in result.text
        assert_no_import_state(cast(Services, application.state.services))


def test_busy_imports_reject_before_reading_and_release_slots(settings: Settings) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)
    with TestClient(application) as client:
        services.ingestion.slots.acquire()
        services.ingestion.slots.acquire()
        try:
            result = client.post(
                "/api/datasets", content=b"a\n1\n", headers={"Content-Type": "text/csv"}
            )
            assert result.status_code == 429
            assert_no_import_state(services)
        finally:
            services.ingestion.slots.release()
            services.ingestion.slots.release()


def test_disconnect_cleans_the_staging_directory_and_session(settings: Settings) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)

    async def disconnected() -> AsyncIterator[bytes]:
        yield b"a\npartial"
        raise ClientDisconnect()

    with TestClient(application), pytest.raises(ApiError, match="interrupted"):
        asyncio.run(
            services.ingestion.ingest(
                disconnected(),
                filename="dataset.csv",
                token=None,
                declared_length=None,
                delimiter=None,
            )
        )
    assert_no_import_state(services)


def test_cleanup_cannot_escape_its_owned_directory(tmp_path: Path) -> None:
    root, outside = tmp_path / "owned", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("preserve", encoding="utf-8")
    with pytest.raises(OSError):
        remove_owned_directory(outside, root)
    with pytest.raises(OSError):
        remove_owned_directory(root, root)
    assert marker.read_text(encoding="utf-8") == "preserve"
