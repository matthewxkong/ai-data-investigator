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

W04 adds local CSV ingestion: streamed uploads, bounded validation, safe header mappings, a text-preserving DuckDB artifact, and immutable versions with source checksums. Server-issued session cookies scope uploaded metadata. The React frontend still reports its API connection; browser upload controls, type inference, profiling, charts, and model-backed investigations are later milestones. No API key is required.

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

Metadata storage is initialized on application startup. Readiness at <http://127.0.0.1:8000/api/ready> should return `{"status":"ready","metadata_schema_version":2}`. Liveness reports that the process responds; readiness checks only the metadata foundation, not a model provider or analytical worker.

## Upload a local CSV

With the API running, execute this from the repository root. On Windows use `curl.exe`; on macOS/Linux use `curl`.

```sh
curl.exe -c cookies.txt -b cookies.txt -H "Content-Type: text/csv" -H "X-Filename: sales.csv" --data-binary @fixtures/generated/sales.csv http://127.0.0.1:8000/api/datasets
```

The API accepts raw file bytes. Keep the returned session cookie to retrieve metadata with `GET /api/datasets/<id>`. The response includes dataset ID, immutable version, row/byte counts, SHA-256 of the exact source, delimiter, and original/safe column-name mappings. It does not expose storage paths or session credentials. Cookie jars are credentials; the example `cookies.txt` is ignored by Git.

Uploads accept UTF-8 with optional BOM, comma/semicolon/tab delimiters, standard CSV quoting and quoted newlines. All imported columns remain VARCHAR; blank fields become NULL. Use `?delimiter=%3B` for an explicit semicolon delimiter. Automatic detection considers comma, semicolon, and tab; ambiguous/single-column inputs fall back to comma.

Initial caps: **25,000,000 bytes, 100,000 data rows, 256 columns**, 256 characters per header, 131,072 per field, and 1,048,576 per physical line. Two imports can run concurrently per API process. The fixed-operation DuckDB child has a 256 MB database-memory budget and 45-second import timeout. Invalid inputs leave no published artifacts or metadata. See [the upload contract](docs/csv-ingestion.md) for exact behavior and recovery limits.

Uploads are for local development/test use and are disabled in production mode. Published artifacts are stored locally under the configured data directory; no model call is made. Dataset listing, preview, deletion, and user-account authentication remain later milestones.

## Backend configuration and persistence

Configuration works without an environment file. To customize it, copy `backend/.env.example` to `backend/.env`. Actual environment variables override the file.

| Setting | Default | Meaning |
| --- | --- | --- |
| `ADI_ENVIRONMENT` | `development` | `development`, `test`, or `production`; production disables local dataset routes |
| `ADI_DATA_DIR` | `backend/data` | Persistent application-data directory; relative values resolve against `backend/` |
| `ADI_SQLITE_TIMEOUT_SECONDS` | `5` | SQLite busy timeout, greater than zero and at most 30 seconds |
| `ADI_MODEL_API_KEY` | Unset | Optional redacted backend secret; reserved for later provider integration |
| `ADI_UPLOADS_ENABLED` | `true` | Enable local ingestion; production mode always disables it |
| `ADI_UPLOAD_MAX_BYTES` | `25000000` | Maximum source bytes; can be reduced |
| `ADI_UPLOAD_MAX_ROWS` | `100000` | Maximum nonblank data records; can be reduced |
| `ADI_UPLOAD_MAX_COLUMNS` | `256` | Maximum columns; can be reduced |
| `ADI_IMPORT_TIMEOUT_SECONDS` | `45` | DuckDB child-process timeout, at most 120 seconds |
| `ADI_UPLOAD_ALLOWED_ORIGINS` | Local ports 5173/8000 | JSON list of exact permitted browser origins for a custom local port |

The application creates `metadata.sqlite3` inside the data directory. Startup applies ordered, checksummed migrations in one transaction and preserves records across restarts. Unknown or modified migration history, missing schema tables, corrupt files, or unusable storage fail startup with an actionable message. Failed upgrades roll back; they do not reset the database. Restore a compatible backup when necessary. Never delete the database as a routine upgrade step.

Keep custom data directories and backups outside tracked source paths. Git ignores the default data directories, SQLite database/journal files, and environment files. Do not commit private data or credentials. To back up this initial SQLite setup, stop the application before copying the data directory.

Dataset and investigation repositories are Python services on `application.state.services`, with ownership-scoped reads and a composite database foreign key preventing cross-session dataset links. The API creates imported datasets and retrieves their metadata through a server-issued upload session; it does not accept caller-chosen owner IDs. The repository layer persists investigation statuses; agent orchestration and account authentication come later.

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

## Synthetic datasets and reference questions

The W03 fixture toolkit provides **120 sales orders, 96 service tickets, and 72 inventory
snapshot records**, plus separate null, duplicate, and mixed-type variants. All data is
synthetic. Twelve CSV files and a hash/provenance manifest are checked in under
[`fixtures/generated`](fixtures/generated).

From `backend`, generate or verify the default fixture bundle:

```sh
uv sync --locked
uv run --locked python -m app.fixtures
uv run --locked python -m app.fixtures --check
```

Use `--seed 7 --output <directory>` for a separate reproducible bundle. Generation never
rewrites the checked-in reference answers. Ten development questions have standalone SQL
and fixed expected results, checked in DuckDB against an independent Python/Decimal oracle.
DuckDB is also used by the controlled ingestion worker; there is no analytical SQL
HTTP endpoint or model-generated SQL execution in this milestone.

See [the fixture dictionary](fixtures/README.md) for columns, units, metric definitions,
quality variants, reproducibility, and development/reserved question separation. The
public held-out manifest is an initial reserved split, not a claim of unseen-task accuracy.
See [W03 progress](docs/progress/w03.md) for this workday's implementation and evidence.
W04 was explicitly brought forward to November 13; see [W04 progress](docs/progress/w04.md).
