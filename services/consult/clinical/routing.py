"""Specialty routing. Deterministic, no model.

Maps a complaint family and the red flags that fired to a specialty and the
facility capabilities that specialty needs.

The Indian misrouting patterns are handled explicitly, in both directions: chest
pain sent to a general physician when it needs cardiology, and dyspepsia sent to
cardiology out of fear. Routing is by presentation, not by the patient's guess
at what is wrong.
"""

from __future__ import annotations

from typing import Final

from spine.schemas.primitives import Band
from spine.schemas.record import Record
from spine.schemas.registry import ComplaintFamily
from spine.schemas.triage import Capability, RedFlagOutcome, Specialty

FAMILY_SPECIALTY: Final[dict[ComplaintFamily, Specialty]] = {
    ComplaintFamily.CHEST_PAIN: Specialty.CARDIOLOGY,
    ComplaintFamily.ABDOMINAL_PAIN: Specialty.GENERAL_MEDICINE,
    ComplaintFamily.HEADACHE: Specialty.NEUROLOGY,
    ComplaintFamily.BREATHLESSNESS: Specialty.PULMONOLOGY,
    ComplaintFamily.FEVER: Specialty.GENERAL_MEDICINE,
    ComplaintFamily.NEUROLOGICAL_DEFICIT: Specialty.NEUROLOGY,
    ComplaintFamily.OBSTETRIC: Specialty.OBSTETRICS_GYNAECOLOGY,
    ComplaintFamily.MENTAL_HEALTH: Specialty.PSYCHIATRY,
    ComplaintFamily.TRAUMA: Specialty.ORTHOPAEDICS,
    ComplaintFamily.GENERAL: Specialty.GENERAL_MEDICINE,
}

RULE_SPECIALTY: Final[dict[str, Specialty]] = {
    "RF_ACS_001": Specialty.CARDIOLOGY,
    "RF_AORTIC_001": Specialty.EMERGENCY,
    "RF_PE_001": Specialty.EMERGENCY,
    "RF_RESP_FAILURE_001": Specialty.EMERGENCY,
    "RF_ANAPHYLAXIS_001": Specialty.EMERGENCY,
    "RF_SYNCOPE_001": Specialty.CARDIOLOGY,
    "RF_HAEMOPTYSIS_001": Specialty.PULMONOLOGY,
    "RF_STROKE_001": Specialty.EMERGENCY,
    "RF_TIA_001": Specialty.NEUROLOGY,
    "RF_SAH_001": Specialty.EMERGENCY,
    "RF_MENINGISM_001": Specialty.EMERGENCY,
    "RF_RAISED_ICP_001": Specialty.EMERGENCY,
    "RF_SEIZURE_001": Specialty.EMERGENCY,
    "RF_TEMPORAL_ARTERITIS_001": Specialty.OPHTHALMOLOGY,
    "RF_VISION_LOSS_001": Specialty.OPHTHALMOLOGY,
    "RF_PERITONISM_001": Specialty.SURGERY,
    "RF_ECTOPIC_001": Specialty.OBSTETRICS_GYNAECOLOGY,
    "RF_OBSTETRIC_BLEED_001": Specialty.OBSTETRICS_GYNAECOLOGY,
    "RF_PRE_ECLAMPSIA_001": Specialty.OBSTETRICS_GYNAECOLOGY,
    "RF_REDUCED_FETAL_MOVEMENT_001": Specialty.OBSTETRICS_GYNAECOLOGY,
    "RF_TORSION_001": Specialty.UROLOGY,
    "RF_GI_BLEED_001": Specialty.EMERGENCY,
    "RF_SEPSIS_001": Specialty.EMERGENCY,
    "RF_DKA_001": Specialty.EMERGENCY,
    "RF_DEHYDRATION_001": Specialty.GENERAL_MEDICINE,
    "RF_PAEDIATRIC_DANGER_001": Specialty.PAEDIATRICS,
    "RF_UNDER_TWO_001": Specialty.HUMAN_REVIEW,
    "RF_SUICIDE_RISK_001": Specialty.PSYCHIATRY,
    "RF_HARM_TO_OTHERS_001": Specialty.PSYCHIATRY,
    "RF_TRAUMA_MAJOR_001": Specialty.EMERGENCY,
    "RF_HEAD_INJURY_001": Specialty.EMERGENCY,
}
"""Where a firing rule sends the patient, overriding the complaint family.

A rule's routing is more specific than its family's: chest pain routes to
cardiology by default, but a firing aortic dissection rule routes to emergency,
because the destination is a department that can operate rather than a clinic
that can investigate.
"""

SPECIALTY_CAPABILITIES: Final[dict[Specialty, tuple[Capability, ...]]] = {
    Specialty.EMERGENCY: (Capability.EMERGENCY_24X7,),
    Specialty.CARDIOLOGY: (),
    Specialty.OBSTETRICS_GYNAECOLOGY: (),
    Specialty.PAEDIATRICS: (),
    Specialty.PSYCHIATRY: (Capability.PSYCHIATRIC_ASSESSMENT,),
}

PAEDIATRIC_OVERRIDE_FAMILIES: Final[frozenset[ComplaintFamily]] = frozenset(
    {
        ComplaintFamily.FEVER,
        ComplaintFamily.ABDOMINAL_PAIN,
        ComplaintFamily.BREATHLESSNESS,
        ComplaintFamily.GENERAL,
    }
)
"""Families whose adult routing is wrong for a child.

Trauma and neurological deficit are deliberately absent: a child with a
significant head injury goes to the same emergency department an adult does.
"""


def _rule_specialty(red_flags: RedFlagOutcome) -> Specialty | None:
    """The most specific specialty among firing rules.

    Terminating rules are consulted before escalating ones, since a rule that
    ends the session has already decided the destination.
    """
    for rule_id in (*red_flags.terminating_rule_ids, *red_flags.rule_ids):
        specialty = RULE_SPECIALTY.get(rule_id)
        if specialty is not None:
            return specialty
    return None


def resolve_specialty(
    record: Record,
    red_flags: RedFlagOutcome,
    band: Band,
) -> Specialty:
    """Where this patient should be seen.

    A firing rule decides first, then the band, then the complaint family. Age
    overrides last, because a child with an emergency still goes to emergency.
    """
    from_rule = _rule_specialty(red_flags)
    if from_rule is not None:
        return from_rule
    if band is Band.U1:
        return Specialty.EMERGENCY
    family = record.consult.complaint_family
    if family is None:
        return Specialty.GENERAL_MEDICINE
    specialty = FAMILY_SPECIALTY[family]
    if record.demographics.is_paediatric and family in PAEDIATRIC_OVERRIDE_FAMILIES:
        return Specialty.PAEDIATRICS
    return specialty


def required_capabilities(
    specialty: Specialty,
    red_flags: RedFlagOutcome,
) -> tuple[Capability, ...]:
    """Everything the destination facility must be able to do.

    The union of what the firing rules need and what the specialty needs. A
    facility satisfying only some of them is not a match.
    """
    combined: list[Capability] = list(red_flags.required_capabilities)
    for capability in SPECIALTY_CAPABILITIES.get(specialty, ()):
        if capability not in combined:
            combined.append(capability)
    return tuple(combined)
