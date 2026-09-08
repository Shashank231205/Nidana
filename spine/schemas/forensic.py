"""Medico-legal examination records.

S5 Forensics writes these. It is the only service whose primary consumer is a
court rather than a clinician, and the only one that reads nothing from the
shared record: a medico-legal document must be defensible as an independent
examination, and contamination from other sources is an attack surface in
cross-examination.

The rule that shapes everything here: **the system structures examiner
findings and never generates them.** If the examiner did not observe it, it
cannot appear. Every field traces to an examiner input or it does not render,
and the schema enforces that rather than trusting it.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.provenance import ExaminerEntry


class InjuryType(str, Enum):
    """Wound classification, in the terms a medico-legal report uses.

    These are descriptive rather than causal. An abrasion is an abrasion
    regardless of what caused it, and what caused it is a separate question the
    examiner answers with 'consistent with', never with a conclusion.
    """

    ABRASION = "abrasion"
    CONTUSION = "contusion"
    LACERATION = "laceration"
    INCISED = "incised"
    STAB = "stab"
    FIREARM = "firearm"
    BURN = "burn"
    FRACTURE = "fracture"
    BITE = "bite"
    OTHER = "other"


class WoundAge(str, Enum):
    """Estimated age of an injury.

    Coarse deliberately. A precise estimate is not defensible and a court will
    test it; a range the examiner can justify is worth more than a number they
    cannot.
    """

    FRESH = "fresh"
    RECENT = "recent"
    HEALING = "healing"
    HEALED = "healed"
    INDETERMINATE = "indeterminate"


class Injury(BaseModel):
    """One documented injury.

    Every field is what the examiner recorded. `provenance` is their signed
    entry, not a transcript or an inference, and there is no other permitted
    source for anything in this shape.

    A missing field is what gets exploited in cross-examination, so the report
    lists incompleteness rather than filling it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    injury_type: InjuryType
    site: str = Field(min_length=1, description="Anatomical site, as the examiner described it")
    landmark_distance_cm: float | None = Field(
        default=None,
        ge=0,
        description="Measured distance from a named anatomical landmark",
    )
    landmark: str | None = Field(default=None, description="The landmark measured from")
    length_cm: float | None = Field(default=None, gt=0)
    width_cm: float | None = Field(default=None, gt=0)
    depth_cm: float | None = Field(default=None, ge=0)
    shape: str | None = None
    margins: str | None = None
    direction: str | None = None
    estimated_age: WoundAge = WoundAge.INDETERMINATE
    provenance: ExaminerEntry
    photograph_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _a_measurement_names_what_it_was_measured_from(self) -> Injury:
        if self.landmark_distance_cm is not None and not self.landmark:
            raise ValueError(
                f"injury at {self.site!r} records a distance of "
                f"{self.landmark_distance_cm}cm but names no landmark; a measurement "
                f"from an unstated point cannot be reproduced or challenged"
            )
        return self

    @property
    def missing_fields(self) -> tuple[str, ...]:
        """Fields a complete medico-legal description would carry.

        Reported so the examiner can fill them before the report closes. Never
        filled by the system: a plausible wound description nobody observed is
        the worst thing this service could produce.
        """
        expected = {
            "landmark_distance_cm": self.landmark_distance_cm,
            "length_cm": self.length_cm,
            "shape": self.shape,
            "margins": self.margins,
            "direction": self.direction,
        }
        missing = tuple(name for name, value in expected.items() if value is None)
        if self.estimated_age is WoundAge.INDETERMINATE:
            missing = (*missing, "estimated_age")
        return missing

    @property
    def is_complete(self) -> bool:
        return not self.missing_fields

    @property
    def has_photograph(self) -> bool:
        return bool(self.photograph_ids)


