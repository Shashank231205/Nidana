"""What Scribe's agents return.

Claims, not facts. A statement becomes part of a note only after its span
verifies against the transcript, the same gate Consult applies to findings.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.note import NoteSection


class Speaker(str, Enum):
    """Who said a segment.

    Diarisation in a noisy Indian OPD with family members present is materially
    harder than the benchmark case, so FAMILY and UNKNOWN are first-class rather
    than error states. A segment attributed to UNKNOWN is still usable; one
    attributed wrongly is worse than one left unattributed.
    """

    CLINICIAN = "clinician"
    PATIENT = "patient"
    FAMILY = "family"
    UNKNOWN = "unknown"


class TranscriptSegment(BaseModel):
    """One diarised stretch of speech."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str = Field(min_length=1)
    speaker: Speaker
    audio_start_ms: int = Field(ge=0)
    audio_end_ms: int = Field(gt=0)
    language: str = Field(default="en", min_length=2)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _the_window_is_ordered(self) -> TranscriptSegment:
        if self.audio_end_ms <= self.audio_start_ms:
            raise ValueError(
                f"segment ends at {self.audio_end_ms}ms, at or before its start at "
                f"{self.audio_start_ms}ms; a segment occupies a span of time"
            )
        return self

    @property
    def duration_ms(self) -> int:
        return self.audio_end_ms - self.audio_start_ms


class Transcript(BaseModel):
    """A consultation, transcribed and diarised."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    segments: tuple[TranscriptSegment, ...] = ()

    @model_validator(mode="after")
    def _segments_run_forwards(self) -> Transcript:
        for earlier, later in zip(self.segments, self.segments[1:], strict=False):
            if later.audio_start_ms < earlier.audio_start_ms:
                raise ValueError(
                    f"segment at {later.audio_start_ms}ms follows one at "
                    f"{earlier.audio_start_ms}ms; segments are ordered by time"
                )
        return self

    @property
    def text(self) -> str:
        """The whole transcript as one string.

        Spans are verified against this, so the joining is part of the
        contract: single newline between segments, nothing else added.
        """
        return "\n".join(segment.text for segment in self.segments)

    def segment_at(self, offset: int) -> TranscriptSegment | None:
        """The segment covering a character offset into `text`."""
        position = 0
        for segment in self.segments:
            end = position + len(segment.text)
            if position <= offset < end:
                return segment
            position = end + 1
        return None

    def by_speaker(self, speaker: Speaker) -> tuple[TranscriptSegment, ...]:
        return tuple(s for s in self.segments if s.speaker is speaker)


class DraftStatement(BaseModel):
    """One statement the note agent claims the consultation contained."""

    model_config = ConfigDict(extra="forbid")

    section: NoteSection
    text: str = Field(min_length=1)
    source_span: str = Field(
        min_length=1,
        description="Exact substring of the transcript that supports this statement",
    )


class NoteDraft(BaseModel):
    """What the note agent returns for one consultation."""

    model_config = ConfigDict(extra="forbid")

    statements: tuple[DraftStatement, ...] = ()
