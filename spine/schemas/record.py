"""The shared clinical record and its per-service context.

ADR 0001 and NIDANA.md section 5. `Record` holds what every service has:
subject, findings, demographics, comorbidities, medications, allergies.
Service-specific state lives in a named context object, so Scribe, Rx, Labs,
and Forensics extend the record rather than defining their own.

Forensics is the exception to the sharing. NIDANA.md section 5 isolates it
evidentially: it writes to its own chain and reads no shared data, because
contamination from other sources is an attack surface in court. It uses this
shape; it does not use anyone else's instance of it.
"""

from __future__ import annotations

from enum import Enum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.finding import Finding
from spine.schemas.primitives import Coding, PregnancyStatus, Sex
from spine.schemas.registry import ComplaintFamily

PAEDIATRIC_AGE_CEILING_YEARS: Final[int] = 18
"""Age below which paediatric rule modifiers apply.

A cohort boundary, not a clinical threshold. Rules that turn on it carry their
own citation; this constant only says where the cohort ends.
"""


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
        return self.age_years is not None and self.age_years < PAEDIATRIC_AGE_CEILING_YEARS


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


class SubjectType(str, Enum):
    """What produced a record. One per service.

    ADR 0006 made the audit log polymorphic for the same reason: Rx works from a
    prescription and Labs from a report, and neither is a session.
    """

    SESSION = "session"
    ENCOUNTER = "encounter"
    PRESCRIPTION = "prescription"
    REPORT = "report"
    EXAMINATION = "examination"


class Record(BaseModel):
    """The accumulated clinical picture for one subject.

    Shared spine. Everything here is meaningful to every service.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_type: SubjectType
    subject_id: UUID
    findings: tuple[Finding, ...] = ()
    demographics: Demographics = Demographics()
    comorbidities: tuple[Comorbidity, ...] = ()
    medications: tuple[Medication, ...] = ()
    allergies: tuple[Allergy, ...] = ()
    consult: ConsultContext = ConsultContext()

    def findings_for(self, field: str) -> tuple[Finding, ...]:
        """Every finding recorded for `field`, oldest first.

        More than one is normal: a source revises a fact, and both the original
        and the correction are kept. Corrections are new rows.

        Order is the order findings were appended. Consult could sort by turn,
        but Scribe, Rx, Labs, and Forensics have no turns, and every service
        appends as it extracts.
        """
        return tuple(f for f in self.findings if f.field == field)

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