class Photograph(BaseModel):
    """One photograph, hashed and timestamped.

    A scale reference is required rather than encouraged. A wound photograph
    without one establishes appearance but not size, and size is usually the
    contested fact.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    photograph_id: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    taken_at: datetime
    scale_reference_present: bool
    taken_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _a_photograph_without_scale_is_flagged_not_rejected(self) -> Photograph:
        """Recorded either way.

        A photograph taken without a scale is still evidence of appearance, and
        discarding it would lose that. The report says which lack one.
        """
        return self


class ExaminationStatus(str, Enum):
    """A report is open until the examiner finalises it.

    Finalisation is where it becomes evidence: the chain is signed and nothing
    further can be altered, only corrected by a new entry carrying a reason.
    """

    OPEN = "open"
    FINALISED = "finalised"


class MedicoLegalReport(BaseModel):
    """One medico-legal examination.

    Evidentially isolated. This shape holds no reference to a Consult session,
    a clinical note, or a prescription, and Forensics reads none of them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    examination_id: UUID
    examiner_id: str = Field(min_length=1)
    examined_at: datetime
    status: ExaminationStatus = ExaminationStatus.OPEN
    injuries: tuple[Injury, ...] = ()
    photographs: tuple[Photograph, ...] = ()
    consistent_with: tuple[str, ...] = Field(
        default=(),
        description="Mechanisms the findings are consistent with, never a conclusion",
    )
    not_consistent_with: tuple[str, ...] = Field(
        default=(),
        description="Mechanisms the findings argue against, often the more useful half",
    )
    finalised_at: datetime | None = None
    signature: str | None = None

    @model_validator(mode="after")
    def _a_finalised_report_is_signed(self) -> MedicoLegalReport:
        if self.status is ExaminationStatus.FINALISED and not self.signature:
            raise ValueError(
                "a finalised report carries the examiner's signature; without it the "
                "chain cannot be shown to have been closed by the person who examined"
            )
        return self

    @model_validator(mode="after")
    def _a_finalised_report_records_when(self) -> MedicoLegalReport:
        if self.status is ExaminationStatus.FINALISED and self.finalised_at is None:
            raise ValueError("a finalised report records when it was finalised")
        return self

    @model_validator(mode="after")
    def _photograph_references_resolve(self) -> MedicoLegalReport:
        known = {photograph.photograph_id for photograph in self.photographs}
        for injury in self.injuries:
            unknown = sorted(set(injury.photograph_ids) - known)
            if unknown:
                raise ValueError(
                    f"injury at {injury.site!r} references photograph(s) "
                    f"{', '.join(unknown)} that this report does not carry; a citation "
                    f"to evidence that is not attached cannot be produced in court"
                )
        return self

    @property
    def incomplete_injuries(self) -> tuple[Injury, ...]:
        return tuple(injury for injury in self.injuries if not injury.is_complete)

    @property
    def photographs_without_scale(self) -> tuple[Photograph, ...]:
        return tuple(p for p in self.photographs if not p.scale_reference_present)

    @property
    def blocking_gaps(self) -> tuple[str, ...]:
        """Everything that should be resolved before finalisation.

        A missing field is exactly what gets exploited under cross-examination,
        so the examiner sees the list before signing rather than a lawyer
        finding it years later.
        """
        gaps: list[str] = []
        for injury in self.incomplete_injuries:
            gaps.append(
                f"injury at {injury.site}: missing {', '.join(injury.missing_fields)}"
            )
        for photograph in self.photographs_without_scale:
            gaps.append(f"photograph {photograph.photograph_id}: no scale reference")
        if not self.injuries:
            gaps.append("no injuries documented")
        return tuple(gaps)

    @property
    def is_finalisable(self) -> bool:
        return not self.blocking_gaps


class DraftInjury(BaseModel):
    """One injury the structuring agent claims the examiner described.

    Measurements are strings because the examiner dictates "three centimetres"
    as often as "3cm", and coercing to a float here would either fail on the
    words or invent a precision the examiner did not state. The builder parses
    and drops what it cannot read.

    There is no provenance field. Provenance for an injury is the examiner's
    own entry, and the builder attaches it from the dictation being structured.
    A model cannot author one, which is the point.
    """

    model_config = ConfigDict(extra="forbid")

    injury_type: InjuryType
    site: str = Field(min_length=1)
    source_span: str = Field(
        min_length=1,
        description="Exact substring of the examiner's dictation describing this injury",
    )
    landmark: str | None = None
    landmark_distance_cm: str | None = None
    length_cm: str | None = None
    width_cm: str | None = None
    depth_cm: str | None = None
    shape: str | None = None
    margins: str | None = None
    direction: str | None = None
    estimated_age: WoundAge = WoundAge.INDETERMINATE


class ExaminationDraft(BaseModel):
    """What the structuring agent returns for one dictation."""

    model_config = ConfigDict(extra="forbid")

    injuries: tuple[DraftInjury, ...] = ()
