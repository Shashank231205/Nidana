"""The shared clinical record and its per-module context.

ADR 0001. `Record` holds what every module has. Module-specific state lives in
a named context object, so Scribe, Rx, Labs, and Forensics extend the record
rather than defining their own.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.finding import Finding
from packages.schemas.primitives import Coding, PregnancyStatus, Sex
from packages.schemas.registry import ComplaintFamily, FamilyRegistry


class Demographics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    age_years: int | None = Field(default=None, ge=0, le=130)
    sex: Sex = Sex.UNKNOWN

    @property
    def is_paediatric(self) -> bool:
        """Whether paediatric modifiers apply.

        Unknown age does not suppress them: it returns False here and the
        clinical layer treats an unknown age as requiring the modifier where a
        rule declares one. Absence of data is not evidence of an adult.
        """
        return self.age_years is not None and self.age_years < 18


class Comorbidity(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    codings: tuple[Coding, ...] = ()


class Medication(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    dose: str | None = None
    codings: tuple[Coding, ...] = ()


class Allergy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    substance: str = Field(min_length=1)
    reaction: str | None = None
    codings: tuple[Coding, ...] = ()


class Sufficiency(BaseModel):
    """Whether the record holds enough to triage on.

    `missing` is the derived form of 'never asked' (ADR 0003): registry-required
    fields minus fields the record actually carries.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    complete: bool
    required_fields: tuple[str, ...]
    missing: tuple[str, ...]
    low_confidence: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _completeness_agrees_with_missing(self) -> Sufficiency:
        if self.complete and self.missing:
            raise ValueError(
                f"sufficiency is complete but {len(self.missing)} required fields are "
                f"missing ({', '.join(self.missing)}); completeness is derived from "
                f"missing, never asserted alongside it"
            )
        return self


class ConsultContext(BaseModel):
    """Module 1 state. Modules 2-5 add their own context class beside this."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    complaint_family: ComplaintFamily | None = None
    is_proxy: bool = False
    pregnancy_status: PregnancyStatus = PregnancyStatus.UNKNOWN
    sufficiency: Sufficiency | None = None


class Record(BaseModel):
    """The accumulated clinical picture for one subject.

    Shared spine. Everything here is meaningful to every module.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID
    findings: tuple[Finding, ...] = ()
    demographics: Demographics = Demographics()
    comorbidities: tuple[Comorbidity, ...] = ()
    medications: tuple[Medication, ...] = ()
    allergies: tuple[Allergy, ...] = ()
    consult: ConsultContext = ConsultContext()

    def findings_for(self, field: str) -> tuple[Finding, ...]:
        """Every finding recorded for `field`, oldest turn first.

        More than one is normal: a patient revises an answer, and both the
        original and the correction are kept. Corrections are new rows.
        """
        matched = tuple(f for f in self.findings if f.field == field)
        return tuple(sorted(matched, key=lambda f: f.turn_index))

    def latest_finding_for(self, field: str) -> Finding | None:
        """The most recent statement about `field`, or None if never stated."""
        matched = self.findings_for(field)
        return matched[-1] if matched else None

    @property
    def recorded_fields(self) -> frozenset[str]:
        return frozenset(f.field for f in self.findings)

    def with_findings(self, *findings: Finding) -> Record:
        """A new record carrying `findings` in addition to the existing ones."""
        return self.model_copy(update={"findings": (*self.findings, *findings)})
