"""The atomic unit of the clinical record.

Nothing enters a Record except as a Finding, and no Finding exists without
provenance. ADR 0003 removes the specified `asked` flag: a field never asked
has no patient utterance behind it, so it has no span, so it cannot be a valid
Finding. Absence carries that meaning instead, and Sufficiency computes it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.schemas.primitives import Coding, Confidence, Quantity
from packages.schemas.provenance import Provenance

FindingValue = str | float | int | bool | Quantity


class Finding(BaseModel):
    """One clinical fact the patient stated, with the words that stated it.

    `negated=True` means the patient was asked and denied it. A field the
    patient was never asked about is not represented here at all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str = Field(min_length=1, description="A field name from the complaint family registry")
    value: FindingValue
    provenance: Provenance
    turn_index: int = Field(ge=0)
    confidence: Confidence
    negated: bool = False
    codings: tuple[Coding, ...] = ()

    @model_validator(mode="after")
    def _negation_carries_a_denial_not_a_value(self) -> Finding:
        if self.negated and self.value is not False and self.value is not True:
            raise ValueError(
                f"finding {self.field!r} is negated but carries value {self.value!r}; "
                f"a denial records what was denied as a boolean, not a measurement"
            )
        return self

    @property
    def is_denial(self) -> bool:
        return self.negated
