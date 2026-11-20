import shutil
from pathlib import Path
from uuid import UUID

from app.errors import ApiError
from app.ingestion.models import DatasetArtifact
from app.repositories.datasets import DatasetRepository


class DatasetDeletion:
    def __init__(self, data_dir: Path, datasets: DatasetRepository) -> None:
        self.data_dir = data_dir
        self.datasets = datasets

    def delete(self, dataset_id: UUID, *, session_id: str) -> None:
        artifact = self.datasets.begin_deletion(dataset_id, session_id=session_id)
        if artifact is None:
            raise ApiError(404, "not_found", "Dataset not found.")
        if not self.clean_up(artifact):
            raise ApiError(
                503, "delete_pending", "Dataset file cleanup is pending. Retry deletion shortly."
            )

    def retry_pending(self) -> None:
        for artifact in self.datasets.pending_deletions():
            self.clean_up(artifact)

    def clean_up(self, artifact: DatasetArtifact) -> bool:
        try:
            root = self.data_dir.resolve() / "datasets"
            target = root / f"{artifact.dataset_id}-{artifact.version}"
            if (
                root.resolve() != root
                or root.is_symlink()
                or root.is_junction()
                or target.resolve() != target
                or target.is_symlink()
                or target.is_junction()
            ):
                return False
            try:
                shutil.rmtree(target)
            except FileNotFoundError:
                if target.exists():
                    return False
        except (OSError, RuntimeError):
            return False
        self.datasets.complete_deletion(artifact)
        return True
