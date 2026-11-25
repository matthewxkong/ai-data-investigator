# Analytical SQL policy

The internal `QueryWorker.select` operation accepts one SELECT over the unqualified `data` table for the active upload session.

```sql
SELECT region, SUM(TRY_CAST(quantity AS BIGINT)) AS units
FROM data WHERE region IS NOT NULL
GROUP BY region ORDER BY units DESC LIMIT 10;
```

Use imported safe column names. The subset includes explicit `AS` aliases, `DISTINCT`, `WHERE`, `GROUP BY` on dataset columns, and `ORDER BY` on dataset columns or aliases. It supports comparison and arithmetic operators, Boolean `AND` and `OR`, and `IS NULL` or `IS NOT NULL`. Allowed functions include `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `LOWER`, `UPPER`, `LENGTH`, `ABS`, `ROUND`, and `COALESCE`. Imported values are text; use `TRY_CAST` to `BIGINT`, `DOUBLE`, `DATE`, or `DECIMAL(18,2)` when needed. `COUNT(*)` is supported; list columns explicitly for other projections.

The launcher rejects unsupported SQL with `sql_policy_denied` and a short correction. Examples include additional statements, writes, joins, subqueries, CTEs, catalog relations, external readers, extension operations, and configuration changes. The worker repeats parsing with the actual artifact's column names. It executes a separate statement compiled from allowed syntax nodes, with literal values bound as parameters. Docker and DuckDB restrictions still apply.

Input is limited to 4,096 characters, 256 tokens, and bounded expression nesting. Output is limited to 12 columns, 50 rows, 256 characters per text cell, and 96 KiB. Without an explicit limit, the worker reads one extra row to detect truncation. An explicit `LIMIT` between 1 and 50 is part of the requested answer and is not itself truncation. A result whose rows, text, or values were clipped or omitted sets `truncated`. For reproducible row order, supply `ORDER BY` with sufficient tie breakers.
