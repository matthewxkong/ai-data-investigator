# AI Data Investigation Assistant: 60-day delivery plan

**Dates:** November 9, 2026 through January 7, 2027, inclusive. **Timezone:** America/Los_Angeles. **Owner:** matthewxkong. **Holiday calendar:** United States federal holidays, as confirmed by the user.

There are **42 working days and 18 rest days**. Workdays are Sunday through Thursday, excluding federal holidays. Every Friday and Saturday is completely free of planned coding, commits, PR review, issue triage, and catch-up work. November 11 and November 26 remove two additional workdays. December 25 and January 1 already fall on Fridays. Holidays are taken on the published federal calendar dates; this personal schedule does not add a substitute day for holidays that already fall on Friday. No state, employer, or additional religious holidays have been assumed. Recheck the calendar if an additional federal holiday is declared during the period.

**Capacity assumption:** about five focused hours per working day, approximately 210 hours total. A workable day is 15 minutes of issue triage, three hours of implementation, one hour of relevant verification, 30 minutes of review, and 15 minutes of notes. At substantially less time, trim scope using the rules below before increasing hours or using rest days.

**GitHub activity:** 6-10 meaningful commits per working day, or an estimated 252-420 development commits over the plan. Each day below offers eight candidate commit units, 336 in total. Combine units when they belong together; split only where there is a distinct reviewable change. These are work packages rather than a requirement to manufacture activity. Each day also has one issue-sized outcome, for 42 planned daily issues, grouped into 21 focused PRs. Additional bug issues are created only for actual findings. All issue and PR identifiers in this plan are local planning labels; nothing has been opened or published to GitHub.

## The product to finish

Build a local-first web application that accepts one CSV dataset per investigation, profiles it, answers analytical questions by executing restricted SQL, displays useful charts, and lets the user inspect the supporting SQL and results. The public hosted demonstration uses curated synthetic datasets; arbitrary private uploads remain a local feature in v1.

Example: upload sales.csv and ask, "How did monthly revenue change by region?" The assistant inspects the schema, clarifies what revenue means if necessary, runs a grouped query, and returns a line chart, the calculated figures, SQL, filters, dataset version, and limitations. A follow-up such as "Only show the West region" refines the existing investigation. The model proposes operations and explains results; DuckDB computes numbers.

**Required v1 capabilities**

- CSV upload with explicit limits, validation, preview, schema inference, and deletion.
- Deterministic row counts, missingness, numeric summaries, category frequencies, and duplicate warnings.
- A bounded single-agent loop using inspect_schema, profile_data, and run_sql tools; charts use constrained specifications referencing real results.
- Clarification for ambiguous questions; bounded repair for recoverable SQL errors; cancellation and useful failure states.
- Read-only analytical SQL in a restricted worker, with policy enforcement and time, memory, output, and concurrency limits.
- Answers, bar/line/scatter charts, follow-up questions, evidence inspection, and investigation report export.
- Persistent metadata, run status, validated result artifacts, and redacted tool execution events.
- Reproducible evaluation, clean installation, curated demo, short video, architecture explanation, and honest benchmark results.

**Deferred beyond these 60 days:** arbitrary Python execution, multi-file joins, vector search, multi-agent coordination, spreadsheets or PDFs, production database connectors, payments, teams, and a general-purpose hosted private-data service. An embeddings database is unnecessary for the initial structured-data workflow.

## Architecture and boundaries

Suggested stack: Python + FastAPI + Pydantic for the API; DuckDB for analytical execution; SQLite for metadata and checkpoints; React + TypeScript + Vite for the interface; Plotly for charts; pytest and Playwright for meaningful backend and browser checks; Docker for query-worker isolation; GitHub Actions for CI. Select one model provider behind a small adapter on W11; record exact model and dependency versions in lockfiles and reports. This plan does not require a particular paid model or a complex agent framework.

```text
Browser -> FastAPI -> bounded agent loop -> model provider
                |           |
                |           +-> validated tool dispatcher
                |                        |
                |                        +-> isolated DuckDB query worker
                |
                +-> SQLite metadata / persisted evidence artifacts
                +-> controlled CSV ingestion and deterministic profiling
```

The model receives schema, metric definitions, and bounded aggregate results by default. Raw-cell examples require explicit local user opt-in. Generated SQL is untrusted input. The worker has no network, no model credentials, an unprivileged user, only the current database mounted read-only, and bounded scratch space. SQL parsing and allowlists are additional controls rather than substitutes for isolation. Keep the supported analytics grammar deliberately small. Controlled ingestion happens outside the untrusted-query path.

Show user-visible actions, tool arguments, validated results, and timing in the activity view; do not depend on access to a model's hidden reasoning. For private local use, communicate which schema and aggregate values leave the machine. Local API endpoints and artifacts must be scoped to the active session. The hosted demo accepts only synthetic samples, has a model spending ceiling, and provides no arbitrary upload endpoint.

## Acceptance gates and measurement

These are proposed release targets, not achieved results. Confirm practical limits from measurements, and publish any change with its rationale.

- **Correctness:** at least 85% result correctness on answerable held-out tasks over three trials. Publish per-category scores and variability; score abstentions separately so refusals cannot inflate accuracy. Expected outcomes for ambiguous and unsupported tasks are graded separately.
- **Evidence:** every reported numeric finding has a valid result reference and a value rendered from that result. Filters, units, dataset version, and truncation are visible. Unsupported causal claims must be flagged or removed.
- **Boundaries:** zero unresolved high-severity issues in the defined adversarial corpus. Test session leakage, external SQL access, filesystem/network escape attempts, resource limits, malicious CSV text, markup, and export formula handling. Passing this corpus is not a claim of universal security.
- **Workload:** initially target at most 25 MB and 100,000 rows per CSV, whichever limit is reached first; 10 seconds per query, at most 8 tool steps and 2 repair attempts per investigation, 1,000 returned rows, and a 90-second end-to-end timeout. Enforce row limits during import, not just after allocating an unbounded table. Check actual feasibility before keeping these defaults.
- **Resource budget:** start with a 512 MB query-worker memory cap and at most two concurrent investigations on a documented 4 GB host. Set an explicit model token and spend cap after measuring the chosen provider; use a provisional $0.10 per investigation ceiling and a separate monthly demo budget. If the provider cannot fit that ceiling, reduce scope or revise the budget visibly.
- **Experience:** three complete browser journeys pass: ordinary analysis; clarification plus follow-up; and recovery/cancellation. Every chart has a table alternative. A clean setup completes the sample investigation using the README.
- **Operations:** staging restart, worker failure, deletion, budget stops, and rollback have been exercised. The production demo uses only synthetic data and the final report identifies model, prompt, code version, hardware, and actual latency/cost.

