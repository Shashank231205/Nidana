"""Specialty routing and the patient output filter.

Routing corrects the Indian misrouting patterns in both directions: chest pain
that needs cardiology going to a general physician, and dyspepsia going to
cardiology out of fear.

The output filter is the enforcement of "no condition name reaches patient
output". It is tested here rather than trusted to a prompt.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from services.consult.clinical import output_filter, routing
from spine.schemas.primitives import Band, Sex
from spine.schemas.record import ConsultContext, Demographics, Record, SubjectType
from spine.schemas.registry import ComplaintFamily
from spine.schemas.triage import Capability, RedFlagOutcome, Specialty


def session(family: ComplaintFamily | None, age: int | None = 40) -> Record:
    return Record(
        subject_type=SubjectType.SESSION,
        subject_id=uuid4(),
        demographics=Demographics(age_years=age, sex=Sex.MALE),
        consult=ConsultContext(complaint_family=family),
    )


QUIET = RedFlagOutcome()


class TestFamilyRouting:
    @pytest.mark.parametrize(
        ("family", "expected"),
        [
            (ComplaintFamily.CHEST_PAIN, Specialty.CARDIOLOGY),
            (ComplaintFamily.HEADACHE, Specialty.NEUROLOGY),
            (ComplaintFamily.BREATHLESSNESS, Specialty.PULMONOLOGY),
            (ComplaintFamily.NEUROLOGICAL_DEFICIT, Specialty.NEUROLOGY),
            (ComplaintFamily.OBSTETRIC, Specialty.OBSTETRICS_GYNAECOLOGY),
            (ComplaintFamily.MENTAL_HEALTH, Specialty.PSYCHIATRY),
            (ComplaintFamily.TRAUMA, Specialty.ORTHOPAEDICS),
            (ComplaintFamily.FEVER, Specialty.GENERAL_MEDICINE),
        ],
    )
    def test_each_family_routes_to_its_specialty(
        self, family: ComplaintFamily, expected: Specialty
    ) -> None:
        assert routing.resolve_specialty(session(family), QUIET, Band.U4) is expected

    def test_every_family_has_a_destination(self) -> None:
        for family in ComplaintFamily:
            assert family in routing.FAMILY_SPECIALTY

    def test_chest_pain_does_not_route_to_general_medicine(self) -> None:
        """The misrouting this product exists partly to correct."""
        assert (
            routing.resolve_specialty(session(ComplaintFamily.CHEST_PAIN), QUIET, Band.U4)
            is not Specialty.GENERAL_MEDICINE
        )

    def test_an_unclassified_record_routes_to_general_medicine(self) -> None:
        routed = routing.resolve_specialty(session(None), QUIET, Band.U4)
        assert routed is Specialty.GENERAL_MEDICINE


class TestBandOverridesFamily:
    def test_u1_without_a_firing_rule_still_routes_to_emergency(self) -> None:
        assert (
            routing.resolve_specialty(session(ComplaintFamily.HEADACHE), QUIET, Band.U1)
            is Specialty.EMERGENCY
        )

    def test_lower_bands_keep_the_family_destination(self) -> None:
        for band in (Band.U2, Band.U3, Band.U4, Band.U5):
            assert (
                routing.resolve_specialty(session(ComplaintFamily.HEADACHE), QUIET, band)
                is Specialty.NEUROLOGY
            )


class TestFiringRuleOverridesEverything:
    def test_a_terminating_rule_decides_the_destination(self) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_AORTIC_001",), terminating_rule_ids=("RF_AORTIC_001",)
        )
        assert (
            routing.resolve_specialty(session(ComplaintFamily.CHEST_PAIN), outcome, Band.U1)
            is Specialty.EMERGENCY
        )

    def test_a_terminating_rule_is_preferred_over_an_escalating_one(self) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_SYNCOPE_001", "RF_STROKE_001"),
            terminating_rule_ids=("RF_STROKE_001",),
            escalating_rule_ids=("RF_SYNCOPE_001",),
        )
        assert (
            routing.resolve_specialty(session(ComplaintFamily.CHEST_PAIN), outcome, Band.U1)
            is Specialty.EMERGENCY
        )

    def test_under_two_routes_to_a_human_not_to_paediatrics(self) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_UNDER_TWO_001",), terminating_rule_ids=("RF_UNDER_TWO_001",)
        )
        assert (
            routing.resolve_specialty(session(ComplaintFamily.FEVER, age=1), outcome, Band.U1)
            is Specialty.HUMAN_REVIEW
        )


class TestPaediatricRouting:
    def test_a_child_with_fever_routes_to_paediatrics(self) -> None:
        assert (
            routing.resolve_specialty(session(ComplaintFamily.FEVER, age=6), QUIET, Band.U4)
            is Specialty.PAEDIATRICS
        )

    def test_an_adult_with_fever_routes_to_general_medicine(self) -> None:
        assert (
            routing.resolve_specialty(session(ComplaintFamily.FEVER, age=30), QUIET, Band.U4)
            is Specialty.GENERAL_MEDICINE
        )

    def test_the_paediatric_boundary_is_eighteen(self) -> None:
        assert (
            routing.resolve_specialty(session(ComplaintFamily.FEVER, age=17), QUIET, Band.U4)
            is Specialty.PAEDIATRICS
        )
        assert (
            routing.resolve_specialty(session(ComplaintFamily.FEVER, age=18), QUIET, Band.U4)
            is Specialty.GENERAL_MEDICINE
        )

    def test_an_unknown_age_does_not_route_to_paediatrics(self) -> None:
        assert (
            routing.resolve_specialty(session(ComplaintFamily.FEVER, age=None), QUIET, Band.U4)
            is Specialty.GENERAL_MEDICINE
        )

    def test_a_child_with_a_neurological_deficit_still_goes_to_neurology(self) -> None:
        """Trauma and neurological deficit are deliberately not overridden."""
        assert (
            routing.resolve_specialty(
                session(ComplaintFamily.NEUROLOGICAL_DEFICIT, age=8), QUIET, Band.U4
            )
            is Specialty.NEUROLOGY
        )


class TestCapabilities:
    def test_rule_capabilities_are_carried_through(self) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_ACS_001",),
            terminating_rule_ids=("RF_ACS_001",),
            required_capabilities=(Capability.CATH_LAB, Capability.EMERGENCY_24X7),
        )
        assert Capability.CATH_LAB in routing.required_capabilities(Specialty.CARDIOLOGY, outcome)

    def test_specialty_capabilities_are_added(self) -> None:
        assert Capability.EMERGENCY_24X7 in routing.required_capabilities(
            Specialty.EMERGENCY, QUIET
        )

    def test_capabilities_are_not_duplicated(self) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_SEPSIS_001",),
            terminating_rule_ids=("RF_SEPSIS_001",),
            required_capabilities=(Capability.EMERGENCY_24X7,),
        )
        result = routing.required_capabilities(Specialty.EMERGENCY, outcome)
        assert len(result) == len(set(result))

    def test_a_quiet_outcome_needs_nothing_special(self) -> None:
        assert routing.required_capabilities(Specialty.DERMATOLOGY, QUIET) == ()


class TestOutputFilter:
    @pytest.mark.parametrize(
        "text",
        [
            "Go to a hospital now.",
            "If the pain comes back while you are resting, go to a hospital immediately.",
            "See a heart specialist within two days.",
            "Aap ko aaj hi hospital jaana chahiye.",
        ],
    )
    def test_safe_text_passes(self, text: str) -> None:
        assert output_filter.is_clean(text)
        assert output_filter.assert_clean(text, "test") == text

    @pytest.mark.parametrize(
        ("text", "term"),
        [
            ("This could be a heart attack.", "heart attack"),
            ("You may have had a stroke.", "stroke"),
            ("It looks like appendicitis.", "appendicitis"),
            ("Possible ectopic pregnancy.", "ectopic pregnancy"),
            ("This suggests sepsis.", "sepsis"),
            ("Signs of dengue.", "dengue"),
            ("Could be TUBERCULOSIS.", "tuberculosis"),
        ],
    )
    def test_condition_names_are_caught(self, text: str, term: str) -> None:
        assert not output_filter.is_clean(text)
        assert term in output_filter.find_blocked_terms(text)

    def test_matching_is_case_insensitive(self) -> None:
        assert not output_filter.is_clean("Heart Attack")

    def test_matching_respects_word_boundaries(self) -> None:
        """'ulcer' must not fire inside an unrelated longer word."""
        assert output_filter.is_clean("The vulcerous claim is not a word")

    def test_redact_replaces_the_term(self) -> None:
        assert output_filter.redact("You may have had a stroke") == "You may have had a [removed]"

    def test_redact_handles_several_terms(self) -> None:
        redacted = output_filter.redact("possible angina or a heart attack")
        assert "angina" not in redacted
        assert "heart attack" not in redacted

    def test_redacted_output_is_clean(self) -> None:
        assert output_filter.is_clean(output_filter.redact("this looks like appendicitis"))

    def test_assert_clean_refuses_and_names_the_origin(self) -> None:
        with pytest.raises(output_filter.ConditionNameLeakError, match="triage_agent"):
            output_filter.assert_clean("could be sepsis", "triage_agent")

    def test_assert_clean_lists_every_term_found(self) -> None:
        with pytest.raises(output_filter.ConditionNameLeakError) as caught:
            output_filter.assert_clean("angina, or possibly pneumonia", "intake_agent")
        message = str(caught.value)
        assert "angina" in message
        assert "pneumonia" in message

    def test_the_error_says_not_to_route_around_the_filter(self) -> None:
        with pytest.raises(output_filter.ConditionNameLeakError, match="do not route around"):
            output_filter.assert_clean("stroke", "test")

    def test_empty_text_is_clean(self) -> None:
        assert output_filter.is_clean("")
