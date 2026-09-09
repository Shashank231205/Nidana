"""The Rx reading agent runtime.

Reads the OCR text of a prescription, produces claimed lines, and hands them to
the builder that verifies every span and then resolves each brand against the
index.

The agent reads; the index decides. A model that named the molecule itself
would bypass the confidence threshold that decides whether a pharmacist is
asked to confirm, and a confident wrong molecule is the failure this service
exists to prevent.
"""

from __future__ import annotations

from services.rx.agents.line_builder import BuildResult, build
from services.rx.agents.resolver import BrandIndex
from spine.inference.adapter import InferenceProvider, complete_structured
from spine.inference.prompts import Prompt, spec_for
from spine.schemas.medication import PrescriptionDraft

MAX_OCR_CHARACTERS = 8_000
"""Above this the prescription is not sent whole.

A prescription is short; text longer than this is a multi-page document or a
bad OCR pass, and truncating either would drop lines silently.
"""


class PrescriptionTooLongError(RuntimeError):
    """Raised when OCR text will not fit in one call."""


def build_prompt(ocr_text: str) -> str:
    """The user-side prompt: the OCR text, verbatim.

    Sent unmodified. Line breaks are how a prescription separates one drug from
    the next, and normalising them merges two lines into one.
    """
    return (
        "OCR text of a prescription. Spans must be exact substrings of this text.\n\n"
        f"{ocr_text}\n\n"
        "Read the medication lines this prescription contains."
    )


def read(
    provider: InferenceProvider,
    prompt: Prompt,
    model: str,
    ocr_text: str,
    *,
    source_id: str,
    index: BrandIndex,
    page: int = 1,
) -> BuildResult:
    """Read the medication lines from a prescription.

    The model call is constrained to PrescriptionDraft and retried once by the
    adapter. Everything it claims then passes through the builder, where the
    span invariant holds and the brand index does the resolving.
    """
    if len(ocr_text) > MAX_OCR_CHARACTERS:
        raise PrescriptionTooLongError(
            f"OCR text is {len(ocr_text)} characters, above the {MAX_OCR_CHARACTERS} "
            f"that fit in one call. Read it page by page; truncating would drop "
            f"whichever lines fall past the cut"
        )
    spec = spec_for(prompt, model)
    draft: PrescriptionDraft = complete_structured(
        provider,
        PrescriptionDraft,
        prompt=build_prompt(ocr_text),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return build(draft, ocr_text, source_id, index, page)