Start development evaluation cases on W03. On W24 freeze 40 held-out tasks, including 30 answerable analytical tasks and 10 ambiguity/unsupported-task cases across three datasets. Grade executed results rather than wording. Compare a fixed-prompt text-to-SQL baseline against the agent using the same model, inputs, safety boundary, and task suite; report the additional tool and token budget instead of implying equal compute. Use three trials per case and variant, so a full baseline-plus-agent comparison has 240 runs. After inspecting held-out failures, label that set a regression benchmark rather than claiming it remains unseen; reserve a small fresh question set for the final review if making generalization claims. Use deterministic providers in normal CI and budget live evaluation separately from demo traffic.

## Milestones

| Gate | Date | Evidence required |
| --- | --- | --- |
| M1: deterministic data foundation | Nov 19 | Import, schema, profiling, deletion, and reference-query baseline |
| M2: agent API alpha v0.1 | Dec 3 | Restricted live analysis, clarification, evidence, follow-ups, and valid chart specifications |
| M3: web MVP v0.2 | Dec 10 | Upload-to-answer-to-chart-to-evidence flow works in the browser |
| M4: measured quality | Dec 14 | Frozen task suite, baseline comparison, and prioritized failure analysis |
| M5: feature freeze / beta v0.3 | Dec 24 | Resource benchmarks, core journeys, and release-blocker list |
| M6: staging ready | Dec 30 | Curated demo, budget controls, restart recovery, and rollback |
| M7: release candidate | Jan 5 | Final evaluation, fresh-install verification, and immutable candidate |
| M8: v1 release or explicitly labeled beta | Jan 7 | Release gates determine the label; demo, docs, video, and maintenance backlog are complete |

## All 60 calendar days

W numbers count actual working days. D numbers count calendar days, including rest. No work is scheduled on a row marked REST.


| Day | Date | Weekday | Work item / rest reason | PR action |
| --- | --- | --- | --- | --- |
| D01 | 2026-11-09 | Mon | W01: Define the product and initialize the repository | Open draft P01 |
| D02 | 2026-11-10 | Tue | W02: Build the API and persistence foundation | Review / merge P01 if checks pass |
| D03 | 2026-11-11 | Wed | REST: Veterans Day | None |
| D04 | 2026-11-12 | Thu | W03: Create synthetic data and expected answers | Open draft P02 |
| D05 | 2026-11-13 | Fri | REST: weekly rest | None |
| D06 | 2026-11-14 | Sat | REST: weekly rest | None |
| D07 | 2026-11-15 | Sun | W04: Implement CSV ingestion | Review / merge P02 if checks pass |
| D08 | 2026-11-16 | Mon | W05: Infer and explain the dataset schema | Open draft P03 |
| D09 | 2026-11-17 | Tue | W06: Build deterministic data profiling | Review / merge P03 if checks pass |
| D10 | 2026-11-18 | Wed | W07: Finish the dataset lifecycle | Open draft P04 |
| D11 | 2026-11-19 | Thu | W08: Establish the trusted SQL baseline | Review / merge P04 if checks pass |
| D12 | 2026-11-20 | Fri | REST: weekly rest | None |
| D13 | 2026-11-21 | Sat | REST: weekly rest | None |
| D14 | 2026-11-22 | Sun | W09: Isolate the query worker | Open draft P05 |
| D15 | 2026-11-23 | Mon | W10: Enforce the SQL execution policy | Review / merge P05 if checks pass |
| D16 | 2026-11-24 | Tue | W11: Connect the model through typed tools | Open draft P06 |
| D17 | 2026-11-25 | Wed | W12: Build the bounded agent loop | Review / merge P06 if checks pass |
| D18 | 2026-11-26 | Thu | REST: Thanksgiving Day | None |
| D19 | 2026-11-27 | Fri | REST: weekly rest | None |
| D20 | 2026-11-28 | Sat | REST: weekly rest | None |
| D21 | 2026-11-29 | Sun | W13: Complete the first live investigation | Open draft P07 |
| D22 | 2026-11-30 | Mon | W14: Handle ambiguity and failed queries | Review / merge P07 if checks pass |
| D23 | 2026-12-01 | Tue | W15: Make answers traceable and numerically grounded | Open draft P08 |
| D24 | 2026-12-02 | Wed | W16: Add scoped conversation and follow-up questions | Review / merge P08 if checks pass |
| D25 | 2026-12-03 | Thu | W17: Define trustworthy chart output | Open draft P09 |
| D26 | 2026-12-04 | Fri | REST: weekly rest | None |
| D27 | 2026-12-05 | Sat | REST: weekly rest | None |
| D28 | 2026-12-06 | Sun | W18: Build the frontend shell and dataset overview | Review / merge P09 if checks pass |
| D29 | 2026-12-07 | Mon | W19: Build upload and dataset selection | Open draft P10 |
| D30 | 2026-12-08 | Tue | W20: Build the investigation conversation UI | Review / merge P10 if checks pass |
| D31 | 2026-12-09 | Wed | W21: Expose evidence in the interface | Open draft P11 |
| D32 | 2026-12-10 | Thu | W22: Render charts and ship the web MVP | Review / merge P11 if checks pass |
| D33 | 2026-12-11 | Fri | REST: weekly rest | None |
| D34 | 2026-12-12 | Sat | REST: weekly rest | None |
| D35 | 2026-12-13 | Sun | W23: Build the agent evaluation harness | Open draft P12 |
| D36 | 2026-12-14 | Mon | W24: Run the first held-out evaluation | Review / merge P12 if checks pass |
| D37 | 2026-12-15 | Tue | W25: Improve resilience and control spending | Open draft P13 |
| D38 | 2026-12-16 | Wed | W26: Optimize profiling and safe result reuse | Review / merge P13 if checks pass |
| D39 | 2026-12-17 | Thu | W27: Add resumable investigations and useful traces | Open draft P14 |
| D40 | 2026-12-18 | Fri | REST: weekly rest | None |
| D41 | 2026-12-19 | Sat | REST: weekly rest | None |
| D42 | 2026-12-20 | Sun | W28: Automate complete user journeys | Review / merge P14 if checks pass |
| D43 | 2026-12-21 | Mon | W29: Improve accessibility and onboarding | Open draft P15 |
| D44 | 2026-12-22 | Tue | W30: Challenge the SQL and data boundaries | Review / merge P15 if checks pass |
| D45 | 2026-12-23 | Wed | W31: Benchmark realistic workloads | Open draft P16 |
| D46 | 2026-12-24 | Thu | W32: Freeze features and stabilize the beta | Review / merge P16 if checks pass |
| D47 | 2026-12-25 | Fri | REST: weekly rest + Christmas Day | None |
| D48 | 2026-12-26 | Sat | REST: weekly rest | None |
| D49 | 2026-12-27 | Sun | W33: Use the first contingency day | Open draft P17 |
| D50 | 2026-12-28 | Mon | W34: Use the second contingency day | Review / merge P17 if checks pass |
| D51 | 2026-12-29 | Tue | W35: Package and deploy the curated demo | Open draft P18 |
| D52 | 2026-12-30 | Wed | W36: Finish deployment health and recovery | Review / merge P18 if checks pass |
| D53 | 2026-12-31 | Thu | W37: Publish the technical explanation and export workflow | Open draft P19 |
| D54 | 2027-01-01 | Fri | REST: weekly rest + New Year's Day | None |
| D55 | 2027-01-02 | Sat | REST: weekly rest | None |
| D56 | 2027-01-03 | Sun | W38: Validate installation and onboarding independently | Review / merge P19 if checks pass |
| D57 | 2027-01-04 | Mon | W39: Run the final frozen evaluation | Open draft P20 |
| D58 | 2027-01-05 | Tue | W40: Prepare and verify the release candidate | Review / merge P20 if checks pass |
| D59 | 2027-01-06 | Wed | W41: Prepare the portfolio demonstration | Open draft P21 |
| D60 | 2027-01-07 | Thu | W42: Release and close the project | Review / merge P21 if checks pass |

