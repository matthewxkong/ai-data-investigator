import time
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, Response

from app.errors import ApiError, ErrorResponse
from app.ingestion.models import DatasetList, DatasetPreview, DatasetResponse, Delimiter
from app.ingestion.preview import MAX_PREVIEW_LIMIT, preview_rows
from app.schema.inspection import MAX_ROWS
from app.services import Services
from app.sessions import SESSION_COOKIE, SessionGrant

router = APIRouter(prefix="/api/datasets", tags=["datasets"])
SESSION_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorResponse} for code in (401, 403)
}


def upload_services(request: Request) -> Services:
    services = cast(Services, request.app.state.services)
    if not services.settings.uploads_enabled or services.settings.environment == "production":
        raise ApiError(
            403, "uploads_disabled", "Local CSV uploads are disabled in this environment."
        )
    if request.url.hostname not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        raise ApiError(
            403, "local_uploads_only", "CSV uploads are available on loopback hosts only."
        )
    origin = request.headers.get("origin")
    if origin is not None and origin not in services.settings.upload_allowed_origins:
        raise ApiError(
            403, "origin_not_allowed", "This browser origin cannot access local datasets."
        )
    return services


def resolve_owner(request: Request) -> tuple[Services, SessionGrant]:
    services = upload_services(request)
    session = services.sessions.resolve(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise ApiError(401, "session_required", "A valid upload session cookie is required.")
    return services, session


@router.post(
    "",
    status_code=201,
    response_model=DatasetResponse,
    responses={code: {"model": ErrorResponse} for code in (400, 401, 403, 408, 413, 415, 429)},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary"}}
                for media in ("text/csv", "application/octet-stream")
            },
        }
    },
)
async def upload_csv(
    request: Request,
    response: Response,
    filename: Annotated[str, Header(alias="X-Filename", max_length=3060)] = "dataset.csv",
    delimiter: Annotated[Delimiter | None, Query()] = None,
) -> DatasetResponse:
    """Upload raw UTF-8 CSV bytes; X-Filename can be UTF-8 percent-encoded."""
    services = upload_services(request)
    media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media not in {"text/csv", "application/octet-stream"}:
        raise ApiError(
            415,
            "unsupported_media_type",
            "Send raw CSV bytes as text/csv or application/octet-stream.",
        )
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise ApiError(415, "unsupported_encoding", "Compressed request bodies are not supported.")
    imported, session = await services.ingestion.ingest(
        request.stream(),
        filename=filename,
        token=request.cookies.get(SESSION_COOKIE),
        declared_length=request.headers.get("content-length"),
        delimiter=delimiter,
    )
    if session.is_new:
        response.set_cookie(
            SESSION_COOKIE,
            session.token,
            max_age=max(0, session.expires_at - int(time.time())),
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/api",
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Location"] = f"/api/datasets/{imported.metadata.id}"
    return imported.response()


@router.get("", response_model=DatasetList, responses=SESSION_ERRORS)
def list_uploaded_datasets(
    request: Request,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=2**63 - 1)] = 0,
) -> DatasetList:
    """List only this session's imported datasets, newest first."""
    services, session = resolve_owner(request)
    result = services.datasets.list_imports(session.owner_id, offset=offset, limit=limit)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{dataset_id}", response_model=DatasetResponse, responses=SESSION_ERRORS)
def get_uploaded_dataset(dataset_id: UUID, request: Request, response: Response) -> DatasetResponse:
    """Inspect an uploaded dataset's metadata using its server-issued session cookie."""
    services, session = resolve_owner(request)
    imported = services.datasets.get_import(dataset_id, session_id=session.owner_id)
    if imported is None:
        raise ApiError(404, "not_found", "Dataset not found.")
    response.headers["Cache-Control"] = "no-store"
    return imported.response()


@router.get(
    "/{dataset_id}/preview",
    response_model=DatasetPreview,
    responses={**SESSION_ERRORS, 429: {"model": ErrorResponse}},
)
def get_dataset_preview(
    dataset_id: UUID,
    request: Request,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=MAX_PREVIEW_LIMIT)] = 20,
    offset: Annotated[int, Query(ge=0, le=MAX_ROWS)] = 0,
) -> DatasetPreview:
    """Read one bounded page of source rows in import order."""
    services, session = resolve_owner(request)
    imported = services.datasets.get_import(dataset_id, session_id=session.owner_id)
    if imported is None:
        raise ApiError(404, "not_found", "Dataset not found.")
    with services.schema.inspector.capacity():
        try:
            database = services.ingestion.artifact_path(imported.metadata) / "data.duckdb"
        except OSError:
            raise ApiError(
                503, "dataset_unavailable", "The dataset artifact is unavailable."
            ) from None
        result = preview_rows(database, imported, offset=offset, limit=limit)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.delete("/{dataset_id}", status_code=204, response_class=Response, responses=SESSION_ERRORS)
def delete_uploaded_dataset(dataset_id: UUID, request: Request) -> Response:
    """Delete an owned import, its dependent metadata, and its files."""
    services, session = resolve_owner(request)
    services.deletion.delete(dataset_id, session_id=session.owner_id)
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
