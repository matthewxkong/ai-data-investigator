import sqlite3
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.database import Database
from app.models import InvestigationStatus
from app.repositories import MetadataNotFoundError
from app.repositories.datasets import DatasetRepository
from app.repositories.investigations import InvestigationRepository


def test_investigation_and_status_survive_new_connections(database: Database) -> None:
    dataset = DatasetRepository(database).create(session_id="owner", name="Sales")
    repository = InvestigationRepository(database)
    created = repository.create(
        session_id="owner", dataset_id=dataset.id, question="What changed by month?"
    )
    assert created.status == InvestigationStatus.QUEUED
    updated = repository.update_status(
        created.id, session_id="owner", status=InvestigationStatus.RUNNING
    )
    assert updated is not None
    assert updated.updated_at >= created.updated_at
    assert updated.created_at == created.created_at
    restarted = InvestigationRepository(Database(database.path))
    assert restarted.get(created.id, session_id="owner") == updated
    assert restarted.list_for_session("owner") == [updated]


def test_other_sessions_cannot_read_or_change_investigations(database: Database) -> None:
    dataset = DatasetRepository(database).create(session_id="owner", name="Sales")
    repository = InvestigationRepository(database)
    created = repository.create(session_id="owner", dataset_id=dataset.id, question="Count orders")
    assert repository.get(created.id, session_id="other") is None
    assert repository.list_for_session("other") == []
    assert (
        repository.update_status(
            created.id, session_id="other", status=InvestigationStatus.COMPLETED
        )
        is None
    )
    assert repository.get(created.id, session_id="owner") == created


def test_cross_session_and_absent_datasets_return_the_same_error(database: Database) -> None:
    dataset = DatasetRepository(database).create(session_id="owner", name="Sales")
    repository = InvestigationRepository(database)
    for dataset_id in (dataset.id, uuid4()):
        with pytest.raises(MetadataNotFoundError, match="Dataset not found"):
            repository.create(session_id="other", dataset_id=dataset_id, question="Count orders")
    assert repository.list_for_session("other") == []


def test_composite_foreign_key_rejects_a_cross_session_link(database: Database) -> None:
    dataset = DatasetRepository(database).create(session_id="owner", name="Sales")
    with pytest.raises(sqlite3.IntegrityError), database.connection(write=True) as connection:
        connection.execute(
            "INSERT INTO investigations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (str(uuid4()), "other", str(dataset.id), "Count", "queued", "now", "now"),
        )


@pytest.mark.parametrize("question", ["", "  ", "x" * 4001])
def test_invalid_questions_do_not_create_metadata(database: Database, question: str) -> None:
    dataset = DatasetRepository(database).create(session_id="owner", name="Sales")
    repository = InvestigationRepository(database)
    with pytest.raises(ValidationError):
        repository.create(session_id="owner", dataset_id=dataset.id, question=question)
    assert repository.list_for_session("owner") == []