## Daily work packages

Each W entry is one planned issue. Create it at the start of that workday with the acceptance evidence below. The eight checkboxes are candidate commit units. A unit can include the implementation and the smallest useful checks needed to verify it; a checkbox is complete only when the change is reviewable and verified. On even W days, review the paired PR, attach actual evidence, and merge only when relevant checks pass. On odd W days, open the next draft PR. If work slips, update the dates and priority explicitly; no rest-day catch-up is assumed.

### W01 / D01 - Monday, November 09, 2026

**Issue W01: Define the product and initialize the repository.** Paired PR: P01.

**Done when:** A fresh checkout has a clear product brief, directory structure, contribution workflow, and runnable skeleton.

**Candidate commits:**

- [ ] Write three target user stories.
- [ ] Define MVP acceptance criteria and exclusions.
- [ ] Record architecture and privacy decisions.
- [ ] Initialize backend and frontend directories.
- [ ] Add environment example and ignore rules.
- [ ] Add issue and PR templates.
- [ ] Add lint and build CI skeleton.
- [ ] Document local setup and first demo scenario.

### W02 / D02 - Tuesday, November 10, 2026

**Issue W02: Build the API and persistence foundation.** Paired PR: P01.

**Done when:** The API starts, reports health, persists metadata, and passes its initial CI checks.

**Candidate commits:**

- [ ] Create FastAPI application factory.
- [ ] Define typed settings and secret loading.
- [ ] Add health and readiness endpoints.
- [ ] Create SQLite metadata schema and migrations.
- [ ] Add dataset and investigation repositories.
- [ ] Define consistent API error envelopes.
- [ ] Add API smoke and persistence checks.
- [ ] Complete developer setup and merge P01.

### W03 / D04 - Thursday, November 12, 2026

**Issue W03: Create synthetic data and expected answers.** Paired PR: P02.

**Done when:** Three reproducible datasets have known answers and documented assumptions, with development and held-out cases separated.

**Candidate commits:**

- [ ] Create seeded sales dataset generator.
- [ ] Create seeded service-ticket dataset generator.
- [ ] Create seeded inventory dataset generator.
- [ ] Add null duplicate and mixed-type variants.
- [ ] Write ten development questions and reference SQL.
- [ ] Create separate held-out question manifest.
- [ ] Record data dictionaries and metric definitions.
- [ ] Add fixture generation command and reproducibility checks.

### W04 / D07 - Sunday, November 15, 2026

**Issue W04: Implement CSV ingestion.** Paired PR: P02.

**Done when:** A valid local CSV becomes an internal dataset; malformed or oversized input produces an actionable error.

**Candidate commits:**

- [ ] Implement streamed upload endpoint.
- [ ] Enforce initial file byte and row limits.
- [ ] Normalize UTF-8 headers and safe identifiers.
- [ ] Handle delimiters quoting and blank lines.
- [ ] Import through controlled DuckDB ingestion.
- [ ] Store checksum and immutable dataset version.
- [ ] Cover malformed empty and oversized files.
- [ ] Document import limits and merge P02.

### W05 / D08 - Monday, November 16, 2026

**Issue W05: Infer and explain the dataset schema.** Paired PR: P03.

**Done when:** Users can inspect inferred types and see warnings when numeric or date interpretation is uncertain.

**Candidate commits:**

- [ ] Implement schema inspection service.
- [ ] Detect numeric categorical date and boolean columns.
- [ ] Flag ambiguous dates and mixed types.
- [ ] Preserve original and normalized column names.
- [ ] Return schema through typed API.
- [ ] Add explicit user type-override contract.
- [ ] Check inference on messy synthetic fixtures.
- [ ] Document inference rules and uncertainty.

### W06 / D09 - Tuesday, November 17, 2026

**Issue W06: Build deterministic data profiling.** Paired PR: P03.

**Done when:** A profile exposes row counts, missing values, distributions, and data-quality warnings computed by the database.

**Candidate commits:**

