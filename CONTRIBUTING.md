# Development workflow

Work Sunday through Thursday, excluding US federal holidays. Fridays and Saturdays are rest days. The delivery calendar is in [the plan](docs/delivery-plan.md).

Create one issue for a concrete daily outcome, using the acceptance evidence in the plan. Group related outcomes into a focused branch and PR. Day one's foundation was merged in PR #3. Day two continues in `work/w02-api-persistence`, tracking issue #2. Open a new branch from the latest `origin/main` when a planned PR has already been merged.

Make coherent commits for behavior, verification, or documentation. The plan offers eight candidate work packages per workday; combine related changes or split genuinely separate changes as needed. Use truthful dates and describe what changed. Do not commit `.env` files, raw private datasets, generated artifacts, or credentials.

## Checks

From `backend`:

```sh
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy app
uv run --locked pytest
```

From `frontend`:

```sh
npm ci
npm run lint
npm run typecheck
npm run build
```

Use `uv run ruff format .` and `npm run format` to apply formatting. Add tests that exercise meaningful behavior or a reproducible failure when implementing features. Normal CI must not require a paid model or credentials.

Before merging, review the complete diff, run the relevant checks, attach actual evidence, and document limitations. The owner controls merges into `main`; active rules require a PR, all four Windows/Linux checks, an up-to-date branch, and resolved review conversations. Follow the setup commands in [README](README.md) for a clean local run.
