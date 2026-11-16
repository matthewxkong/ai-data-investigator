# Semantic schema inspection

W05 inspects an imported dataset and suggests semantic types without changing its bytes or DuckDB storage. All stored columns remain `VARCHAR`. The API returns original labels, safe identifiers, evidence counts, explanations, and warnings rather than raw cell samples. No model, generated SQL, timezone guess, or locale guess is involved.

## Inspect a schema

Upload a CSV using [the ingestion instructions](csv-ingestion.md), retaining `cookies.txt`. From PowerShell:

```powershell
curl.exe -b cookies.txt http://127.0.0.1:8000/api/datasets/DATASET_ID/schema
```

`GET /api/datasets/{dataset_id}/schema` returns `dataset_id`, immutable `dataset_version`, `source_sha256`, `inference_version` (`"1"`), `schema_revision`, `rows_examined`, `complete`, and `columns`. Each column includes:

- `position`, `original_name`, `safe_name`, and physical `storage_type` (`VARCHAR`).
- `inferred_type`, `effective_type`, `type_source` (`inferred` or `override`), and `date_order` for an effective slash-date interpretation.
- `non_null_count`, `null_count`, scalar-family `evidence`, a fixed-rule `explanation`, and coded `warnings`.
- The explicit `override`, if present. Warnings continue to describe the original inference even when an override selects another effective type.

Evidence counts can overlap: decimal syntax includes integer syntax; a slash date can be valid under both MDY and DMY. Counts are lexical evidence rather than confidence probabilities or guarantees about business meaning. Numeric-looking identifiers without leading zeros can still require a text override.

## Inference version 1

Every accepted row is examined. Null means the SQL `NULL` produced by an empty CSV cell; whitespace and textual `NULL`/`NA` are preserved as text. Missing cells do not vote for a type. Scalar interpretations examine at most 256 characters per value. Longer values stay text with a warning. No whitespace trimming, currency stripping, numeric grouping removal, or locale conversion occurs.

Rules are conservative and ordered:

| Suggested type | Required non-null evidence |
| --- | --- |
| `boolean` | Every value is a case-insensitive true/false/yes/no word. Numeric 0/1 alone infer integer. |
| `integer` | Every value matches signed ASCII integer syntax, with no leading-zero integer token. |
| `decimal` | Every value matches finite decimal/scientific syntax, with no leading-zero integer token; at least one is not integer syntax. Examples: `1.20`, `.5`, `-2e3`. |
| `date` | Every value is a valid `YYYY-MM-DD` date, or all slash dates fit one unambiguous column-wide MDY/DMY order (optionally mixed with ISO dates). |
| `datetime` | Every value is a valid supported ISO timestamp: `YYYY-MM-DD[T or space]HH:MM:SS`, optional 1-6 fractional digits, optional `Z` or `+/-HH:MM` offset. No timezone conversion occurs. Missing offsets produce a warning. |
| `categorical` | Otherwise unambiguous repeated text has at least 10 non-null values, at most 20 distinct values, and a distinct/non-null ratio at most 20%. This is a heuristic. |
| `text` | All-null, mixed, ambiguous, unsupported, or remaining values. |

Dates use Gregorian calendar validation, including leap years. `03/04/2026` alone stays text because both slash orders work. `13/04/2026` supplies DMY evidence; a column containing both `13/04/2026` and `04/13/2026` stays text because no single order fits. Basic/week ISO dates, abbreviated dates, localized month names, and arbitrary timestamp formats are unsupported. A mixture of date-only values and timestamps stays text.

Leading-zero integer tokens such as `001` retain text automatically; explicit numeric overrides can authorize their interpretation. NaN and infinity are unsupported numeric evidence. Syntactically numeric types are semantic annotations: they do not guarantee fit in a particular DuckDB integer/decimal precision. Physical casts and query policy belong to later milestones.

