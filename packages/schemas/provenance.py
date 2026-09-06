"""Traceability from a clinical finding back to the exact text that produced it.

ADR 0002. A finding whose provenance does not verify against its source text is
not a weaker finding; it is a fabrication, and it is rejected rather than
downgraded.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(str, Enum):
    """Where a span was taken from.

    PATIENT_UTTERANCE is the only value Module 1 produces. The rest are declared
    now so modules 2-5 extend the record without altering this shape.
    """

    PATIENT_UTTERANCE = "patient_utterance"
    TRANSCRIPT_SEGMENT = "transcript_segment"
    DOCUMENT_SPAN = "document_span"
    OCR_REGION = "ocr_region"


class SpanVerificationError(ValueError):
    """Raised when a span does not match the source text it claims to quote."""


class Provenance(BaseModel):
    """A verified pointer into stored source text.

    Offsets are Python string indices over the raw stored text: the original
    script, no normalisation, no transliteration, no case folding. This holds
    unchanged for code-switched input and for ASR output.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: SourceType
    source_id: str = Field(min_length=1, description="Identifier of the stored source text")
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    text: str = Field(min_length=1, description="The quoted text, verbatim")

    @model_validator(mode="after")
    def _offsets_describe_the_text(self) -> Provenance:
        if self.char_end <= self.char_start:
            raise ValueError(
                f"char_end ({self.char_end}) must be greater than char_start "
                f"({self.char_start}); an empty span cannot support a finding"
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

        Called at the point of extraction, where the utterance is in hand. A
        finding is never reconstructed from the database and verified later.
        """
        if self.char_end > len(source_text):
            raise SpanVerificationError(
                f"span [{self.char_start}:{self.char_end}] runs past the end of "
                f"{self.source_id} (length {len(source_text)}); the finding does not "
                f"come from this text"
            )
        quoted = source_text[self.char_start : self.char_end]
        if quoted != self.text:
            raise SpanVerificationError(
                f"span [{self.char_start}:{self.char_end}] of {self.source_id} is "
                f"{quoted!r} but the finding quotes {self.text!r}; a paraphrase is not "
                f"a source span"
            )

    @classmethod
    def locate(
        cls,
        source_type: SourceType,
        source_id: str,
        source_text: str,
        quote: str,
        search_from: int = 0,
    ) -> Provenance:
        """Build provenance by finding `quote` inside `source_text`.

        The single supported construction path. It cannot produce an unverifiable
        span because a quote that is not present raises instead of being stored.
        """
        if not quote:
            raise SpanVerificationError(
                f"cannot locate an empty quote in {source_id}; a finding requires the "
                f"patient's own words"
            )
        start = source_text.find(quote, search_from)
        if start == -1:
            raise SpanVerificationError(
                f"{quote!r} does not occur in {source_id} at or after character "
                f"{search_from}; record what the patient said, not a rephrasing of it"
            )
        return cls(
            source_type=source_type,
            source_id=source_id,
            char_start=start,
            char_end=start + len(quote),
            text=quote,
        )
