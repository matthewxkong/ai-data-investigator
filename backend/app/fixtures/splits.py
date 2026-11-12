"""Validate the reserved question split without using it in development answer checks."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.fixtures.references import PROJECT_ROOT, DevelopmentSuite


class HeldOutQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^held_[a-z_]+$")]
    dataset: Literal["sales", "tickets", "inventory"]
    question: str = Field(min_length=1)
    behavior: Literal["answer", "clarify", "explain_limit"]


class HeldOutManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    generator_version: Literal[1]
    fixture_seed: int = Field(ge=0, le=2**32 - 1)
    split: Literal["heldout"]
    status: Literal["reserved_not_frozen"]
    cases: list[HeldOutQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_question_ids(self) -> "HeldOutManifest":
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Held-out question IDs must be unique.")
        return self


def load_heldout_manifest() -> HeldOutManifest:
    return HeldOutManifest.model_validate_json(
        (PROJECT_ROOT / "evaluation" / "heldout" / "manifest.json").read_text(encoding="utf-8")
    )


def validate_split_separation(development: DevelopmentSuite, heldout: HeldOutManifest) -> None:
    if (
        development.fixture_seed != heldout.fixture_seed
        or development.generator_version != heldout.generator_version
    ):
        raise ValueError("Question splits must reference the same fixture version and seed.")
    dev_ids = {case.id for case in development.cases}
    dev_questions = {case.question.strip().casefold() for case in development.cases}
    if dev_ids.intersection(case.id for case in heldout.cases):
        raise ValueError("Question IDs overlap between splits.")
    if dev_questions.intersection(case.question.strip().casefold() for case in heldout.cases):
        raise ValueError("Question text overlaps between splits.")
