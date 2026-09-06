"""Traceability from a clinical fact back to the exact evidence that produced it.

ADR 0002 and NIDANA.md section 6. Every clinical fact carries the span it came
from. No span, no fact.

`Provenance` is a discriminated union from the start, not a string and not one
flat shape. The five services locate evidence differently -- Consult in the
patient's verbatim words, Scribe in a transcript with an audio offset, Rx in an
OCR bounding box, Labs in a cell of a parsed report, Forensics in the examiner's
own signed entry -- and a shape that fits only Consult would have to be widened
later, when four services already depend on it.

What every variant shares: `text`, the evidence rendered as characters, and a
refusal to accept a paraphrase in place of it.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(str, Enum):
    """Where a span was taken from. One value per service."""

    PATIENT_UTTERANCE = "patient_utterance"
    TRANSCRIPT_SEGMENT = "transcript_segment"
    DOCUMENT_SPAN = "document_span"
    OCR_REGION = "ocr_region"
    EXAMINER_ENTRY = "examiner_entry"


class SpanVerificationError(ValueError):
    """Raised when a span does not match the evidence it claims to quote."""


class TextAnchoredSpan(BaseModel):
    """Evidence addressed by character offsets into stored text.

    Offsets are Python string indices over the raw stored text: original script,
    no normalisation, no transliteration, no case folding. This holds unchanged
    for code-switched input and for ASR output.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1, description="Identifier of the stored source text")
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    text: str = Field(min_length=1, description="The quoted evidence, verbatim")

    @model_validator(mode="after")
    def _offsets_describe_the_text(self) -> TextAnchoredSpan:
        if self.char_end <= self.char_start:
            raise ValueError(
                f"char_end ({self.char_end}) must be greater than char_start "
                f"({self.char_start}); an empty span cannot support a clinical fact"
            )
        span_length = self.char_end - self.char_start
        if span_length != len(self.text):
            raise ValueError(
                f"span [{self.char_start}:{self.char_end}] is {span_length} characters "
                f"but text is {len(self.text)}; the offsets and the quoted text disagree"
            )
        return self

    def verify_against(self, source_text: str) -> None:
        """Confirm this span actually quotes `source_text`.

        Called at the point of extraction, where the source is in hand. A fact is
        never reconstructed from the database and verified afterwards.
        """
        if self.char_end > len(source_text):
            raise SpanVerificationError(
                f"span [{self.char_start}:{self.char_end}] runs past the end of "
                f"{self.source_id} (length {len(source_text)}); the fact does not come "
                f"from this text"
            )
        quoted = source_text[self.char_start : self.char_end]
        if quoted != self.text:
            raise SpanVerificationError(
                f"span [{self.char_start}:{self.char_end}] of {self.source_id} is "
                f"{quoted!r} but the fact quotes {self.text!r}; a paraphrase is not a "
                f"source span"
            )


class UtteranceSpan(TextAnchoredSpan):
    """S1 Consult. The patient's own words, verbatim."""

    source_type: Literal[SourceType.PATIENT_UTTERANCE] = SourceType.PATIENT_UTTERANCE
    turn_index: int = Field(ge=0)


class TranscriptSpan(TextAnchoredSpan):
    """S2 Scribe. Transcript text plus the audio moment it was said.

    The audio offset is what lets a clinician click a line in the note and hear
    the moment it came from.
    """

    source_type: Literal[SourceType.TRANSCRIPT_SEGMENT] = SourceType.TRANSCRIPT_SEGMENT
    audio_start_ms: int = Field(ge=0)
    audio_end_ms: int = Field(gt=0)
    speaker: str | None = Field(default=None, description="Diarised speaker label")

    @model_validator(mode="after")
    def _audio_window_is_ordered(self) -> TranscriptSpan:
        if self.audio_end_ms <= self.audio_start_ms:
            raise ValueError(
                f"audio_end_ms ({self.audio_end_ms}) must be after audio_start_ms "
                f"({self.audio_start_ms}); a segment occupies a span of time"
            )
        return self


