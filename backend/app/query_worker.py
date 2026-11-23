"""Launch the fixed count query in a disposable local Linux container."""

import csv
import io
import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore, Thread
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.errors import ApiError
from app.repositories.datasets import DatasetRepository

IMAGE = "adi-query-worker:local"
DATASET_MOUNT = "/input/data.duckdb"
MAX_OUTPUT = 1024
MAX_DATABASE_BYTES = 128 * 1024**2
DOCKER_DEADLINE = 15.0
QUERY_DEADLINE = 10.0


class CountResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    schema_version: int = Field(ge=1, le=1)
    row_count: int = Field(ge=0, le=100_000)


def dataset_file(data_dir: Path, dataset_id: UUID, version: UUID) -> Path:
    root = data_dir.resolve() / "datasets"
    folder = root / f"{dataset_id}-{version}"
    artifact = folder / "data.duckdb"
    if (
        any(path.is_symlink() or path.is_junction() for path in (root, folder, artifact))
        or artifact.resolve() != artifact
        or not artifact.is_file()
    ):
        raise ApiError(503, "dataset_unavailable", "The dataset artifact is unavailable.")
    return artifact


def create_args(name: str, database: Path) -> list[str]:
    mount = io.StringIO(newline="")
    csv.writer(mount, lineterminator="\n").writerow(
        ("type=bind", f"source={database}", f"target={DATASET_MOUNT}", "readonly")
    )
    return [
        "create",
        "--name",
        name,
        "--label",
        "adi.query-worker=true",
        "--pull",
        "never",
        "--user",
        "65532:65532",
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges=true",
        "--ipc",
        "none",
        "--cpus",
        "1",
        "--memory",
        "256m",
        "--memory-swap",
        "256m",
        "--pids-limit",
        "32",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=40m,mode=1777",
        "--log-driver",
        "none",
        "--no-healthcheck",
        "--mount",
        mount.getvalue().removesuffix("\n"),
        IMAGE,
    ]


def docker_environment() -> dict[str, str]:
    allowed = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def attached_output(command: list[str], *, env: dict[str, str], timeout: float) -> bytes:
    with subprocess.Popen(
        command,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        stream = process.stdout
        output = bytearray()

        def drain() -> None:
            try:
                output.extend(stream.read(MAX_OUTPUT + 1))
                if len(output) > MAX_OUTPUT:
                    process.kill()
            except OSError:
                pass

        reader = Thread(target=drain)
        reader.start()
        try:
            process.wait(timeout=timeout)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            reader.join()
        if len(output) > MAX_OUTPUT:
            raise ApiError(503, "worker_output_limit", "The query worker returned too much data.")
        if process.returncode != 0:
            raise ApiError(503, "worker_failed", "The query worker could not read the dataset.")
        return bytes(output)


def run_container(args: list[str], name: str, *, timeout: float) -> CountResult:
    executable = shutil.which("docker")
    if executable is None:
        raise ApiError(503, "worker_unavailable", "The local Docker worker is unavailable.")
    endpoint = (
        "npipe:////./pipe/docker_engine" if os.name == "nt" else "unix:///var/run/docker.sock"
    )
    env = docker_environment()
    with TemporaryDirectory(prefix="adi-docker-") as config:
        docker = [executable, "--config", config, "--host", endpoint]

        def control(*parts: str) -> int:
            return subprocess.run(
                [*docker, *parts],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=DOCKER_DEADLINE,
                check=False,
            ).returncode

        created = False
        try:
            try:
                if control(*args) != 0:
                    raise ApiError(
                        503, "worker_unavailable", "The local Docker worker is unavailable."
                    )
                created = True
                try:
                    output = attached_output(
                        [*docker, "start", "--attach", name], env=env, timeout=timeout
                    )
                except subprocess.TimeoutExpired:
                    raise ApiError(
                        408, "worker_timeout", "The query worker exceeded its time limit."
                    ) from None
                return CountResult.model_validate_json(output)
            finally:
                try:
                    removed = control("rm", "--force", name) == 0
                except (subprocess.TimeoutExpired, OSError):
                    removed = False
                if created and not removed:
                    raise ApiError(
                        503, "worker_cleanup_failed", "The query worker could not be removed."
                    )
        except subprocess.TimeoutExpired:
            raise ApiError(
                503, "worker_unavailable", "The local Docker worker did not respond."
            ) from None
        except (OSError, ValueError):
            raise ApiError(
                503, "worker_failed", "The query worker did not return a valid result."
            ) from None


class QueryWorker:
    def __init__(self, data_dir: Path, datasets: DatasetRepository) -> None:
        self.data_dir = data_dir
        self.datasets = datasets
        self.slots = BoundedSemaphore(2)

    def count_rows(self, dataset_id: UUID, *, session_id: str) -> CountResult:
        if not self.slots.acquire(blocking=False):
            raise ApiError(429, "worker_busy", "Two query workers are active. Retry shortly.")
        try:
            imported = self.datasets.get_import(dataset_id, session_id=session_id)
            if imported is None:
                raise ApiError(404, "not_found", "Dataset not found.")
            try:
                database = dataset_file(self.data_dir, dataset_id, imported.metadata.version)
                with TemporaryDirectory(prefix="adi-query-input-") as workspace:
                    snapshot = Path(workspace) / "data.duckdb"
                    with database.open("rb") as source, snapshot.open("xb") as destination:
                        if os.fstat(source.fileno()).st_size > MAX_DATABASE_BYTES:
                            raise OSError("Dataset exceeds the worker input budget.")
                        shutil.copyfileobj(source, destination)
                    if os.name != "nt":
                        snapshot.chmod(0o444)
                    name = f"adi-query-{uuid4().hex}"
                    result = run_container(
                        create_args(name, snapshot), name, timeout=QUERY_DEADLINE
                    )
            except (OSError, RuntimeError):
                raise ApiError(
                    503, "dataset_unavailable", "The dataset artifact is unavailable."
                ) from None
            if result.row_count != imported.metadata.row_count:
                raise ApiError(
                    503, "worker_failed", "The dataset row count differs from its metadata."
                )
            return result
        finally:
            self.slots.release()
