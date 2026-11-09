# Delivery progress

## W01 / November 9, 2026

Status: day-one foundation complete locally. The P01 branch remains a draft until W02's API and persistence work is complete.

Completed work packages:

- [x] Product brief and three target user stories.
- [x] MVP acceptance criteria and exclusions.
- [x] Architecture, generated-SQL isolation design, and privacy decisions.
- [x] Runnable FastAPI and React/TypeScript application skeletons with locked dependencies.
- [x] Environment examples, ignored private-data paths, and consistent source formatting.
- [x] Issue forms, PR template, and contribution workflow.
- [x] CI configuration for backend and frontend checks on Windows and Linux.
- [x] Local setup instructions, first-investigation scenario, delivery calendar, and verified screenshots.

## Verification evidence

Verified on Windows with Python 3.13.3 and Node 22.18.0:

- Backend: Ruff lint and formatting, strict mypy, and two bootstrap HTTP tests pass.
- Frontend: Biome lint/format, TypeScript checks, and the Vite production build pass.
- Headless Chrome: the browser connects to the actual API through the Vite development proxy.
- Desktop at 1440 pixels and mobile at 390 pixels render correctly, with no horizontal mobile overflow.
- HTTP failure and an unexpected health payload display the unavailable state; retry restores the connected state.
- No uncaught browser errors or external runtime requests occurred during these checks.

These are foundation checks. They do not demonstrate ingestion, database persistence, model integration, SQL execution, or analytical correctness; those implementations begin in the following milestones. GitHub-hosted checks must be inspected separately after publication.

![Desktop foundation with a connected API](images/foundation-desktop.png)

[Mobile foundation screenshot](images/foundation-mobile.png)

## Next: W02 / November 10, 2026

Deliver the API and persistence foundation:

- Add typed application settings and backend-only secret loading.
- Extend health with a distinct readiness contract.
- Create the SQLite metadata schema and migrations.
- Add dataset and investigation metadata repositories.
- Define consistent API error envelopes.
- Verify persistence across application instances and startup failures.
- Update setup documentation and complete P01 when the combined scope passes checks.

The health-only application factory is already available from W01. Build on it rather than recreating it. November 11 is Veterans Day and remains a rest day.
