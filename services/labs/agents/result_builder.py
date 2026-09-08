"""Turning an extracted report draft into results, dropping what is not supported.

The same gate Consult applies to findings and Scribe to statements, applied to
lab results. A claimed result becomes a LabResult only if its span is an exact
substring of the report text and its value parses as a number.

Two failures matter more here than elsewhere.

A misread value is worse than a missing one. "5.4" read as "54" is a tenfold
error that reads as plausible, so a value that does not parse cleanly is
dropped rather than coerced.

A missing unit cannot be inferred. Potassium in mmol/L and potassium in mg/dL
have different critical thresholds, and guessing which the lab used would make
the critical value check silently wrong.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from spine.schemas.lab import DraftResult, LabResult, ReferenceRange, ReportDraft
from spine.schemas.provenance import SpanVerificationError, locate_document

NUMERIC = re.compile(r"^-?\d+(?:\.\d+)?$")
"""What a value must look like to be read as a number.

Deliberately strict. A report prints "<0.01", "not detected", "5.4 (H)" and
"TRACE", and only the last form of those is a number. The others are real
results that this parser does not handle, so they are dropped and named rather
than approximated.
"""


@dataclass(frozen=True)
class DroppedResult:
    """A claimed result that did not become a result, and why."""

    analyte: str
    value: str
    reason: str


@dataclass(frozen=True)
class BuildResult:
    results: tuple[LabResult, ...]
    dropped: tuple[DroppedResult, ...]

    @property
    def fabrication_count(self) -> int:
        """Claims the report did not support.

        Non-zero means the model tried; reaching a record would mean the gate
        failed.
        """
        return len(self.dropped)


def _reference_range(claim: DraftResult) -> ReferenceRange | None:
    """The printed reference range, where both bounds parse.

    A half-parsed range is dropped entirely: a range with one bound silently
    missing would report values on that side as within range.
    """
    if claim.reference_low is None and claim.reference_high is None:
        return None
    low = claim.reference_low
    high = claim.reference_high
    if low is not None and not NUMERIC.match(low.strip()):
        return None
    if high is not None and not NUMERIC.match(high.strip()):
        return None
    return ReferenceRange(
        low=float(low) if low is not None else None,
        high=float(high) if high is not None else None,
        unit=claim.unit,
    )


def _locate(
    claim: DraftResult, report_text: str, source_id: str
) -> LabResult | DroppedResult:
    value = claim.value.strip()
    if not NUMERIC.match(value):
        return DroppedResult(
            analyte=claim.analyte,
            value=claim.value,
            reason=(
                f"{claim.analyte} reads {claim.value!r}, which is not a plain number. "
                f"Qualified results such as '<0.01' or 'not detected' are not parsed "
                f"here; record them by hand rather than approximating a value"
            ),
        )
    try:
        span = locate_document(
            source_id=source_id,
            source_text=report_text,
            quote=claim.source_span,
            page=claim.page,
        )
    except SpanVerificationError as error:
        return DroppedResult(
            analyte=claim.analyte, value=claim.value, reason=str(error)
        )
    return LabResult(
        analyte=claim.analyte.strip().lower(),
        value=float(value),
        unit=claim.unit.strip(),
        reference_range=_reference_range(claim),
        provenance=span,
    )


def build(draft: ReportDraft, report_text: str, source_id: str) -> BuildResult:
    """Turn claimed results into results, dropping the unsupported.

    Pure, and separately testable from the model call, so golden reports run
    against recorded output rather than a live model.
    """
    results: list[LabResult] = []
    dropped: list[DroppedResult] = []
    for claim in draft.results:
        located = _locate(claim, report_text, source_id)
        if isinstance(located, DroppedResult):
            dropped.append(located)
            continue
        results.append(located)
    return BuildResult(results=tuple(results), dropped=tuple(dropped))
