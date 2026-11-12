# Implemented API: metadata foundation

As of W02, November 10, 2026. The application remains version 0.0.1 while its foundation is built.

## Endpoints

| Method and path | Success | Failure behavior |
| --- | --- | --- |
| `GET /api/health` | 200; process liveness | Independent of metadata availability |
| `GET /api/ready` | 200; metadata store reachable with the complete supported schema | 503 if startup is incomplete, storage is missing/locked, or the schema is incompatible |
| `GET /docs` | Interactive API documentation | Standard HTTP errors |
| `GET /openapi.json` | Machine-readable endpoint and error schemas | Standard HTTP errors |

Health response, unchanged from day one:

```json
{"status":"ok","service":"ai-data-investigator"}
```

Readiness response:

```json
{"status":"ready","metadata_schema_version":1}
```

Readiness checks metadata only. A successful response does not imply CSV ingestion, model access, or an analytical execution worker is implemented. Probes read existing storage without creating replacement files. The configured SQLite timeout bounds waiting for locks. Readiness can recover after storage becomes available again; restarting with corrupt, incomplete, or incompatible storage instead fails startup.

All HTTP responses include a server-generated `X-Request-ID`. Caller-provided request identifiers do not replace it.

## Public error envelope

```json
{
  "error": {
    "code": "metadata_unavailable",
    "message": "Metadata storage is temporarily unavailable.",
    "request_id": "example-server-generated-id",
    "details": []
  }
}
```

The ID in the envelope matches the response header. The example ID above is illustrative; actual IDs are UUID hex strings.

| HTTP status | Code | Meaning |
| --- | --- | --- |
| 404 | `not_found` | Route or owned resource not found |
| 405 | `method_not_allowed` | Unsupported HTTP method; the `Allow` header is preserved |
| Other explicit HTTP errors | `http_error` | Standard status description, without arbitrary exception details |
| 422 | `validation_error` | Invalid request; details identify locations and error types, not submitted values |
| 503 | `metadata_unavailable` | Metadata storage is temporarily unavailable |
| 500 | `internal_error` | Unexpected request failure; correlate using the request ID |

Validation error details have `location`, `type`, and a generic `message`. Raw inputs, validation context, database paths, SQL, and exception messages are not returned. The application logs the request ID and exception class for contained unexpected failures rather than their raw text. Startup errors provide local configuration and recovery guidance; they are not API responses. Future streaming endpoints will need a separate policy for failures after response headers have already been sent.

## Metadata lifecycle

Constructing the app loads configuration and creates per-app service objects; it does not create metadata storage. Entering the FastAPI lifespan creates the configured data directory, serializes migration execution with `BEGIN IMMEDIATE`, validates schema history and required columns, and marks the app started. Failed migrations roll back DDL and ledger changes. Existing history is never rewritten to match a new binary.

`schema_migrations` records version, name, checksum, and application timestamp. Migration 1 creates:

- `datasets`: UUID ID and version, owning session, display name, byte/row counts, and UTC creation time.
- `investigations`: UUID ID, owning session, dataset link, question, validated status, and UTC creation/update times.
- Session/creation indexes and a composite foreign key tying each investigation to a dataset in the same session.

Repositories use parameter-bound SQL and close every connection after the operation. Reads and status updates require a session. Cross-session and absent records are indistinguishable to callers. Status values are `queued`, `running`, `completed`, `failed`, and `cancelled`; this persistence API does not yet dispatch work or enforce an agent transition graph.

These services are internal. There are no HTTP endpoints accepting caller-controlled session IDs, creating datasets, or running investigations in this release. Authentication and the public dataset lifecycle will arrive with their planned milestones.

## Verification

The test suite uses isolated temporary directories and no real credentials, model calls, or private datasets. It exercises settings precedence and secret redaction, transactional migration rollback, incompatible schemas, repository ownership, foreign keys, application recreation, concurrent startup, readiness failure/recovery, unavailable storage, generic errors, and OpenAPI response contracts.
