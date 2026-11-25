import duckdb
import pytest

from worker.policy import PolicyDenied, parse_select

COLUMNS = {"region", "quantity", "label", "order_date"}


def test_compiled_query_returns_known_aggregate_and_treats_text_as_data() -> None:
    sql = (
        "SELECT region, SUM(TRY_CAST(quantity AS BIGINT)) AS units "
        "FROM data WHERE label = 'Spring''s sale; 2026' GROUP BY region ORDER BY units DESC"
    )
    statement, parameters = parse_select(sql, COLUMNS).compile()
    assert "Spring" not in statement
    assert parameters == ["Spring's sale; 2026"]
    with duckdb.connect(":memory:") as database:
        database.execute("CREATE TABLE data (region VARCHAR, quantity VARCHAR, label VARCHAR)")
        database.executemany(
            "INSERT INTO data VALUES (?, ?, ?)",
            [
                ("West", "3", parameters[0]),
                ("West", "5", parameters[0]),
                ("East", "2", parameters[0]),
                ("West", "99", "unrelated"),
            ],
        )
        assert database.execute(statement, parameters).fetchall() == [("West", 8), ("East", 2)]


def test_missing_values_and_explicit_limits_keep_sql_meaning() -> None:
    statement, parameters = parse_select(
        "SELECT region FROM data WHERE quantity IS NULL OR region = 'East' "
        "ORDER BY region DESC LIMIT 1",
        COLUMNS,
    ).compile()
    with duckdb.connect(":memory:") as database:
        database.execute("CREATE TABLE data (region VARCHAR, quantity VARCHAR)")
        database.execute("INSERT INTO data VALUES ('West', NULL), ('East', '1'), ('North', '2')")
        assert database.execute(statement, parameters).fetchall() == [("West",)]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM data",
        "ATTACH 'other.duckdb' AS other",
        "INSTALL httpfs",
        "SET threads = 16",
        "SELECT region FROM information_schema.tables",
        "SELECT region FROM main.data",
        "SELECT COUNT(*) FROM read_csv('synthetic.csv')",
        "SELECT unknown_function(region) FROM data",
        "SELECT region FROM data; SELECT region FROM data",
        "SELECT (SELECT region FROM data) FROM data",
        "SELECT region FROM data UNION SELECT region FROM data",
        "SELECT region FROM data LIMIT 51",
        "SELECT region FROM data LIMIT 1.0",
        "SELECT * FROM data",
        "SELECT absent_column FROM data",
        "SELECT " + "(" * 17 + "region" + ")" * 17 + " FROM data",
    ],
)
def test_unsupported_queries_are_rejected(sql: str) -> None:
    with pytest.raises(PolicyDenied):
        parse_select(sql, COLUMNS)
