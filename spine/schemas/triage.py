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

    Deliberately coarse. A specialty a patient cannot actually find nearby is
    not a useful routing decision.
    """

    EMERGENCY = "emergency"
    GENERAL_MEDICINE = "general_medicine"
    CARDIOLOGY = "cardiology"
    NEUROLOGY = "neurology"
    GASTROENTEROLOGY = "gastroenterology"
    PULMONOLOGY = "pulmonology"
    OBSTETRICS_GYNAECOLOGY = "obstetrics_gynaecology"
    PAEDIATRICS = "paediatrics"
    SURGERY = "surgery"
    UROLOGY = "urology"
    ORTHOPAEDICS = "orthopaedics"
    OPHTHALMOLOGY = "ophthalmology"
    ENT = "ent"
    DERMATOLOGY = "dermatology"
    PSYCHIATRY = "psychiatry"
    HUMAN_REVIEW = "human_review"


class Capability(str, Enum):
    """What a facility must be able to do.

    Routing matches on capability, not distance. A facility index without these
    degrades to distance-only and says so.
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
