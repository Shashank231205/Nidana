"""The Scribe note agent runtime.

Reads a diarised transcript, produces note statements, and hands them to the
builder that verifies every span against the transcript.

The agent proposes; the builder disposes. Nothing the model writes reaches a
note without its span being found character-for-character in what was recorded.
"""

from __future__ import annotations

from services.scribe.agents.note_builder import BuildResult, build
from spine.inference.adapter import InferenceProvider, ModelSpec, complete_structured
from spine.inference.prompts import Prompt
from spine.schemas.transcript import NoteDraft, Transcript

MAX_TRANSCRIPT_CHARACTERS = 24_000
"""Above this the transcript is not sent whole.

A 7B model on laptop hardware has a bounded context, and silently truncating a
consultation would drop its end — where the plan and the follow-up live. The
agent refuses rather than truncating, and the caller segments.
"""


class TranscriptTooLongError(RuntimeError):
    """Raised when a transcript will not fit in one call."""


def build_prompt(transcript: Transcript) -> str:
    """The user-side prompt: the transcript, diarised and timed.

    Speaker labels are included because attribution is part of the task. In an
    Indian OPD the person answering is often not the patient, and a clinician
    reads 'family reports' differently from 'patient reports'.
    """
    lines = ["Diarised transcript. Spans must be exact substrings of this text.", ""]
    for segment in transcript.segments:
        marker = "  [low confidence]" if segment.is_low_confidence else ""
        lines.append(f"[{segment.speaker.value}] {segment.text}{marker}")
    lines.extend(["", "Write the statements this consultation contained."])
    return "\n".join(lines)


def draft_note(
    provider: InferenceProvider,
    prompt: Prompt,
    transcript: Transcript,
    source_id: str,
) -> BuildResult:
    """Produce note statements from a transcript.

    The model call is constrained to NoteDraft and retried once by the adapter.
    Everything it claims then passes through the builder, which is where the
    span invariant is enforced and where fabrications are dropped.
    """
    text = transcript.text
    if len(text) > MAX_TRANSCRIPT_CHARACTERS:
        raise TranscriptTooLongError(
            f"transcript is {len(text)} characters, above the {MAX_TRANSCRIPT_CHARACTERS} "
            f"that fit in one call. Segment the consultation and draft each part; "
            f"truncating would drop the end, where the plan and follow-up are"
        )
    spec = ModelSpec(
        name=prompt.model_class,
        temperature=prompt.temperature,
        max_output_tokens=prompt.max_output_tokens,
    )
    draft: NoteDraft = complete_structured(
        provider,
        NoteDraft,
        prompt=build_prompt(transcript),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return build(draft, transcript, source_id)
