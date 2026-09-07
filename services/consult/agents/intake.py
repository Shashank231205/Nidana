"""The intake agent: one question per turn.

It elicits. It does not reason about diagnosis, assess urgency, or reassure.
Giving it both jobs is how chatbots leak premature conclusions to frightened
people.

The red flag engine runs before this agent speaks. If it fired a terminating
rule, no question is generated at all.
"""

from __future__ import annotations

from services.consult.agents.schemas import IntakeOutput
from services.consult.clinical.output_filter import assert_clean
from spine.inference.adapter import InferenceProvider, ModelSpec, complete_structured
from spine.inference.prompts import Prompt
from spine.schemas.record import Record, Sufficiency
from spine.schemas.registry import FamilyRegistry


def build_prompt(
    record: Record,
    registry: FamilyRegistry | None,
    sufficiency: Sufficiency | None,
    transcript: tuple[tuple[str, str], ...],
) -> str:
    """The user-side prompt for one turn.

    Carries what was already asked and what is still missing, so the agent picks
    the next node rather than free-associating. The missing list is the actual
    mechanism behind the feeling of talking to a doctor.
    """
    lines: list[str] = []
    demographics = record.demographics
    age = demographics.age_years
    lines.append(f"Age: {age if age is not None else 'not yet asked'}")
    lines.append(f"Sex: {demographics.sex.value}")
    family = record.consult.complaint_family
    lines.append(f"Complaint family: {family.value if family else 'not yet identified'}")

    lines.extend(["", "Conversation so far:"])
    if not transcript:
        lines.append("  (none — this is the opening turn)")
    for agent_said, patient_said in transcript:
        lines.append(f"  You: {agent_said}")
        lines.append(f"  Patient: {patient_said}")

    lines.extend(["", "Recorded so far:"])
    if not record.findings:
        lines.append("  nothing yet")
    for finding in record.findings:
        state = "denied" if finding.negated else str(finding.value)
        lines.append(f"  {finding.field} = {state}")

    if sufficiency is not None:
        lines.extend(["", "Still missing, required for this complaint family:"])
        lines.append("  " + (", ".join(sufficiency.missing) if sufficiency.missing else "nothing"))
        if sufficiency.low_confidence:
            lines.append("Answered but unclear, re-ask: " + ", ".join(sufficiency.low_confidence))
    elif registry is not None:
        lines.extend(["", "Required fields: " + ", ".join(registry.required_field_names)])

    lines.extend(["", "Ask the single next question."])
    return "\n".join(lines)


def next_question(
    provider: InferenceProvider,
    prompt: Prompt,
    *,
    record: Record,
    registry: FamilyRegistry | None,
    sufficiency: Sufficiency | None,
    transcript: tuple[tuple[str, str], ...] = (),
) -> IntakeOutput:
    """Generate the next question.

    The utterance passes through the output filter before it is returned. The
    intake agent is patient-facing, so a condition name in its question is a
    leak, and the filter refuses rather than redacts.
    """
    spec = ModelSpec(
        name=prompt.model_class,
        temperature=prompt.temperature,
        max_output_tokens=prompt.max_output_tokens,
    )
    output: IntakeOutput = complete_structured(
        provider,
        IntakeOutput,
        prompt=build_prompt(record, registry, sufficiency, transcript),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    assert_clean(output.utterance, f"intake_agent v{prompt.version}")
    return output
