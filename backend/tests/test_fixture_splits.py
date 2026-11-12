import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.fixtures import references
from app.fixtures.references import load_development_suite
from app.fixtures.splits import HeldOutManifest, load_heldout_manifest, validate_split_separation


def test_reserved_questions_are_distinct_and_include_non_answer_behaviors() -> None:
    development = load_development_suite()
    heldout = load_heldout_manifest()
    validate_split_separation(development, heldout)
    assert len(heldout.cases) == 10
    assert {case.behavior for case in heldout.cases} == {"answer", "clarify", "explain_limit"}


def test_duplicate_question_text_is_rejected() -> None:
    development = load_development_suite()
    data = load_heldout_manifest().model_dump()
    data["cases"][0]["question"] = f"  {development.cases[0].question.upper()}  "
    with pytest.raises(ValueError, match="Question text overlaps"):
        validate_split_separation(development, HeldOutManifest.model_validate(data))


def test_heldout_contract_rejects_answer_payloads() -> None:
    data = load_heldout_manifest().model_dump()
    data["cases"][0]["expected_rows"] = [[123]]
    with pytest.raises(ValidationError):
        HeldOutManifest.model_validate(data)


def test_development_loader_does_not_read_heldout_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = load_development_suite().model_dump()
    development = tmp_path / "evaluation" / "development"
    heldout = tmp_path / "evaluation" / "heldout"
    development.mkdir(parents=True)
    heldout.mkdir()
    (development / "cases.json").write_text(json.dumps(data), encoding="utf-8")
    (heldout / "manifest.json").write_text("invalid on purpose", encoding="utf-8")
    monkeypatch.setattr(references, "PROJECT_ROOT", tmp_path)
    assert load_development_suite().model_dump() == data