- [ ] Compute row and distinct-value counts.
- [ ] Compute per-column missingness.
- [ ] Compute numeric range quantiles and mean.
- [ ] Compute bounded categorical frequencies.
- [ ] Detect exact duplicate rows.
- [ ] Return structured profile and quality warnings.
- [ ] Check profiles against reference calculations.
- [ ] Document profiling behavior and merge P03.

### W07 / D10 - Wednesday, November 18, 2026

**Issue W07: Finish the dataset lifecycle.** Paired PR: P04.

**Done when:** Dataset metadata, preview, profiling, and deletion work together without exposing another session's data.

**Candidate commits:**

- [ ] Create opaque local-session identifiers.
- [ ] Scope dataset lookup to session ownership.
- [ ] Add paginated bounded preview endpoint.
- [ ] Add dataset list and metadata endpoints.
- [ ] Add explicit dataset deletion endpoint.
- [ ] Delete associated artifacts and cached metadata.
- [ ] Check cross-session access and cleanup.
- [ ] Document retention policy and deletion semantics.

### W08 / D11 - Thursday, November 19, 2026

**Issue W08: Establish the trusted SQL baseline.** Paired PR: P04.

**Done when:** Known developer-authored SQL reproduces fixture answers; the benchmark runner records exact expected results.

**Candidate commits:**

- [ ] Create query result and evidence schemas.
- [ ] Execute fixed reference queries against imported data.
- [ ] Normalize numeric null and date results.
- [ ] Record SQL result hash and dataset version.
- [ ] Add row truncation and aggregate completeness markers.
- [ ] Implement configurable numeric tolerances.
- [ ] Run ten development reference cases.
- [ ] Save deterministic baseline report and merge P04.

### W09 / D14 - Sunday, November 22, 2026

**Issue W09: Isolate the query worker.** Paired PR: P05.

**Done when:** The worker can query its mounted dataset while blocked from network access, host secrets, and unrelated files.

**Candidate commits:**

- [ ] Separate query worker from API process.
- [ ] Build non-root worker container.
- [ ] Mount only the current dataset read-only.
- [ ] Disable worker networking and inherited secrets.
- [ ] Apply CPU memory time and output limits.
- [ ] Terminate timed-out queries and clean workers.
- [ ] Check prohibited network and filesystem access.
- [ ] Document worker boundary and deployment requirements.

### W10 / D15 - Monday, November 23, 2026

**Issue W10: Enforce the SQL execution policy.** Paired PR: P05.

**Done when:** Allowed analytical queries succeed; disallowed statements, file functions, and extension operations fail before execution.

**Candidate commits:**

- [ ] Parse SQL into a syntax tree.
- [ ] Allow one approved analytical statement shape.
- [ ] Allowlist dataset relations and scalar functions.
- [ ] Reject writes attachments external scans and extensions.
- [ ] Restrict catalog access and configuration changes.
- [ ] Return actionable policy-denial errors.
- [ ] Add bypass cases and isolation regression checks.
- [ ] Document policy limits and merge P05.

### W11 / D16 - Tuesday, November 24, 2026

**Issue W11: Connect the model through typed tools.** Paired PR: P06.

**Done when:** A fake provider and one selected real provider use the same interface, budgets, and validated tool contracts.

**Candidate commits:**

- [ ] Define provider-neutral model adapter.
- [ ] Implement fake deterministic provider.
- [ ] Connect one selected real model provider.
- [ ] Define inspect_schema and profile_data tools.
- [ ] Define run_sql result-handle contract.
- [ ] Validate tool arguments and returned envelopes.
- [ ] Add model timeout token and step budgets.
- [ ] Check adapter behavior without paid API calls.

### W12 / D17 - Wednesday, November 25, 2026

**Issue W12: Build the bounded agent loop.** Paired PR: P06.

**Done when:** A scripted model can inspect a schema, request a query, receive results, and finish within a fixed step budget.

**Candidate commits:**

- [ ] Define investigation state and terminal states.
- [ ] Implement tool dispatch and observation loop.
- [ ] Restrict available tools by investigation state.
- [ ] Add structured clarification and refusal states.
- [ ] Persist tool calls results and execution events.
- [ ] Keep raw cells out of model context by default.
- [ ] Check success malformed calls and budget exhaustion.
- [ ] Document agent contracts and merge P06.

### W13 / D21 - Sunday, November 29, 2026

**Issue W13: Complete the first live investigation.** Paired PR: P07.

**Done when:** A real model answers five development questions using the isolated query worker and visible evidence.

**Candidate commits:**

- [ ] Add create-investigation API endpoint.
- [ ] Compose schema and metric-definition context.
- [ ] Route generated SQL through policy and worker.
- [ ] Return bounded aggregate results to the model.
- [ ] Generate answer with evidence references.
- [ ] Save result artifacts and selected model metadata.
- [ ] Run five live questions and inspect outcomes.
- [ ] Write first end-to-end walkthrough.

### W14 / D22 - Monday, November 30, 2026

**Issue W14: Handle ambiguity and failed queries.** Paired PR: P07.

**Done when:** Ambiguous requests ask a specific question; repairable SQL errors recover with bounded retries and visible failure status.

**Candidate commits:**

- [ ] Detect missing measures and ambiguous column references.
- [ ] Ask targeted clarification before execution.
- [ ] Accept a clarification response through the API.
- [ ] Classify SQL errors for bounded repair.
- [ ] Cap repair attempts and prevent retry loops.
- [ ] Stop cleanly on cancellation or exhausted budgets.
- [ ] Exercise unknown columns ambiguous dates and empty results.
- [ ] Record recovery examples and merge P07.

### W15 / D23 - Tuesday, December 01, 2026

**Issue W15: Make answers traceable and numerically grounded.** Paired PR: P08.

**Done when:** Each reported numeric finding references an executed result and states filters, units, and relevant limitations.

**Candidate commits:**

- [ ] Define structured findings and evidence schema.
- [ ] Bind findings to result identifiers.
- [ ] Render numeric values from result fields.
- [ ] Include filters units and dataset version.
- [ ] Expose exact SQL and result previews.
- [ ] Flag truncation and unsupported causal explanations.
- [ ] Check invented numbers and missing evidence references.
- [ ] Document how readers can verify a finding.

### W16 / D24 - Wednesday, December 02, 2026

