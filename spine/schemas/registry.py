"""The field registry: what each complaint family requires, and in what shape.

Rule atoms and finding fields both resolve against this. It is loaded from
`rules/fields/<family>.yaml` and is the reason a finding cannot name a field
that does not exist. ADR 0005.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ComplaintFamily(str, Enum):
    """The classification that determines which fields are required.

    Adding a member requires a registry file and is a schema change, not an
    ad-hoc addition inside a prompt.
    """

    CHEST_PAIN = "chest_pain"
    ABDOMINAL_PAIN = "abdominal_pain"
    HEADACHE = "headache"
    BREATHLESSNESS = "breathlessness"
    FEVER = "fever"
    NEUROLOGICAL_DEFICIT = "neurological_deficit"
    OBSTETRIC = "obstetric"
    MENTAL_HEALTH = "mental_health"
    TRAUMA = "trauma"
    GENERAL = "general"


class FieldType(str, Enum):
    NUMBER = "number"
    ENUM = "enum"
    BOOLEAN = "boolean"
    TEXT = "text"


class FieldSpec(BaseModel):
    """One field a complaint family may record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str = Field(min_length=1)
    type: FieldType
    unit: str | None = None
    values: tuple[str, ...] = ()
    multi: bool = False
    description: str | None = None

    @model_validator(mode="after")
    def _shape_matches_type(self) -> FieldSpec:
        if self.type is FieldType.ENUM and not self.values:
            raise ValueError(
                f"field {self.field!r} is an enum with no values; declare its permitted "
                f"values in the registry file"
            )
        if self.type is not FieldType.ENUM and self.values:
            raise ValueError(
                f"field {self.field!r} is {self.type.value} but declares enum values; "
                f"only enum fields carry values"
            )
        if self.type is FieldType.NUMBER and not self.unit:
            raise ValueError(
                f"numeric field {self.field!r} has no unit; a unitless clinical number "
                f"is ambiguous between hours and days"
            )
        if self.multi and self.type is not FieldType.ENUM:
            raise ValueError(
                f"field {self.field!r} is multi-valued but not an enum; only enums may "
                f"carry more than one value"
            )
        return self

    def permits(self, value: object) -> bool:
        """Whether `value` is a legal value for this field."""
        if self.type is FieldType.BOOLEAN:
            return isinstance(value, bool)
        if self.type is FieldType.ENUM:
            return isinstance(value, str) and value in self.values
        if self.type is FieldType.TEXT:
            return isinstance(value, str)
        return isinstance(value, (int, float)) and not isinstance(value, bool)


class FamilyRegistry(BaseModel):
    """The required and optional fields for one complaint family."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: ComplaintFamily
    required: tuple[FieldSpec, ...]
    optional: tuple[FieldSpec, ...] = ()

    @model_validator(mode="after")
    def _field_names_are_unique(self) -> FamilyRegistry:
        seen: set[str] = set()
        for spec in (*self.required, *self.optional):
            if spec.field in seen:
                raise ValueError(
                    f"field {spec.field!r} is declared twice in family "
                    f"{self.family.value}; each field has one definition"
                )
            seen.add(spec.field)
        return self

    @property
    def required_field_names(self) -> tuple[str, ...]:
        return tuple(spec.field for spec in self.required)

    def spec_for(self, field: str) -> FieldSpec | None:
        for spec in (*self.required, *self.optional):
            if spec.field == field:
                return spec
        return None

    def knows(self, field: str) -> bool:
        return self.spec_for(field) is not None
