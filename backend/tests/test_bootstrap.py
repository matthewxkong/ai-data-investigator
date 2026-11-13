"""Check the fresh-checkout HTTP contract used by the frontend and local setup."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_application_starts_and_exposes_its_health_contract(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "ai-data-investigator"}
        schema = client.get("/openapi.json").json()
        assert "/api/health" in schema["paths"]


def test_unimplemented_investigation_endpoint_is_unavailable(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/investigations", json={"question": "Show revenue"})
        assert response.status_code == 404


def test_startup_initializes_storage_and_exposes_readiness(settings: Settings) -> None:
    application = create_app(settings)
    assert not settings.database_path.exists()
    with TestClient(application) as client:
        response = client.get("/api/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "metadata_schema_version": 2}
        assert settings.database_path.exists()
    assert not application.state.started
