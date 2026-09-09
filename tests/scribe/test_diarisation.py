"""Working out who was speaking in a consultation.

pyannote is not exercised here and does not need to be. What is tested is the
part that decides what a note says: how speaker turns are matched to transcript
segments, and how conservatively a role is inferred from that.

Every test is really about one asymmetry. A segment left UNKNOWN makes a
clinician read it and decide, which costs seconds. A segment attributed to the
wrong person reads as fact, and in a note that joins the record it stays wrong.
So the module is built to prefer the first, and these tests pin that it does.
"""

from __future__ import annotations

from pathlib import Path

from services.scribe.asr.diarisation import (
    MINIMUM_OVERLAP_RATIO,
    PyannoteDiariser,
    SpeakerTurn,
    assign_speakers,
    diarise,
    infer_roles,
)
from spine.schemas.transcript import Speaker, Transcript, TranscriptSegment


def segment(text: str, start_ms: int, end_ms: int) -> TranscriptSegment:
    return TranscriptSegment(
        text=text,
        speaker=Speaker.UNKNOWN,
        audio_start_ms=start_ms,
        audio_end_ms=end_ms,
    )


def turn(label: str, start_ms: int, end_ms: int) -> SpeakerTurn:
    return SpeakerTurn(label=label, start_ms=start_ms, end_ms=end_ms)


def consultation() -> tuple[tuple[TranscriptSegment, ...], tuple[SpeakerTurn, ...]]:
    """A short consultation: the doctor asks, the patient answers."""
    segments = (
        segment("What brings you in today?", 0, 2000),
        segment("I have had chest pain since morning.", 2000, 5000),
        segment("Does it move anywhere?", 5000, 7000),
        segment("It goes to my left arm.", 7000, 9000),
    )
    turns = (
        turn("SPEAKER_00", 0, 2000),
        turn("SPEAKER_01", 2000, 5000),
        turn("SPEAKER_00", 5000, 7000),
        turn("SPEAKER_01", 7000, 9000),
    )
    return segments, turns


class TestAssigningSpeakers:
    def test_a_segment_goes_to_the_turn_that_covers_it(self) -> None:
        segments = (segment("Hello.", 0, 1000),)
        turns = (turn("SPEAKER_00", 0, 1000),)
        assigned = assign_speakers(segments, turns, {"SPEAKER_00": Speaker.CLINICIAN})
        assert assigned[0].speaker is Speaker.CLINICIAN

    def test_a_segment_split_between_two_voices_is_unknown(self) -> None:
        """ASR splits on pauses, diarisation on voice changes.

        A sentence half-owned by each has no owner, and handing it to whoever
        overlapped by a few more milliseconds is a guess about who said it.
        """
        segments = (segment("Hello.", 0, 1000),)
        turns = (turn("SPEAKER_00", 0, 500), turn("SPEAKER_01", 500, 1000))
        assigned = assign_speakers(
            segments, turns, {"SPEAKER_00": Speaker.CLINICIAN, "SPEAKER_01": Speaker.PATIENT}
        )
        assert assigned[0].speaker is Speaker.UNKNOWN

    def test_a_mostly_covered_segment_is_assigned(self) -> None:
        segments = (segment("Hello.", 0, 1000),)
        turns = (turn("SPEAKER_00", 0, 900), turn("SPEAKER_01", 900, 1000))
        assigned = assign_speakers(
            segments, turns, {"SPEAKER_00": Speaker.CLINICIAN, "SPEAKER_01": Speaker.PATIENT}
        )
        assert assigned[0].speaker is Speaker.CLINICIAN

    def test_a_label_with_no_role_is_unknown_not_guessed(self) -> None:
        """Diarisation separates voices; it does not say which is the doctor."""
        segments = (segment("Hello.", 0, 1000),)
        turns = (turn("SPEAKER_00", 0, 1000),)
        assigned = assign_speakers(segments, turns, {})
        assert assigned[0].speaker is Speaker.UNKNOWN

    def test_no_turns_leaves_everything_unknown(self) -> None:
        segments = (segment("Hello.", 0, 1000),)
        assert assign_speakers(segments, (), {})[0].speaker is Speaker.UNKNOWN

    def test_the_text_is_never_edited(self) -> None:
        """Diarisation decides who spoke. It does not touch what was said."""
        segments, turns = consultation()
        assigned = assign_speakers(segments, turns, {})
        assert [s.text for s in assigned] == [s.text for s in segments]

    def test_the_timing_is_never_edited(self) -> None:
        segments, turns = consultation()
        assigned = assign_speakers(segments, turns, {})
        assert [s.audio_start_ms for s in assigned] == [s.audio_start_ms for s in segments]

    def test_the_overlap_floor_is_where_it_is_claimed(self) -> None:
        assert 0.0 < MINIMUM_OVERLAP_RATIO <= 1.0


