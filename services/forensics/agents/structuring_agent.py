"""The Forensics structuring agent runtime.

Reads an examiner's dictation, produces claimed injuries, and hands them to the
builder that verifies every span against what was dictated.

The agent proposes; the builder disposes. Provenance for an injury is the
examiner's own entry, attached by the builder from the dictation being
structured, so the model can shape a record but never author one.
"""

from __future__ import annotations

from services.forensics.agents.injury_builder import BuildResult, build
from spine.inference.adapter import InferenceProvider, ModelSpec, complete_structured
from spine.inference.prompts import Prompt
from spine.schemas.forensic import ExaminationDraft

MAX_DICTATION_CHARACTERS = 12_000
"""Above this the dictation is not sent whole.

Truncating a medico-legal dictation would drop injuries described last, and
which those are is an accident of the order the examiner worked in. The agent
refuses rather than silently losing one.
"""


class DictationTooLongError(RuntimeError):
    """Raised when a dictation will not fit in one call."""


def build_prompt(dictation: str) -> str:
    """The user-side prompt: the dictation, verbatim.

    Sent unmodified. The examiner's own words are the record, and normalising
    them would change what the spans have to match.
    """
    return (
        "Examiner's dictation. Spans must be exact substrings of this text.\n\n"
        f"{dictation}\n\n"
        "Structure the injuries this examination described."
    )


def structure(
    provider: InferenceProvider,
    prompt: Prompt,
    dictation: str,
    source_id: str,
    examiner_id: str,
) -> BuildResult:
    """Structure the injuries in a dictation.

    The model call is constrained to ExaminationDraft and retried once by the
    adapter. Everything it claims then passes through the builder, which is
    where the span invariant and the measurement rules are enforced.
    """
    if len(dictation) > MAX_DICTATION_CHARACTERS:
        raise DictationTooLongError(
            f"dictation is {len(dictation)} characters, above the "
            f"{MAX_DICTATION_CHARACTERS} that fit in one call. Structure it in "
            f"parts; truncating would drop whichever injuries were described last"
        )
    spec = ModelSpec(
        name=prompt.model_class,
        temperature=prompt.temperature,
        max_output_tokens=prompt.max_output_tokens,
    )
    draft: ExaminationDraft = complete_structured(
        provider,
        ExaminationDraft,
        prompt=build_prompt(dictation),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return build(draft, dictation, source_id, examiner_id)
