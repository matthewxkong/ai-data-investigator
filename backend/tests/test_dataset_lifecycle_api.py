import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from app import migrations
from app.config import Settings
from app.ingestion import deletion
from app.ingestion.models import DatasetResponse
from app.main import create_app
from app.services import Services
from app.sessions import SESSION_COOKIE


def upload(
    client: TestClient, csv: str = "value\n1\n", name: str = "sample.csv"
) -> DatasetResponse:
    response = client.post(
        "/api/datasets",
        content=csv.encode(),
        headers={"Content-Type": "text/csv", "X-Filename": name},
    )
    assert response.status_code == 201, response.text
    return DatasetResponse.model_validate(response.json())


def test_list_paginates_only_the_owners_imports(settings: Settings) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)
    with TestClient(application) as owner, TestClient(application) as visitor:
        assert owner.get("/api/datasets").status_code == 401
        first = upload(owner, name="first.csv")
        second = upload(owner, name="second.csv")
        other = upload(visitor, name="visitor.csv")
        session = services.sessions.resolve(owner.cookies.get(SESSION_COOKIE))
        assert session is not None
        services.datasets.create(session_id=session.owner_id, name="internal record")
        response = owner.get("/api/datasets?limit=1")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == {
            "datasets": [second.model_dump(mode="json", exclude={"columns", "delimiter"})],
            "next_offset": 1,
        }
        assert owner.get("/api/datasets?limit=1&offset=1").json() == {
            "datasets": [first.model_dump(mode="json", exclude={"columns", "delimiter"})],
            "next_offset": None,
        }
        assert owner.get("/api/datasets?offset=2").json() == {"datasets": [], "next_offset": None}
        assert [row["id"] for row in visitor.get("/api/datasets").json()["datasets"]] == [
            str(other.id)
        ]
        assert owner.get("/api/datasets?limit=101").status_code == 422
        assert owner.get("/api/datasets?offset=9223372036854775808").status_code == 422


def test_preview_returns_bounded_rows_in_original_order(settings: Settings) -> None:
    long_text = "\u00e9" * 129
    with TestClient(create_app(settings)) as client:
        dataset = upload(
            client, f'rowid,Label,Label\n9,{long_text},\n2,"two\nlines",001\n1,end,x\n'
        )
        url = f"/api/datasets/{dataset.id}/preview"
        response = client.get(url, params={"limit": 2})
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        body = response.json()
        assert body["dataset_version"] == str(dataset.version)
        assert [column["safe_name"] for column in body["columns"]] == ["rowid", "label", "label_2"]
        assert body["rows"] == [
            [
                {"value": "9", "truncated": False},
                {"value": long_text[:128], "truncated": True},
                {"value": None, "truncated": False},
            ],
            [
                {"value": "2", "truncated": False},
                {"value": "two\nlines", "truncated": False},
                {"value": "001", "truncated": False},
            ],
        ]
        assert (body["row_count"], body["offset"], body["next_offset"]) == (3, 0, 2)
        second = client.get(url, params={"limit": 2, "offset": 2}).json()
        assert [cell["value"] for cell in second["rows"][0]] == ["1", "end", "x"]
        assert second["next_offset"] is None
        empty = client.get(url, params={"offset": 100000}).json()
        assert empty["rows"] == [] and empty["next_offset"] is None
        for query in ("limit=0", "limit=26", "offset=-1", "offset=100001"):
            assert client.get(f"{url}?{query}").status_code == 422


def test_deletion_is_owner_only_and_removes_files_and_dependent_records(settings: Settings) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)
    with TestClient(application) as owner, TestClient(application) as visitor:
        dataset = upload(owner)
        url = f"/api/datasets/{dataset.id}"
        folder = services.ingestion.artifact_root / f"{dataset.id}-{dataset.version}"
        assert folder.is_dir()
        assert visitor.get(url + "/preview").status_code == 401
        assert visitor.delete(url).status_code == 401
        other = upload(visitor)
        assert visitor.get(url + "/preview").status_code == 404
        assert visitor.delete(url).status_code == 404
        origin = {"Origin": "https://elsewhere.example"}
        assert owner.get("/api/datasets", headers=origin).status_code == 403
        assert owner.get(url + "/preview", headers=origin).status_code == 403
        assert owner.delete(url, headers=origin).status_code == 403
        assert folder.is_dir()
        session = services.sessions.resolve(owner.cookies.get(SESSION_COOKIE))
        assert session is not None
        investigation = services.investigations.create(
            session_id=session.owner_id, dataset_id=dataset.id, question="How many rows?"
        )
        assert (
            owner.put(
                url + "/schema/overrides", json={"expected_revision": 0, "overrides": {}}
            ).status_code
            == 200
        )
        response = owner.delete(url)
        assert response.status_code == 204 and response.content == b""
        assert response.headers["cache-control"] == "no-store"
        assert not folder.exists()
        assert owner.get("/api/datasets").json() == {"datasets": [], "next_offset": None}
        for suffix in ("", "/preview", "/schema", "/profile"):
            assert owner.get(url + suffix).status_code == 404
        assert owner.delete(url).status_code == 404
        assert services.investigations.get(investigation.id, session_id=session.owner_id) is None
        assert services.datasets.get_import(dataset.id, session_id=session.owner_id) is None
        with services.database.connection() as connection:
            assert (
                connection.execute("SELECT COUNT(*) FROM dataset_schema_overrides").fetchone()[0]
                == 0
            )
            assert connection.execute("SELECT COUNT(*) FROM dataset_deletions").fetchone()[0] == 0
        assert visitor.get(f"/api/datasets/{other.id}/preview").status_code == 200


