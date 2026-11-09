# MVP scope and acceptance criteria

Target: a versioned portfolio release by January 7, 2027. The initial web MVP is planned for December 10, 2026. The delivery calendar runs Sunday through Thursday and excludes US federal holidays.

## Supported workflow

Upload one CSV, inspect its profile, ask an analytical question, clarify ambiguous terms, inspect computed results and a chart, ask a follow-up, and export an evidence-backed report.

## Acceptance criteria

- Import rejects empty, malformed, or oversized files with an actionable error. Initial limits: 25 MB or 100,000 rows, subject to benchmarking.
- Profiles expose inferred types, row counts, nulls, duplicates, and bounded numerical and categorical summaries.
- Supported questions include filtering, counts, grouped totals, comparisons, and date-based trends over one dataset.
- Ambiguous metric definitions or dates trigger clarification rather than an unannounced assumption.
- Generated SQL is validated and executed in an isolated worker. Writes, external file scans, network access, and extension loading are unavailable.
- Numerical findings reference actual result fields, SQL, filters, units, and an immutable dataset version.
- Bar, line, and scatter charts use validated result data and have a table alternative.
- Follow-ups remain scoped to the current dataset and session; deletion removes derived artifacts.
- The local application supports private CSV uploads. The hosted portfolio demo uses only curated synthetic datasets.
- A reproducible evaluation reports answer correctness, abstentions, evidence integrity, latency, and cost, including failures.
- A clean environment can complete the sample investigation by following the README.

## Initial budgets

Use at most eight tool steps, two SQL repair attempts, a ten-second query timeout, a 90-second investigation timeout, and 1,000 returned rows. Measure a 512 MB worker memory cap and two concurrent investigations on a documented 4 GB host before finalizing those limits. Provider token and spending limits will be configured when the provider is selected.

## Release evidence

The proposed correctness target is at least 85% on answerable evaluation tasks, measured over three trials. Grade clarification and unsupported requests separately. Every numerical finding must have valid evidence. Release requires the supported browser journeys and boundary checks to pass, with no unresolved high-severity defect in the defined attack corpus. Retain a beta label if the gates fail.

## Deferred work

Multi-file joins, arbitrary Python execution, PDF/Excel inputs, embeddings, multi-agent coordination, production database connectors, teams, billing, and general-purpose private-data hosting are outside this release.

## Day-one completion

A fresh checkout explains the product, scope, architecture, and privacy boundaries; starts a backend and a frontend skeleton; has dependency locks, environment examples, issue/PR templates, and reproducible lint, type, and build checks. Upload and model controls remain absent until their actual implementation.
