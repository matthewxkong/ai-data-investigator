"""Per-application services; repositories open their own short-lived connections."""

from dataclasses import dataclass

from app.config import Settings
from app.database import Database
from app.ingestion.deletion import DatasetDeletion
from app.ingestion.service import IngestionService
from app.repositories.datasets import DatasetRepository
from app.repositories.investigations import InvestigationRepository
from app.schema.repository import SchemaRepository
from app.schema.service import SchemaService
from app.sessions import SessionStore


@dataclass(frozen=True)
class Services:
    settings: Settings
    database: Database
    datasets: DatasetRepository
    investigations: InvestigationRepository
    sessions: SessionStore
    ingestion: IngestionService
    deletion: DatasetDeletion
    schema: SchemaService


def create_services(settings: Settings) -> Services:
    database = Database(settings.database_path, timeout_seconds=settings.sqlite_timeout_seconds)
    datasets = DatasetRepository(database)
    sessions = SessionStore(database)
    ingestion = IngestionService(settings, datasets, sessions)
    return Services(
        settings=settings,
        database=database,
        datasets=datasets,
        investigations=InvestigationRepository(database),
        sessions=sessions,
        ingestion=ingestion,
        deletion=DatasetDeletion(settings.data_dir, datasets),
        schema=SchemaService(ingestion, SchemaRepository(database)),
    )
