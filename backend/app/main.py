"""Health-only foundation. Analytical routes arrive in subsequent milestones."""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


def create_app() -> FastAPI:
    application = FastAPI(
        title="AI Data Investigator",
        version="0.0.1",
        description="Development foundation; CSV and agent endpoints are not available yet.",
    )

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        """Report process liveness, not database or model readiness."""
        return HealthResponse(status="ok", service="ai-data-investigator")

    return application
