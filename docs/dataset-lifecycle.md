# Local dataset lifecycle

All dataset routes require a valid upload session after the first successful upload issues its cookie. They enforce the [local host and Origin restrictions](csv-ingestion.md) and send `Cache-Control: no-store`. For requests with a valid session, missing datasets and other sessions' datasets both return `404`.

| Request | Result |
| --- | --- |
| `GET /api/datasets?limit=20&offset=0` | Summaries with ID, version, name, byte and row counts, creation time, and source SHA-256. Newest first, with ID as a stable tie breaker. Use `next_offset` until it is `null`. The limit can be 1 to 100; uploads and deletions between pages can shift offsets. |
| `GET /api/datasets/{id}` | Complete import metadata, including delimiter and column mappings. |
| `GET /api/datasets/{id}/preview?limit=20&offset=0` | A page of rows in import order, with dataset ID, version, column mappings, total row count, `offset`, and `next_offset`. The limit can be 1 to 25 and the offset 0 to 100,000. An offset at or beyond the end returns an empty page. |
| `DELETE /api/datasets/{id}` | `204` with no body when metadata and the versioned artifact directory are gone. |

Preview cells are `{ "value": "...", "truncated": false }`. Values stay in their imported text form, and missing values are JSON `null`. A value longer than 128 characters is trimmed to 128 characters and marked `truncated: true`. Render cells as plain text. Preview reads the immutable DuckDB artifact with a fixed read-only query and shares the two scan slots used by schema and profiling. A busy scanner returns `429`; an unavailable or inconsistent artifact returns `503`.

Deletion removes the dataset record, import metadata, saved schema overrides, and dependent investigations in one SQLite transaction. Profiles and previews are computed on request and do not have a separate cache to purge. Once the transaction commits, new dataset lookups return `404`; an in-flight read may finish. File cleanup targets only that import's versioned directory. If cleanup fails, the response is `503` with `delete_pending`. Retry `DELETE` with the same session, or restart the app to retry up to 100 pending deletions per startup. A repeat after successful cleanup returns `404`.

The local session expires after 30 days; expiration and clearing the session cookie do not remove files. Delete uploads before losing the session if you no longer want to retain them. The API removes its own stored copy and metadata. It does not erase the original CSV, filesystem backups, or exports. There is no scheduled expiration or purge of unrequested uploads.
