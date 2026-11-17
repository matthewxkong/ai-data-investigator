import csv
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.fixtures.references import PROJECT_ROOT
from app.main import create_app


def upload(client, content):
    result = client.post("/api/datasets", content=content, headers={"Content-Type": "text/csv"})
    assert result.status_code == 201
    return "/api/datasets/" + result.json()["id"]


@pytest.mark.parametrize("source", sorted((PROJECT_ROOT / "fixtures/generated").glob("*.csv")))
def test_profiles_match_independent_fixture_counts(settings: Settings, source: Path):
    with source.open(encoding="utf-8", newline="") as file:
        records = list(csv.reader(file))
    rows = [tuple(value or None for value in row) for row in records[1:]]
    with TestClient(create_app(settings)) as client:
        path = upload(client, source.read_bytes())
        response = client.get(path + "/profile")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["row_count"] == len(rows)
        assert result["duplicate_row_count"] == len(rows) - len(set(rows))
        for index, column in enumerate(result["columns"]):
            values = [row[index] for row in rows]
            assert column["null_count"] == values.count(None)
            assert column["distinct_count"] == len(set(values) - {None})
            if column["numeric"]:
                numbers = sorted(float(value) for value in values if value is not None)
                summary = column["numeric"]
                assert summary["count"] == len(numbers)
                assert summary["minimum"] == min(numbers)
                assert summary["maximum"] == max(numbers)
                assert summary["mean"] == pytest.approx(sum(numbers) / len(numbers))
            if column["frequencies"]:
                counts = Counter(value for value in values if value is not None)
                expected = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
                assert [
                    (item["value"], item["count"]) for item in column["frequencies"]
                ] == expected
        assert client.get(path + "/profile").json() == result
        assert response.headers["Cache-Control"] == "no-store"


def test_quantiles_missingness_duplicates_and_overrides(settings: Settings):
    with TestClient(create_app(settings)) as client:
        path = upload(client, b"Value,Label\n1,A\n2,B\n3,A\n4,B\n,A\n")
        result = client.get(path + "/profile").json()
        summary = result["columns"][0]["numeric"]
        assert summary == dict(
            count=4,
            excluded_count=0,
            minimum=1,
            maximum=4,
            mean=2.5,
            q25=1.75,
            median=2.5,
            q75=3.25,
        )
        changed = client.put(
            path + "/schema/overrides",
            json={
                "expected_revision": 0,
                "overrides": {"value": {"type": "text"}, "label": {"type": "categorical"}},
            },
        )
        assert changed.status_code == 200
        after = client.get(path + "/profile").json()
        assert after["schema_revision"] == 1
        assert after["columns"][0]["numeric"] is None
        assert after["columns"][1]["frequencies"][0]["count"] == 3


def test_ownership_guards_and_missing_artifact(settings: Settings):
    with TestClient(create_app(settings)) as owner:
        path = upload(owner, b"x\n1\n")
        with TestClient(create_app(settings)) as other:
            assert other.get(path + "/profile").status_code == 401
            upload(other, b"x\n2\n")
            assert other.get(path + "/profile").status_code == 404
        assert (
            owner.get(path + "/profile", headers={"Origin": "https://evil.example"}).status_code
            == 403
        )
        folder = next((settings.data_dir / "datasets").glob(path.split("/")[-1] + "-*"))
        (folder / "data.duckdb").unlink()
        assert owner.get(path + "/profile").status_code == 503


def test_frequency_bounds_and_numeric_overflow(settings: Settings):
    with TestClient(create_app(settings)) as client:
        path = upload(
            client,
            ("n,c\n" + "".join("1e999," + str(i) + "x" * 300 + "\n" for i in range(12))).encode(),
        )
        assert (
            client.put(
                path + "/schema/overrides",
                json={"expected_revision": 0, "overrides": {"c": {"type": "categorical"}}},
            ).status_code
            == 200
        )
        result = client.get(path + "/profile").json()
        assert result["columns"][0]["numeric"]["excluded_count"] == 12
        assert result["columns"][0]["numeric"]["mean"] is None
        categorical = result["columns"][1]
        assert len(categorical["frequencies"]) == 10
        assert not categorical["frequencies_complete"]
        assert all(
            item["truncated"] and len(item["value"]) == 256 for item in categorical["frequencies"]
        )
