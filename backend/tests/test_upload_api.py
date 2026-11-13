import hashlib
from typing import cast

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.services import Services
from app.sessions import SESSION_COOKIE


def test_upload_sets_owned_cookie_and_returns_inspectable_metadata(settings: Settings) -> None:
    application = create_app(settings)
    content = b"Name,Quantity\nA,001\nB,2\n"
    with TestClient(application) as client:
        response = client.post(
            "/api/datasets",
            content=content,
            headers={"Content-Type": "text/csv", "X-Filename": "sales.csv"},
        )
        assert response.status_code == 201, response.text
        dataset = response.json()
        assert dataset["row_count"] == 2
        assert dataset["byte_count"] == len(content)
        assert dataset["sha256"] == hashlib.sha256(content).hexdigest()
        assert "session_id" not in dataset and "token" not in dataset
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api" in cookie
        assert response.headers["Cache-Control"] == "no-store"
        assert client.get(response.headers["Location"]).json() == dataset
        services = cast(Services, application.state.services)
        assert services.sessions.resolve(client.cookies.get(SESSION_COOKIE)) is not None


def test_one_browser_cannot_read_another_browsers_dataset(settings: Settings) -> None:
    application = create_app(settings)
    with TestClient(application) as first:
        response = first.post(
            "/api/datasets", content=b"a\n1\n", headers={"Content-Type": "text/csv"}
        )
        assert response.status_code == 201
        location = response.headers["Location"]
        with TestClient(application) as second:
            assert second.get(location).status_code == 401
            other = second.post(
                "/api/datasets", content=b"a\n2\n", headers={"Content-Type": "text/csv"}
            )
            assert other.status_code == 201
            assert second.get(location).status_code == 404


def test_upload_session_and_artifact_metadata_survive_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as first:
        response = first.post(
            "/api/datasets", content=b"a\n1\n", headers={"Content-Type": "text/csv"}
        )
        assert response.status_code == 201
        cookie, location = first.cookies.get(SESSION_COOKIE), response.headers["Location"]
        expected = response.json()
    with TestClient(create_app(settings)) as restarted:
        response = restarted.get(location, headers={"Cookie": f"{SESSION_COOKIE}={cookie}"})
        assert response.status_code == 200
        assert response.json() == expected


def test_openapi_exposes_raw_upload_and_limits_errors(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        schema = client.get("/openapi.json").json()["paths"]["/api/datasets"]["post"]
        assert "text/csv" in schema["requestBody"]["content"]
        assert "413" in schema["responses"]
