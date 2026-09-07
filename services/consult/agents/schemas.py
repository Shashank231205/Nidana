"""The shapes agents return.

These are what the model is constrained to produce. They are separate from the
record schemas because a model's output is a claim, not a fact: it becomes a
Finding only after its span verifies against the utterance.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.primitives import Band, Confidence
from spine.schemas.registry import ComplaintFamily
from spine.schemas.triage import DifferentialEntry, Specialty


class ExtractedFinding(BaseModel):
    """One fact the structuring agent claims the patient stated.

    `source_span` is checked against the utterance before this becomes a
    Finding. A claim whose span does not verify is dropped, so this shape is
    deliberately not the record shape.
    """

    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    value: str | float | int | bool
    source_span: str = Field(min_length=1)
    confidence: Confidence = Confidence.MEDIUM
    negated: bool = False


class StructuringOutput(BaseModel):
    """What the structuring agent returns for one utterance."""

    model_config = ConfigDict(extra="forbid")

    findings: tuple[ExtractedFinding, ...] = ()


class IntakeOutput(BaseModel):
    """What the intake agent returns for one turn."""

    model_config = ConfigDict(extra="forbid")

    utterance: str = Field(min_length=1, description="The single question to ask")
    language: str = Field(default="en", min_length=2)
    field_targeted: str | None = None
    complaint_family: ComplaintFamily | None = None
    handoff_requested: bool = False

    @model_validator(mode="after")
    def _one_question_per_turn(self) -> IntakeOutput:
        """A compound question gets a partial answer and the other half is lost.

        Counting question marks catches the common form. It does not catch every
        compound question, and the eval suite carries the rest.
        """
        if self.utterance.count("?") > 1:
            raise ValueError(
                f"utterance asks more than one question: {self.utterance!r}. One question "
                f"per turn; a compound question gets a partial answer and the rest is lost"
            )
        return self


class TriageOutput(BaseModel):
    """What the triage agent returns.

    Return criteria are validated here as well as on TriageResult, so a model
    that omits them fails at the parse rather than downstream.
    """

    model_config = ConfigDict(extra="forbid")

    band: Band
    specialty: Specialty
    rationale: str = Field(min_length=1)
    escalating_factors: tuple[str, ...] = ()
    uncertainty: str | None = None
    return_criteria: tuple[str, ...] = ()
    differential: tuple[DifferentialEntry, ...] = ()
    history_gaps: tuple[str, ...] = ()


class CriticVerdictName(BaseModel):
    """What the safety critic returns.

    There is no output shape for de-escalation. The critic may raise urgency and
    may never lower it, so the vocabulary does not contain the option.
    """

    model_config = ConfigDict(extra="forbid")

    verdict: str = Field(pattern=r"^(no_change|raise_to)$")
    band: Band | None = None
    reason: str = Field(min_length=1)
    grounds: tuple[str, ...] = ()
    citing_findings: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _raise_to_names_a_band(self) -> CriticVerdictName:
        if self.verdict == "raise_to" and self.band is None:
            raise ValueError(
                "verdict is raise_to but no band was named; say which band to raise to"
            )
        if self.verdict == "no_change" and self.band is not None:
            raise ValueError(
                f"verdict is no_change but band {self.band.value} was named; a verdict "
                f"that changes nothing does not carry a target"
            )
        return self
