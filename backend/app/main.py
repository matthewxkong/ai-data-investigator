"""Application lifecycle and system routes; analytical APIs arrive in later milestones."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Settings
from app.errors import ApiError, ErrorResponse, install_error_handlers
from app.ingestion.routes import router as dataset_router
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
        description="Local CSV ingestion and metadata; analytical agents are not enabled.",
        lifespan=lifespan,
        responses={
            404: {"model": ErrorResponse, "description": "Resource not found."},
            422: {"model": ErrorResponse, "description": "Invalid request."},
            500: {"model": ErrorResponse, "description": "Unexpected error."},
            503: {"model": ErrorResponse, "description": "Metadata store unavailable."},
        },
    )
    application.state.services = services
    application.state.started = False
    install_error_handlers(application)
    application.include_router(dataset_router)

    @application.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        """Report process liveness, not database or model readiness."""
        return HealthResponse()

    @application.get(
        "/api/ready",
        response_model=ReadyResponse,
        tags=["system"],
    )
    def ready() -> ReadyResponse:
        """Check initialized, reachable metadata storage without creating or repairing it."""
        if not application.state.started or not services.database.is_ready():
            raise ApiError(
                status_code=503,
                code="metadata_unavailable",
                message="Metadata storage is temporarily unavailable.",
            )
        return ReadyResponse(metadata_schema_version=MIGRATIONS[-1].version)

    return application