**Issue W16: Add scoped conversation and follow-up questions.** Paired PR: P08.

**Done when:** A follow-up can refine an existing analysis without leaking context from another dataset or session.

**Candidate commits:**

- [ ] Persist conversation turns by investigation.
- [ ] Track explicit filters measures and date range.
- [ ] Resolve simple follow-ups from stored context.
- [ ] Invalidate context when dataset version changes.
- [ ] Bound stored context and summarize validated facts.
- [ ] Add investigation list and detail endpoints.
- [ ] Check follow-up accuracy and cross-session isolation.
- [ ] Document conversation behavior and merge P08.

### W17 / D25 - Thursday, December 03, 2026

**Issue W17: Define trustworthy chart output.** Paired PR: P09.

**Done when:** The API emits valid bar, line, and scatter specifications bound to actual result columns; tag API alpha v0.1.

**Candidate commits:**

- [ ] Define constrained chart specification schema.
- [ ] Select chart type from result field types.
- [ ] Bind chart data to executed result handles.
- [ ] Validate axes units labels and date ordering.
- [ ] Limit points and reject misleading specifications.
- [ ] Add a plain table fallback for unsuitable charts.
- [ ] Check three chart types against fixture results.
- [ ] Record API alpha demo and tag v0.1.

### W18 / D28 - Sunday, December 06, 2026

**Issue W18: Build the frontend shell and dataset overview.** Paired PR: P09.

**Done when:** The browser loads a responsive layout and displays real dataset metadata and profiles from the API.

**Candidate commits:**

- [ ] Initialize React TypeScript and Vite app.
- [ ] Add typed API client and request errors.
- [ ] Build application navigation and layout.
- [ ] Create dataset overview and schema panel.
- [ ] Display profile metrics and quality warnings.
- [ ] Add loading empty and failed-request states.
- [ ] Check component rendering and API integration.
- [ ] Complete chart-contract and frontend-foundation PR P09.

### W19 / D29 - Monday, December 07, 2026

**Issue W19: Build upload and dataset selection.** Paired PR: P10.

**Done when:** A user can upload a permitted CSV, inspect its preview, choose a dataset, and delete it from the browser.

**Candidate commits:**

- [ ] Add file picker and drag-and-drop upload.
- [ ] Show upload size and validation feedback.
- [ ] Show import progress and cancel controls.
- [ ] Render paginated data preview.
- [ ] Build dataset selector and current dataset state.
- [ ] Wire delete confirmation and post-delete cleanup.
- [ ] Check upload invalid file and delete flows.
- [ ] Document supported upload workflow.

### W20 / D30 - Tuesday, December 08, 2026

**Issue W20: Build the investigation conversation UI.** Paired PR: P10.

**Done when:** A user can ask a question, answer clarification, observe status, and cancel an investigation.

**Candidate commits:**

- [ ] Build question composer and example prompts.
- [ ] Render user turns and assistant answers.
- [ ] Poll typed investigation status endpoints.
- [ ] Show tool names status and timing.
- [ ] Add clarification reply interface.
- [ ] Add cancellation and retry controls.
- [ ] Check conversation and error-recovery flows.
- [ ] Finish upload and conversation PR P10.

### W21 / D31 - Wednesday, December 09, 2026

**Issue W21: Expose evidence in the interface.** Paired PR: P11.

**Done when:** Every answer has inspectable SQL, result tables, dataset version, and assumptions in an accessible evidence panel.

**Candidate commits:**

- [ ] Add evidence reference links in findings.
- [ ] Build expandable SQL panel.
- [ ] Render result tables with truncation markers.
- [ ] Show metric definitions filters and units.
- [ ] Display warnings and answer limitations.
- [ ] Add copy SQL and result download actions.
- [ ] Check links against actual result identifiers.
- [ ] Write evidence-first demo scenario.

### W22 / D32 - Thursday, December 10, 2026

**Issue W22: Render charts and ship the web MVP.** Paired PR: P11.

**Done when:** A complete upload-to-question-to-chart-to-evidence flow works in the browser; tag web MVP v0.2.

**Candidate commits:**

- [ ] Integrate React Plotly chart renderer.
- [ ] Render bar line and scatter specifications.
- [ ] Add chart table toggle and responsive resizing.
- [ ] Display chart labels units and sample limits.
- [ ] Export a supported chart image.
- [ ] Exercise three user journeys end to end.
- [ ] Fix MVP integration defects found in those journeys.
- [ ] Record MVP demo tag v0.2 and merge P11.

### W23 / D35 - Sunday, December 13, 2026

**Issue W23: Build the agent evaluation harness.** Paired PR: P12.

**Done when:** One command runs fixed tasks with recorded outcomes, tool traces, cost, latency, and deterministic result grading.

**Candidate commits:**

- [ ] Define evaluation task and result schemas.
- [ ] Implement isolated dataset setup per case.
- [ ] Grade tables scalars and numeric tolerance.
- [ ] Grade evidence coverage and invalid chart references.
- [ ] Record retries latency tokens and estimated model cost.
- [ ] Add non-agent fixed-prompt SQL baseline.
- [ ] Run development suite and classify failures.
- [ ] Write reproducible evaluation command.

### W24 / D36 - Monday, December 14, 2026

**Issue W24: Run the first held-out evaluation.** Paired PR: P12.

**Done when:** A frozen 40-case task set has repeated baseline and agent runs, failure categories, and a published result table.

**Candidate commits:**

- [ ] Complete forty held-out tasks across three datasets.
- [ ] Include ambiguity missing-data and unsupported requests.
- [ ] Freeze expected answers and grading rules.
- [ ] Run three trials per task for baseline and agent.
- [ ] Summarize success rates and trial variation.
- [ ] Separate wrong answers from explicit abstentions.
- [ ] Publish failure taxonomy and prioritized fixes.
- [ ] Save benchmark artifacts and merge P12.

### W25 / D37 - Tuesday, December 15, 2026

**Issue W25: Improve resilience and control spending.** Paired PR: P13.

**Done when:** Rate limits, transient provider failures, cancellation, and per-run budget limits produce predictable outcomes.

**Candidate commits:**

