from uuid import UUID

from fastapi import APIRouter, Request, Response

from app.errors import ApiError, ErrorResponse
from app.ingestion.models import ImportedDataset
from app.ingestion.routes import resolve_owner
from app.profiling import Profiler, ProfileResponse
from app.schema.models import OverrideRequest, SchemaResponse
from app.services import Services

router = APIRouter(
    prefix="/api/datasets",
    tags=["schema"],
    responses={code: {"model": ErrorResponse} for code in (401, 403, 404, 409, 422, 429, 503)},
)


@router.get("/{dataset_id}/profile", response_model=ProfileResponse)
def get_profile(dataset_id: UUID, request: Request, response: Response) -> ProfileResponse:
    """Compute a local owned profile using fixed read-only queries."""
    services, imported = owned_dataset(dataset_id, request)
    result = Profiler(services.schema).inspect(imported)
    response.headers["Cache-Control"] = "no-store"
    return result


def owned_dataset(dataset_id: UUID, request: Request) -> tuple[Services, ImportedDataset]:
    services, session = resolve_owner(request)
    imported = services.datasets.get_import(dataset_id, session_id=session.owner_id)
    if imported is None:
        raise ApiError(404, "not_found", "Dataset not found.")
    return services, imported


@router.get("/{dataset_id}/schema", response_model=SchemaResponse)
def get_schema(dataset_id: UUID, request: Request, response: Response) -> SchemaResponse:
    """Inspect every imported row; return evidence and semantic types without raw cells."""
    services, imported = owned_dataset(dataset_id, request)
    result = services.schema.inspect(imported)
    response.headers["Cache-Control"] = "no-store"
    return result


@router.put("/{dataset_id}/schema/overrides", response_model=SchemaResponse)
def replace_overrides(
    dataset_id: UUID, body: OverrideRequest, request: Request, response: Response
) -> SchemaResponse:
    """Replace all semantic overrides; an empty map resets them. Source data is unchanged."""
    services, imported = owned_dataset(dataset_id, request)
    result = services.schema.replace(imported, body)
    response.headers["Cache-Control"] = "no-store"
    return result
