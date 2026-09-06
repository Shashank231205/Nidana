"""The atomic unit of the clinical record.

Nothing enters a Record except as a Finding, and no Finding exists without
provenance. ADR 0003 removes the specified `asked` flag: a field never asked
has no evidence behind it, so it has no span, so it cannot be a valid Finding.
Absence carries that meaning instead, and Sufficiency computes it.

Findings are written by every service. The provenance variant says which one
produced it, and where the evidence sits.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.primitives import Coding, Confidence, Quantity
from spine.schemas.provenance import Provenance, SourceType, UtteranceSpan

FindingValue = str | float | int | bool | Quantity


class Finding(BaseModel):
    """One clinical fact, with the evidence that produced it.

    `negated=True` means the fact was asked about and denied. A field nobody was
    ever asked about is not represented here at all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str = Field(min_length=1, description="A field name from the complaint family registry")
    value: FindingValue
    provenance: Provenance
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
    def source_type(self) -> SourceType:
        return self.provenance.source_type

    @property
    def turn_index(self) -> int | None:
        """The conversation turn this came from, for Consult findings only.

        None for findings written by the other services, which have no turns.
        """
        if isinstance(self.provenance, UtteranceSpan):
            return self.provenance.turn_index
        return None

    @property
    def is_denial(self) -> bool:
        return self.negated