- [ ] Add transient-error backoff with retry cap.
- [ ] Propagate cancellation through API model and worker.
- [ ] Add per-session request throttles.
- [ ] Enforce per-run model spend ceiling.
- [ ] Limit concurrent investigations and queue depth.
- [ ] Expose provider failures without leaking secrets.
- [ ] Check throttling timeout cancellation and cleanup.
- [ ] Document operational limits and recovery actions.

### W26 / D38 - Wednesday, December 16, 2026

**Issue W26: Optimize profiling and safe result reuse.** Paired PR: P13.

**Done when:** Repeated identical requests reuse valid work while dataset changes and session boundaries prevent incorrect reuse.

**Candidate commits:**

- [ ] Measure ingestion profiling and query timings.
- [ ] Cache deterministic schema and profile outputs.
- [ ] Key result reuse by session dataset version and SQL.
- [ ] Exclude errors and partial results from reuse.
- [ ] Invalidate artifacts after dataset deletion.
- [ ] Bound cache storage and retention.
- [ ] Check stale-cache and cross-session cases.
- [ ] Publish before-after timings and merge P13.

### W27 / D39 - Thursday, December 17, 2026

**Issue W27: Add resumable investigations and useful traces.** Paired PR: P14.

**Done when:** Restarting the API preserves completed evidence and gives interrupted runs a correct resumable or failed status.

**Candidate commits:**

- [ ] Persist state transitions transactionally.
- [ ] Add recoverable checkpoint boundaries.
- [ ] Mark interrupted model calls for explicit retry.
- [ ] Resume from validated stored result handles.
- [ ] Expose event timeline with tool outputs and durations.
- [ ] Redact sensitive fields in logs and traces.
- [ ] Check crash recovery and duplicate dispatch handling.
- [ ] Document recovery guarantees and limitations.

### W28 / D42 - Sunday, December 20, 2026

**Issue W28: Automate complete user journeys.** Paired PR: P14.

**Done when:** Browser tests cover three real workflows and failure recovery against deterministic model responses.

**Candidate commits:**

- [ ] Add Playwright application test setup.
- [ ] Cover upload profile ask and evidence journey.
- [ ] Cover clarification then follow-up journey.
- [ ] Cover charts download and dataset deletion journey.
- [ ] Cover provider failure and user cancellation.
- [ ] Add deterministic fake-provider integration mode.
- [ ] Run browser tests in CI with failure artifacts.
- [ ] Document test setup and merge P14.

### W29 / D43 - Monday, December 21, 2026

**Issue W29: Improve accessibility and onboarding.** Paired PR: P15.

**Done when:** A new user can complete a sample investigation using keyboard navigation and understandable status feedback.

**Candidate commits:**

- [ ] Add keyboard navigation and visible focus.
- [ ] Label controls and announce run status.
- [ ] Check contrast and chart color choices.
- [ ] Make table views available for all charts.
- [ ] Improve empty states and sample question guidance.
- [ ] Check narrow viewport and long-value layouts.
- [ ] Fix accessibility and usability defects found.
- [ ] Write a five-minute first-investigation guide.

### W30 / D44 - Tuesday, December 22, 2026

**Issue W30: Challenge the SQL and data boundaries.** Paired PR: P15.

**Done when:** The defined attack corpus is blocked or safely handled, with no unresolved high-severity boundary failures.

**Candidate commits:**

- [ ] Create malicious CSV-cell instruction cases.
- [ ] Create SQL external-access and extension bypass cases.
- [ ] Create oversized-query and resource-exhaustion cases.
- [ ] Probe session and artifact identifier access.
- [ ] Probe markup rendering and exported CSV formulas.
- [ ] Fix confirmed boundary failures.
- [ ] Rerun policy worker and browser regressions.
- [ ] Publish threat-model results and merge P15.

### W31 / D45 - Wednesday, December 23, 2026

**Issue W31: Benchmark realistic workloads.** Paired PR: P16.

**Done when:** A reproducible report measures performance and cost on fixed datasets, identifies bottlenecks, and records actual limits.

**Candidate commits:**

- [ ] Generate small medium and limit-size datasets.
- [ ] Record hardware container limits and model settings.
- [ ] Measure upload and profiling latency.
- [ ] Measure query and end-to-end p50 and p95.
- [ ] Measure worker peak memory and concurrent-run behavior.
- [ ] Measure model tokens and estimated per-run spend.
- [ ] Fix the largest measured performance problem.
- [ ] Publish results with workload definitions.

### W32 / D46 - Thursday, December 24, 2026

**Issue W32: Freeze features and stabilize the beta.** Paired PR: P16.

**Done when:** Feature work stops; a repeatable demo and a prioritized defect list define the remaining release work.

**Candidate commits:**

- [ ] Run the core browser journeys against the live provider.
- [ ] Resolve the most disruptive confirmed UX defects.
- [ ] Resolve the most frequent development-eval failure.
- [ ] Check consistent errors and progress states.
- [ ] Review deletion and cache cleanup behavior.
- [ ] Record known limitations and beta release notes.
- [ ] Create prioritized release-blocker issue list.
- [ ] Tag beta v0.3 and merge P16.

### W33 / D49 - Sunday, December 27, 2026

**Issue W33: Use the first contingency day.** Paired PR: P17.

**Done when:** The highest-priority release blocker is resolved with evidence; otherwise improve a documented weak case.

**Candidate commits:**

- [ ] Triage remaining blockers by user impact.
- [ ] Select one bounded defect or reliability improvement.
- [ ] Reproduce it with a concrete failing case.
- [ ] Implement the smallest complete correction.
- [ ] Check adjacent behavior affected by the change.
- [ ] Rerun the relevant development evaluation subset.
- [ ] Update issue evidence and affected documentation.
- [ ] Review release readiness against acceptance criteria.

### W34 / D50 - Monday, December 28, 2026

**Issue W34: Use the second contingency day.** Paired PR: P17.

**Done when:** The next highest-priority defect is resolved, and a fresh checkout passes the supported local workflow.

**Candidate commits:**

- [ ] Select the next confirmed blocker or weak case.
- [ ] Reproduce the problem on a fresh environment.
- [ ] Correct the owning component.
- [ ] Add a meaningful regression case.
- [ ] Check dependency and platform compatibility.
- [ ] Run the affected full user journey.
- [ ] Update known limitations and setup instructions.
- [ ] Merge documented stabilization changes in P17.

