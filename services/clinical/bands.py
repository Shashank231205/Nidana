"""Urgency band arithmetic.

The safety critic may raise urgency and may never lower it. ADR 0004 records
why this is enforced by a single constructor and an exhaustive test rather than
by the type system: a Python function annotated `-> Band` may return any Band,
so the guarantee cannot live in the annotation.

`escalate_only` is the only function in the codebase that decides which band
gets written onto a record.
"""

from __future__ import annotations

from dataclasses import dataclass

from packages.schemas.primitives import Band


class BandDeescalationError(ValueError):
    """Raised when something attempts to make a record less urgent."""


@dataclass(frozen=True)
class NoChange:
    """The critic agrees with the triage agent's band."""

    reason: str


@dataclass(frozen=True)
class RaiseTo:
    """The critic requires a more urgent band than the one proposed.

    Validates on construction, so an instance that de-escalates cannot exist to
    be passed around and applied later.
    """

    band: Band
    reason: str

    def validated_against(self, current: Band) -> RaiseTo:
        if not self.band.is_more_urgent_than(current):
            raise BandDeescalationError(
                f"cannot raise {current.value} to {self.band.value}: the target is not "
                f"more urgent. The safety critic may only escalate; return NoChange to "
                f"leave the band as it stands"
            )
        return self


CriticVerdict = NoChange | RaiseTo


def escalate_only(current: Band, proposed: Band) -> Band:
    """Return whichever band is more urgent.

    Total over all 25 ordered pairs and never returns a band less urgent than
    `current`, which is what the exhaustive test asserts.
    """
    return proposed if proposed.is_more_urgent_than(current) else current


def apply_verdict(current: Band, verdict: CriticVerdict) -> Band:
    """Apply a critic verdict to the band standing on the record."""
    if isinstance(verdict, NoChange):
        return current
    return escalate_only(current, verdict.validated_against(current).band)


def most_urgent(bands: tuple[Band, ...], floor: Band) -> Band:
    """The most urgent of `bands`, or `floor` when none are supplied."""
    result = floor
    for band in bands:
        result = escalate_only(result, band)
    return result
