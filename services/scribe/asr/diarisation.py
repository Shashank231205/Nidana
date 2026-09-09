"""Working out who was speaking, for a consultation with more than one voice.

Consult has one speaker and needs none of this. Scribe records a clinician and
a patient, often a family member translating or answering for them, and a note
that attributes the patient's symptom to the doctor is worse than a note with
no attribution at all.

That asymmetry runs through the whole module, and it is why `Speaker.UNKNOWN`
is a first-class outcome rather than a failure. A segment left unattributed
makes a clinician read it and decide. A segment attributed wrongly reads as
fact, and in a note that becomes part of the record it stays wrong.

**What this does and does not decide.** Diarisation separates voices: it can
say two people spoke and which turns belong to each. It cannot say which one is
the doctor. That mapping is a separate inference — made here from turn
structure, and deliberately conservative — because a diariser labelling
speakers SPEAKER_00 and SPEAKER_01 has told you nothing about who to believe
about a symptom.

The model is pyannote's speaker-diarization pipeline, MIT-licensed, running on
CPU. CPU rather than GPU is not a limitation but a decision: ADR 0008 records
that a 7B language model and the ASR model already contend for 4GB of VRAM, and
a third model in that contention costs a load on the turn where it happens.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from spine.schemas.transcript import Speaker, Transcript, TranscriptSegment

DEFAULT_PIPELINE: Final[str] = "pyannote/speaker-diarization-3.1"
"""The diarisation pipeline, by its Hugging Face identifier.

MIT-licensed and gated: a deployment accepts the terms once, downloads the
weights, and points NIDANA_DIARISATION_MODEL at the local directory. Nothing
here reaches the network at inference time.
"""

MINIMUM_OVERLAP_RATIO: Final[float] = 0.5
"""How much of a transcript segment a speaker turn must cover to claim it.

The comparison is strictly greater than this, not greater or equal, and the
difference is the case it exists for. ASR splits on pauses and diarisation on
voice changes, so the two do not align, and a sentence divided exactly in half
between two voices is the commonest way that shows up. At exactly 0.5 neither
speaker owns it, and handing it to whichever turn was checked first is a coin
toss recorded as a fact.
"""

MINIMUM_VOICES_TO_INFER_ROLES: Final[int] = 2
"""One voice cannot be split into a doctor and a patient.

A single-speaker recording could be either, and a heuristic that picks one is
guessing about who to believe on a symptom.
"""

MINIMUM_TURNS_TO_INFER_ROLES: Final[int] = 4
"""Below this many turns, roles are not inferred at all.

A three-turn recording does not contain enough structure to tell a doctor from
a patient, and the heuristic below would produce a confident answer from noise.
Everything stays UNKNOWN, which a clinician resolves in seconds when they read
a short note.
"""


@dataclass(frozen=True)
class SpeakerTurn:
    """One stretch of audio attributed to one voice by the diariser.

    `label` is the diariser's own — SPEAKER_00, SPEAKER_01 — and carries no
    meaning about who that person is.
    """

    label: str
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    def overlap_ms(self, start_ms: int, end_ms: int) -> int:
        return max(0, min(self.end_ms, end_ms) - max(self.start_ms, start_ms))


class DiarisationError(RuntimeError):
    """Raised when diarisation cannot run."""


class Diariser(Protocol):
    """What any diarisation backend must do.

    A protocol rather than a base class so a deployment can substitute one
    without importing torch, and so the role inference below can be tested
    without a model.
    """

    def turns(self, audio_path: Path) -> tuple[SpeakerTurn, ...]:
        """Every stretch of speech, with the diariser's own speaker labels."""


def assign_speakers(
    segments: tuple[TranscriptSegment, ...],
    turns: tuple[SpeakerTurn, ...],
    roles: dict[str, Speaker],
) -> tuple[TranscriptSegment, ...]:
    """Attach a speaker to each transcript segment.

    A segment goes to the turn that covers most of it, and only if that turn
    covers at least MINIMUM_OVERLAP_RATIO of its length. Otherwise UNKNOWN.

    The segments' text and timing are untouched. Diarisation decides who spoke;
    it never edits what was said.
    """
    if not turns:
        return tuple(
            segment.model_copy(update={"speaker": Speaker.UNKNOWN}) for segment in segments
        )

    assigned: list[TranscriptSegment] = []
    for segment in segments:
        best_label, best_overlap = None, 0
        for turn in turns:
            overlap = turn.overlap_ms(segment.audio_start_ms, segment.audio_end_ms)
            if overlap > best_overlap:
                best_label, best_overlap = turn.label, overlap

        covered = best_overlap / segment.duration_ms if segment.duration_ms else 0.0
        speaker = (
            roles.get(best_label or "", Speaker.UNKNOWN)
            if covered > MINIMUM_OVERLAP_RATIO
            else Speaker.UNKNOWN
        )
        assigned.append(segment.model_copy(update={"speaker": speaker}))
    return tuple(assigned)


