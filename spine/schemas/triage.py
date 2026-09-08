"""Triage outputs: what a red flag firing means, and what triage decides.

Consult writes these. They are in the spine rather than the service because the
handoff packet and the audit log are shared shapes, and Labs reuses the routing
half when it routes an abnormal result to a specialty.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.primitives import Band

MIN_RETURN_CRITERIA = 3
"""Every outcome below U1 carries at least this many return criteria.

Not a clinical threshold. It is the floor at which the patient-facing safety net
stops being a gesture: one criterion is a platitude, three force specificity
about what actually changes the picture.
"""


class Specialty(str, Enum):
    """Where a patient is routed.

    Scoped to what an Indian district hospital is expected to provide. IPHS
    2022 Volume I names these as essential or desirable specialist services at
    a District Hospital, and routing to a specialty the referral network does
    not staff is not a useful decision.

    Source: Indian Public Health Standards 2022, Volume I (Sub-District and
    District Hospital), Ministry of Health and Family Welfare, specialist
    services table. Verified against the published document 2026-09-08.

    A presentation this list cannot express routes to HUMAN_REVIEW rather than
    to the nearest approximate match. A wrong specialty sends someone to the
    wrong queue; a stated refusal sends them to a person.
    """

    EMERGENCY = "emergency"
    GENERAL_MEDICINE = "general_medicine"
    CARDIOLOGY = "cardiology"
    NEUROLOGY = "neurology"
    GASTROENTEROLOGY = "gastroenterology"
    PULMONOLOGY = "pulmonology"
    NEPHROLOGY = "nephrology"
    ENDOCRINOLOGY = "endocrinology"
    RHEUMATOLOGY = "rheumatology"
    HAEMATOLOGY = "haematology"
    ONCOLOGY = "oncology"
    INFECTIOUS_DISEASE = "infectious_disease"
    OBSTETRICS_GYNAECOLOGY = "obstetrics_gynaecology"
    PAEDIATRICS = "paediatrics"
    NEONATOLOGY = "neonatology"
    GERIATRICS = "geriatrics"
    SURGERY = "surgery"
    UROLOGY = "urology"
    ORTHOPAEDICS = "orthopaedics"
    OPHTHALMOLOGY = "ophthalmology"
    ENT = "ent"
    DENTISTRY = "dentistry"
    DERMATOLOGY = "dermatology"
    PSYCHIATRY = "psychiatry"
    HUMAN_REVIEW = "human_review"


class Capability(str, Enum):
    """What a facility must be able to do.

    Routing matches on capability, not distance. The nearest hospital is the
    wrong hospital when it cannot treat what the patient has, and a facility
    index without these degrades to distance-only and says so.

    Scoped to services IPHS 2022 expects at a district hospital, plus the
    treatments whose absence is itself the emergency. Source: Indian Public
    Health Standards 2022, Volume I, emergency and critical care services.
    Verified against the published document 2026-09-08.
    """

    EMERGENCY_24X7 = "emergency_24x7"
    CATH_LAB = "cath_lab"
    CT_SCANNER = "ct_scanner"
    THROMBOLYSIS = "thrombolysis"
    OBSTETRIC_THEATRE = "obstetric_theatre"
    NEONATAL_CARE = "neonatal_care"
    SURGICAL_THEATRE = "surgical_theatre"
    BLOOD_BANK = "blood_bank"
    INTENSIVE_CARE = "intensive_care"
    PSYCHIATRIC_ASSESSMENT = "psychiatric_assessment"
    OPHTHALMOLOGY_ON_CALL = "ophthalmology_on_call"

    DIALYSIS = "dialysis"
    BURN_UNIT = "burn_unit"
    """IPHS 2022: every District Hospital should have a separate burn unit and
    burn cases should go directly to it."""

    ANTIVENOM = "antivenom"
    """Anti-snake venom, stocked.

    A capability rather than a specialty because it is the one thing that
    matters: a snakebite routed to a hospital without antivenom has been sent
    to the wrong place however well staffed it is. India records the highest
    snakebite mortality in the world, and the treatment is a stocked vial.
    """

    RABIES_IMMUNOGLOBULIN = "rabies_immunoglobulin"
    """Distinct from vaccine, which is widely held. Immunoglobulin for a
    category III exposure is not, and it is time-critical."""

    VENTILATOR = "ventilator"
    ENDOSCOPY = "endoscopy"


class RedFlagOutcome(BaseModel):
    """What the red flag engine concluded for one turn.

    `fired` is derived from `rule_ids` rather than stored alongside it, so the
    two cannot disagree.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_ids: tuple[str, ...] = ()
    terminating_rule_ids: tuple[str, ...] = ()
    escalating_rule_ids: tuple[str, ...] = ()
    required_capabilities: tuple[Capability, ...] = ()
    matched_atoms: tuple[str, ...] = ()
    unverified_rule_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _terminating_and_escalating_are_subsets(self) -> RedFlagOutcome:
        known = set(self.rule_ids)
        for label, subset in (
            ("terminating", self.terminating_rule_ids),
            ("escalating", self.escalating_rule_ids),
        ):
            unknown = sorted(set(subset) - known)
            if unknown:
                raise ValueError(
                    f"{label} rule ids {', '.join(unknown)} are not among the rules that "
                    f"fired; every terminating or escalating rule must have fired"
                )
        return self

    @property
    def fired(self) -> bool:
        return bool(self.rule_ids)

    @property
    def terminates_session(self) -> bool:
        return bool(self.terminating_rule_ids)


class DifferentialEntry(BaseModel):
    """One clinician-facing possibility, with the evidence for and against it.

    Never rendered to a patient. The output filter enforces that.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    condition: str = Field(min_length=1)
    supporting: tuple[str, ...] = Field(min_length=1)
    opposing: tuple[str, ...] = ()


class TriageResult(BaseModel):
    """The complete triage decision for a session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    band: Band
    specialty: Specialty
    rationale: str = Field(min_length=1)
    escalating_factors: tuple[str, ...] = ()
    uncertainty: str | None = None
    required_capabilities: tuple[Capability, ...] = ()
    return_criteria: tuple[str, ...] = ()
    differential: tuple[DifferentialEntry, ...] = ()
    history_gaps: tuple[str, ...] = ()
    red_flags: RedFlagOutcome = RedFlagOutcome()
    critic_raised_from: Band | None = None

    @model_validator(mode="after")
    def _non_u1_outcomes_carry_return_criteria(self) -> TriageResult:
        if self.band is not Band.U1 and len(self.return_criteria) < MIN_RETURN_CRITERIA:
            raise ValueError(
                f"band {self.band.value} carries {len(self.return_criteria)} return "
                f"criteria; every outcome below U1 needs at least "
                f"{MIN_RETURN_CRITERIA}. These are the specific, observable developments "
                f"that mean seek care immediately regardless of the band, and they are "
                f"what makes a non-diagnostic system clinically safe"
            )
        return self

    @model_validator(mode="after")
    def _critic_only_escalated(self) -> TriageResult:
        if self.critic_raised_from is not None and not self.band.is_more_urgent_than(
            self.critic_raised_from
        ):
            raise ValueError(
                f"critic_raised_from is {self.critic_raised_from.value} but the band is "
                f"{self.band.value}, which is not more urgent; the safety critic may "
                f"only escalate"
            )
        return self

    @property
    def was_escalated_by_critic(self) -> bool:
        return self.critic_raised_from is not None
