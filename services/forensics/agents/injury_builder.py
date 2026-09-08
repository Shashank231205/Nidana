"""Turning a structured dictation into injuries, dropping what is not supported.

The same gate the other services apply, applied to injuries, and stricter in
one respect: provenance here is an ExaminerEntry, built from the examiner's own
dictation. A model cannot author one. Every injury this builder produces is
attributed to the examiner who dictated it, and an injury whose span is not in
that dictation does not exist.

A medico-legal record is read years later by people looking for the seam. A
measurement the model rounded, a laterality it inferred, or a wound age it
estimated is that seam.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from spine.schemas.forensic import DraftInjury, ExaminationDraft, Injury
from spine.schemas.provenance import ExaminerEntry

MEASUREMENT = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:cm|cms|centimetres?|centimeters?)?\s*$", re.I)
"""What a dictated measurement must look like to be read as a number.

Accepts "3", "3cm", "3 cm", "3.5 centimetres". Rejects "about 3", "3 to 4",
"a few" — all things an examiner says, and none of them a measurement that can
be reproduced or challenged.
"""


@dataclass(frozen=True)
class DroppedInjury:
    """A claimed injury that did not become one, and why."""

    site: str
    reason: str


@dataclass(frozen=True)
class BuildResult:
    injuries: tuple[Injury, ...]
    dropped: tuple[DroppedInjury, ...]

    @property
    def fabrication_count(self) -> int:
        return len(self.dropped)


def _measurement(value: str | None) -> float | None:
    """Parse a dictated measurement, or None.

    None where the examiner was approximate. An approximate measurement
    recorded as exact is the kind of thing a defence expert is paid to find.
    """
    if value is None:
        return None
    matched = MEASUREMENT.match(value)
    return float(matched.group(1)) if matched else None


def _locate(
    claim: DraftInjury,
    dictation: str,
    source_id: str,
    examiner_id: str,
) -> Injury | DroppedInjury:
    if claim.source_span not in dictation:
        return DroppedInjury(
            site=claim.site,
            reason=(
                f"span {claim.source_span!r} does not occur in the examiner's "
                f"dictation; an injury in a medico-legal record must quote what the "
                f"examiner said, not summarise it"
            ),
        )

    distance = _measurement(claim.landmark_distance_cm)
    if distance is not None and not claim.landmark:
        return DroppedInjury(
            site=claim.site,
            reason=(
                f"injury at {claim.site!r} carries a distance of {distance}cm but "
                f"names no landmark; a measurement from an unstated point cannot be "
                f"reproduced or challenged"
            ),
        )

    provenance = ExaminerEntry(
        source_id=source_id,
        examiner_id=examiner_id,
        text=claim.source_span,
        field_path="injuries",
    )
    try:
        return Injury(
            injury_type=claim.injury_type,
            site=claim.site,
            landmark=claim.landmark,
            landmark_distance_cm=distance,
            length_cm=_measurement(claim.length_cm),
            width_cm=_measurement(claim.width_cm),
            depth_cm=_measurement(claim.depth_cm),
            shape=claim.shape,
            margins=claim.margins,
            direction=claim.direction,
            estimated_age=claim.estimated_age,
            provenance=provenance,
        )
    except ValueError as error:
        return DroppedInjury(site=claim.site, reason=str(error))


def build(
    draft: ExaminationDraft,
    dictation: str,
    source_id: str,
    examiner_id: str,
) -> BuildResult:
    """Turn claimed injuries into injuries, dropping the unsupported.

    Pure, and separately testable from the model call.
    """
    injuries: list[Injury] = []
    dropped: list[DroppedInjury] = []
    for claim in draft.injuries:
        located = _locate(claim, dictation, source_id, examiner_id)
        if isinstance(located, DroppedInjury):
            dropped.append(located)
            continue
        injuries.append(located)
    return BuildResult(injuries=tuple(injuries), dropped=tuple(dropped))
