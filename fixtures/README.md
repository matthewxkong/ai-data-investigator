# Synthetic fixture dictionary

Generator version 1, default seed **20261112**, supported reference runtime Python **3.13**. The generators use local random-number instances and fixed dates, never the current clock, real customer records, or external services. Source lives in `backend/app/fixtures`. Files in `generated/` are intentional, small, version-controlled test assets rather than uploaded user data.

## Common format and provenance

CSV files use UTF-8 without a BOM, a header row, comma delimiters, standard double-quote escaping, and LF line endings. Blank fields mean missing values. Prices and costs are USD decimal strings with exactly two places; counts are integers. IDs are synthetic identifiers. No generated field identifies a real person.

`generated/manifest.json` records the generator version, seed, encoding, per-file SHA-256, row count, columns, source dataset, variant kind, and exact injected changes. Row numbers in change records are one-based **data records**, excluding the header. The manifest does not hash itself and contains no timestamp or absolute output path. Byte reproducibility is checked across Windows and Linux with the pinned Python runtime; a future Python/generator change must be reviewed as a fixture-version change.

## Sales: 120 clean rows

One row is one order line. Every month from January through June 2026 has five rows in each of North, South, East, and West. `order_id` is unique. Product names deliberately include commas and quotes to exercise valid CSV escaping.

| Column | Logical type / unit | Meaning |
| --- | --- | --- |
| `order_id` | String | Unique order-line identifier `S0001`, etc. |
| `order_date` | ISO calendar date | Date in January-June 2026; no timezone conversion |
| `region` | Category | North, South, East, or West |
| `product` | Category | Notebook, A5; Monitor; Keyboard "Pro"; Mouse |
| `quantity` | Integer units | 1-6 purchased units |
| `unit_price` | Decimal USD/unit | Fixed catalog price for that product |

**Revenue** is `quantity * unit_price`, summed without intermediate floating-point calculations. There are no discounts, taxes, refunds, or cost-of-goods fields. Revenue is not profit. Monthly grouping follows the calendar month in `order_date`. Ranking by units uses product name ascending as the tie-breaker. Reference revenue outputs serialize decimal values as two-place strings; counts and unit totals remain JSON integers.

## Service tickets: 96 clean rows

One row is one ticket, with 24 creation records per month from January through April 2026. There are 48 resolved tickets; the remaining 48 are open or escalated. Creation/resolution times are UTC ISO-8601 strings ending in `Z`. Resolution can extend into a later month.

| Column | Logical type / unit | Meaning |
| --- | --- | --- |
| `ticket_id` | String | Unique synthetic ticket identifier |
| `created_at` | UTC timestamp | Creation time |
| `resolved_at` | Nullable UTC timestamp | Resolution time; blank unless resolved |
| `status` | Category | open, resolved, or escalated |
| `priority` | Category | low, normal, high, or urgent |
| `category` | Category | account, billing, or technical |
| `assigned_team` | Category | Support, Billing, or Platform, respectively |
| `resolution_hours` | Nullable integer hours | Exact elapsed hours from creation to resolution; blank for unresolved tickets |
| `customer_tier` | Category | free, pro, or enterprise; no actual customer identity |

**Unresolved** means `status != 'resolved'`. Resolution-time metrics include resolved tickets only; missing durations must not be treated as zero. Grouping by creation month uses UTC. Priority ordering is lexical unless the question explicitly requests a severity order. The reference SQL loader keeps timestamp text as VARCHAR, and parses numeric durations as INTEGER. No claim about causal team performance follows from these synthetic distributions.

## Inventory: 72 clean rows

One row is one SKU at one warehouse on **June 30, 2026**. There are 24 SKUs in each of North Hub, Central Hub, and West Hub. `(sku, warehouse)` is unique; costs and reorder points are consistent across locations for the same SKU. The first SKU has zero stock in each warehouse to provide explicit stock-out examples.

| Column | Logical type / unit | Meaning |
| --- | --- | --- |
| `snapshot_date` | ISO calendar date | Fixed point-in-time snapshot |
| `sku` | String | Synthetic SKU-001 through SKU-024 |
| `warehouse` | Category | North Hub, Central Hub, or West Hub |
| `category` | Category | hardware, accessories, or office |
| `on_hand` | Integer units | Physical stock, nonnegative |
| `reserved` | Integer units | Allocated stock, between zero and on_hand |
| `reorder_point` | Integer units | Strictly positive reorder threshold |
| `unit_cost` | Decimal USD/unit | Cost used for inventory valuation |

**Available units** = `on_hand - reserved`. A SKU location **needs reorder** when available units are **strictly below** `reorder_point`; equality does not count. **Stock value** = `on_hand * unit_cost`, including reserved units. Counts of SKU locations are not counts of distinct SKUs. A single snapshot does not support a stock trend or a precise future-stock forecast.

## Deliberate quality variants

Each clean dataset has three separate variants, for **12 CSV files total**:

| Suffix | Row count | Intent |
| --- | --- | --- |
| No suffix | 120 sales / 96 tickets / 72 inventory | Clean synthetic data |
| `_nulls` | Same as source | Exactly three additional blank cells; see manifest |
| `_duplicates` | Source + 2 | Exact copies of source data rows 1 and 8 appended |
| `_mixed_types` | Same as source | Three changed cells with invalid numeric formats or ambiguous dates |

Ticket blanks in unresolved resolution fields are legitimate in the clean data. Injected blanks are additional anomalies. Variants remain well-formed CSV; they are not pre-cleaned, imputed, or silently skipped. Clean source tables are never mutated. Development expected answers apply to clean tables only; variants prepare later ingestion/profiling checks rather than model accuracy scores.

## Generate and verify

From `backend`:

```sh
uv sync --locked
uv run --locked python -m app.fixtures
uv run --locked python -m app.fixtures --check
uv run --locked python -m app.fixtures --seed 7 --output ../fixtures/local-seed-7
```

The default output is this repository's `fixtures/generated`, independent of the shell's working directory. `--check` compares expected file bytes and never creates or repairs files. Generation writes the named fixture files and the manifest; it preserves unrelated files and performs no recursive deletion. Alternate-seed output directories should stay outside tracked paths or be explicitly ignored. The checked-in development answers target the default seed only; generating another seed does not rewrite those answers.

## Development and reserved questions

`evaluation/development/cases.json` contains ten explicit questions, ordered result columns, and fixed expected rows. Each case has a standalone SQL file. CI compares that SQL in DuckDB against both the checked-in answer and independent Python/Decimal calculations. Money is loaded as DECIMAL(18,2), not an inferred binary float. These queries are trusted repository fixtures, not an endpoint for executing model-generated SQL.

`evaluation/heldout/manifest.json` contains ten reserved questions, including analytical, clarification, and unsupported-request cases. It contains no SQL or numeric answers and is not read by the development answer loader. Structural tests check version compatibility and exact text/ID overlap. This is an initial split, not the later frozen 40-case benchmark. Because its questions are public, it is not secret, guaranteed unseen, or proof against semantic leakage. A fresh independently authored task set will be needed for claims about unseen-task performance.
