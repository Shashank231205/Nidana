"""The triage agent: band and specialty from a completed record.

The model proposes. Deterministic code disposes: a fired escalating rule sets a
floor the model cannot go below, routing resolves the specialty, and the return
criteria pass through the output filter before a patient sees them.
"""

from __future__ import annotations

from services.consult.agents.schemas import TriageOutput
from services.consult.clinical import routing
from services.consult.clinical.bands import escalate_only
from services.consult.clinical.output_filter import assert_clean
from spine.inference.adapter import InferenceProvider, complete_structured
from spine.inference.prompts import Prompt, spec_for
from spine.schemas.primitives import Band
from spine.schemas.record import Record, Sufficiency
from spine.schemas.triage import RedFlagOutcome, TriageResult

ESCALATION_FLOOR = Band.U2
"""The least urgent band an escalating red flag permits.

A rule that fires with ESCALATE_BAND has found something the triage agent must
not band below. U2 is the floor because an escalating rule means hours matter;
a rule needing more than that terminates the session instead.
"""


def build_prompt(
    record: Record,
    sufficiency: Sufficiency | None,
    red_flags: RedFlagOutcome,
) -> str:
    """The user-side prompt: the record, its gaps, and what fired."""
    lines: list[str] = []
    demographics = record.demographics
    age = demographics.age_years
    lines.append(f"Age: {age if age is not None else 'not recorded'}")
    lines.append(f"Sex: {demographics.sex.value}")
    lines.append(f"Pregnancy status: {record.consult.pregnancy_status.value}")
    family = record.consult.complaint_family
    lines.append(f"Complaint family: {family.value if family else 'not classified'}")
    lines.append(f"Describing someone else: {record.consult.is_proxy}")

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
        lines.append("Medications: " + ", ".join(m.name for m in record.medications))
    if record.allergies:
        lines.append("Allergies: " + ", ".join(a.substance for a in record.allergies))

    lines.extend(["", "Never asked (history gaps):"])
    gaps = sufficiency.missing if sufficiency else ()
    lines.append("  " + (", ".join(gaps) if gaps else "none"))
    if sufficiency and sufficiency.low_confidence:
        lines.append("Answered unclearly: " + ", ".join(sufficiency.low_confidence))

    lines.extend(["", "Red flag rules fired:"])
    if red_flags.fired:
        lines.append("  " + ", ".join(red_flags.rule_ids))
        lines.append("  matched on: " + ", ".join(red_flags.matched_atoms))
        if red_flags.escalating_rule_ids:
            lines.append(
                f"  escalating: {', '.join(red_flags.escalating_rule_ids)} — the band "
                f"must be at least {ESCALATION_FLOOR.value}"
            )
    else:
        lines.append("  none")

    lines.extend(["", "Assign the band and specialty."])
    return "\n".join(lines)


def apply_floors(proposed: Band, red_flags: RedFlagOutcome) -> Band:
    """Raise a proposed band to whatever the fired rules require.

    Deterministic. The model's band is a proposal; a fired escalating rule is
    not, and escalate_only guarantees this can never lower anything.
    """
    if red_flags.terminates_session:
        return escalate_only(proposed, Band.U1)
    if red_flags.escalating_rule_ids:
        return escalate_only(proposed, ESCALATION_FLOOR)
    return proposed


def to_result(
    output: TriageOutput,
    record: Record,
    red_flags: RedFlagOutcome,
    prompt_version: str,
) -> TriageResult:
    """Turn agent output into a validated result.

    Three things happen that the model does not control: the band is floored by
    what fired, the specialty is resolved deterministically, and every return
    criterion passes the output filter. TriageResult then rejects a non-U1
    outcome carrying fewer than three of them.
    """
    band = apply_floors(output.band, red_flags)
    specialty = routing.resolve_specialty(record, red_flags, band)
    for index, criterion in enumerate(output.return_criteria):
        assert_clean(criterion, f"triage_agent v{prompt_version} return_criteria[{index}]")
    return TriageResult(
        band=band,
        specialty=specialty,
        rationale=output.rationale,
        escalating_factors=output.escalating_factors,
        uncertainty=output.uncertainty,
        required_capabilities=routing.required_capabilities(specialty, red_flags),
        return_criteria=output.return_criteria,
        differential=output.differential,
        history_gaps=output.history_gaps,
        red_flags=red_flags,
    )


def assess(
    provider: InferenceProvider,
    prompt: Prompt,
    model: str,
    *,
    record: Record,
    sufficiency: Sufficiency | None,
    red_flags: RedFlagOutcome,
) -> TriageResult:
    """Produce a triage result for a completed record."""
    spec = spec_for(prompt, model)
    output: TriageOutput = complete_structured(
        provider,
        TriageOutput,
        prompt=build_prompt(record, sufficiency, red_flags),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return to_result(output, record, red_flags, prompt.version)
