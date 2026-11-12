import pytest
from pydantic import ValidationError

from app.database import Database
from app.repositories.datasets import DatasetRepository


def test_dataset_round_trip_persists_across_repository_instances(database: Database) -> None:
    created = DatasetRepository(database).create(
        session_id="owner", name="Sales", byte_count=120, row_count=3
    )
    restarted = DatasetRepository(Database(database.path))
    assert restarted.get(created.id, session_id="owner") == created
    assert created.id != created.version
    assert created.created_at.utcoffset() is not None


def test_dataset_reads_and_lists_are_scoped_to_the_session(database: Database) -> None:
    repository = DatasetRepository(database)
    mine = repository.create(session_id="owner", name="Private metadata")
    theirs = repository.create(session_id="other", name="Different metadata")
    assert repository.get(mine.id, session_id="other") is None
    assert repository.get(theirs.id, session_id="owner") is None
    assert repository.list_for_session("owner") == [mine]
    assert repository.list_for_session("unknown") == []


def test_metadata_text_is_bound_as_data_not_executed_sql(database: Database) -> None:
    repository = DatasetRepository(database)
    name = "Orders'; DROP TABLE datasets; --"
    created = repository.create(session_id="owner", name=name)
    assert repository.get(created.id, session_id="owner") == created
    assert database.is_ready()


@pytest.mark.parametrize("name", ["", "   ", "x" * 256])
def test_invalid_names_are_rejected_before_persistence(database: Database, name: str) -> None:
    repository = DatasetRepository(database)
    with pytest.raises(ValidationError):
        repository.create(session_id="owner", name=name)
    assert repository.list_for_session("owner") == []


def test_negative_counts_and_unbounded_lists_are_rejected(database: Database) -> None:
    repository = DatasetRepository(database)
    with pytest.raises(ValidationError):
        repository.create(session_id="owner", name="Sales", byte_count=-1)
    with pytest.raises(ValueError):
        repository.list_for_session("owner", limit=1000)
