"""Application lifecycle and system routes; analytical APIs arrive in later milestones."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import Settings
from app.migrations import MIGRATIONS
from app.services import create_services


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["ai-data-investigator"] = "ai-data-investigator"


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"
    metadata_schema_version: int


def create_app(settings: Settings | None = None) -> FastAPI:
    services = create_services(settings if settings is not None else Settings())

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        services.database.initialize()
        application.state.started = True
        try:
            yield
        finally:
            application.state.started = False

    application = FastAPI(
        title="AI Data Investigator",
        version="0.0.1",
        description="Metadata foundation; CSV and agent endpoints are not available yet.",
        lifespan=lifespan,
    )
    application.state.services = services
    application.state.started = False

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        """Report process liveness, not database or model readiness."""
        return HealthResponse()

    @application.get(
        "/api/ready",
        response_model=ReadyResponse,
        tags=["system"],
        responses={503: {"description": "Metadata store unavailable."}},
    )
    def ready() -> ReadyResponse:
        """Check initialized, reachable metadata storage without creating or repairing it."""
        if not application.state.started or not services.database.is_ready():
            raise HTTPException(status_code=503, detail="Metadata store is unavailable.")
        return ReadyResponse(metadata_schema_version=MIGRATIONS[-1].version)

    return application
