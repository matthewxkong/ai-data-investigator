import shutil
import tempfile
from collections.abc import AsyncIterable
from datetime import UTC, datetime
from pathlib import Path
from threading import BoundedSemaphore
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.errors import ApiError
from app.ingestion.importer import run_controlled_import
from app.ingestion.models import Delimiter, ImportedDataset
from app.ingestion.parser import parse_csv, validate_filename
from app.ingestion.stream import ReceivedUpload, content_length, receive_upload
from app.models import DatasetMetadata
from app.repositories.datasets import DatasetRepository
from app.sessions import SessionExpiredError, SessionGrant, SessionStore


def contained_directory(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if resolved == root.resolve() or not resolved.is_relative_to(root.resolve()):
        raise OSError("Storage directory escapes the configured data root.")
    return resolved


def remove_owned_directory(path: Path, root: Path) -> None:
    resolved = contained_directory(path, root)
    if resolved.parent != root.resolve():
        raise OSError("Cleanup target is not a directly owned storage directory.")
    if resolved.exists():
        shutil.rmtree(resolved)


class IngestionService:
    def __init__(
        self, settings: Settings, datasets: DatasetRepository, sessions: SessionStore
    ) -> None:
        self.settings = settings
        self.datasets = datasets
        self.sessions = sessions
        self.slots = BoundedSemaphore(2)

    @property
    def artifact_root(self) -> Path:
        return contained_directory(self.settings.data_dir / "datasets", self.settings.data_dir)

    def artifact_path(self, metadata: DatasetMetadata) -> Path:
        return contained_directory(
            self.artifact_root / f"{metadata.id}-{metadata.version}", self.artifact_root
        )

    async def ingest(
        self,
        chunks: AsyncIterable[bytes],
        *,
        filename: str,
        token: str | None,
        declared_length: str | None,
        delimiter: Delimiter | None,
    ) -> tuple[ImportedDataset, SessionGrant]:
        name = validate_filename(filename)
        length = content_length(declared_length, self.settings.upload_max_bytes)
        if not self.slots.acquire(blocking=False):
            raise ApiError(429, "upload_busy", "Two imports are already active. Retry shortly.")
        try:
            session = await run_in_threadpool(self.sessions.resolve, token)
            session = session or self.sessions.candidate()
            staging = contained_directory(
                self.settings.data_dir / "staging", self.settings.data_dir
            )
            staging.mkdir(mode=0o700, parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="upload-", dir=staging) as directory:
                working = Path(directory)
                received = await receive_upload(
                    chunks,
                    working / "source.csv",
                    maximum=self.settings.upload_max_bytes,
                    expected_length=length,
                )
                return await run_in_threadpool(
                    self._complete, working, name, received, session, delimiter
                )
        except SessionExpiredError:
            raise ApiError(
                401, "session_expired", "The upload session expired. Start a new session."
            ) from None
        except OSError:
            raise ApiError(
                503, "upload_storage_unavailable", "Upload storage is unavailable."
            ) from None
        finally:
            self.slots.release()

    def _complete(
        self,
        working: Path,
        name: str,
        received: ReceivedUpload,
        session: SessionGrant,
        delimiter: Delimiter | None,
    ) -> tuple[ImportedDataset, SessionGrant]:
        canonical = working / "canonical.csv"
        parsed = parse_csv(
            working / "source.csv",
            canonical,
            max_rows=self.settings.upload_max_rows,
            max_columns=self.settings.upload_max_columns,
            delimiter=delimiter,
        )
        run_controlled_import(
            canonical,
            working / "data.duckdb",
            parsed,
            timeout_seconds=self.settings.import_timeout_seconds,
        )
        metadata = DatasetMetadata(
            id=uuid4(),
            version=uuid4(),
            session_id=session.owner_id,
            name=name,
            byte_count=received.byte_count,
            row_count=parsed.row_count,
            created_at=datetime.now(UTC),
        )
        imported = ImportedDataset(metadata, received.sha256, parsed.delimiter, parsed.columns)
        canonical.unlink()
        (working / "import.json").unlink()
        remove_owned_directory(working / "spill", working)
        root = self.artifact_root
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = self.artifact_path(metadata)
        if destination.exists():
            raise OSError("Immutable artifact already exists.")
        # Both directories are checked against server-controlled roots before the rename.
        if working.resolve().parent != (self.settings.data_dir / "staging").resolve():
            raise OSError("Unrecognized staging directory.")
        working.rename(destination)
        try:
            self.datasets.register_import(imported, session)
        except BaseException:
            remove_owned_directory(destination, root)
            raise
        return imported, session
