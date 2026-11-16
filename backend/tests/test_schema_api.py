import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.errors import ApiError
from app.fixtures.references import PROJECT_ROOT
from app.main import create_app
from app.schema.models import OverrideRequest
from app.services import Services
from app.sessions import SESSION_COOKIE

FIXTURES = sorted((PROJECT_ROOT / "fixtures/generated").glob("*.csv"))


def upload(
    client: TestClient, content: bytes = b"Amount,Code,When\n1,001,03/04/2026\n2,002,04/05/2026\n"
):
    response = client.post("/api/datasets", content=content, headers={"Content-Type": "text/csv"})
    assert response.status_code == 201, response.text
    return response.json()


def column_map(result):
    return {column["safe_name"]: column for column in result["columns"]}


@pytest.mark.parametrize("source", FIXTURES, ids=lambda path: path.name)
def test_all_reference_fixtures_infer_full_schema(settings: Settings, source: Path) -> None:
    with TestClient(create_app(settings)) as client:
        metadata = upload(client, source.read_bytes())
        response = client.get(f"/api/datasets/{metadata['id']}/schema")
        assert response.status_code == 200, response.text
        schema = response.json()
        assert schema["complete"] is True
        assert schema["rows_examined"] == metadata["row_count"]
        assert schema["dataset_version"] == metadata["version"]
        assert schema["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
        assert schema["schema_revision"] == 0
        columns = column_map(schema)
        for imported in metadata["columns"]:
            column = columns[imported["safe_name"]]
            assert column["original_name"] == imported["original_name"]
            assert column["position"] == imported["position"]
            assert column["null_count"] + column["non_null_count"] == schema["rows_examined"]
        prefix = source.stem.split("_")[0]
        if prefix == "sales":
            assert columns["region"]["inferred_type"] == "categorical"
            assert columns["order_id"]["inferred_type"] == "text"
            if "mixed_types" in source.stem:
                assert columns["quantity"]["inferred_type"] == "text"
                assert columns["unit_price"]["inferred_type"] == "text"
                assert "ambiguous_dates" in {w["code"] for w in columns["order_date"]["warnings"]}
            else:
                assert columns["quantity"]["inferred_type"] == "integer"
                assert columns["unit_price"]["inferred_type"] == "decimal"
                assert columns["order_date"]["inferred_type"] == "date"
        elif prefix == "tickets":
            assert columns["status"]["inferred_type"] == "categorical"
            assert columns["resolved_at"]["inferred_type"] == "datetime"
            assert columns["created_at"]["inferred_type"] == (
                "text" if "mixed_types" in source.stem else "datetime"
            )
            assert columns["resolution_hours"]["inferred_type"] == (
                "text" if "mixed_types" in source.stem else "integer"
            )
        else:
            assert columns["warehouse"]["inferred_type"] == "categorical"
            assert columns["unit_cost"]["inferred_type"] == (
                "text" if "mixed_types" in source.stem else "decimal"
            )


def test_overrides_persist_reset_and_do_not_modify_artifacts(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        metadata = upload(client)
        path = f"/api/datasets/{metadata['id']}/schema"
        services = cast(Services, app.state.services)
        folder = next(services.ingestion.artifact_root.iterdir())
        before = {p.name: p.read_bytes() for p in folder.iterdir()}
        schema = client.get(path).json()
        assert column_map(schema)["code"]["effective_type"] == "text"
        updated = client.put(
            path + "/overrides",
            json={
                "expected_revision": 0,
                "overrides": {
                    "code": {"type": "integer"},
                    "when": {"type": "date", "date_order": "dmy"},
                },
            },
        )
        assert updated.status_code == 200, updated.text
        result = updated.json()
        assert result["schema_revision"] == 1
        assert result["dataset_version"] == metadata["version"]
        assert result["source_sha256"] == metadata["sha256"]
        code = column_map(result)["code"]
        assert (code["inferred_type"], code["effective_type"], code["type_source"]) == (
            "text",
            "integer",
            "override",
        )
        assert column_map(result)["when"]["date_order"] == "dmy"
        assert client.get(path).json() == result
        token = client.cookies.get(SESSION_COOKIE)
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.set(SESSION_COOKIE, token)
        assert restarted.get(path).json() == result
        reset = restarted.put(path + "/overrides", json={"expected_revision": 1, "overrides": {}})
        assert reset.status_code == 200
        assert reset.json()["schema_revision"] == 2
        assert column_map(reset.json())["code"]["effective_type"] == "text"
        stale = restarted.put(path + "/overrides", json={"expected_revision": 0, "overrides": {}})
        assert stale.status_code == 409
        assert stale.json()["error"]["code"] == "schema_revision_conflict"
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before


@pytest.mark.parametrize(
    "overrides",
    [
        {"amount": {"type": "boolean"}},
        {"when": {"type": "date"}},
        {"missing": {"type": "text"}},
        {"code": {"type": "nonsense"}},
        {"amount": {"type": "integer", "date_order": "dmy"}},
        {"code": {"type": "text", "extra": "PRIVATE SECRET"}},
    ],
)
def test_invalid_overrides_are_atomic_and_sanitized(settings: Settings, overrides) -> None:
    with TestClient(create_app(settings)) as client:
        metadata = upload(client)
        path = f"/api/datasets/{metadata['id']}/schema"
        result = client.put(
            path + "/overrides", json={"expected_revision": 0, "overrides": overrides}
        )
        assert result.status_code == 422, result.text
        assert "PRIVATE SECRET" not in result.text
        assert result.json()["error"]["request_id"] == result.headers["X-Request-ID"]
        assert result.headers["Cache-Control"] == "no-store"
        assert client.get(path).json()["schema_revision"] == 0


def test_schema_ownership_and_expiration_precede_artifact_access(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as owner:
        metadata = upload(owner)
        path = f"/api/datasets/{metadata['id']}/schema"
        with TestClient(create_app(settings)) as stranger:
            assert stranger.get(path).status_code == 401
            upload(stranger)
            assert stranger.get(path).status_code == 404
            assert (
                stranger.put(
                    path + "/overrides", json={"expected_revision": 0, "overrides": {}}
                ).status_code
                == 404
            )
        assert owner.get(f"/api/datasets/{uuid4()}/schema").status_code == 404
        services = cast(Services, app.state.services)
        with services.database.connection(write=True) as connection:
            connection.execute("UPDATE upload_sessions SET expires_at = 1")
        assert owner.get(path).status_code == 401


def test_schema_does_not_sample_away_late_outliers_or_expose_cells(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        metadata = upload(client, b"Value\n" + b"1\n" * 1000 + b"PRIVATE LATE OUTLIER\n")
        response = client.get(f"/api/datasets/{metadata['id']}/schema")
        assert response.status_code == 200
        assert "PRIVATE LATE OUTLIER" not in response.text
        result = response.json()
        assert result["rows_examined"] == 1001
        assert result["columns"][0]["inferred_type"] == "text"
        invalid = client.put(
            f"/api/datasets/{metadata['id']}/schema/overrides",
            json={
                "expected_revision": 0,
                "overrides": {"value": {"type": "integer"}},
            },
        )
        assert invalid.status_code == 422


def test_missing_artifact_is_not_recreated_and_busy_slot_recovers(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        metadata = upload(client)
        path = f"/api/datasets/{metadata['id']}/schema"
        services = cast(Services, app.state.services)
        inspector = services.schema.inspector
        with inspector.capacity(), inspector.capacity():
            assert client.get(path).status_code == 429
        assert client.get(path).status_code == 200
        folder = next(services.ingestion.artifact_root.iterdir())
        database = folder / "data.duckdb"
        backup = folder / "backup.duckdb"
        database.rename(backup)
        unavailable = client.get(path)
        assert unavailable.status_code == 503
        assert str(folder) not in unavailable.text
        assert not database.exists()


def test_parallel_reads_and_competing_override_writes(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        metadata = upload(client)
        services = cast(Services, app.state.services)
        grant = services.sessions.resolve(client.cookies.get(SESSION_COOKIE))
        imported = services.datasets.get_import(metadata["id"], session_id=grant.owner_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            reads = list(pool.map(lambda _: services.schema.inspect(imported), range(2)))
        assert reads[0] == reads[1]

        def edit(_):
            try:
                return services.schema.replace(
                    imported, OverrideRequest(expected_revision=0, overrides={})
                ).schema_revision
            except ApiError as error:
                return error.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(edit, range(2))) == [1, 409]


@pytest.mark.parametrize("mode", ["production", "disabled", "origin", "host"])
def test_schema_routes_keep_local_access_guards(settings: Settings, mode: str) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        metadata = upload(client)
        services = cast(Services, app.state.services)
        headers = {}
        if mode == "production":
            services.settings.environment = "production"
        elif mode == "disabled":
            services.settings.uploads_enabled = False
        elif mode == "origin":
            headers = {"Origin": "https://untrusted.example"}
        else:
            headers = {"Host": "untrusted.example"}
        path = f"/api/datasets/{metadata['id']}/schema"
        assert client.get(path, headers=headers).status_code == 403
        assert (
            client.put(
                path + "/overrides", headers=headers, json={"expected_revision": 0, "overrides": {}}
            ).status_code
            == 403
        )


def test_openapi_documents_schema_and_revision_contract(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        schema = client.get("/openapi.json").json()
        assert "/api/datasets/{dataset_id}/schema" in schema["paths"]
        override = schema["paths"]["/api/datasets/{dataset_id}/schema/overrides"]["put"]
        assert {"200", "401", "403", "404", "409", "422", "429", "503"} <= set(
            override["responses"]
        )
        contract = schema["components"]["schemas"]["OverrideRequest"]
        assert set(contract["required"]) == {"expected_revision", "overrides"}
        assert contract["additionalProperties"] is False
