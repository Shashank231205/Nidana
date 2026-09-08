"""The Labs extraction agent runtime.

Reads the text of a lab report, produces claimed results, and hands them to the
builder that verifies every span against the report.

The agent proposes; the builder disposes. Nothing the model reads reaches a
record without its span being found character-for-character in the report, and
nothing that does not parse as a number reaches it at all.
"""

from __future__ import annotations

from services.labs.agents.result_builder import BuildResult, build
from spine.inference.adapter import InferenceProvider, ModelSpec, complete_structured
from spine.inference.prompts import Prompt
from spine.schemas.lab import ReportDraft

MAX_REPORT_CHARACTERS = 16_000
"""Above this the report is not sent whole.

A 7B model on laptop hardware has a bounded context, and truncating a report
would drop its end, where the analytes printed last happen to sit. Which
analytes those are is an accident of the lab's template, so the agent refuses
rather than silently losing a potassium.
"""


class ReportTooLongError(RuntimeError):
    """Raised when a report will not fit in one call."""


def build_prompt(report_text: str) -> str:
    """The user-side prompt: the report, verbatim.

    Sent unmodified, including its whitespace. Column alignment is how a lab
    report separates a value from its reference range, and normalising it would
    remove the only structure the text has.
    """
    return (
        "Lab report text. Spans must be exact substrings of this text.\n\n"
        f"{report_text}\n\n"
        "Read the results this report contains."
    )


def extract(
    provider: InferenceProvider,
    prompt: Prompt,
    report_text: str,
    source_id: str,
) -> BuildResult:
    """Read the results from a report.

    The model call is constrained to ReportDraft and retried once by the
    adapter. Everything it claims then passes through the builder, which is
    where the span invariant is enforced.
    """
    if len(report_text) > MAX_REPORT_CHARACTERS:
        raise ReportTooLongError(
            f"report is {len(report_text)} characters, above the "
            f"{MAX_REPORT_CHARACTERS} that fit in one call. Split it by page and "
            f"extract each; truncating would drop whichever analytes the lab "
            f"happens to print last"
        )
    spec = ModelSpec(
        name=prompt.model_class,
        temperature=prompt.temperature,
        max_output_tokens=prompt.max_output_tokens,
    )
    draft: ReportDraft = complete_structured(
        provider,
        ReportDraft,
        prompt=build_prompt(report_text),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return build(draft, report_text, source_id)
