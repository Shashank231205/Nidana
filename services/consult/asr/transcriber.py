"""Local transcription.

ASR is local in every mode. There is no hosted transcription path and no
configuration flag that creates one: audio of a patient describing their
symptoms is the most identifying thing this system handles.

The model is IndicWhisper by default, because the hard half of this problem is
code-switched Hindi, Kannada, Marathi, Bengali and Tamil rather than English.
Drug names and anatomical terms are the failure surface and need a targeted
fine-tune set, which does not exist yet.

Nothing here decides anything clinical. It turns audio into text with
timestamps, and everything downstream treats that text as what the patient
said.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from spine.schemas.transcript import (
    Speaker,
    Transcript,
    TranscriptSegment,
)

DEFAULT_MODEL_PATH: Final[Path] = Path("./models/asr/indicwhisper")

SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset(
    {"en", "hi", "kn", "mr", "bn", "ta", "te", "gu", "ml", "pa"}
)
"""Languages the ASR layer will accept a hint for.

A hint is a hint. Code-switched speech is the normal case here, so a segment
tagged `hi` routinely contains English clinical vocabulary, and nothing
downstream should treat the tag as a guarantee.
"""

# LOW_CONFIDENCE_FLOOR lives on the transcript shape rather than here: both
# Consult and Scribe consume transcripts, and two floors would drift apart.


class TranscriptionError(RuntimeError):
    """Raised when audio cannot be transcribed."""


@dataclass(frozen=True)
class AudioInput:
    """One recording to transcribe."""

    path: Path
    language_hint: str | None = None
    expect_multiple_speakers: bool = False

    def __post_init__(self) -> None:
        if self.language_hint and self.language_hint not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"language hint {self.language_hint!r} is not supported; use one of "
                f"{', '.join(sorted(SUPPORTED_LANGUAGES))}, or omit the hint and let the "
                f"model detect it"
            )


@dataclass(frozen=True)
class TranscriptionResult:
    """What the transcriber produced.

    `low_confidence_segments` is surfaced rather than buried, because the
    correct response to an unclear segment is to ask again, and that decision
    belongs to the intake agent.
    """

    transcript: Transcript
    model_version: str
    detected_language: str | None = None

    @property
    def text(self) -> str:
        return self.transcript.text

    @property
    def low_confidence_segments(self) -> tuple[TranscriptSegment, ...]:
        return tuple(
            segment for segment in self.transcript.segments if segment.is_low_confidence
        )

    @property
    def needs_confirmation(self) -> bool:
        return bool(self.low_confidence_segments)


class Transcriber(ABC):
    """What every ASR backend must do.

    Narrow by design. A transcriber produces text and timestamps; it does not
    decide what the text means, whether to re-ask, or who was speaking beyond
    what diarisation tells it.
    """

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Recorded on every audit entry, so a transcript is reproducible."""

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the model is present and loadable.

        Called at startup, so a deployment missing its weights fails there
        rather than at the first patient utterance.
        """

    @abstractmethod
    def transcribe(self, audio: AudioInput) -> TranscriptionResult:
        """Turn audio into a diarised transcript."""


class WhisperTranscriber(Transcriber):
    """Local Whisper-family transcription.

    The model is loaded lazily. A 7B language model and an ASR model competing
    for 4GB of VRAM is the constraint on the target hardware (ADR 0008), so the
    ASR weights are not held resident between consultations.

    Diarisation is not attempted here. Consult has one speaker and needs none;
    Scribe has several and needs a diariser, which is a separate model and a
    separate decision.
    """

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        *,
        default_speaker: Speaker = Speaker.PATIENT,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self._model_path = model_path
        self._default_speaker = default_speaker
        self._device = device
        self._compute_type = compute_type
        self._model: object | None = None

    @property
    def model_version(self) -> str:
        return self._model_path.name

    def is_available(self) -> bool:
        return self._model_path.is_dir()

    def _load(self) -> object:
        """Load the model, once per process.

        faster-whisper rather than transformers, decided by measurement on
        target-class hardware: CPU int8, 6 seconds of audio decoded in 2.0s
        with `base` and 1.1s with `tiny`, against a ~75s one-off load. Both are
        comfortably inside the gap between a patient finishing an answer and
        reading the next question, and neither needs the GPU that ADR 0008
        reserves for the language model.
        """
        if self._model is None:
            try:
                from faster_whisper import WhisperModel  # noqa: PLC0415
            except ImportError as error:
                raise TranscriptionError(
                    "faster-whisper is not installed; install the asr extra with "
                    "'pip install -e .[asr]'"
                ) from error
            self._model = WhisperModel(
                str(self._model_path), device=self._device, compute_type=self._compute_type
            )
        return self._model

    def transcribe(self, audio: AudioInput) -> TranscriptionResult:
        """Transcribe one recording.

        `word_timestamps` is on because the transcript is segmented on pauses
        rather than punctuation, and punctuation is unreliable in code-switched
        speech where a pause is not.

        The language hint is passed through when given and omitted otherwise.
        Forcing a language on code-switched speech is worse than detecting it:
        a Hindi hint on "mujhe do din se chest pain hai" can push the model to
        transliterate the English clinical terms it should be keeping.
        """
        if not audio.path.is_file():
            raise TranscriptionError(
                f"no audio at {audio.path}; the file was not written or the path is wrong"
            )
        if not self.is_available():
            raise TranscriptionError(
                f"no ASR model at {self._model_path}. Run "
                f"'python scripts/download_models.py --asr indicwhisper', then set "
                f"NIDANA_ASR_MODEL_PATH to where it landed"
            )

        model = self._load()
        try:
            raw_segments, info = model.transcribe(  # type: ignore[attr-defined]
                str(audio.path),
                language=audio.language_hint,
                word_timestamps=True,
                vad_filter=True,
            )
            words = _words_from(raw_segments)
        except TranscriptionError:
            raise
        except Exception as error:
            raise TranscriptionError(
                f"transcription failed for {audio.path}: {error}. The audio may be "
                f"empty, truncated, or in a format the decoder cannot read"
            ) from error

        return TranscriptionResult(
            transcript=Transcript(segments=segments_from_words(words, self._default_speaker)),
            model_version=self.model_version,
            detected_language=getattr(info, "language", None),
        )


def segments_from_words(
    words: tuple[tuple[str, int, int, float], ...],
    speaker: Speaker = Speaker.PATIENT,
    *,
    max_gap_ms: int = 700,
) -> tuple[TranscriptSegment, ...]:
    """Group timed words into segments, splitting on silence.

    Whisper returns word-level timings; the transcript needs segments. Splitting
    on a pause rather than on punctuation matters for code-switched speech,
    where punctuation is unreliable and a pause is not.

    Pure, so it is testable without a model.
    """
    if not words:
        return ()
    segments: list[TranscriptSegment] = []
    bucket: list[tuple[str, int, int, float]] = [words[0]]
    for word in words[1:]:
        previous_end = bucket[-1][2]
        if word[1] - previous_end > max_gap_ms:
            segments.append(_segment(bucket, speaker))
            bucket = [word]
        else:
            bucket.append(word)
    segments.append(_segment(bucket, speaker))
    return tuple(segments)


def _segment(
    words: list[tuple[str, int, int, float]], speaker: Speaker
) -> TranscriptSegment:
    """One segment from a run of words.

    Confidence is the minimum across the run rather than the mean: a segment
    containing one badly-heard drug name is not a confident segment, and
    averaging would hide exactly the word that matters.
    """
    return TranscriptSegment(
        text=" ".join(word for word, _, _, _ in words),
        speaker=speaker,
        audio_start_ms=words[0][1],
        audio_end_ms=words[-1][2],
        confidence=min(confidence for _, _, _, confidence in words),
    )


def _words_from(raw_segments: object) -> tuple[tuple[str, int, int, float], ...]:
    """Flatten faster-whisper output into the timed words the segmenter takes.

    Timestamps arrive in seconds and the transcript works in milliseconds, so
    they are converted here rather than in the segmenter, which stays free of
    any one backend's conventions.

    A word carrying no probability is treated as certain rather than dropped.
    Dropping it would silently remove a word from the record; treating it as
    uncertain would flag a segment for re-asking on a backend quirk.
    """
    words: list[tuple[str, int, int, float]] = []
    for segment in raw_segments:  # type: ignore[attr-defined]
        for word in getattr(segment, "words", None) or ():
            text = (word.word or "").strip()
            if not text:
                continue
            words.append(
                (
                    text,
                    int(word.start * 1000),
                    int(word.end * 1000),
                    float(getattr(word, "probability", 1.0)),
                )
            )
    return tuple(words)