def infer_roles(
    segments: tuple[TranscriptSegment, ...], turns: tuple[SpeakerTurn, ...]
) -> dict[str, Speaker]:
    """Guess which diariser label is the clinician, conservatively.

    The signal used is that a consultation is a question-and-answer structure
    and the clinician asks most of the questions. It is a weak signal, and it
    is used only where it is unambiguous:

    - fewer than MINIMUM_TURNS_TO_INFER_ROLES turns: nothing is inferred
    - one voice: nothing is inferred, because a single speaker could be either
    - three or more voices: the two who speak most become clinician and
      patient, everyone else is FAMILY, since a third voice in an Indian OPD is
      usually a relative
    - no clear question-asker: nothing is inferred

    Everything not inferred is UNKNOWN, and UNKNOWN is a usable outcome. A
    clinician reading the note sees an unattributed line and knows to check;
    they cannot see a line attributed to the wrong person.
    """
    labels = [turn.label for turn in turns]
    distinct = sorted(set(labels))
    if (
        len(turns) < MINIMUM_TURNS_TO_INFER_ROLES
        or len(distinct) < MINIMUM_VOICES_TO_INFER_ROLES
    ):
        return {}

    questions: Counter[str] = Counter()
    speech_ms: Counter[str] = Counter()
    for turn in turns:
        speech_ms[turn.label] += turn.duration_ms
    for segment, label in zip(segments, _labels_for(segments, turns), strict=False):
        if label and segment.text.strip().endswith("?"):
            questions[label] += 1

    if not questions:
        return {}
    asker, asked = questions.most_common(1)[0]
    rival = max((count for label, count in questions.items() if label != asker), default=0)
    if asked <= rival:
        # Both voices ask about equally often. That happens, and it means this
        # heuristic cannot separate them.
        return {}

    others = [label for label in distinct if label != asker]
    patient = max(others, key=lambda label: speech_ms[label])
    roles: dict[str, Speaker] = {asker: Speaker.CLINICIAN, patient: Speaker.PATIENT}
    for label in others:
        if label != patient:
            roles[label] = Speaker.FAMILY
    return roles


def _labels_for(
    segments: tuple[TranscriptSegment, ...], turns: tuple[SpeakerTurn, ...]
) -> list[str | None]:
    """The best-overlapping turn label per segment, without applying the floor."""
    labels: list[str | None] = []
    for segment in segments:
        best_label, best_overlap = None, 0
        for turn in turns:
            overlap = turn.overlap_ms(segment.audio_start_ms, segment.audio_end_ms)
            if overlap > best_overlap:
                best_label, best_overlap = turn.label, overlap
        labels.append(best_label)
    return labels


def diarise(
    transcript: Transcript, audio_path: Path, diariser: Diariser
) -> Transcript:
    """Attribute a transcript's segments to speakers.

    Returns a transcript whose text is identical and whose speakers are filled
    in where they could be established. A failure to diarise leaves every
    segment UNKNOWN rather than raising: a note with unattributed lines is
    usable and a note that does not exist is not.
    """
    turns = diariser.turns(audio_path)
    roles = infer_roles(transcript.segments, turns)
    return Transcript(
        segments=assign_speakers(transcript.segments, turns, roles)
    )


class PyannoteDiariser:
    """pyannote.audio, running locally on CPU.

    Loaded lazily and not held resident, for the same reason the ASR model is
    not: three models competing for one 4GB card is the constraint on the
    target hardware, and a consultation is not so latency-sensitive that a
    model load matters against the length of the recording.
    """

    def __init__(
        self,
        model_path: Path | str = DEFAULT_PIPELINE,
        *,
        device: str = "cpu",
    ) -> None:
        self._model_path = model_path
        self._device = device
        self._pipeline: object | None = None

    @property
    def model_version(self) -> str:
        return str(self._model_path)

    def is_available(self) -> bool:
        """Whether pyannote and the weights are both present."""
        try:
            import pyannote.audio  # noqa: F401, PLC0415
        except ImportError:
            return False
        return Path(self._model_path).exists() or "/" in str(self._model_path)

    def _load(self) -> object:
        if self._pipeline is not None:
            return self._pipeline
        try:
            import torch  # noqa: PLC0415
            from pyannote.audio import Pipeline  # noqa: PLC0415
        except ImportError as error:
            raise DiarisationError(
                "pyannote.audio is not installed; install it with "
                "'pip install pyannote.audio', or run Scribe without diarisation "
                "and every segment will be recorded as an unknown speaker"
            ) from error

        pipeline = Pipeline.from_pretrained(str(self._model_path))
        if pipeline is None:
            raise DiarisationError(
                f"could not load the diarisation pipeline from {self._model_path}. "
                f"The weights are gated: accept the terms once on Hugging Face, "
                f"download them, and point NIDANA_DIARISATION_MODEL at the local "
                f"directory"
            )
        pipeline.to(torch.device(self._device))
        self._pipeline = pipeline
        return pipeline

    def turns(self, audio_path: Path) -> tuple[SpeakerTurn, ...]:
        """Every stretch of speech, with the diariser's own labels."""
        if not audio_path.is_file():
            raise DiarisationError(f"no audio at {audio_path}")
        pipeline = self._load()
        annotation = pipeline(str(audio_path))  # type: ignore[operator]
        return tuple(
            SpeakerTurn(
                label=str(label),
                start_ms=int(segment.start * 1000),
                end_ms=int(segment.end * 1000),
            )
            for segment, _track, label in annotation.itertracks(yield_label=True)
        )
