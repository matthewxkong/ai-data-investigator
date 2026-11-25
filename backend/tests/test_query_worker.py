import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app import query_worker
from app.config import Settings
from app.errors import ApiError
from app.main import create_app
from app.query_worker import (
    IMAGE,
    MAX_OUTPUT,
    attached_output,
    create_args,
    dataset_file,
    run_container,
)
from app.services import Services
from app.sessions import SESSION_COOKIE

docker_required = pytest.mark.skipif(
    os.environ.get("ADI_TEST_QUERY_WORKER") != "1",
    reason="requires the locally built query-worker image and Linux Docker engine",
)


def test_worker_rejects_foreign_session_before_launch(settings: Settings) -> None:
    app = create_app(settings)
    services = cast(Services, app.state.services)
    with TestClient(app) as client:
        response = client.post(
            "/api/datasets", content=b"name\nexample\n", headers={"Content-Type": "text/csv"}
        )
        assert response.status_code == 201
        with pytest.raises(ApiError) as error:
            services.query_worker.count_rows(UUID(response.json()["id"]), session_id="other")
        assert error.value.status_code == 404


def test_denied_query_never_launches_docker(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = create_app(settings)
    services = cast(Services, application.state.services)

    def unexpected_container(*args: object, **kwargs: object) -> bytes:
        pytest.fail("A denied query must not launch a container.")

    monkeypatch.setattr(query_worker, "run_container", unexpected_container)
    with TestClient(application) as client:
        uploaded = client.post(
            "/api/datasets", content=b"name\nexample\n", headers={"Content-Type": "text/csv"}
        )
        assert uploaded.status_code == 201
        session = services.sessions.resolve(client.cookies.get(SESSION_COOKIE))
        assert session is not None
        with pytest.raises(ApiError) as error:
            services.query_worker.select(
                UUID(uploaded.json()["id"]), session_id=session.owner_id, sql="SHOW TABLES"
            )
        assert (error.value.status_code, error.value.code) == (422, "sql_policy_denied")


def test_launcher_bounds_stdout_without_waiting_for_extra_output() -> None:
    code = (
        f"import sys,time; sys.stdout.write('x'*{MAX_OUTPUT + 1}); "
        "sys.stdout.flush(); time.sleep(5)"
    )
    with pytest.raises(ApiError) as error:
        attached_output([sys.executable, "-c", code], env=os.environ.copy(), timeout=2)
    assert error.value.code == "worker_output_limit"


def test_worker_rejects_redirected_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset, version = uuid4(), uuid4()
    source = tmp_path / "datasets" / f"{dataset}-{version}" / "data.duckdb"
    source.parent.mkdir(parents=True)
    source.touch()
    assert dataset_file(tmp_path, dataset, version) == source.resolve()
    resolve = Path.resolve

    def redirected(path: Path, *, strict: bool = False) -> Path:
        return tmp_path / "unrelated.duckdb" if path == source else resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", redirected)
    with pytest.raises(ApiError) as error:
        dataset_file(tmp_path, dataset, version)
    assert error.value.code == "dataset_unavailable"


@docker_required
def test_container_counts_owned_import_and_has_only_one_read_only_mount(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(settings)
    services = cast(Services, app.state.services)
    name = f"adi-query-test-{uuid4().hex}"
    monkeypatch.setenv("ADI_TEST_HOST_ONLY_SECRET", "synthetic")
    with TestClient(app) as client:
        response = client.post(
            "/api/datasets",
            content=b"name\nfirst\nsecond\n",
            headers={"Content-Type": "text/csv"},
        )
        assert response.status_code == 201
        dataset = UUID(response.json()["id"])
        version = UUID(response.json()["version"])
        session = services.sessions.resolve(client.cookies.get(SESSION_COOKIE))
        assert session is not None
        database = dataset_file(settings.data_dir, dataset, version)
        sibling = database.with_name("host-only-marker")
        sibling.write_text("synthetic", encoding="utf-8")
        database.chmod(0o644)
        args = create_args(name, database)
        probe = (
            "import os,runpy,socket; "
            "assert os.geteuid()==65532; "
            "assert {name for _,name in socket.if_nameindex()}=={'lo'}; "
            "assert 'ADI_TEST_HOST_ONLY_SECRET' not in os.environ; "
            "assert os.listdir('/input')==['data.duckdb']; "
            "assert os.statvfs('/input/data.duckdb').f_flag & os.ST_RDONLY; "
            "assert os.statvfs('/worker').f_flag & os.ST_RDONLY; "
            "assert not os.path.exists('/var/run/docker.sock'); "
            "assert not os.path.exists('/input/host-only-marker'); "
            "assert runpy.run_path('/worker/query.py')['count_rows']()==2"
        )
        try:
            subprocess.run(
                ["docker", *args[:-1], "--entrypoint", "python", IMAGE, "-I", "-c", probe],
                check=True,
                capture_output=True,
                timeout=20,
            )
            inspected = subprocess.run(
                ["docker", "inspect", name], check=True, capture_output=True, timeout=20
            )
            container = json.loads(inspected.stdout)[0]
            assert [(item["Destination"], item["RW"]) for item in container["Mounts"]] == [
                ("/input/data.duckdb", False)
            ]
            host = container["HostConfig"]
            assert host["NetworkMode"] == "none"
            assert host["CapDrop"] == ["ALL"]
            assert host["MemorySwap"] == host["Memory"] == 256 * 1024**2
            assert host["NanoCpus"] == 10**9 and host["PidsLimit"] == 32
            assert host["LogConfig"]["Type"] == "none"
            probed = subprocess.run(
                ["docker", "start", "--attach", name], capture_output=True, timeout=20
            )
            assert probed.returncode == 0, probed.stderr.decode("utf-8", errors="replace")
            result = services.query_worker.count_rows(dataset, session_id=session.owner_id)
            assert result.row_count == 2
            selected = services.query_worker.select(
                dataset,
                session_id=session.owner_id,
                sql="SELECT UPPER(name) AS label FROM data WHERE name = 'second' ORDER BY label",
            )
            assert selected.columns == ["label"]
            assert selected.rows == [["SECOND"]]
            assert not selected.truncated
        finally:
            subprocess.run(
                ["docker", "rm", "--force", name], capture_output=True, timeout=20, check=False
            )


@docker_required
def test_timed_out_container_is_removed(tmp_path: Path) -> None:
    dummy = tmp_path / "dataset.duckdb"
    dummy.touch()
    name = f"adi-query-test-{uuid4().hex}"
    args = create_args(name, dummy)
    sleeper = [
        *args[:-1],
        "--entrypoint",
        "python",
        IMAGE,
        "-I",
        "-c",
        "import time; time.sleep(60)",
    ]
    try:
        with pytest.raises(ApiError) as error:
            run_container(sleeper, name, timeout=1)
        assert error.value.code == "worker_timeout"
        containers = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
            check=True,
            capture_output=True,
            timeout=20,
        )
        assert not containers.stdout.strip()
    finally:
        subprocess.run(
            ["docker", "rm", "--force", name], capture_output=True, timeout=20, check=False
        )
