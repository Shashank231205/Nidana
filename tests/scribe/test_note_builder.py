"""Scribe's groundedness gate and note lifecycle.

The gate is the same one Consult applies to findings, and it matters more here
in one respect: a fabricated finding distorts a triage decision, while a
fabricated line in a signed note is a clinical record of something that did not
happen.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from services.scribe.agents.note_builder import build
from spine.schemas.note import (
    ClinicalNote,
    NoteSection,
    NoteStatus,
    Omission,
    Statement,
)
from spine.schemas.provenance import ExaminerEntry, TranscriptSpan, locate_transcript
from spine.schemas.transcript import (
    DraftStatement,
    NoteDraft,
    Speaker,
    Transcript,
    TranscriptSegment,
)

CONSULTATION = Transcript(
    segments=(
        TranscriptSegment(
            text="Since when is the pain there?",
            speaker=Speaker.CLINICIAN,
            audio_start_ms=0,
            audio_end_ms=2000,
        ),
        TranscriptSegment(
            text="do din se, chest mein",
            speaker=Speaker.PATIENT,
            audio_start_ms=2100,
            audio_end_ms=4500,
            language="hi-en",
        ),
        TranscriptSegment(
            text="Any breathlessness?",
            speaker=Speaker.CLINICIAN,
            audio_start_ms=4600,
            audio_end_ms=6000,
        ),
        TranscriptSegment(
            text="nahi, saans theek hai",
            speaker=Speaker.PATIENT,
            audio_start_ms=6100,
            audio_end_ms=8000,
            language="hi-en",
        ),
    )
)


def draft(*claims: tuple[NoteSection, str, str]) -> NoteDraft:
    return NoteDraft(
        statements=tuple(
            DraftStatement(section=section, text=text, source_span=span)
            for section, text, span in claims
        )
    )


class TestGroundedness:
    def test_a_supported_claim_becomes_a_statement(self) -> None:
        result = build(
            draft((NoteSection.SUBJECTIVE, "Chest pain two days", "do din se, chest mein")),
            CONSULTATION,
            "enc-1",
        )
        assert len(result.statements) == 1
        assert result.fabrication_count == 0

    def test_an_unsupported_claim_is_dropped(self) -> None:
        result = build(
            draft((NoteSection.ASSESSMENT, "Patient appeared anxious", "seemed worried")),
            CONSULTATION,
            "enc-1",
        )
        assert not result.statements
        assert result.fabrication_count == 1

    def test_the_drop_reason_says_quote_rather_than_summarise(self) -> None:
        result = build(
            draft((NoteSection.ASSESSMENT, "Anxious", "seemed worried")), CONSULTATION, "enc-1"
        )
        assert "not summarise it" in result.dropped[0].reason

    def test_a_paraphrase_of_a_real_utterance_is_still_dropped(self) -> None:
        """'Two days' is what the patient meant; it is not what they said."""
        result = build(
            draft((NoteSection.SUBJECTIVE, "Two days", "chest pain for two days")),
            CONSULTATION,
            "enc-1",
        )
        assert result.fabrication_count == 1

    def test_supported_and_unsupported_claims_are_separated(self) -> None:
        result = build(
            draft(
                (NoteSection.SUBJECTIVE, "Chest pain", "do din se, chest mein"),
                (NoteSection.ASSESSMENT, "Anxious", "seemed worried"),
                (NoteSection.SUBJECTIVE, "No breathlessness", "nahi, saans theek hai"),
            ),
            CONSULTATION,
            "enc-1",
        )
        assert len(result.statements) == 2
        assert result.fabrication_count == 1

    def test_an_empty_draft_produces_nothing(self) -> None:
        result = build(NoteDraft(), CONSULTATION, "enc-1")
        assert result.statements == ()
        assert result.fabrication_count == 0


class TestAudioOffsets:
    """Click-to-hear is the feature that earns trust, so it is tested."""

    def test_a_statement_carries_the_audio_window_of_its_segment(self) -> None:
        result = build(
            draft((NoteSection.SUBJECTIVE, "Chest pain", "do din se, chest mein")),
            CONSULTATION,
            "enc-1",
        )
        assert result.statements[0].audio_offset_ms == 2100

    def test_a_later_statement_lands_on_a_later_segment(self) -> None:
        result = build(
            draft((NoteSection.SUBJECTIVE, "No breathlessness", "nahi, saans theek hai")),
            CONSULTATION,
            "enc-1",
        )
        assert result.statements[0].audio_offset_ms == 6100

    def test_the_speaker_is_carried_through(self) -> None:
        result = build(
            draft((NoteSection.SUBJECTIVE, "Chest pain", "do din se, chest mein")),
            CONSULTATION,
            "enc-1",
        )
        provenance = result.statements[0].provenance
        assert isinstance(provenance, TranscriptSpan)
        assert provenance.speaker == "patient"


class TestTranscript:
    def test_a_reversed_segment_window_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="span of time"):
            TranscriptSegment(
                text="x", speaker=Speaker.PATIENT, audio_start_ms=900, audio_end_ms=100
            )

    def test_out_of_order_segments_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="ordered by time"):
            Transcript(
                segments=(
                    TranscriptSegment(
                        text="second",
                        speaker=Speaker.PATIENT,
                        audio_start_ms=5000,
                        audio_end_ms=6000,
                    ),
                    TranscriptSegment(
                        text="first",
                        speaker=Speaker.PATIENT,
                        audio_start_ms=1000,
                        audio_end_ms=2000,
                    ),
                )
            )

    def test_unknown_is_a_valid_speaker_not_an_error(self) -> None:
        """A segment attributed wrongly is worse than one left unattributed."""
        segment = TranscriptSegment(
            text="x", speaker=Speaker.UNKNOWN, audio_start_ms=0, audio_end_ms=10
        )
        assert segment.speaker is Speaker.UNKNOWN

    def test_family_is_a_first_class_speaker(self) -> None:
        segment = TranscriptSegment(
            text="x", speaker=Speaker.FAMILY, audio_start_ms=0, audio_end_ms=10
        )
        assert segment.speaker is Speaker.FAMILY

    def test_segments_can_be_filtered_by_speaker(self) -> None:
        assert len(CONSULTATION.by_speaker(Speaker.PATIENT)) == 2

    def test_duration_is_derived(self) -> None:
        assert CONSULTATION.segments[0].duration_ms == 2000


class TestStatementProvenance:
    def test_a_generated_statement_must_quote_the_transcript(self) -> None:
        examiner = ExaminerEntry(
            source_id="enc-1",
            examiner_id="dr_x",
            text="Chest clear on auscultation",
            field_path="examination",
        )
        with pytest.raises(ValueError, match="must quote the transcript"):
            Statement(
                section=NoteSection.EXAMINATION,
                text="Chest clear",
                provenance=examiner,
            )

    def test_a_clinician_written_statement_may_carry_examiner_provenance(self) -> None:
        """A clinician may write what they observed; a model may not."""
        examiner = ExaminerEntry(
            source_id="enc-1",
            examiner_id="dr_x",
            text="Chest clear on auscultation",
            field_path="examination",
        )
        statement = Statement(
            section=NoteSection.EXAMINATION,
            text="Chest clear",
            provenance=examiner,
            clinician_edited=True,
        )
        assert statement.clinician_edited


class TestNoteLifecycle:
    def test_a_draft_needs_no_signer(self) -> None:
        assert ClinicalNote(encounter_id=uuid4()).status is NoteStatus.DRAFT

    def test_a_signed_note_must_name_its_signer(self) -> None:
        with pytest.raises(ValueError, match="must name the clinician"):
            ClinicalNote(encounter_id=uuid4(), status=NoteStatus.SIGNED)

    def test_an_outstanding_blocking_omission_prevents_signing(self) -> None:
        omission = Omission(
            rule_id="NC_ALLERGY_001",
            label="Allergy check before new prescription",
            section=NoteSection.PLAN,
            blocking=True,
        )
        with pytest.raises(ValueError, match="will not fill it"):
            ClinicalNote(
                encounter_id=uuid4(),
                status=NoteStatus.SIGNED,
                signed_by="Dr X",
                omissions=(omission,),
            )

    def test_a_dismissed_omission_allows_signing(self) -> None:
        omission = Omission(
            rule_id="NC_ALLERGY_001",
            label="Allergy check",
            section=NoteSection.PLAN,
            blocking=True,
            dismissed_reason="No new prescription issued",
        )
        note = ClinicalNote(
            encounter_id=uuid4(),
            status=NoteStatus.SIGNED,
            signed_by="Dr X",
            omissions=(omission,),
        )
        assert note.is_signable

    def test_a_non_blocking_omission_never_prevents_signing(self) -> None:
        """Advisory means advisory. A tool that blocks gets switched off."""
        omission = Omission(
            rule_id="NC_FOLLOWUP_001",
            label="Follow-up interval not stated",
            section=NoteSection.FOLLOW_UP,
            blocking=False,
        )
        note = ClinicalNote(
            encounter_id=uuid4(),
            status=NoteStatus.SIGNED,
            signed_by="Dr X",
            omissions=(omission,),
        )
        assert note.is_signable

    def test_statements_can_be_read_by_section(self) -> None:
        span = locate_transcript(
            source_id="enc-1",
            source_text=CONSULTATION.text,
            quote="do din se, chest mein",
            audio_start_ms=2100,
            audio_end_ms=4500,
        )
        note = ClinicalNote(
            encounter_id=uuid4(),
            statements=(
                Statement(
                    section=NoteSection.SUBJECTIVE, text="Chest pain", provenance=span
                ),
            ),
        )
        assert len(note.in_section(NoteSection.SUBJECTIVE)) == 1
        assert note.in_section(NoteSection.PLAN) == ()

    def test_a_consult_session_can_be_linked(self) -> None:
        """Where Consult preceded the visit, the note starts pre-populated."""
        session_id = uuid4()
        note = ClinicalNote(encounter_id=uuid4(), consult_session_id=session_id)
        assert note.consult_session_id == session_id
