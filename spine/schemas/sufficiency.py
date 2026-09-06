"""Deriving sufficiency from what the record does and does not carry."""

from __future__ import annotations

from spine.schemas.primitives import Confidence
from spine.schemas.record import Record, Sufficiency
from spine.schemas.registry import FamilyRegistry


def assess(record: Record, registry: FamilyRegistry) -> Sufficiency:
    """Compare the record against its complaint family's required fields.

    Pure. A field is missing when no finding names it, which is exactly the
    'never asked' case ADR 0003 removed from Finding.
    """
    required = registry.required_field_names
    recorded = record.recorded_fields
    missing = tuple(name for name in required if name not in recorded)
    low_confidence = tuple(
        name
        for name in required
        if name not in missing
        and (latest := record.latest_finding_for(name)) is not None
        and latest.confidence is Confidence.LOW
    )
    return Sufficiency(
        complete=not missing,
        required_fields=required,
        missing=missing,
        low_confidence=low_confidence,
    )
