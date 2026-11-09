# AI Data Investigator

A local-first assistant for investigating CSV data with analytical SQL, charts, and inspectable evidence.

## Product brief

The application helps an analyst understand an unfamiliar dataset, ask a question, and verify the answer. The model selects analytical tools and explains their outputs; the database computes the numbers.

Three primary user stories:

1. As an analyst, I can inspect a CSV's columns, missing values, and distributions before asking questions.
2. As an analyst, I can ask how a metric changes across categories or time and receive a chart supported by executed SQL.
3. As a reviewer, I can inspect the dataset version, query, results, and assumptions behind a finding, then refine the investigation with a follow-up.

The first demonstration will answer: **How did monthly revenue change by region?** It will use reproducible synthetic sales data with known expected results.

Status: project initialization. Data ingestion and model-backed investigations are planned capabilities, not implemented features.
