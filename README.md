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

Day-one foundation: a health-only FastAPI backend and a React frontend that reports its connection to that backend. Data ingestion, profiling, persistence, charts, and model-backed investigations are scheduled capabilities and are not implemented yet. No API key is required to run the skeleton.

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
| `backend/app` | HTTP application factory and typed routes |
| `backend/tests` | Bootstrap HTTP contract checks |
| `frontend/src` | Browser application and styling |
| `docs/mvp-scope.md` | User-visible behavior, release gates, and deferred work |
| `docs/architecture.md` | Components, execution boundary, and privacy decisions |
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
DuckDB is a development dependency for these trusted checks; there is no analytical SQL
HTTP endpoint or model-generated SQL execution in this milestone.

See [the fixture dictionary](fixtures/README.md) for columns, units, metric definitions,
quality variants, reproducibility, and development/reserved question separation. The
public held-out manifest is an initial reserved split, not a claim of unseen-task accuracy.
See [W03 progress](docs/progress/w03.md) for this workday's implementation and evidence.
