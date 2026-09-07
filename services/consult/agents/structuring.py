"""The structuring agent: utterances become typed findings.

This is where model output crosses into the record, and it is the narrowest
gate in the system. A claim becomes a Finding only if three things hold: the
field exists in the registry, the value is permitted for that field, and the
span is an exact substring of the utterance.

A claim failing any of them is dropped, with the reason recorded. Dropping is
correct rather than harsh: a finding that cannot be traced to the patient's own
words is a fabrication, and the M2 gate requires the fabrication rate to be zero
structurally rather than measured.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.consult.agents.schemas import ExtractedFinding, StructuringOutput
from spine.inference.adapter import InferenceProvider, ModelSpec, complete_structured
from spine.inference.prompts import Prompt
from spine.schemas.finding import Finding
from spine.schemas.primitives import Quantity
from spine.schemas.provenance import SpanVerificationError, locate_utterance
from spine.schemas.registry import FamilyRegistry, FieldType


@dataclass(frozen=True)
class DroppedClaim:
    """A claim that did not become a finding, and why.

    Kept rather than discarded because the drop rate is an eval metric: a model
    dropping many claims is a prompt problem, and one dropping none may be a
    validator problem.
    """

    field: str
    reason: str
    span: str


@dataclass(frozen=True)
class StructuringResult:
    findings: tuple[Finding, ...]
    dropped: tuple[DroppedClaim, ...]

    @property
    def drop_rate(self) -> float:
        total = len(self.findings) + len(self.dropped)
        return 0.0 if total == 0 else len(self.dropped) / total


def _coerce(value: str | float | int | bool, spec_type: FieldType, unit: str | None) -> (
    str | float | int | bool | Quantity
):
    """Shape a claimed value to what the registry declares.

    A numeric field with a unit becomes a Quantity, so that downstream code
    cannot compare six hours against six days by accident.
    """
    if spec_type is FieldType.NUMBER and unit and isinstance(value, (int, float)):
        return Quantity(value=float(value), unit=unit)
    return value


def _validate_claim(
    claim: ExtractedFinding,
    registry: FamilyRegistry,
    utterance: str,
    source_id: str,
    turn_index: int,
) -> Finding | DroppedClaim:
    spec = registry.spec_for(claim.field)
    if spec is None:
        return DroppedClaim(
            field=claim.field,
            reason=(
                f"no field {claim.field!r} in the {registry.family.value} registry; a "
                f"finding with nowhere to go is not recorded"
            ),
            span=claim.source_span,
        )
    if claim.negated:
        value: str | float | int | bool | Quantity = False
    else:
        if not spec.permits(claim.value):
            permitted = ", ".join(spec.values) if spec.values else spec.type.value
            return DroppedClaim(
                field=claim.field,
                reason=(
                    f"value {claim.value!r} is not permitted for {claim.field}; "
                    f"expected {permitted}"
                ),
                span=claim.source_span,
            )
        value = _coerce(claim.value, spec.type, spec.unit)
    try:
        provenance = locate_utterance(
            source_id=source_id,
            source_text=utterance,
            quote=claim.source_span,
            turn_index=turn_index,
        )
    except SpanVerificationError as error:
        return DroppedClaim(field=claim.field, reason=str(error), span=claim.source_span)
    return Finding(
        field=claim.field,
        value=value,
        provenance=provenance,
        confidence=claim.confidence,
        negated=claim.negated,
    )


def validate_claims(
    claims: tuple[ExtractedFinding, ...],
    registry: FamilyRegistry,
    utterance: str,
    source_id: str,
    turn_index: int,
) -> StructuringResult:
    """Turn model claims into findings, dropping the ones that do not verify.

    Pure, and separately testable from the model call. Golden transcripts run
    against this function with recorded model output rather than a live model.
    """
    findings: list[Finding] = []
    dropped: list[DroppedClaim] = []
    for claim in claims:
        outcome = _validate_claim(claim, registry, utterance, source_id, turn_index)
        if isinstance(outcome, Finding):
            findings.append(outcome)
        else:
            dropped.append(outcome)
    return StructuringResult(findings=tuple(findings), dropped=tuple(dropped))


def build_prompt(utterance: str, registry: FamilyRegistry, turn_index: int) -> str:
    """The user-side prompt for one utterance.

    The registry is rendered into the prompt so the model sees the exact field
    names and permitted values it may use. Sending the vocabulary with the
    request is what makes a schema-invalid claim rare rather than routine.
    """
    lines = [f"Turn index: {turn_index}", f"Complaint family: {registry.family.value}", ""]
    lines.append("Fields you may emit, with their permitted values:")
    for spec in (*registry.required, *registry.optional):
        marker = "required" if spec in registry.required else "optional"
        detail = f"type {spec.type.value}"
        if spec.values:
            detail = f"one of: {', '.join(spec.values)}"
        elif spec.unit:
            detail = f"number in {spec.unit}"
        lines.append(f"  {spec.field} ({marker}) — {detail}")
    lines.extend(
        [
            "",
            "Patient utterance, verbatim. Spans must be exact substrings of this text:",
            utterance,
        ]
    )
    return "\n".join(lines)


def structure(
    provider: InferenceProvider,
    prompt: Prompt,
    *,
    utterance: str,
    registry: FamilyRegistry,
    source_id: str,
    turn_index: int,
) -> StructuringResult:
    """Extract findings from one utterance.

    The model call is constrained to StructuringOutput and retried once by the
    adapter. Everything it claims then passes through validate_claims, which is
    where the span invariant is enforced.
    """
    spec = ModelSpec(
        name=prompt.model_class,
        temperature=prompt.temperature,
        max_output_tokens=prompt.max_output_tokens,
    )
    output: StructuringOutput = complete_structured(
        provider,
        StructuringOutput,
        prompt=build_prompt(utterance, registry, turn_index),
        system=prompt.body,
        spec=spec,
        prompt_version=prompt.version,
    )
    return validate_claims(output.findings, registry, utterance, source_id, turn_index)
