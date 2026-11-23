# Local query worker

W09 runs a fixed row count against the selected CSV import in a fresh Linux container. The backend service looks up the import using its owning session and checks the count against recorded metadata. No HTTP route or model tool invokes it yet. W10 is responsible for deciding which caller-supplied SQL is allowed.

Build the image and run the isolation tests from `backend` on Docker Engine (Linux) or Docker Desktop configured for Linux containers (Windows):

```powershell
docker build --tag adi-query-worker:local worker
$env:ADI_TEST_QUERY_WORKER = "1"
uv run --locked pytest -q tests/test_query_worker.py
```

On Linux, set the test flag with `ADI_TEST_QUERY_WORKER=1 uv run --locked pytest -q tests/test_query_worker.py`. The tests use synthetic uploads in temporary directories. Linux CI builds the image and runs them. Normal application startup and HTTP tests do not require Docker.

The launcher uses the local Docker socket or Windows named pipe and a fresh CLI configuration directory. It uses the prebuilt image and never pulls it during a query. The worker runs as UID/GID 65532, without Linux capabilities, with a read-only root filesystem and no external network. The only bind mount is a read-only copy of the immutable DuckDB file, staged in a private temporary directory with a 128 MiB input limit. This lets the worker read the file without changing the original upload permissions. Source CSVs, metadata SQLite, the Docker socket, and host credentials are not mounted or passed to the container. DuckDB also disables external access and extension loading, and locks its configuration.

Each worker is limited to one CPU, 256 MiB RAM with no swap, 32 processes, and 40 MiB of scratch space. The launcher admits two workers per app process, gives each attached execution 10 seconds, and reads at most 1 KiB of result output plus one byte to detect overflow. Docker setup and cleanup have separate deadlines. The backend removes the container after each attempt, including timeouts, and returns a generic error if cleanup fails.

Run on a trusted local Linux Docker daemon using the standard local socket. Keep the dataset storage directory under application control. Docker socket access grants substantial authority on the host; the worker itself has no socket access. If the host or daemon stops mid-run, an operator can inspect the remaining containers with `docker ps -a --filter label=adi.query-worker=true` and remove confirmed stale containers by name.