Warnings use stable codes: `all_null`, `mixed_types`, `ambiguous_dates`, `inconsistent_dates`, `invalid_dates`, `leading_zeros`, `nonfinite_numbers`, `long_values`, `timezone_unspecified`, `low_cardinality`, and `no_type_evidence`. Uncertainty warnings take priority over a categorical suggestion. Inference holds at most 21 distinct SHA-256 value digests per column for the categorical threshold, retaining no raw sample cache. It does not expose category distributions or implement the W06 profiling endpoint.

## Explicit type overrides

`PUT /api/datasets/{dataset_id}/schema/overrides` **replaces the entire override map**. Fetch the schema first, then send its `schema_revision` as `expected_revision`. Keys must be existing `safe_name` values. Supported types are `integer`, `decimal`, `boolean`, `date`, `datetime`, `categorical`, and `text`. `date_order` accepts `mdy`/`dmy` only for a `date` override.

Example request body, saved as `overrides.json`:

```json
{
  "expected_revision": 0,
  "overrides": {
    "code": {"type": "integer"},
    "when": {"type": "date", "date_order": "dmy"}
  }
}
```

```powershell
curl.exe -b cookies.txt -X PUT -H "Content-Type: application/json" --data-binary @overrides.json http://127.0.0.1:8000/api/datasets/DATASET_ID/schema/overrides
```

Use column names from your own schema. An explicit scalar override must match **every** non-null value. Integer/decimal overrides allow leading zeros, boolean overrides additionally allow `0` and `1`, and ambiguous slash dates require an explicit compatible order. Text/categorical accept any text. An all-null column permits an explicit type annotation, but keeps its all-null evidence warning. Invalid requests do not partially apply or increment the revision.

The response is the complete updated schema. Every successful replacement increments the schema revision, including identical replacements. Reset with `{"expected_revision":1,"overrides":{}}`, using the current revision. The reset retains revision history rather than returning to revision 0, so old clients cannot silently overwrite newer edits. Concurrent edits with the same expected revision yield one success and one 409 conflict; refresh and reconsider the change before retrying. SQLite migration 3 persists revisions/overrides and preserves migrations 1-2, imported metadata, and session ownership.

This changes semantic metadata only. Source checksum, dataset ID/version, source file, and physical DuckDB values stay unchanged. No casted table is created. Overrides are not yet consumed by analytical queries or an agent.

## Access and resource limits

Both routes use the upload session cookie and the existing local Host/Origin and production-disable guards. Missing/expired sessions return 401; missing/other-owner datasets return 404. Responses use `Cache-Control: no-store`. There is no caller-controlled owner, filename, SQL, expression, or arbitrary date-format argument. Additional status codes are 409 for stale revisions, 422 for invalid/unknown/incompatible overrides, 429 for occupied scan capacity, and 503 for unavailable/incompatible artifacts or metadata. Errors omit raw values and underlying exceptions and include a matching request ID.

The inspector opens the server-owned DuckDB artifact read-only, disables extensions and external access, locks configuration at connection creation, and executes a fixed `SELECT`. It checks actual column names/storage types and row count against import metadata, fetches at most 256 rows per batch, and enforces the original 100,000-row/25,000,000-text-byte workload bounds. Missing artifacts are never recreated. At most two scans run concurrently per API process, with one DuckDB thread and a 128 MB allocator setting per database instance. These settings are not an OS sandbox or process memory cap. Scanning runs in the API's worker thread, without a separate wall-clock deadline or schema cache. Do not expose this local development service as an arbitrary hosted-data API.

See [W05 evidence](progress/w05.md) for full-fixture, boundary, restart, concurrency, and live HTTP verification. Implementation references: [DuckDB Python DB API](https://duckdb.org/docs/2.0/clients/python/dbapi), [Python calendar parsing](https://docs.python.org/3.13/library/datetime.html), and [Decimal semantics](https://docs.python.org/3.13/library/decimal.html).
