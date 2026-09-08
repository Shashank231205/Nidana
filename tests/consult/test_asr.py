"""Transcription.

The model is not loaded here. What is tested is everything around it: the
refusals, the word-to-segment grouping, and the confidence rule that decides
whether a patient is asked to repeat themselves.

The grouping matters more than it looks. Segments split on pauses rather than
punctuation, because punctuation is unreliable in code-switched speech and a
pause is not, and the segment boundaries are what the audio offsets in the
record point at.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.consult.asr.transcriber import (
    AudioInput,
    TranscriptionError,
    TranscriptionResult,
    WhisperTranscriber,
    _words_from,
    segments_from_words,
)
from spine.schemas.transcript import LOW_CONFIDENCE_FLOOR, Speaker, Transcript


def word(
    text: str, start: int, end: int, confidence: float = 0.99
) -> tuple[str, int, int, float]:
    return (text, start, end, confidence)


class TestAudioInput:
    def test_a_supported_language_hint_is_accepted(self) -> None:
        assert AudioInput(path=Path("a.wav"), language_hint="hi").language_hint == "hi"

    def test_no_hint_is_accepted(self) -> None:
        """Detection beats a forced language on code-switched speech."""
        assert AudioInput(path=Path("a.wav")).language_hint is None

    def test_an_unsupported_hint_lists_the_alternatives(self) -> None:
        with pytest.raises(ValueError, match="omit the hint"):
            AudioInput(path=Path("a.wav"), language_hint="fr")


class TestSegmentation:
    def test_words_without_a_pause_form_one_segment(self) -> None:
        segments = segments_from_words(
            (word("mujhe", 0, 300), word("chest", 350, 700), word("pain", 720, 1000))
        )
        assert len(segments) == 1
        assert segments[0].text == "mujhe chest pain"

    def test_a_long_pause_starts_a_new_segment(self) -> None:
        segments = segments_from_words(
            (word("first", 0, 400), word("second", 2000, 2400)), max_gap_ms=700
        )
        assert len(segments) == 2

    def test_a_short_pause_does_not(self) -> None:
        segments = segments_from_words(
            (word("first", 0, 400), word("second", 900, 1300)), max_gap_ms=700
        )
        assert len(segments) == 1

    def test_segment_times_span_its_words(self) -> None:
        """The audio offsets are what click-to-hear lands on."""
        segments = segments_from_words((word("a", 100, 400), word("b", 450, 900)))
        assert segments[0].audio_start_ms == 100
        assert segments[0].audio_end_ms == 900

    def test_confidence_is_the_worst_word_not_the_mean(self) -> None:
        """A segment with one badly-heard drug name is not a confident segment."""
        segments = segments_from_words(
            (word("take", 0, 300, 0.99), word("warfarin", 350, 900, 0.31))
        )
        assert segments[0].confidence == pytest.approx(0.31)

    def test_no_words_produce_no_segments(self) -> None:
        assert segments_from_words(()) == ()

    def test_the_speaker_is_carried_through(self) -> None:
        segments = segments_from_words((word("x", 0, 100),), Speaker.CLINICIAN)
        assert segments[0].speaker is Speaker.CLINICIAN


class TestLowConfidence:
    def test_a_poor_segment_asks_for_confirmation(self) -> None:
        """The right response to an unclear segment is to ask again."""
        result = TranscriptionResult(
            transcript=Transcript(
                segments=segments_from_words(
                    (word("something", 0, 500, LOW_CONFIDENCE_FLOOR - 0.1),)
                )
            ),
            model_version="test",
        )
        assert result.needs_confirmation
        assert len(result.low_confidence_segments) == 1

    def test_a_clear_segment_does_not(self) -> None:
        result = TranscriptionResult(
            transcript=Transcript(
                segments=segments_from_words((word("clear", 0, 500, 0.95),))
            ),
            model_version="test",
        )
        assert not result.needs_confirmation

    def test_the_text_is_the_whole_transcript(self) -> None:
        result = TranscriptionResult(
            transcript=Transcript(
                segments=segments_from_words(
                    (word("chest", 0, 400), word("pain", 2000, 2400))
                )
            ),
            model_version="test",
        )
        assert "chest" in result.text
        assert "pain" in result.text


class FakeWord:
    def __init__(self, text: str, start: float, end: float, probability: float) -> None:
        self.word = text
        self.start = start
        self.end = end
        self.probability = probability


class FakeSegment:
    def __init__(self, words: list[FakeWord]) -> None:
        self.words = words


class TestWordExtraction:
    def test_seconds_become_milliseconds(self) -> None:
        """The backend works in seconds; the transcript works in milliseconds."""
        words = _words_from([FakeSegment([FakeWord("hi", 1.5, 2.25, 0.9)])])
        assert words == (("hi", 1500, 2250, 0.9),)

    def test_empty_words_are_dropped(self) -> None:
        words = _words_from([FakeSegment([FakeWord("  ", 0.0, 0.1, 0.9)])])
        assert words == ()

    def test_a_word_with_no_probability_is_treated_as_certain(self) -> None:
        """Dropping it would silently remove a word from the record."""

        class Bare:
            word = "x"
            start = 0.0
            end = 0.5

        words = _words_from([FakeSegment([Bare()])])  # type: ignore[list-item]
        assert words[0][3] == 1.0

    def test_segments_without_words_produce_nothing(self) -> None:
        class NoWords:
            words = None

        assert _words_from([NoWords()]) == ()


class TestRefusals:
    def test_missing_audio_is_refused_before_the_model_loads(self, tmp_path: Path) -> None:
        transcriber = WhisperTranscriber(tmp_path)
        with pytest.raises(TranscriptionError, match="no audio at"):
            transcriber.transcribe(AudioInput(path=tmp_path / "absent.wav"))

    def test_missing_weights_name_the_download_script(self, tmp_path: Path) -> None:
        """A deployment missing its weights should fail loudly, with the remedy."""
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"RIFF")
        transcriber = WhisperTranscriber(tmp_path / "no-such-model")
        with pytest.raises(TranscriptionError, match=r"download_models.py"):
            transcriber.transcribe(AudioInput(path=audio))

    def test_availability_follows_the_model_directory(self, tmp_path: Path) -> None:
        assert WhisperTranscriber(tmp_path).is_available()
        assert not WhisperTranscriber(tmp_path / "absent").is_available()

    def test_the_model_version_is_recorded(self, tmp_path: Path) -> None:
        """A transcript that cannot name its model is not reproducible."""
        assert WhisperTranscriber(tmp_path / "indicwhisper").model_version == "indicwhisper"
