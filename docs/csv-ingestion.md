# Local CSV ingestion

W04 adds backend ingestion and metadata lookup. Upload controls, schema inference, preview, deletion, profiling, and generated SQL are later work. No model or API key is involved.

## Upload and retrieve metadata

Start the API on `127.0.0.1:8000` using the README. From the repository root, use PowerShell:

```powershell
curl.exe -c cookies.txt -b cookies.txt -H "Content-Type: text/csv" -H "X-Filename: sales.csv" --data-binary @fixtures/generated/sales.csv http://127.0.0.1:8000/api/datasets
curl.exe -b cookies.txt http://127.0.0.1:8000/api/datasets/DATASET_ID
```

The first call returns HTTP 201 and a `Location` header for the second call. Replace `DATASET_ID` with the returned `id`. The endpoint takes a raw request body, rather than multipart form data. Accepted media types are `text/csv` and `application/octet-stream`; compressed request bodies are rejected. `X-Filename` defaults to `dataset.csv`, accepts UTF-8 percent encoding, and must decode to a `.csv` filename without directory components. It is display metadata, never a storage path.

The response contains `id`, `version`, `name`, `byte_count`, `row_count`, `created_at`, `sha256`, `delimiter`, and `columns`. Each column records its zero-based `position`, exact `original_name`, and normalized `safe_name`. It omits storage paths, owner IDs, raw cells, and session tokens. Both successful metadata responses and errors use `Cache-Control: no-store`.

Automatic delimiter detection samples the first 65,536 characters and considers comma, semicolon, and tab; it falls back to comma. Specify `?delimiter=%3B`, `?delimiter=%09`, or `?delimiter=%2C` when detection is ambiguous. Detection is a convenience rather than a guarantee for every CSV dialect.

## Parsing and limits

| Boundary | Default |
| --- | --- |
| Source bytes, including BOM/newlines | 25,000,000 |
| Data records | 100,000 |
| Columns | 256 |
| Characters per field | 131,072 |
| Characters per physical line | 1,048,576 |
| Characters per original header | 256 |
| Characters per normalized identifier | 63 |
| Simultaneous uploads/imports per API process | 2 |
| DuckDB allocator memory setting | 256 MB |
| DuckDB spill setting | 256 MB |
| Import subprocess timeout | 45 seconds |

Only UTF-8, optionally with a BOM, is supported. Quoted delimiters and embedded newlines are supported. Empty physical records are skipped; records containing only empty cells still count. Headers must be nonblank text. Duplicate or colliding headers receive stable suffixes, numeric/reserved names receive a prefix, and headers without ASCII identifiers receive positional names. Original labels remain available in the mapping.

Every data record must have the header width. Empty/header-only files, malformed quoting, NUL cells, and invalid UTF-8 fail validation before DuckDB import. Source bytes are streamed with an incremental checksum and a cumulative cap even when Content-Length is absent or understates the body. Row count is checked during validation before creating the database.

The import deliberately stores every column as `VARCHAR`; empty cells become SQL `NULL`. Leading zeros, dates, formula-like strings, SQL-looking text, and numbers remain text. No formulas or uploaded SQL execute. Type inference belongs to W05. The exact source bytes are retained independently of the temporary canonical CSV used for import.

`ADI_UPLOAD_MAX_BYTES`, `ADI_UPLOAD_MAX_ROWS`, and `ADI_UPLOAD_MAX_COLUMNS` can reduce the defaults. `ADI_IMPORT_TIMEOUT_SECONDS` can change the subprocess timeout up to 120 seconds. See [the configuration example](../backend/.env.example).

## Session and local-access boundary

A successful first upload issues an opaque `adi_session` cookie with a 30-day lifetime, `HttpOnly`, `SameSite=Strict`, and `/api` scope. HTTPS adds `Secure`. Only the token hash is stored in SQLite. Subsequent uploads use the same owner while the cookie remains valid. Metadata lookup requires that cookie: missing/invalid sessions return 401, and another owner's dataset returns 404. Clients cannot choose ownership through request fields. Treat the cookie file as a credential; `cookies.txt` is ignored by Git.

This is local session ownership, not account authentication. Bind the server to loopback as documented. Dataset routes reject non-loopback Host names and browser Origins outside the configured exact allowlist. A Host check does not replace a loopback network bind or authenticate remote clients. `ADI_UPLOADS_ENABLED=false` disables the routes, and `ADI_ENVIRONMENT=production` always disables them. The current public demo must not accept arbitrary private uploads. Session expiration does not automatically delete stored datasets.

## Import and persistence boundary

The validator writes a canonical CSV inside a private staging directory. A separate Python process executes a fixed, parameterized DuckDB import using only validated identifiers and this canonical file. It runs with one DuckDB thread, disabled extension loading/autoinstall, disabled external access, an explicit canonical-file allowlist, locked configuration, and a minimal environment excluding model/provider credentials. The parent terminates and waits for a timed-out child.

This process is not an operating-system sandbox, and DuckDB's allocator setting is not an OS-level process memory cap. No arbitrary-query endpoint exists. The future generated-SQL worker requires the stronger isolation described in [the architecture](architecture.md).

Each successful upload receives fresh UUID dataset/version identifiers, even for identical bytes. Equal source bytes have equal SHA-256 checksums. Published directories under the configured data root contain `source.csv` and `data.duckdb`; names come from server UUIDs. Canonical CSV, import specification, and spill files are removed before publication. SQLite migration 2 adds session/import records without rewriting migration 1 or removing existing metadata. Session, dataset, and import metadata are registered in one transaction.

Validation failures, byte/row limits, timeouts, ordinary worker failures, and ordinary metadata-commit failures remove this upload's temporary or published artifacts. Cleanup validates containment and operates only on owned directories. Filesystem publication and SQLite commit are separate operations: abrupt host/process termination can leave private unreferenced directories. Automatic crash reconciliation, retention, and dataset deletion are not implemented. Preserve backups and inspect such artifacts during maintenance with the application stopped; do not assume session expiry removes them.

## Error handling and verification

| HTTP status | Examples |
| --- | --- |
| 400 | Empty/malformed CSV, invalid filename, invalid UTF-8, incomplete body |
| 401 | Missing/invalid lookup session or expiry during registration |
| 403 | Disabled routes, rejected Host/Origin |
| 404 | Missing dataset or another owner |
| 408 | Import subprocess exceeded its deadline |
| 413 | Byte, record, column, field, or physical-line limit |
| 415 | Unsupported media type or compressed request |
| 422 | Invalid typed query/path/header parameter |
| 429 | Both local import slots are busy |
| 503 | Storage or importer unavailable |

Errors use the shared sanitized envelope and matching `X-Request-ID`; raw cell values and underlying exception text are excluded. The W04 suite verifies all 12 checked-in fixtures against actual imported text values, byte/checksum fidelity, 100,000/100,001-row boundaries, session isolation across restarts, migration upgrade, restricted file access, timeout handling, and failure cleanup. See [W04 evidence](progress/w04.md).
