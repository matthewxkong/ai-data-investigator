"""Per-application services; repositories open their own short-lived connections."""

from dataclasses import dataclass

from app.config import Settings
from app.database import Database
from app.ingestion.service import IngestionService
from app.repositories.datasets import DatasetRepository
from app.repositories.investigations import InvestigationRepository
from app.sessions import SessionStore


@dataclass(frozen=True)
class Services:
    settings: Settings
    database: Database
    datasets: DatasetRepository
    investigations: InvestigationRepository
    sessions: SessionStore
    ingestion: IngestionService


def create_services(settings: Settings) -> Services:
    database = Database(settings.database_path, timeout_seconds=settings.sqlite_timeout_seconds)
    datasets = DatasetRepository(database)
    sessions = SessionStore(database)
    return Services(
        settings=settings,
        database=database,
        datasets=datasets,
        investigations=InvestigationRepository(database),
        sessions=sessions,
        ingestion=IngestionService(settings, datasets, sessions),
    )
