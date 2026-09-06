"""The red flag engine, as Consult uses it.

Runs after every patient turn against the accumulated record, before the intake
agent produces its next question. On a terminating fire the conversation ends,
the emergency instruction renders, facility lookup restricts to emergency-capable,
and the session is flagged in the audit log.

Pure. No model, no I/O, no clock. The spine's engine does the evaluation; this
module says what a firing means for a session.
"""

from __future__ import annotations

from typing import Final

from services.consult.clinical.actions import RedFlagAction
from spine.rules.engine import Firing, evaluate_rule_set
from spine.schemas.predicate import Predicate
from spine.schemas.record import Record
from spine.schemas.rule import RuleSet
from spine.schemas.triage import Capability, RedFlagOutcome

RULE_CAPABILITIES: Final[dict[str, tuple[Capability, ...]]] = {
    "RF_ACS_001": (Capability.CATH_LAB, Capability.EMERGENCY_24X7),
    "RF_AORTIC_001": (
        Capability.CT_SCANNER,
        Capability.SURGICAL_THEATRE,
        Capability.EMERGENCY_24X7,
    ),
    "RF_PE_001": (Capability.CT_SCANNER, Capability.EMERGENCY_24X7),
    "RF_RESP_FAILURE_001": (Capability.INTENSIVE_CARE, Capability.EMERGENCY_24X7),
    "RF_ANAPHYLAXIS_001": (Capability.EMERGENCY_24X7,),
    "RF_STROKE_001": (
        Capability.CT_SCANNER,
        Capability.THROMBOLYSIS,
        Capability.EMERGENCY_24X7,
    ),
    "RF_SAH_001": (Capability.CT_SCANNER, Capability.EMERGENCY_24X7),
    "RF_MENINGISM_001": (Capability.EMERGENCY_24X7,),
    "RF_RAISED_ICP_001": (Capability.CT_SCANNER, Capability.EMERGENCY_24X7),
    "RF_SEIZURE_001": (Capability.EMERGENCY_24X7,),
    "RF_VISION_LOSS_001": (Capability.OPHTHALMOLOGY_ON_CALL, Capability.EMERGENCY_24X7),
    "RF_PERITONISM_001": (Capability.SURGICAL_THEATRE, Capability.EMERGENCY_24X7),
    "RF_ECTOPIC_001": (
        Capability.OBSTETRIC_THEATRE,
        Capability.BLOOD_BANK,
        Capability.EMERGENCY_24X7,
    ),
    "RF_OBSTETRIC_BLEED_001": (
        Capability.OBSTETRIC_THEATRE,
        Capability.BLOOD_BANK,
        Capability.EMERGENCY_24X7,
    ),
    "RF_PRE_ECLAMPSIA_001": (Capability.OBSTETRIC_THEATRE, Capability.EMERGENCY_24X7),
    "RF_TORSION_001": (Capability.SURGICAL_THEATRE, Capability.EMERGENCY_24X7),
    "RF_GI_BLEED_001": (Capability.BLOOD_BANK, Capability.EMERGENCY_24X7),
    "RF_SEPSIS_001": (Capability.EMERGENCY_24X7, Capability.INTENSIVE_CARE),
    "RF_DKA_001": (Capability.EMERGENCY_24X7, Capability.INTENSIVE_CARE),
    "RF_PAEDIATRIC_DANGER_001": (Capability.EMERGENCY_24X7, Capability.NEONATAL_CARE),
    "RF_UNDER_TWO_001": (Capability.NEONATAL_CARE,),
    "RF_SUICIDE_RISK_001": (Capability.PSYCHIATRIC_ASSESSMENT, Capability.EMERGENCY_24X7),
    "RF_HARM_TO_OTHERS_001": (Capability.PSYCHIATRIC_ASSESSMENT, Capability.EMERGENCY_24X7),
    "RF_TRAUMA_MAJOR_001": (
        Capability.SURGICAL_THEATRE,
        Capability.BLOOD_BANK,
        Capability.EMERGENCY_24X7,
    ),
    "RF_HEAD_INJURY_001": (Capability.CT_SCANNER, Capability.EMERGENCY_24X7),
}
"""Facility capabilities each rule requires.

A STEMI needs a catheterisation lab; a suspected stroke needs CT plus
thrombolysis. Routing on distance alone sends a patient to a hospital that
cannot treat them.

A rule absent from this table requires no specific capability, which is correct
for the annotating rules. A terminating rule missing from it is a defect, and a
test asserts every terminating rule appears.
"""


def _capabilities_for(firings: tuple[Firing[RedFlagAction], ...]) -> tuple[Capability, ...]:
    """Union of capabilities across firings, in declaration order, deduplicated."""
    seen: list[Capability] = []
    for firing in firings:
        for capability in RULE_CAPABILITIES.get(firing.rule_id, ()):
            if capability not in seen:
                seen.append(capability)
    return tuple(seen)


def _ids_with_action(
    firings: tuple[Firing[RedFlagAction], ...], action: RedFlagAction
) -> tuple[str, ...]:
    """Rule ids whose action is `action`.

    Compares by value rather than identity. A Firing built from an unresolved
    TypeVar carries the action as a plain string, since ActionT falls back to
    its str bound at runtime, and identity comparison then silently matches
    nothing.
    """
    return tuple(firing.rule_id for firing in firings if firing.action == action.value)


def evaluate(
    record: Record,
    rule_sets: tuple[RuleSet[RedFlagAction], ...],
    predicates: dict[str, Predicate],
) -> RedFlagOutcome:
    """Run every red flag rule against `record`.

    Every rule set is evaluated in full. There is no short-circuit on the first
    terminating fire, because a second fire may require a capability the first
    does not, and the emergency facility must satisfy all of them.
    """
    firings: tuple[Firing[RedFlagAction], ...] = tuple(
        firing
        for rule_set in rule_sets
        for firing in evaluate_rule_set(rule_set, record, predicates)
    )
    if not firings:
        return RedFlagOutcome()

    matched: list[str] = []
    for firing in firings:
        for atom in (*firing.matched_atoms, *firing.escalating_atoms):
            if atom not in matched:
                matched.append(atom)

    return RedFlagOutcome(
        rule_ids=tuple(firing.rule_id for firing in firings),
        terminating_rule_ids=_ids_with_action(firings, RedFlagAction.TERMINATE_EMERGENCY),
        escalating_rule_ids=_ids_with_action(firings, RedFlagAction.ESCALATE_BAND),
        required_capabilities=_capabilities_for(firings),
        matched_atoms=tuple(matched),
        unverified_rule_ids=tuple(f.rule_id for f in firings if f.unverified),
    )
