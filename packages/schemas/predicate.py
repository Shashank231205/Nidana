"""Named tests over registry fields.

ADR 0005. A red flag rule references predicates by name rather than naming
fields directly, so each rule atom has one definition rather than one per rule,
and an atom that resolves to nothing fails the build instead of evaluating
false forever.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Comparator(str, Enum):
    """How a predicate tests a field's recorded value."""

    IS_PRESENT = "is_present"
    EQUALS = "equals"
    IN = "in"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"


_NEEDS_NOTHING = frozenset({Comparator.IS_PRESENT, Comparator.IS_TRUE, Comparator.IS_FALSE})
_NEEDS_SCALAR = frozenset(
    {
        Comparator.EQUALS,
        Comparator.GREATER_THAN,
        Comparator.LESS_THAN,
        Comparator.AT_LEAST,
        Comparator.AT_MOST,
    }
)
_NEEDS_NUMBER = frozenset(
    {Comparator.GREATER_THAN, Comparator.LESS_THAN, Comparator.AT_LEAST, Comparator.AT_MOST}
)

PredicateOperand = str | float | int | bool


class Predicate(BaseModel):
    """One named, declarative test over a single registry field.

    Pure and side-effect free by construction: a predicate is data, and the
    evaluator is the only thing that runs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    field: str = Field(min_length=1)
    comparator: Comparator
    value: PredicateOperand | None = None
    values: tuple[PredicateOperand, ...] = ()
    description: str | None = None
    source: str | None = Field(
        default=None,
        description="Citation, required when the predicate encodes a clinical threshold",
    )

    @model_validator(mode="after")
    def _operands_match_the_comparator(self) -> Predicate:
        if self.comparator in _NEEDS_NOTHING and (self.value is not None or self.values):
            raise ValueError(
                f"predicate {self.id!r} uses {self.comparator.value}, which tests the "
                f"field alone, but supplies an operand; remove 'value' and 'values'"
            )
        if self.comparator in _NEEDS_SCALAR:
            if self.value is None:
                raise ValueError(
                    f"predicate {self.id!r} uses {self.comparator.value} but supplies no "
                    f"'value' to compare against"
                )
            if self.values:
                raise ValueError(
                    f"predicate {self.id!r} uses {self.comparator.value}, which takes one "
                    f"operand, but also supplies 'values'; use the 'in' comparator instead"
                )
        if self.comparator is Comparator.IN:
            if not self.values:
                raise ValueError(
                    f"predicate {self.id!r} uses 'in' but supplies no 'values'; an empty "
                    f"set matches nothing and the predicate would never fire"
                )
            if self.value is not None:
                raise ValueError(
                    f"predicate {self.id!r} uses 'in' with a scalar 'value'; supply "
                    f"'values' instead"
                )
        if self.comparator in _NEEDS_NUMBER and isinstance(self.value, (str, bool)):
            raise ValueError(
                f"predicate {self.id!r} compares {self.field!r} numerically against "
                f"{self.value!r}, which is not a number"
            )
        return self

    @property
    def is_threshold(self) -> bool:
        """Whether this predicate encodes a numeric clinical cut-off."""
        return self.comparator in _NEEDS_NUMBER
