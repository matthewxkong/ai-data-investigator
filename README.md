# AI Data Investigator

A local-first assistant for investigating CSV data with analytical SQL, charts, and inspectable evidence.

## Product brief

The application helps an analyst understand an unfamiliar dataset, ask a question, and verify the answer. The model selects analytical tools and explains their outputs; the database computes the numbers.

Three primary user stories:

1. As an analyst, I can inspect a CSV's columns, missing values, and distributions before asking questions.
2. As an analyst, I can ask how a metric changes across categories or time and receive a chart supported by executed SQL.
3. As a reviewer, I can inspect the dataset version, query, results, and assumptions behind a finding, then refine the investigation with a follow-up.

The first demonstration will answer: **How did monthly revenue change by region?** It will use reproducible synthetic sales data with known expected results.

## Current status

Day-two foundation: a FastAPI backend with validated settings, transactional SQLite metadata migrations, session-scoped internal repositories, liveness/readiness endpoints, and consistent API errors. The React frontend reports its API connection. CSV ingestion, profiling, charts, and model-backed investigations remain scheduled capabilities. No API key is required.

## Run locally

Prerequisites: Git, Python 3.13, [uv](https://docs.astral.sh/uv/), and Node.js 22.12 or later within the Node 22 release line. Dependencies are recorded in `backend/uv.lock` and `frontend/package-lock.json`.

Run these commands from the checked-out repository in two terminals.

**Terminal 1 - API:**

```sh
cd backend
uv sync --locked
uv run --locked uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 - browser interface:**

```sh
cd frontend
npm ci
npm run dev
```

Open <http://127.0.0.1:5173>. The page should report **API connected**. The API health endpoint is <http://127.0.0.1:8000/api/health> and interactive API documentation is at <http://127.0.0.1:8000/docs>.

Metadata storage is initialized on application startup. Readiness at <http://127.0.0.1:8000/api/ready> should return `{"status":"ready","metadata_schema_version":1}`. Liveness reports that the process responds; readiness checks only the metadata foundation, not a model provider or analytical worker.

## Backend configuration and persistence

Configuration works without an environment file. To customize it, copy `backend/.env.example` to `backend/.env`. Actual environment variables override the file.

| Setting | Default | Meaning |
| --- | --- | --- |
| `ADI_ENVIRONMENT` | `development` | `development`, `test`, or `production`; descriptive environment tag |
| `ADI_DATA_DIR` | `backend/data` | Persistent application-data directory; relative values resolve against `backend/` |
| `ADI_SQLITE_TIMEOUT_SECONDS` | `5` | SQLite busy timeout, greater than zero and at most 30 seconds |
| `ADI_MODEL_API_KEY` | Unset | Optional redacted backend secret; reserved for later provider integration |

The application creates `metadata.sqlite3` inside the data directory. Startup applies ordered, checksummed migrations in one transaction and preserves records across restarts. Unknown or modified migration history, missing schema tables, corrupt files, or unusable storage fail startup with an actionable message. Failed upgrades roll back; they do not reset the database. Restore a compatible backup when necessary. Never delete the database as a routine upgrade step.

Keep custom data directories and backups outside tracked source paths. Git ignores the default data directories, SQLite database/journal files, and environment files. Do not commit private data or credentials. To back up this initial SQLite setup, stop the application before copying the data directory.

Dataset and investigation repositories are internal Python services on `application.state.services`, with ownership-scoped reads and a composite database foreign key preventing cross-session dataset links. The current HTTP API does not expose metadata creation/list endpoints, session authentication, CSV ingestion, or investigation execution. The repository layer persists metadata and statuses; agent orchestration and transition policy come later.

See [the API contract](docs/api.md) for endpoints, response examples, and error handling.

## Development connection troubleshooting

If the API is unavailable, the page shows a retry control. Start the backend and retry. If port 8000 is occupied, use a different backend port and set `API_PROXY_TARGET` in `frontend/.env` to that address, then restart Vite. Copy `frontend/.env.example` to `frontend/.env` as a starting point. The frontend uses relative `/api` requests and Vite proxies those requests during development. A production deployment will need its own `/api` reverse-proxy routing; `vite preview` alone does not provide the backend.

Both development servers bind to loopback. The project uses local system fonts and requires no third-party font or asset requests. The only runtime request from the frontend skeleton is the API health probe.

## Checks

From `backend`:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app
uv run --locked pytest
```

From `frontend`:

```sh
npm run lint
npm run typecheck
npm run build
```

GitHub Actions is configured to run these checks on Windows and Linux after publication. Live model calls are not required by CI.

## Project guide

| Location | Purpose |
| --- | --- |
| `backend/app` | Settings, migrations, repositories, HTTP lifecycle, and error contracts |
| `backend/tests` | Configuration, ownership, migrations, lifecycle, and HTTP integration checks |
| `frontend/src` | Browser application and styling |
| `docs/mvp-scope.md` | User-visible behavior, release gates, and deferred work |
| `docs/architecture.md` | Components, execution boundary, and privacy decisions |
| `docs/api.md` | Implemented endpoints, errors, and metadata lifecycle |
| `docs/delivery-plan.md` | Complete 60-day schedule and daily work packages |
| `docs/progress.md` | Completed work and next issue |
| `.github` | CI, issue forms, and PR template |

## First investigation scenario

The first complete workflow will use a reproducible synthetic sales CSV with `order_date`, `region`, `quantity`, and `unit_price` columns. Define revenue explicitly as `quantity * unit_price`, aggregate it by calendar month and region, and compare results with fixed reference SQL. The assistant will ask for clarification when the dataset or metric definition cannot support the question. This scenario is a planned acceptance case rather than sample data included in day one.

## Data handling

Keep raw datasets and model credentials outside Git. The local product will retain uploaded files locally and disclose any schema or aggregate values sent to a model provider. Generated SQL will require an isolated worker before execution is enabled. The public demonstration will use synthetic datasets. See [architecture and privacy decisions](docs/architecture.md).

See [CONTRIBUTING](CONTRIBUTING.md) for issue, commit, PR, and review conventions.
