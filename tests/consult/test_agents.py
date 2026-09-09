"""The agent runtime: where model output crosses into the record.

Every test here mocks the model and runs the real validation. The clinical
layer is never mocked, so the span check, the registry check, the band floor,
and the output filter all run for real.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from services.consult.agents import critic, intake, structuring, triage
from services.consult.agents.schemas import (
    CriticVerdictName,
    ExtractedFinding,
    IntakeOutput,
    TriageOutput,
)
from services.consult.clinical.output_filter import ConditionNameLeakError, assert_clean
from spine.inference.prompts import (
    PromptLoadError,
    assert_clinical_prompts_are_deterministic,
    load,
    load_all,
)
from spine.rules.registry_loader import load_family
from spine.schemas.primitives import Band, Confidence, Quantity, Sex
from spine.schemas.record import ConsultContext, Demographics, Record, SubjectType
from spine.schemas.registry import ComplaintFamily, FamilyRegistry
from spine.schemas.sufficiency import assess
from spine.schemas.triage import Capability, RedFlagOutcome, Specialty, TriageResult

UTTERANCE = "mujhe do din se chest pain hai, jabde mein bhi ja raha hai, pasina nahi aa raha"
CONVERSATIONAL_AGENTS = frozenset({"intake_agent"})


@pytest.fixture(scope="module")
def chest_pain() -> FamilyRegistry:
    return load_family(ComplaintFamily.CHEST_PAIN)


def claim(
    field: str,
    value: str | float | int | bool,
    span: str,
    *,
    negated: bool = False,
) -> ExtractedFinding:
    return ExtractedFinding(
        field=field,
        value=value,
        source_span=span,
        confidence=Confidence.HIGH,
        negated=negated,
    )


def session(band_context: ComplaintFamily = ComplaintFamily.CHEST_PAIN) -> Record:
    return Record(
        subject_type=SubjectType.SESSION,
        subject_id=uuid4(),
        demographics=Demographics(age_years=54, sex=Sex.MALE),
        consult=ConsultContext(complaint_family=band_context),
    )


class TestPromptLoading:
    """Prompts are files, versioned in git, never string literals."""

    def test_every_consult_prompt_loads(self) -> None:
        """rule_critic is a design-time reviewer, not part of a session.

        It is listed here because load_all reads the directory, and a prompt
        that stopped loading should fail a test rather than fail at the first
        model call.
        """
        prompts = load_all("consult")
        assert set(prompts) == {
            "intake_agent",
            "structuring_agent",
            "triage_agent",
            "safety_critic",
            "rule_critic",
        }

    def test_each_prompt_carries_a_version(self) -> None:
        for prompt in load_all("consult").values():
            assert prompt.version

    def test_reasoning_prompts_run_deterministic(self) -> None:
        assert_clinical_prompts_are_deterministic(load_all("consult"), CONVERSATIONAL_AGENTS)

    def test_a_non_conversational_agent_above_zero_is_caught(self) -> None:
        with pytest.raises(PromptLoadError, match="temperature 0"):
            assert_clinical_prompts_are_deterministic(load_all("consult"), frozenset())

    def test_a_missing_prompt_names_the_path(self) -> None:
        with pytest.raises(PromptLoadError, match="never string literals"):
            load("consult", "no_such_agent")

    def test_a_prompt_without_a_header_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "bare.md").write_text("# Bare\n\n## ROLE\nx\n", encoding="utf-8")
        with pytest.raises(PromptLoadError, match="no header block"):
            load("consult", "bare", tmp_path)

    def test_a_prompt_missing_output_section_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "partial.md").write_text(
            "# Partial\n\n```\nversion: 1.0.0\nmodule: m\nmodel: x\ntemperature: 0.0\n"
            "max_output_tokens: 10\nowner: clinical\n```\n\n## ROLE\nx\n## TASK\nx\n"
            "## CONTEXT\nx\n",
            encoding="utf-8",
        )
        with pytest.raises(PromptLoadError, match="OUTPUT"):
            load("consult", "partial", tmp_path)


class TestStructuringValidation:
    """The narrowest gate in the system. Three checks, all of them refusals."""

    def test_a_verified_claim_becomes_a_finding(self, chest_pain: FamilyRegistry) -> None:
        result = structuring.validate_claims(
            (claim("radiation", "jaw", "jabde mein bhi ja raha hai"),),
            chest_pain,
            UTTERANCE,
            "u1",
            2,
        )
        assert len(result.findings) == 1
        assert result.findings[0].provenance.text == "jabde mein bhi ja raha hai"

    def test_a_translated_span_is_dropped(self, chest_pain: FamilyRegistry) -> None:
        """The failure the structuring prompt exists to prevent."""
        result = structuring.validate_claims(
            (claim("radiation", "jaw", "radiating to the jaw"),), chest_pain, UTTERANCE, "u1", 2
        )
        assert not result.findings
        assert "does not occur" in result.dropped[0].reason

    def test_a_field_outside_the_registry_is_dropped(self, chest_pain: FamilyRegistry) -> None:
        result = structuring.validate_claims(
            (claim("anxiety_level", "high", "do din se"),), chest_pain, UTTERANCE, "u1", 2
        )
        assert not result.findings
        assert "nowhere to go" in result.dropped[0].reason

    def test_an_impermissible_enum_value_is_dropped(self, chest_pain: FamilyRegistry) -> None:
        result = structuring.validate_claims(
            (claim("radiation", "elbow", "do din se"),), chest_pain, UTTERANCE, "u1", 2
        )
        assert not result.findings
        assert "not permitted" in result.dropped[0].reason

    def test_a_denial_becomes_a_negated_finding(self, chest_pain: FamilyRegistry) -> None:
        result = structuring.validate_claims(
            (claim("diaphoresis", False, "pasina nahi aa raha", negated=True),),
            chest_pain,
            UTTERANCE,
            "u1",
            2,
        )
        assert result.findings[0].negated is True
        assert result.findings[0].value is False

    def test_a_numeric_field_becomes_a_quantity_with_its_unit(
        self, chest_pain: FamilyRegistry
    ) -> None:
        result = structuring.validate_claims(
            (claim("onset_duration_hours", 48, "do din se"),), chest_pain, UTTERANCE, "u1", 2
        )
        value = result.findings[0].value
        assert isinstance(value, Quantity)
        assert value.unit == "hours"

    def test_valid_and_invalid_claims_are_separated(self, chest_pain: FamilyRegistry) -> None:
        result = structuring.validate_claims(
            (
                claim("radiation", "jaw", "jabde mein bhi ja raha hai"),
                claim("radiation", "jaw", "radiating to the jaw"),
                claim("anxiety_level", "high", "do din se"),
            ),
            chest_pain,
            UTTERANCE,
            "u1",
            2,
        )
        assert len(result.findings) == 1
        assert len(result.dropped) == 2
        assert result.drop_rate == pytest.approx(2 / 3)

    def test_no_claims_produces_no_findings_and_no_drops(
        self, chest_pain: FamilyRegistry
    ) -> None:
        result = structuring.validate_claims((), chest_pain, UTTERANCE, "u1", 2)
        assert result.findings == ()
        assert result.drop_rate == 0.0

    def test_the_turn_index_lands_on_the_provenance(self, chest_pain: FamilyRegistry) -> None:
        result = structuring.validate_claims(
            (claim("radiation", "jaw", "jabde mein bhi ja raha hai"),),
            chest_pain,
            UTTERANCE,
            "u1",
            7,
        )
        assert result.findings[0].turn_index == 7

    def test_the_prompt_carries_the_registry_vocabulary(
        self, chest_pain: FamilyRegistry
    ) -> None:
        built = structuring.build_prompt(UTTERANCE, chest_pain, 2)
        assert "radiation" in built
        assert "left_arm" in built
        assert UTTERANCE in built


class TestCriticAsymmetry:
    """Enforced in code, not in the prompt."""

    def test_an_escalation_is_applied(self) -> None:
        verdict = CriticVerdictName(
            verdict="raise_to", band=Band.U1, reason="confusion unaddressed"
        )
        outcome = critic.review(verdict, Band.U3)
        assert outcome.final_band is Band.U1
        assert outcome.escalated

    def test_agreement_leaves_the_band_alone(self) -> None:
        outcome = critic.review(
            CriticVerdictName(verdict="no_change", reason="nothing unaddressed"), Band.U2
        )
        assert outcome.final_band is Band.U2
        assert not outcome.escalated

    def test_a_de_escalation_is_rejected_and_the_band_stands(self) -> None:
        verdict = CriticVerdictName(verdict="raise_to", band=Band.U4, reason="seems overblown")
        outcome = critic.review(verdict, Band.U1)
        assert outcome.final_band is Band.U1
        assert outcome.rejected_reason is not None

    def test_an_equal_band_is_rejected_rather_than_read_as_agreement(self) -> None:
        verdict = CriticVerdictName(verdict="raise_to", band=Band.U2, reason="agree really")
        outcome = critic.review(verdict, Band.U2)
        assert outcome.final_band is Band.U2
        assert outcome.rejected_reason is not None

    def test_a_rejected_verdict_does_not_raise(self) -> None:
        """A misbehaving critic must not fail the session."""
        verdict = CriticVerdictName(verdict="raise_to", band=Band.U5, reason="x")
        assert critic.review(verdict, Band.U1).final_band is Band.U1

    def test_raise_to_without_a_band_is_refused_at_the_schema(self) -> None:
        with pytest.raises(ValueError, match="no band was named"):
            CriticVerdictName(verdict="raise_to", reason="x")

    def test_no_change_carrying_a_band_is_refused_at_the_schema(self) -> None:
        with pytest.raises(ValueError, match="does not carry a target"):
            CriticVerdictName(verdict="no_change", band=Band.U1, reason="x")

    def test_an_unknown_verdict_word_is_refused(self) -> None:
        """There is no vocabulary for lowering a band, deliberately."""
        with pytest.raises(ValueError, match=r"string_pattern_mismatch|does not match"):
            CriticVerdictName(verdict="lower_to", band=Band.U4, reason="x")

    def test_the_prompt_shows_findings_with_their_spans(self) -> None:
        record = session()
        result = TriageResult(
            band=Band.U1, specialty=Specialty.EMERGENCY, rationale="immediate"
        )
        built = critic.build_prompt(record, result, RedFlagOutcome())
        assert "TRIAGE RESULT TO CHECK" in built
        assert "History gaps" in built


class TestTriageFloors:
    """A fired rule sets a floor the model cannot go below."""

    def test_a_terminating_rule_forces_u1(self) -> None:
        fired = RedFlagOutcome(
            rule_ids=("RF_ACS_001",), terminating_rule_ids=("RF_ACS_001",)
        )
        assert triage.apply_floors(Band.U4, fired) is Band.U1

    def test_an_escalating_rule_forces_at_least_u2(self) -> None:
        fired = RedFlagOutcome(
            rule_ids=("RF_SYNCOPE_001",), escalating_rule_ids=("RF_SYNCOPE_001",)
        )
        assert triage.apply_floors(Band.U4, fired) is Band.U2

    def test_a_floor_never_lowers_a_more_urgent_band(self) -> None:
        fired = RedFlagOutcome(
            rule_ids=("RF_SYNCOPE_001",), escalating_rule_ids=("RF_SYNCOPE_001",)
        )
        assert triage.apply_floors(Band.U1, fired) is Band.U1

    def test_no_firing_leaves_the_proposed_band(self) -> None:
        assert triage.apply_floors(Band.U4, RedFlagOutcome()) is Band.U4


class TestTriageResultAssembly:
    def test_specialty_is_resolved_deterministically_not_taken_from_the_model(self) -> None:
        output = TriageOutput(
            band=Band.U2,
            specialty=Specialty.DERMATOLOGY,
            rationale="model proposed dermatology for chest pain",
            return_criteria=(
                "If the pain returns while resting, go to a hospital immediately.",
                "If it lasts more than fifteen minutes, go to a hospital immediately.",
                "If you start sweating heavily, go to a hospital the same day.",
            ),
        )
        result = triage.to_result(output, session(), RedFlagOutcome(), "1.0.0")
        assert result.specialty is Specialty.CARDIOLOGY

    def test_a_fired_rule_capability_reaches_the_result(self) -> None:
        fired = RedFlagOutcome(
            rule_ids=("RF_ACS_001",),
            terminating_rule_ids=("RF_ACS_001",),
            required_capabilities=(Capability.CATH_LAB, Capability.EMERGENCY_24X7),
        )
        output = TriageOutput(band=Band.U1, specialty=Specialty.CARDIOLOGY, rationale="acs")
        result = triage.to_result(output, session(), fired, "1.0.0")
        assert Capability.CATH_LAB in result.required_capabilities

    def test_a_condition_name_in_return_criteria_is_refused(self) -> None:
        output = TriageOutput(
            band=Band.U3,
            specialty=Specialty.CARDIOLOGY,
            rationale="x",
            return_criteria=(
                "If you think you are having a heart attack, go to a hospital.",
                "If the pain lasts more than fifteen minutes, go to a hospital.",
                "If you start sweating heavily, go to a hospital the same day.",
            ),
        )
        with pytest.raises(ConditionNameLeakError, match="heart attack"):
            triage.to_result(output, session(), RedFlagOutcome(), "1.0.0")

    def test_a_non_u1_band_without_three_return_criteria_is_refused(self) -> None:
        output = TriageOutput(
            band=Band.U3,
            specialty=Specialty.CARDIOLOGY,
            rationale="x",
            return_criteria=("If the pain returns, go to a hospital.",),
        )
        with pytest.raises(ValueError, match="return criteria"):
            triage.to_result(output, session(), RedFlagOutcome(), "1.0.0")

    def test_u1_needs_no_return_criteria(self) -> None:
        output = TriageOutput(band=Band.U1, specialty=Specialty.EMERGENCY, rationale="now")
        assert triage.to_result(output, session(), RedFlagOutcome(), "1.0.0").band is Band.U1


class TestIntakeOutput:
    def test_one_question_is_accepted(self) -> None:
        assert IntakeOutput(utterance="Since when?").utterance == "Since when?"

    def test_a_compound_question_is_refused(self) -> None:
        with pytest.raises(ValueError, match="One question per turn"):
            IntakeOutput(utterance="Since when? And does it spread anywhere?")

    def test_a_question_naming_a_condition_is_refused_by_the_filter(self) -> None:
        with pytest.raises(ConditionNameLeakError):
            assert_clean("Do you think this is a heart attack?", "intake_agent")

    def test_the_prompt_lists_what_is_still_missing(self, chest_pain: FamilyRegistry) -> None:
        record = session()
        built = intake.build_prompt(record, chest_pain, assess(record, chest_pain), ())
        assert "Still missing" in built
        assert "radiation" in built

    def test_the_opening_turn_says_so(self, chest_pain: FamilyRegistry) -> None:
        built = intake.build_prompt(session(), chest_pain, None, ())
        assert "opening turn" in built
