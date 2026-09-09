"""The safety critic: a second pass that may only escalate.

The asymmetry is enforced here in code, not in the prompt. The prompt tells the
model it cannot de-escalate; this module makes it so. A model that returns a
less urgent band has its verdict rejected and the band stands.

That difference matters. A prompt instruction is a tendency. This is the last
place the guarantee can be made real before a band is written to a record.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.consult.agents.schemas import CriticVerdictName
from services.consult.clinical.bands import (
    BandDeescalationError,
    CriticVerdict,
    NoChange,
    RaiseTo,
    apply_verdict,
)
from spine.inference.adapter import InferenceProvider, complete_structured
from spine.inference.prompts import Prompt, spec_for
from spine.schemas.primitives import Band
from spine.schemas.record import Record
from spine.schemas.triage import RedFlagOutcome, TriageResult


@dataclass(frozen=True)
class CriticReview:
    """The critic's verdict and what the band became.

    `rejected_reason` is set when the model attempted something the asymmetry
    forbids. It is kept rather than swallowed: a critic repeatedly attempting to
    de-escalate is a prompt regression the eval suite must see.
    """

    final_band: Band
    original_band: Band
    verdict: CriticVerdict
    reason: str
    grounds: tuple[str, ...] = ()
    citing_findings: tuple[str, ...] = ()
    rejected_reason: str | None = None

    @property
    def escalated(self) -> bool:
        return self.final_band.is_more_urgent_than(self.original_band)


def _to_verdict(named: CriticVerdictName) -> CriticVerdict:
    if named.verdict == "no_change" or named.band is None:
        return NoChange(reason=named.reason)
    return RaiseTo(band=named.band, reason=named.reason)


def review(
    named: CriticVerdictName,
    current: Band,
) -> CriticReview:
    """Apply a critic verdict, refusing anything that lowers urgency.

    Pure, and separately testable from the model call. A rejected verdict leaves
    the band untouched and records why, rather than raising: the triage result
    is still valid and the session should not fail because the critic
    misbehaved.
    """
    verdict = _to_verdict(named)
    try:
        final = apply_verdict(current, verdict)
    except BandDeescalationError as error:
        return CriticReview(
            final_band=current,
            original_band=current,
            verdict=NoChange(reason="verdict rejected"),
            reason=named.reason,
            rejected_reason=str(error),
        )
    return CriticReview(
        final_band=final,
        original_band=current,
        verdict=verdict,
        reason=named.reason,
        grounds=named.grounds,
        citing_findings=named.citing_findings,
    )


def build_prompt(record: Record, result: TriageResult, red_flags: RedFlagOutcome) -> str:
    """The user-side prompt: the record and the decision to check.

    Findings are rendered with their spans so the critic reads what the patient
    said rather than a summary of it, and history gaps are listed separately
    because 'not asked' is the distinction the critic most often needs.
    """
    lines: list[str] = ["RECORD", ""]
    demographics = record.demographics
    age = demographics.age_years
    lines.append(f"Age: {age if age is not None else 'not recorded'}")
    lines.append(f"Sex: {demographics.sex.value}")
    lines.append(f"Pregnancy status: {record.consult.pregnancy_status.value}")
    family = record.consult.complaint_family
    lines.append(f"Complaint family: {family.value if family else 'not classified'}")

    lines.extend(["", "Findings, with the patient's own words:"])
    if not record.findings:
        lines.append("  none recorded")
    for finding in record.findings:
        state = "denied" if finding.negated else str(finding.value)
        lines.append(
            f"  {finding.field} = {state} "
            f"[{finding.confidence.value}] \"{finding.provenance.text}\""
        )

    if record.comorbidities:
        lines.extend(["", "Comorbidities: " + ", ".join(c.name for c in record.comorbidities)])
    if record.medications:
        lines.extend(["Medications: " + ", ".join(m.name for m in record.medications)])

    lines.extend(["", "Red flag rules fired:"])
    lines.append("  none" if not red_flags.fired else "  " + ", ".join(red_flags.rule_ids))

    lines.extend(["", "TRIAGE RESULT TO CHECK", ""])
    lines.append(f"Band: {result.band.value}")
    lines.append(f"Specialty: {result.specialty.value}")
    lines.append(f"Rationale: {result.rationale}")
    lines.append(
        "Escalating factors: "
        + (", ".join(result.escalating_factors) if result.escalating_factors else "none named")
    )
    lines.append(f"Uncertainty: {result.uncertainty or 'none stated'}")
    lines.append(
        "History gaps (fields never asked): "
        + (", ".join(result.history_gaps) if result.history_gaps else "none")
    )
    return "\n".join(lines)


def critique(
    provider: InferenceProvider,
    prompt: Prompt,
    model: str,
    *,
    record: Record,
    result: TriageResult,
    red_flags: RedFlagOutcome,
) -> CriticReview:
    """Run the critic over a triage result."""
    spec = spec_for(prompt, model)
    named: CriticVerdictName = complete_structured(
        provider,
        CriticVerdictName,
        prompt=build_prompt(record, result, red_flags),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return review(named, result.band)