@pytest.mark.parametrize("restart", [False, True])
def test_locked_artifact_is_hidden_and_cleanup_is_retried(
    settings: Settings, monkeypatch: pytest.MonkeyPatch, restart: bool
) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)

    def locked(target: Path) -> None:
        raise PermissionError(str(target))

    with TestClient(application) as owner:
        dataset = upload(owner)
        url = f"/api/datasets/{dataset.id}"
        folder = services.ingestion.artifact_root / f"{dataset.id}-{dataset.version}"
        with monkeypatch.context() as patch:
            patch.setattr(deletion.shutil, "rmtree", locked)
            blocked = owner.delete(url)
            assert blocked.status_code == 503
            assert blocked.json()["error"]["code"] == "delete_pending"
            assert str(folder) not in blocked.text
        assert folder.is_dir()
        assert owner.get(url + "/preview").status_code == 404
        assert owner.get("/api/datasets").json()["datasets"] == []
        assert len(services.datasets.pending_deletions()) == 1
        if not restart:
            assert owner.delete(url).status_code == 204
    if restart:
        with TestClient(create_app(settings)) as restarted:
            assert restarted.get("/api/ready").status_code == 200
    assert not folder.exists()
    assert services.datasets.pending_deletions() == []


def test_v3_upgrade_preserves_existing_upload_and_session(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b"name\nlegacy\n"

    application = create_app(settings)
    services = cast(Services, application.state.services)
    with monkeypatch.context() as patch:
        patch.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS[:3])
        settings.data_dir.mkdir(parents=True)
        with services.database.connection(write=True, create=True) as connection:
            migrations.apply_migrations(connection)
        imported, session = asyncio.run(
            services.ingestion.ingest(
                body(), filename="legacy.csv", token=None, declared_length=None, delimiter=None
            )
        )
    with TestClient(create_app(settings)) as client:
        client.cookies.set(SESSION_COOKIE, session.token)
        url = f"/api/datasets/{imported.metadata.id}"
        response = client.get(url)
        assert response.status_code == 200
        assert response.json() == imported.response().model_dump(mode="json")
        assert client.get(url + "/preview").json()["rows"] == [
            [{"value": "legacy", "truncated": False}]
        ]
        assert client.get("/api/ready").json()["metadata_schema_version"] == 4
        assert client.delete(url).status_code == 204


def test_preview_refuses_a_missing_artifact_without_recreating_it(settings: Settings) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)
    with TestClient(application) as client:
        dataset = upload(client)
        folder = services.ingestion.artifact_root / f"{dataset.id}-{dataset.version}"
        (folder / "data.duckdb").unlink()
        response = client.get(f"/api/datasets/{dataset.id}/preview")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "dataset_unavailable"
        assert not (folder / "data.duckdb").exists()


def test_cleanup_rejects_a_redirect_to_another_dataset(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)
    with TestClient(application) as client:
        dataset = upload(client)
        other = upload(client)
        root = services.ingestion.artifact_root
        original = root / f"{dataset.id}-{dataset.version}"
        protected = root / f"{other.id}-{other.version}"
        resolve = Path.resolve

        def redirected(path: Path, *, strict: bool = False) -> Path:
            return protected if path == original else resolve(path, strict=strict)

        with monkeypatch.context() as patch:
            patch.setattr(Path, "resolve", redirected)
            response = client.delete(f"/api/datasets/{dataset.id}")
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "delete_pending"
        assert original.is_dir() and protected.is_dir()
        assert client.delete(f"/api/datasets/{dataset.id}").status_code == 204
        assert client.get(f"/api/datasets/{other.id}/preview").status_code == 200