### W35 / D51 - Tuesday, December 29, 2026

**Issue W35: Package and deploy the curated demo.** Paired PR: P18.

**Done when:** A staging deployment serves only synthetic sample datasets and survives a clean restart without leaking credentials.

**Candidate commits:**

- [ ] Create production API and frontend build configuration.
- [ ] Package isolated worker deployment separately.
- [ ] Configure staging secrets outside images.
- [ ] Disable arbitrary uploads in the public demo.
- [ ] Seed curated synthetic sample datasets.
- [ ] Set deployment concurrency spend and retention limits.
- [ ] Deploy staging and exercise one complete investigation.
- [ ] Document hosting cost and operating requirements.

### W36 / D52 - Wednesday, December 30, 2026

**Issue W36: Finish deployment health and recovery.** Paired PR: P18.

**Done when:** The staging service exposes health, logs useful events, enforces budgets, and has a tested rollback procedure.

**Candidate commits:**

- [ ] Add readiness for metadata and worker availability.
- [ ] Add structured request and investigation identifiers.
- [ ] Track error rate run duration and spend estimates.
- [ ] Add configured alert thresholds and budget stop behavior.
- [ ] Exercise restart and worker failure recovery.
- [ ] Test rollback to the previous build.
- [ ] Check staging dataset and session isolation.
- [ ] Write operational runbook and merge P18.

### W37 / D53 - Thursday, December 31, 2026

**Issue W37: Publish the technical explanation and export workflow.** Paired PR: P19.

**Done when:** The repository explains the architecture and tradeoffs, and users can export an investigation with evidence.

**Candidate commits:**

- [ ] Write architecture diagram and component responsibilities.
- [ ] Explain agent loop tool contracts and SQL boundary.
- [ ] Document model data-sharing and retention behavior.
- [ ] Add Markdown investigation report export.
- [ ] Include SQL findings charts references and limitations.
- [ ] Check export escaping and artifact completeness.
- [ ] Write tradeoffs and deferred-features discussion.
- [ ] Draft the technical case study.

### W38 / D56 - Sunday, January 03, 2027

**Issue W38: Validate installation and onboarding independently.** Paired PR: P19.

**Done when:** A clean environment follows the README and completes the sample investigation without undocumented steps.

**Candidate commits:**

- [ ] Run installation in a fresh environment.
- [ ] Verify dependency pins and lockfiles.
- [ ] Verify API-key and fake-provider setup paths.
- [ ] Check sample dataset and first-query instructions.
- [ ] Check links commands and screenshots.
- [ ] Fix discovered setup and documentation defects.
- [ ] Record supported platforms and known constraints.
- [ ] Merge reports and onboarding documentation in P19.

### W39 / D57 - Monday, January 04, 2027

**Issue W39: Run the final frozen evaluation.** Paired PR: P20.

**Done when:** The final report compares the original baseline and release candidate on identical frozen tasks with honest failures.

**Candidate commits:**

- [ ] Freeze release-candidate code prompt and model settings.
- [ ] Rerun forty held-out tasks with three trials.
- [ ] Recheck baseline comparability and version metadata.
- [ ] Compute correctness abstention and evidence coverage.
- [ ] Report latency spend and trial variation.
- [ ] Run the adversarial and resource-boundary corpus.
- [ ] Publish result files and limitations.
- [ ] Classify every remaining release blocker.

### W40 / D58 - Tuesday, January 05, 2027

**Issue W40: Prepare and verify the release candidate.** Paired PR: P20.

**Done when:** An immutable release candidate passes critical checks or remains explicitly labeled beta with documented blockers.

**Candidate commits:**

- [ ] Resolve the highest-priority remaining blocker.
- [ ] Run affected regression and browser checks.
- [ ] Run fresh-install and staging smoke checks.
- [ ] Verify complete dataset and session cleanup.
- [ ] Review dependency image and secret handling.
- [ ] Finalize release notes and changelog.
- [ ] Tag v1.0-rc1 with artifact checksums.
- [ ] Merge candidate-validation PR P20.

### W41 / D59 - Wednesday, January 06, 2027

**Issue W41: Prepare the portfolio demonstration.** Paired PR: P21.

**Done when:** A reviewer can understand the problem, watch a short demo, and inspect measured results and architectural decisions.

**Candidate commits:**

- [ ] Record a two-to-three-minute product walkthrough.
- [ ] Capture upload profile answer chart and SQL views.
- [ ] Show one clarification and one honest limitation.
- [ ] Finalize the technical case study.
- [ ] Add architecture and benchmark links to README.
- [ ] Prepare a concise project description for the portfolio.
- [ ] Correct issues uncovered while recording.
- [ ] Prepare release announcement text and final checklist.

### W42 / D60 - Thursday, January 07, 2027

**Issue W42: Release and close the project.** Paired PR: P21.

**Done when:** The versioned app, repository documentation, demo, benchmark report, and maintenance backlog are ready for review.

**Candidate commits:**

- [ ] Run release-gate checks on the final candidate.
- [ ] Promote to v1.0 only if acceptance gates pass.
- [ ] Deploy the approved build or retain beta label.
- [ ] Verify the demo from a fresh browser session.
- [ ] Publish versioned release notes and demo links.
- [ ] Close completed issues with evidence.
- [ ] Move incomplete enhancements into a future milestone.
- [ ] Merge P21 and record the final project retrospective.

## PR map

P labels are planning identifiers, not existing GitHub PR numbers. Use one branch per paired scope; keep the default branch usable. The listed merge date is a target, contingent on checks and self-review.

