"""The clinical note.

S2 Scribe writes this. It is in the spine rather than the service because
Consult's handoff packet and Labs' routing both read from it, and because the
groundedness mechanism is the same one every service uses.

Every clinical statement carries the transcript span it came from, with an
audio offset. That offset is what lets a clinician click a line and hear the
moment it was said, and it is the feature that earns trust rather than an
optional extra.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.primitives import Coding
from spine.schemas.provenance import Provenance, SourceType


class NoteSection(str, Enum):
    """SOAP, plus the sections an Indian OPD note actually carries."""

    SUBJECTIVE = "subjective"
    OBJECTIVE = "objective"
    ASSESSMENT = "assessment"
    PLAN = "plan"
    EXAMINATION = "examination"
    INVESTIGATIONS = "investigations"
    FOLLOW_UP = "follow_up"


class NoteStatus(str, Enum):
    """A note is a draft until a clinician signs it.

    Nothing generated is clinical record until a qualified person has put their
    name to it. The distinction is the whole liability model.
    """

    DRAFT = "draft"
    EDITED = "edited"
    SIGNED = "signed"
    AMENDED = "amended"


class Statement(BaseModel):
    """One clinical statement in a note, with the transcript behind it.

    `provenance` is a TranscriptSpan for anything the model wrote. A statement
    the clinician typed themselves carries ExaminerEntry-style provenance
    instead, because its source is the clinician rather than the recording.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    section: NoteSection
    text: str = Field(min_length=1)
    provenance: Provenance
    codings: tuple[Coding, ...] = ()
    clinician_edited: bool = False

    @model_validator(mode="after")
    def _generated_statements_quote_the_transcript(self) -> Statement:
        """A statement the model wrote must trace to something that was said.

        A clinician may write anything they observed. A model may only write
        what it heard, and the span type is what distinguishes the two.
        """
        if not self.clinician_edited and self.provenance.source_type not in {
            SourceType.TRANSCRIPT_SEGMENT,
            SourceType.PATIENT_UTTERANCE,
        }:
            raise ValueError(
                f"generated statement in {self.section.value} carries "
                f"{self.provenance.source_type.value} provenance; a statement the model "
                f"wrote must quote the transcript, or be marked clinician_edited"
            )
        return self

    @property
    def audio_offset_ms(self) -> int | None:
        """Where in the recording this was said, for click-to-hear."""
        return getattr(self.provenance, "audio_start_ms", None)


class Omission(BaseModel):
    """A clinically expected element the consultation did not cover.

    Advisory. `dismissed_reason` records a clinician deciding it did not apply,
    which is a different thing from the element being present.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    section: NoteSection
    blocking: bool = False
    dismissed_reason: str | None = None

    @property
    def is_outstanding(self) -> bool:
        return self.blocking and self.dismissed_reason is None


class ClinicalNote(BaseModel):
    """One consultation, documented.

    The clinician edits rather than writes. What they change is the highest
    value training signal this product generates, so `edit_distance_from_draft`
    is carried on the note rather than computed later from a diff that may not
    survive.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    encounter_id: UUID
    status: NoteStatus = NoteStatus.DRAFT
    statements: tuple[Statement, ...] = ()
    omissions: tuple[Omission, ...] = ()
    signed_by: str | None = None
    edit_distance_from_draft: int | None = None
    consult_session_id: UUID | None = Field(
        default=None,
        description="The Consult session that preceded this visit, where there was one",
    )

    @model_validator(mode="after")
    def _a_signed_note_names_its_signer(self) -> ClinicalNote:
        if self.status is NoteStatus.SIGNED and not self.signed_by:
            raise ValueError(
                "a signed note must name the clinician who signed it; an unsigned note "
                "is a draft and carries no clinical authority"
            )
        return self

    @model_validator(mode="after")
    def _outstanding_blocking_omissions_prevent_signing(self) -> ClinicalNote:
        outstanding = [o.rule_id for o in self.omissions if o.is_outstanding]
        if self.status is NoteStatus.SIGNED and outstanding:
            raise ValueError(
                f"note has {len(outstanding)} outstanding blocking omission(s): "
                f"{', '.join(outstanding)}. Fill the element or dismiss the flag with a "
                f"reason; the system will not fill it"
            )
        return self

    def in_section(self, section: NoteSection) -> tuple[Statement, ...]:
        return tuple(s for s in self.statements if s.section is section)

    @property
    def outstanding_omissions(self) -> tuple[Omission, ...]:
        return tuple(o for o in self.omissions if o.is_outstanding)

    @property
    def is_signable(self) -> bool:
        return not self.outstanding_omissions
