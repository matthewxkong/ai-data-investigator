import logging
import sqlite3
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.main import create_app
from app.repositories import MetadataNotFoundError


def test_unknown_route_and_wrong_method_share_the_error_contract(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        for method, path, status, code in (
            ("GET", "/api/absent", 404, "not_found"),
            ("POST", "/api/health", 405, "method_not_allowed"),
        ):
            response = client.request(method, path, headers={"X-Request-ID": "untrusted-value"})
            assert response.status_code == status
            error = response.json()["error"]
            assert error["code"] == code
            assert error["request_id"] == response.headers["X-Request-ID"]
            assert error["request_id"] != "untrusted-value"
            UUID(error["request_id"])
            assert error["details"] == []
        assert "GET" in response.headers["Allow"]


def test_validation_errors_do_not_return_request_values(settings: Settings) -> None:
    application = create_app(settings)

    class Payload(BaseModel):
        count: int

    @application.post("/test-validation")
    def validate(payload: Payload) -> int:
        return payload.count

    with TestClient(application) as client:
        response = client.post("/test-validation", json={"count": "private-example-secret"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"
        assert response.json()["error"]["details"][0]["location"] == ["body", "count"]
        assert "private-example-secret" not in response.text
        assert "input" not in response.json()["error"]["details"][0]


@pytest.mark.parametrize(
    ("exception", "status", "code"),
    [
        (MetadataNotFoundError("private-example-secret"), 404, "not_found"),
        (sqlite3.OperationalError("private-example-secret"), 503, "metadata_unavailable"),
        (HTTPException(403, detail="private-example-secret"), 403, "http_error"),
        (RuntimeError("private-example-secret"), 500, "internal_error"),
    ],
)
def test_errors_hide_internal_messages_and_have_request_ids(
    settings: Settings,
    exception: Exception,
    status: int,
    code: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = create_app(settings)

    @application.get("/test-failure")
    def fail() -> None:
        raise exception

    with (
        caplog.at_level(logging.ERROR),
        TestClient(application, raise_server_exceptions=False) as client,
    ):
        response = client.get("/test-failure")
        assert response.status_code == status
        error = response.json()["error"]
        assert error["code"] == code
        assert error["request_id"] == response.headers["X-Request-ID"]
        assert "private-example-secret" not in response.text
        assert "private-example-secret" not in caplog.text


def test_openapi_documents_the_error_envelope(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        schema = client.get("/openapi.json").json()
        response = schema["paths"]["/api/ready"]["get"]["responses"]["503"]
        assert response["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }


def test_unexpected_error_does_not_escape_to_the_asgi_server(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    application = create_app(settings)

    @application.get("/test-contained-failure")
    def fail() -> None:
        raise RuntimeError("private-example-secret")

    # The default transport re-raises server exceptions; a contained failure must not escape.
    with caplog.at_level(logging.ERROR), TestClient(application) as client:
        response = client.get("/test-contained-failure")
        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert "RuntimeError" in caplog.text
        assert "private-example-secret" not in caplog.text
