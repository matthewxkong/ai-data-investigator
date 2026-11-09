"""Check the fresh-checkout HTTP contract used by the frontend and local setup."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_application_starts_and_exposes_its_health_contract() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "ai-data-investigator"}
        schema = client.get("/openapi.json").json()
        assert "/api/health" in schema["paths"]


def test_unimplemented_investigation_endpoint_is_unavailable() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/investigations", json={"question": "Show revenue"})
        assert response.status_code == 404
