"""Scalar clinical types shared by every Nidana module.

Nothing here is Consult-specific. Modules 2-5 import from this file unchanged.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Confidence(str, Enum):
    """How much weight the record places on a finding's value.

    LOW marks a finding for re-asking: the patient hedged, the transcription was
    unclear, or a colloquialism carried more than one plausible reading.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PregnancyStatus(str, Enum):
    UNKNOWN = "unknown"
    POSSIBLE = "possible"
    CONFIRMED = "confirmed"
    NOT_APPLICABLE = "not_applicable"


class Sex(str, Enum):
    """Recorded to gate clinical logic, not as an identity claim.

    OTHER and UNKNOWN both suppress sex-gated rules rather than defaulting them.
    """

    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    UNKNOWN = "unknown"


_BAND_URGENCY: Final[dict[str, int]] = {
    "U1": 5,
    "U2": 4,
    "U3": 3,
    "U4": 2,
    "U5": 1,
}


class Band(str, Enum):
    """Urgency band. U1 is the most urgent.

    Ordering comparison is deliberately not defined on this type. See ADR 0004:
    the spec writes `U1 < U2 < U3 < U4 < U5 (U1 most urgent)`, which makes `<`
    mean ordinal position while urgency runs the other way. Code that compares
    bands directly reads correctly and does the opposite of what it says.

    Use `is_more_urgent_than`, or `services.clinical.bands.escalate_only`.
    """

    U1 = "U1"
    U2 = "U2"
    U3 = "U3"
    U4 = "U4"
    U5 = "U5"

    @property
    def urgency(self) -> int:
        """Higher is more urgent. U1 is 5."""
        return _BAND_URGENCY[self.value]

    def is_more_urgent_than(self, other: Band) -> bool:
        return self.urgency > other.urgency

    def __lt__(self, other: object) -> bool:
        raise TypeError(
            "Band does not support ordering comparison because '<' and urgency run "
            "in opposite directions; use Band.is_more_urgent_than or "
            "services.clinical.bands.escalate_only"
        )

    __gt__ = __lt__
    __le__ = __lt__
    __ge__ = __lt__


class Coding(BaseModel):
    """A terminology code, shaped after the FHIR R4 Coding datatype.

    Code-system-agnostic so the SNOMED CT licensing position for India
    (docs/BUILD_SPEC.md section 8, question 4) does not need resolving before
    the schema is fixed. ICD-10 is the fallback system.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    system: str = Field(min_length=1, description="Code system URI, e.g. http://hl7.org/fhir/sid/icd-10")
    code: str = Field(min_length=1)
    display: str | None = None
    version: str | None = None


class Quantity(BaseModel):
    """A numeric clinical value with its unit.

    A unitful number without a unit is a defect, not a missing nicety: 'onset 6'
    is six hours or six days depending on who reads it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: float
    unit: str = Field(min_length=1)

    @field_validator("unit")
    @classmethod
    def _unit_is_not_placeholder(cls, v: str) -> str:
        if v.strip() in {"", "-", "none", "None", "n/a", "N/A"}:
            raise ValueError(
                f"unit {v!r} is a placeholder, not a unit; omit the Quantity or supply a real unit"
            )
        return v.strip()
