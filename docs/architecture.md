# Architecture and data boundaries

Decision date: November 9, 2026. Status: accepted for the first release.

```mermaid
flowchart LR
    UI[React browser interface] --> API[FastAPI]
    API --> ING[Controlled CSV ingestion and profiles]
    API --> AG[Bounded agent loop]
    AG --> MODEL[One model provider]
    AG --> TOOLS[Typed tool dispatcher]
    TOOLS --> POLICY[SQL validation]
    POLICY --> WORKER[Isolated DuckDB worker]
    API --> META[SQLite metadata and checkpoints]
    WORKER --> RESULTS[Validated result artifacts]
    RESULTS --> API
```

## Decisions

- Python and FastAPI provide typed HTTP interfaces. Keep application construction in a factory so tests and local configurations do not share accidental global state.
- DuckDB owns analytical calculations; the model proposes queries and explains their executed results. SQLite owns application metadata and checkpoints. Introduce each dependency when its implementation begins.
- React, TypeScript, Vite, and Plotly provide the browser interface. Use a development proxy for relative `/api` requests; the production deployment must route that prefix to the API as well.
- A small explicit agent loop exposes `inspect_schema`, `profile_data`, and `run_sql`. Defer frameworks and additional providers until an actual need appears.
- Treat uploaded files, column names, cell contents, and generated SQL as untrusted input. SQL syntax validation complements an operating-system isolation boundary.
- Store immutable dataset versions and result handles. Findings and charts reference executed result fields instead of invented values.

## Query boundary

Generated SQL will run in a separate, unprivileged worker with no network, no provider credentials, only the relevant database mounted read-only, bounded scratch space, and CPU, memory, time, and output limits. Allow one supported analytical statement and an explicit set of tables and functions. Deny writes, attachments, file scans, extension loading, catalog inspection, and configuration changes. The normal API process must not execute generated SQL before this boundary exists.

Controlled CSV ingestion is a separate path with file-byte, row-count, parse, and storage limits. Cleanup must remove dataset-derived profiles, cached results, and reports.

## Privacy

The local product retains raw datasets locally. The model receives schema, metric definitions, and bounded aggregate results by default. Schema and aggregates can themselves be sensitive, so disclose external processing before enabling the model. Raw examples require explicit user opt-in. Never send credentials, unrelated files, or complete datasets as context.

Use session-scoped ownership checks for datasets, investigations, and artifacts. Production demo uploads are disabled; only synthetic samples are available. Store model keys on the backend, outside version control. Redact raw cells and secrets from application logs.

The activity view shows tools, arguments, validated outputs, and timings. It does not depend on hidden model reasoning.

## Present implementation

Day two provides validated backend settings, a lifespan-managed SQLite metadata store, ordered/checksummed migrations, and internal dataset/investigation repositories. Database relationships enforce session-scoped dataset links, and repository reads and updates require the owning session. Each operation owns and closes its connection; writes and migrations use explicit transactions.

The API exposes `/api/health` for liveness and `/api/ready` for initialized, reachable metadata with a compatible schema. Readiness probes never recreate missing files or repair damaged state. Errors use a consistent envelope with a server-generated request ID and omit request values and raw exception details. Unexpected pre-response request failures are contained before the ASGI server's traceback logger receives them.

The frontend still checks the health endpoint; its connected indicator is not a claim that the metadata database, model provider, or analytical worker is ready. Investigation HTTP routes, account authentication, model integration, and generated-SQL execution remain future work. Metadata status storage does not implement agent state-transition policy.

W04 extends this foundation with local CSV creation and owned metadata lookup. Request bytes stream into a private temporary directory before bounded UTF-8/CSV validation. Canonical text-preserving CSV is imported by a separate fixed-operation DuckDB process with a path allowlist, disabled external access/extensions, a database memory limit, and a parent-enforced timeout. This import process is not an OS-level sandbox or the future arbitrary-query worker. Model/provider environment variables are not passed to it.

Each successful upload receives a fresh dataset/version pair and retains the exact source bytes. The server publishes its private artifact directory and commits session/dataset/import metadata transactionally, removing artifacts on ordinary commit failures. SQLite and filesystem publication are separate operations; process termination can leave private unreferenced artifacts requiring maintenance. See [the ingestion contract](csv-ingestion.md). The current frontend does not yet expose upload controls.

## Consequences

One dataset and one provider keep the first release understandable. The isolated worker adds operational overhead but creates a meaningful boundary for generated queries. A frontend/API split requires two development processes and an explicit production routing configuration. Evaluation and evidence integrity are part of product behavior throughout development.

References: [DuckDB security](https://duckdb.org/security), [FastAPI](https://fastapi.tiangolo.com/), [Vite](https://vite.dev/guide/).
