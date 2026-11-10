"""Per-application services; repositories open their own short-lived connections."""

from dataclasses import dataclass

from app.config import Settings
from app.database import Database
from app.repositories.datasets import DatasetRepository
from app.repositories.investigations import InvestigationRepository


@dataclass(frozen=True)
class Services:
    settings: Settings
    database: Database
    datasets: DatasetRepository
    investigations: InvestigationRepository


def create_services(settings: Settings) -> Services:
    database = Database(settings.database_path, timeout_seconds=settings.sqlite_timeout_seconds)
    return Services(
        settings=settings,
        database=database,
        datasets=DatasetRepository(database),
        investigations=InvestigationRepository(database),
    )