class DocumentSpan(TextAnchoredSpan):
    """S4 Labs. A cell or region of a parsed report."""

    source_type: Literal[SourceType.DOCUMENT_SPAN] = SourceType.DOCUMENT_SPAN
    page: int = Field(ge=1)
    cell_reference: str | None = Field(
        default=None, description="Table cell or region identifier within the page"
    )


class BoundingBox(BaseModel):
    """A rectangle on a source image, in pixels from the top-left origin."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class OcrRegion(BaseModel):
    """S3 Rx. A bounding box on a prescription image plus the text read from it.

    Not text-anchored: the evidence is a region of an image, and the characters
    are the OCR engine's reading of it rather than stored source text. It carries
    the engine's confidence because Rx refuses rather than guesses below a
    threshold, and that decision needs the number.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: Literal[SourceType.OCR_REGION] = SourceType.OCR_REGION
    source_id: str = Field(min_length=1, description="Identifier of the stored image")
    page: int = Field(default=1, ge=1)
    box: BoundingBox
    text: str = Field(min_length=1, description="Characters read from this region")
    ocr_confidence: float = Field(ge=0.0, le=1.0)


class ExaminerEntry(BaseModel):
    """S5 Forensics. The examiner's own signed entry.

    Forensics generates nothing: if the examiner did not observe it, it cannot
    appear. The provenance is the examiner's identity and the field they filled,
    which is what makes the record defensible as an independent examination.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: Literal[SourceType.EXAMINER_ENTRY] = SourceType.EXAMINER_ENTRY
    source_id: str = Field(min_length=1, description="Identifier of the examination record")
    examiner_id: str = Field(min_length=1)
    text: str = Field(min_length=1, description="What the examiner recorded, verbatim")
    field_path: str = Field(min_length=1, description="Which field of the form this entry filled")


Provenance: TypeAlias = Annotated[
    UtteranceSpan | TranscriptSpan | DocumentSpan | OcrRegion | ExaminerEntry,
    Field(discriminator="source_type"),
]

TextAnchoredProvenance: TypeAlias = UtteranceSpan | TranscriptSpan | DocumentSpan


def _require_quote(source_id: str, source_text: str, quote: str, search_from: int) -> int:
    if not quote:
        raise SpanVerificationError(
            f"cannot locate an empty quote in {source_id}; a clinical fact requires the "
            f"words that stated it"
        )
    start = source_text.find(quote, search_from)
    if start == -1:
        raise SpanVerificationError(
            f"{quote!r} does not occur in {source_id} at or after character "
            f"{search_from}; record what was said, not a rephrasing of it"
        )
    return start


def locate_utterance(
    source_id: str,
    source_text: str,
    quote: str,
    turn_index: int,
    search_from: int = 0,
) -> UtteranceSpan:
    """Build Consult provenance by finding `quote` inside a patient utterance.

    The single supported construction path for S1. It cannot produce an
    unverifiable span, because a quote that is not present raises instead of
    being stored.
    """
    start = _require_quote(source_id, source_text, quote, search_from)
    return UtteranceSpan(
        source_id=source_id,
        char_start=start,
        char_end=start + len(quote),
        text=quote,
        turn_index=turn_index,
    )


def locate_transcript(
    *,
    source_id: str,
    source_text: str,
    quote: str,
    audio_start_ms: int,
    audio_end_ms: int,
    speaker: str | None = None,
    search_from: int = 0,
) -> TranscriptSpan:
    """Build Scribe provenance by finding `quote` inside a transcript segment."""
    start = _require_quote(source_id, source_text, quote, search_from)
    return TranscriptSpan(
        source_id=source_id,
        char_start=start,
        char_end=start + len(quote),
        text=quote,
        audio_start_ms=audio_start_ms,
        audio_end_ms=audio_end_ms,
        speaker=speaker,
    )


def locate_document(
    *,
    source_id: str,
    source_text: str,
    quote: str,
    page: int,
    cell_reference: str | None = None,
    search_from: int = 0,
) -> DocumentSpan:
    """Build Labs provenance by finding `quote` inside a parsed report."""
    start = _require_quote(source_id, source_text, quote, search_from)
    return DocumentSpan(
        source_id=source_id,
        char_start=start,
        char_end=start + len(quote),
        text=quote,
        page=page,
        cell_reference=cell_reference,
    )
