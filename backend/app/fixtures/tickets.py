from datetime import UTC, datetime, timedelta
from random import Random

from app.fixtures.common import DEFAULT_SEED, FixtureTable

PRIORITIES = ("low", "normal", "high", "urgent")
CATEGORY_TEAMS = {"account": "Support", "billing": "Billing", "technical": "Platform"}
STATUSES = ("open", "resolved", "resolved", "escalated")


def generate_tickets(seed: int = DEFAULT_SEED) -> FixtureTable:
    rng = Random(seed + 1)
    rows: list[tuple[str, ...]] = []
    for index in range(96):
        created = datetime(2026, index // 24 + 1, rng.randint(1, 28), rng.randrange(24), tzinfo=UTC)
        status = STATUSES[index % len(STATUSES)]
        priority = rng.choice(PRIORITIES)
        category = rng.choice(tuple(CATEGORY_TEAMS))
        hours = rng.randint(1, 96) if status == "resolved" else None
        resolved = created + timedelta(hours=hours) if hours is not None else None
        rows.append(
            (
                f"T{index + 1:04d}",
                created.isoformat().replace("+00:00", "Z"),
                resolved.isoformat().replace("+00:00", "Z") if resolved else "",
                status,
                priority,
                category,
                CATEGORY_TEAMS[category],
                str(hours) if hours is not None else "",
                rng.choice(("free", "pro", "enterprise")),
            )
        )
    return FixtureTable(
        name="tickets",
        columns=(
            "ticket_id",
            "created_at",
            "resolved_at",
            "status",
            "priority",
            "category",
            "assigned_team",
            "resolution_hours",
            "customer_tier",
        ),
        rows=tuple(rows),
    )
