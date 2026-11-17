# Deterministic profiling (W06)

With the API running on loopback, upload a CSV and keep the session cookie as described in [CSV ingestion](csv-ingestion.md). Then request:

```powershell
curl.exe -b cookies.txt http://127.0.0.1:8000/api/datasets/DATASET_ID/profile
```

The typed response contains the dataset ID/version, effective schema revision, profile version `1`, exact row count, duplicate-row count, and column summaries. Missingness counts SQL NULL only; whitespace and textual NA/NULL stay text. Distinct counts exclude NULL and compare original stored text, so `1` and `01` differ. Duplicate rows count occurrences beyond the first, over all original columns; matching NULLs compare equal for this purpose.

Numeric summaries apply to effective integer/decimal columns. DuckDB computes min/max/mean and continuous 25th/50th/75th percentiles after conversion to finite DOUBLE values. For `[1,2,3,4]`, quartiles are `1.75,2.5,3.25`. These summaries use binary floating point, which can round large integers and decimals; every numeric column carries `binary_float_summary`. Values that cannot convert to finite DOUBLE are excluded and counted in `excluded_count`, with `numeric_values_excluded`. Empty aggregates return null. An overflowing aggregate returns null with `numeric_aggregate_overflow`. These are exploratory statistics, not exact financial arithmetic.

Effective categorical and boolean columns expose up to ten original-value frequencies, ordered by descending count then ascending original value. NULLs are excluded. Labels are limited to 256 characters and marked `truncated`; different full values can therefore display the same label. `frequencies_complete` describes whether all distinct categories fit the ten-result limit, independently of label truncation. Text columns have no category samples unless explicitly overridden to categorical. Category labels are local data: no model receives them, but this endpoint intentionally returns those bounded values to the session owner.

Column warnings include schema uncertainty, `missing_values`, and numeric limitations. Dataset warnings flag `duplicate_rows`. The endpoint uses the effective schema revision, including persisted overrides; setting a numeric column to text suppresses its numeric summary. Artifacts, source checksum, dataset version, and physical VARCHAR types remain unchanged. Profiles are recomputed, not cached or persisted.

The existing local Host/Origin, production-disable, and session checks apply. Missing sessions return 401; other-owner/absent datasets return 404; occupied scan slots return 429; unavailable artifacts or failed aggregation return sanitized 503 errors. Responses use `Cache-Control: no-store`. The profiler shares the two-slot schema capacity, first verifies the full accepted workload through schema inspection, and then executes fixed read-only aggregate queries. Stored column identifiers must pass an ASCII allowlist and are quoted. No user SQL or expression is accepted.

DuckDB uses one thread and a 128 MB allocator setting, disabled external access/extensions, and locked configuration. This is a local fixed-query operation with the existing 100,000-row/25 MB input boundary; it has no separate wall-clock deadline or OS sandbox. Wide/high-cardinality datasets can exceed the allocator budget and fail with 503. A future query worker remains separate work. See [schema inspection](schema-inference.md) for its additional limits.
