"""Turning a note draft into a note, dropping anything the transcript does not
support.

The same gate Consult applies to findings, applied to statements. A claim
becomes a Statement only if its span is an exact substring of the transcript.

Scribe's fabrication gate matters more than Consult's in one respect: a
fabricated finding distorts a triage decision, while a fabricated line in a
signed note is a clinical record of something that did not happen.
"""

from __future__ import annotations

from dataclasses import dataclass

from spine.schemas.note import Statement
from spine.schemas.provenance import (
    SpanVerificationError,
    TranscriptSpan,
    locate_transcript,
)
from spine.schemas.transcript import DraftStatement, NoteDraft, Transcript


@dataclass(frozen=True)
class DroppedStatement:
    """A claim that did not become a statement, and why."""

    section: str
    text: str
    reason: str


@dataclass(frozen=True)
class BuildResult:
    statements: tuple[Statement, ...]
    dropped: tuple[DroppedStatement, ...]

    @property
    def fabrication_count(self) -> int:
        """Claims the transcript did not support.

        The M2-equivalent gate for Scribe is zero fabrication, structurally
        enforced. This number being non-zero means the model tried; it reaching
        the note would mean the gate failed.
        """
        return len(self.dropped)


def _locate(
    claim: DraftStatement,
    transcript: Transcript,
    source_id: str,
) -> TranscriptSpan | DroppedStatement:
    """Find the claim's span in the transcript, with its audio offsets.

    The audio window comes from the segment the span falls in, so click-to-hear
    lands on the moment rather than the start of the recording.
    """
    text = transcript.text
    start = text.find(claim.source_span)
    if start == -1:
        return DroppedStatement(
            section=claim.section.value,
            text=claim.text,
            reason=(
                f"span {claim.source_span!r} does not occur in the transcript; a "
                f"statement the model wrote must quote what was said, not summarise it"
            ),
        )
    segment = transcript.segment_at(start)
    if segment is None:
        return DroppedStatement(
            section=claim.section.value,
            text=claim.text,
            reason=(
                f"span at offset {start} falls between segments; it cannot be located in "
                f"the audio and would not be playable"
            ),
        )
    try:
        return locate_transcript(
            source_id=source_id,
            source_text=text,
            quote=claim.source_span,
            audio_start_ms=segment.audio_start_ms,
            audio_end_ms=segment.audio_end_ms,
            speaker=segment.speaker.value,
        )
    except SpanVerificationError as error:
        return DroppedStatement(
            section=claim.section.value, text=claim.text, reason=str(error)
        )


def build(draft: NoteDraft, transcript: Transcript, source_id: str) -> BuildResult:
    """Turn claims into statements, dropping the unsupported.

    Pure, and separately testable from the model call, so golden transcripts run
    against recorded output rather than a live model.
    """
    statements: list[Statement] = []
    dropped: list[DroppedStatement] = []
    for claim in draft.statements:
        located = _locate(claim, transcript, source_id)
        if isinstance(located, DroppedStatement):
            dropped.append(located)
            continue
        statements.append(
            Statement(section=claim.section, text=claim.text, provenance=located)
        )
    return BuildResult(statements=tuple(statements), dropped=tuple(dropped))