class TestInferringRoles:
    def test_the_question_asker_is_the_clinician(self) -> None:
        segments, turns = consultation()
        roles = infer_roles(segments, turns)
        assert roles["SPEAKER_00"] is Speaker.CLINICIAN
        assert roles["SPEAKER_01"] is Speaker.PATIENT

    def test_a_single_voice_infers_nothing(self) -> None:
        """One speaker could be either, and picking is guessing."""
        segments = tuple(segment(f"Line {n}?", n * 1000, (n + 1) * 1000) for n in range(6))
        turns = tuple(turn("SPEAKER_00", n * 1000, (n + 1) * 1000) for n in range(6))
        assert infer_roles(segments, turns) == {}

    def test_too_few_turns_infers_nothing(self) -> None:
        """A three-turn recording has no structure to read."""
        segments = (segment("What is wrong?", 0, 1000), segment("Pain.", 1000, 2000))
        turns = (turn("SPEAKER_00", 0, 1000), turn("SPEAKER_01", 1000, 2000))
        assert infer_roles(segments, turns) == {}

    def test_no_questions_at_all_infers_nothing(self) -> None:
        """The heuristic has no signal, so it declines rather than picking."""
        segments = tuple(segment(f"Statement {n}.", n * 1000, (n + 1) * 1000) for n in range(4))
        turns = tuple(
            turn(f"SPEAKER_0{n % 2}", n * 1000, (n + 1) * 1000) for n in range(4)
        )
        assert infer_roles(segments, turns) == {}

    def test_both_voices_asking_equally_infers_nothing(self) -> None:
        """A tie means the heuristic cannot separate them, and it says so."""
        segments = (
            segment("How are you?", 0, 1000),
            segment("And you?", 1000, 2000),
            segment("Fine?", 2000, 3000),
            segment("Yes?", 3000, 4000),
        )
        turns = (
            turn("SPEAKER_00", 0, 1000),
            turn("SPEAKER_01", 1000, 2000),
            turn("SPEAKER_00", 2000, 3000),
            turn("SPEAKER_01", 3000, 4000),
        )
        assert infer_roles(segments, turns) == {}

    def test_a_third_voice_becomes_family(self) -> None:
        """A relative answering for the patient is the normal case here."""
        segments = (
            segment("What brings you in?", 0, 1000),
            segment("He has had fever for three days.", 1000, 4000),
            segment("Since when exactly?", 4000, 5000),
            segment("Monday.", 5000, 5500),
            segment("Any cough?", 5500, 6500),
            segment("Yes, at night.", 6500, 8000),
        )
        turns = (
            turn("SPEAKER_00", 0, 1000),
            turn("SPEAKER_02", 1000, 4000),
            turn("SPEAKER_00", 4000, 5000),
            turn("SPEAKER_01", 5000, 5500),
            turn("SPEAKER_00", 5500, 6500),
            turn("SPEAKER_02", 6500, 8000),
        )
        roles = infer_roles(segments, turns)
        assert roles["SPEAKER_00"] is Speaker.CLINICIAN
        assert Speaker.FAMILY in roles.values()

    def test_the_patient_is_the_other_voice_that_speaks_most(self) -> None:
        segments, turns = consultation()
        assert infer_roles(segments, turns)["SPEAKER_01"] is Speaker.PATIENT


class TestDiarisingATranscript:
    class StubDiariser:
        def __init__(self, *turns: SpeakerTurn) -> None:
            self._turns = turns

        def turns(self, audio_path: Path) -> tuple[SpeakerTurn, ...]:  # noqa: ARG002
            return self._turns

    def test_a_transcript_comes_back_attributed(self) -> None:
        segments, turns = consultation()
        result = diarise(
            Transcript(segments=segments), Path("audio.wav"), self.StubDiariser(*turns)
        )
        assert result.segments[0].speaker is Speaker.CLINICIAN
        assert result.segments[1].speaker is Speaker.PATIENT

    def test_a_diariser_that_finds_nothing_leaves_it_unattributed(self) -> None:
        """A note with unattributed lines is usable; one that does not exist is not."""
        segments, _ = consultation()
        result = diarise(
            Transcript(segments=segments), Path("audio.wav"), self.StubDiariser()
        )
        assert all(s.speaker is Speaker.UNKNOWN for s in result.segments)

    def test_the_transcript_text_survives_diarisation(self) -> None:
        segments, turns = consultation()
        result = diarise(
            Transcript(segments=segments), Path("audio.wav"), self.StubDiariser(*turns)
        )
        assert [s.text for s in result.segments] == [s.text for s in segments]


class TestOverlapArithmetic:
    def test_a_turn_inside_a_segment_overlaps_fully(self) -> None:
        assert turn("A", 100, 200).overlap_ms(0, 1000) == 100

    def test_a_disjoint_turn_does_not_overlap(self) -> None:
        assert turn("A", 0, 100).overlap_ms(200, 300) == 0

    def test_a_touching_turn_does_not_overlap(self) -> None:
        assert turn("A", 0, 100).overlap_ms(100, 200) == 0

    def test_duration_is_the_span(self) -> None:
        assert turn("A", 100, 400).duration_ms == 300


class TestAvailability:
    def test_availability_is_false_without_local_weights(self) -> None:
        assert not PyannoteDiariser(Path("no-such-directory")).is_available()

    def test_the_model_version_is_reported(self) -> None:
        """A transcript must be reproducible from what produced it."""
        assert PyannoteDiariser("pyannote/speaker-diarization-3.1").model_version.startswith(
            "pyannote/"
        )
