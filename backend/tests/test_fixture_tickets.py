from datetime import datetime, timedelta

from app.fixtures.tickets import CATEGORY_TEAMS, PRIORITIES, generate_tickets


def test_ticket_seed_and_coverage() -> None:
    table = generate_tickets()
    records = list(table.records())
    assert table.csv_bytes() == generate_tickets().csv_bytes()
    assert table.csv_bytes() != generate_tickets(7).csv_bytes()
    assert len(records) == len({row["ticket_id"] for row in records}) == 96
    assert {row["priority"] for row in records} == set(PRIORITIES)
    assert {row["category"] for row in records} == set(CATEGORY_TEAMS)
    assert {row["status"] for row in records} == {"open", "resolved", "escalated"}


def test_ticket_timestamps_and_nulls_match_resolution_states() -> None:
    records = list(generate_tickets().records())
    for row in records:
        created = datetime.fromisoformat(row["created_at"])
        assert created.utcoffset() == timedelta(0)
        assert row["assigned_team"] == CATEGORY_TEAMS[row["category"]]
        if row["status"] == "resolved":
            resolved = datetime.fromisoformat(row["resolved_at"])
            assert resolved - created == timedelta(hours=int(row["resolution_hours"]))
        else:
            assert row["resolved_at"] == row["resolution_hours"] == ""
    assert sum(row["status"] == "resolved" for row in records) == 48