| PR | Scope | Open draft | Target review / merge | Related issues |
| --- | --- | --- | --- | --- |
| P01 | Product brief, API, and persistence foundation | Nov 09 | Nov 10 | W01, W02 |
| P02 | Synthetic data, reference answers, and CSV ingestion | Nov 12 | Nov 15 | W03, W04 |
| P03 | Schema inference and deterministic profiling | Nov 16 | Nov 17 | W05, W06 |
| P04 | Dataset lifecycle and trusted SQL baseline | Nov 18 | Nov 19 | W07, W08 |
| P05 | Isolated query execution and SQL policy | Nov 22 | Nov 23 | W09, W10 |
| P06 | Model adapter, tools, and bounded agent loop | Nov 24 | Nov 25 | W11, W12 |
| P07 | Live investigations, clarification, and query repair | Nov 29 | Nov 30 | W13, W14 |
| P08 | Grounded answers and scoped follow-up context | Dec 01 | Dec 02 | W15, W16 |
| P09 | Chart contracts and frontend foundation | Dec 03 | Dec 06 | W17, W18 |
| P10 | Upload and investigation conversation interface | Dec 07 | Dec 08 | W19, W20 |
| P11 | Evidence inspection, charts, and web MVP | Dec 09 | Dec 10 | W21, W22 |
| P12 | Evaluation harness and first held-out results | Dec 13 | Dec 14 | W23, W24 |
| P13 | Resilience, budgets, and safe result reuse | Dec 15 | Dec 16 | W25, W26 |
| P14 | Resumable investigations and browser regression tests | Dec 17 | Dec 20 | W27, W28 |
| P15 | Accessibility and adversarial boundary fixes | Dec 21 | Dec 22 | W29, W30 |
| P16 | Performance evidence and stabilized beta | Dec 23 | Dec 24 | W31, W32 |
| P17 | Contingency fixes and release-blocker resolution | Dec 27 | Dec 28 | W33, W34 |
| P18 | Curated demo deployment and operations | Dec 29 | Dec 30 | W35, W36 |
| P19 | Report export, technical explanation, and onboarding | Dec 31 | Jan 03 | W37, W38 |
| P20 | Final evaluation and release candidate | Jan 04 | Jan 05 | W39, W40 |
| P21 | Portfolio demonstration and versioned release | Jan 06 | Jan 07 | W41, W42 |

## Issue and PR workflow

Use labels such as area:data, area:agent, area:ui, area:eval, area:ops, type:feature, type:bug, priority:high, and status:blocked. Group daily issues under the milestones above. Track work in Backlog, Ready, In progress, Review, and Done. Keep only one primary issue and one main PR active at a time.

Daily issue template:

```text
Title: [Wxx] Concrete user-visible outcome
Problem / user story:
In scope:
Acceptance evidence:
Dependencies:
Candidate commit units:
Relevant checks:
Actual result / link to PR:
```

PR template:

```text
Problem and resulting behavior:
Linked daily issues:
Main implementation decisions:
Validation performed and actual results:
Screenshots or sample SQL/evidence where useful:
Known limitations / follow-up issues:
```

A useful commit changes a coherent behavior, interface, check, example, or piece of documentation. Examples include `feat: infer ambiguous CSV date columns`, `fix: cancel timed-out query workers`, `test: reject external SQL scan functions`, and `docs: explain result evidence`. The first two daily commit units need not be artificially separated if they form one small change. Do not repeat formatting changes or placeholder documentation to reach a count. Use truthful commit dates and reference real issue identifiers once created.

Review the complete paired diff before merging, even as a solo developer. For UI changes, include a screenshot or recorded journey where it helps review. For agent changes, attach an example and relevant evaluation results. For boundary changes, attach adversarial regression evidence. CI should run appropriate lint, type checks, builds, and meaningful tests; do not require paid model calls on every commit. Keep PRs as drafts if acceptance evidence is missing. A rest day never becomes a merge deadline.

## Scope control and fallback decisions

- If ingestion or isolation is behind at M1, delay polish and exports; finish the deterministic foundation before introducing generated SQL.
- If API alpha is behind at M2, keep one provider, one dataset per investigation, and only bar/line charts initially. Defer scatter and image export into the contingency days only if core behavior is stable.
- If result correctness is weak at M4, narrow supported questions and improve clarification, metric definitions, and result handling. Keep the evaluation honest and record unsupported cases explicitly.
- W33-W34 are reserved contingency days. Use them for release blockers first. If no blockers exist, select a documented weak case or improve clean setup; do not add unrelated features.
- Freeze new features on December 24. W35-W42 focus on deployment, documentation, final evaluation, stabilization, and release. Fix a blocker before recording a polished demo of that path.
- If time is lost, drop image export, advanced recovery polish, and extra chart types before dropping evidence, SQL isolation, deletion, evaluation, or basic accessibility.
- If a release gate still fails on January 7, publish an accurately labeled beta with the blocker list and measurements. Reserve the v1 label for the build that passes the declared gates. Do not silently claim success or work on Fridays, Saturdays, or holidays to preserve a label.

## Final portfolio package

The finished repository should contain a clear problem statement, sample datasets and reproducible generators, setup instructions, a versioned application, an architecture diagram, meaningful CI, a short product video, measured evaluation reports and raw result files, a documented SQL boundary, deployment/rollback notes, and a concise discussion of tradeoffs and remaining limitations. The README should let a reviewer reproduce one investigation and inspect its supporting SQL within a few minutes.

Suggested final portfolio description, to revise with actual results: "Built an AI data investigation assistant that profiles CSV datasets, executes restricted analytical SQL, and produces charts with inspectable evidence. Evaluated it against a reproducible task suite and documented correctness, cost, latency, and failure cases." Add numbers only after the final measurements exist.

## Sources and calendar checks

- [US Office of Personnel Management: federal holidays](https://www.opm.gov/policy-data-oversight/pay-leave/federal-holidays/) - confirms November 11 and 26 and December 25, 2026, plus January 1, 2027. Checked November 9, 2026.
- [DuckDB Python API](https://duckdb.org/docs/stable/clients/python/overview) - analytical SQL and CSV integration.
- [DuckDB security](https://duckdb.org/security) and [securing DuckDB](https://duckdb.org/docs/preview/operations_manual/securing_duckdb/overview) - generated SQL requires a genuine isolation boundary in addition to application controls.
- [FastAPI documentation](https://fastapi.tiangolo.com/) - API framework reference.
- [Plotly React integration](https://plotly.com/javascript/react/) - chart-renderer reference.
- [Anthropic: building effective agents](https://www.anthropic.com/research/building-effective-agents) - simple agent design and explicit tools.
- [Anthropic: demystifying agent evaluations](https://www.anthropic.com/research/demystifying-evals-for-ai-agents) - outcome-based grading, traces, repeated trials, and regression measurement.

This is a delivery plan and proposed backlog. It does not create repositories, branches, commits, GitHub issues, PRs, deployments, or calendar events.
