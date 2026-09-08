"""Turning a read prescription into resolved medication lines.

Two steps, and the order matters. Every claimed line must be found in the OCR
text, and only then is its brand resolved against the index. The model reads;
the index decides what molecule that reading means.

A line the model invented would otherwise be resolved confidently to a real
molecule, and every downstream check — interaction, duplicate therapy, allergy
— would run against a drug nobody prescribed.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.rx.agents.resolver import (
    UNREADABLE_PLACEHOLDER,
    BrandIndex,
    resolve_line,
)
from spine.schemas.medication import (
    DraftLine,
    MedicationList,
    PrescribedMedication,
    PrescriptionDraft,
    ResolutionStatus,
)
from spine.schemas.provenance import SpanVerificationError, locate_document


@dataclass(frozen=True)
class DroppedLine:
    """A claimed line that did not become a medication, and why."""

    written_as: str
    reason: str


@dataclass(frozen=True)
class BuildResult:
    medications: MedicationList
    dropped: tuple[DroppedLine, ...]

    @property
    def fabrication_count(self) -> int:
        return len(self.dropped)

    @property
    def unresolved_count(self) -> int:
        """Lines read but not resolved to a molecule.

        Separate from fabrication: a line the pharmacist must confirm is a
        working outcome, and a line the model invented is not.
        """
        return len(self.medications.unresolved)


def _build_line(
    claim: DraftLine,
    ocr_text: str,
    source_id: str,
    index: BrandIndex,
    page: int,
) -> PrescribedMedication | DroppedLine:
    try:
        span = locate_document(
            source_id=source_id, source_text=ocr_text, quote=claim.source_span, page=page
        )
    except SpanVerificationError as error:
        return DroppedLine(written_as=claim.written_as, reason=str(error))

    if not claim.legible:
        # An illegible line is recorded rather than dropped: the pharmacist
        # needs to see that a line existed and could not be read.
        return PrescribedMedication(
            written_as=UNREADABLE_PLACEHOLDER,
            resolution=ResolutionStatus.UNREADABLE,
            resolution_confidence=0.0,
            provenance=span,
            frequency=claim.frequency,
            route=claim.route,
        )

    resolved = resolve_line(claim.written_as, index, span)
    return resolved.model_copy(
        update={"frequency": claim.frequency, "route": claim.route}
    )


def build(
    draft: PrescriptionDraft,
    ocr_text: str,
    source_id: str,
    index: BrandIndex,
    page: int = 1,
) -> BuildResult:
    """Turn claimed lines into medications, dropping the unsupported.

    Pure given an index, and separately testable from the model call.
    """
    medications: list[PrescribedMedication] = []
    dropped: list[DroppedLine] = []
    for claim in draft.lines:
        built = _build_line(claim, ocr_text, source_id, index, page)
        if isinstance(built, DroppedLine):
            dropped.append(built)
            continue
        medications.append(built)
    return BuildResult(
        medications=MedicationList(medications=tuple(medications)),
        dropped=tuple(dropped),
    )
