"""Challenging a draft rule.

The model is mocked. What is tested is the part that must hold regardless of
what the model says: that a critique cannot clear a flag, that a critique
reading as approval is caught, and that a threshold the model invented is
surfaced rather than passed through as though it were sourced.

Those three are guarantees made in code because the prompt cannot make them.
A prompt instruction is a tendency; a model on a bad day produces "this rule
is clinically sound and can be verified", and something has to notice.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from services.consult.agents.rule_critic import (
    Challenge,
    build_brief,
    challenge_rule,
    find_approving_language,
    find_proposed_thresholds,
    looks_truncated,
    render,
)
from services.consult.clinical.actions import RedFlagAction
from spine.inference.adapter import Completion, InferenceProvider, ModelSpec, Transport
from spine.inference.prompts import Prompt
from spine.schemas.rule import Clause, Modifiers, Rule


def rule(*, verify: bool = True, notes: str | None = None) -> Rule[RedFlagAction]:
    return Rule[RedFlagAction](
        id="RF_ACS_001",
        label="Possible acute coronary syndrome",
        any_of=(
            Clause(all_of=("chest_pain_present", "diaphoresis_present")),
            Clause(all_of=("chest_pain_present", "dyspnoea_present", "age_over_40")),
        ),
        modifiers=Modifiers(escalate_if=("age_over_60",)),
        action=RedFlagAction.TERMINATE_EMERGENCY,
        source="PLACEHOLDER pending clinician review.",
        verify_before_ship=verify,
        verified_on=None if verify else date(2026, 1, 1),
        notes=notes,
    )


def spec() -> ModelSpec:
    return ModelSpec(name="granite4.1:3b", temperature=0.0, max_output_tokens=2048)


def prompt() -> Prompt:
    return Prompt(
        name="rule_critic",
        version="1.0.0",
        module="nidana-consult",
        model_class="local instruct",
        temperature=0.0,
        max_output_tokens=2048,
        owner="clinical",
        body="You are a senior emergency physician reviewing draft rules.",
        path=Path("services/consult/prompts/rule_critic.md"),
    )


class StubProvider(InferenceProvider):
    """Returns whatever the test needs the critic to have said."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.seen_prompt = ""

    @property
    def transport(self) -> Transport:
        return Transport.LOCAL

    def is_available(self) -> bool:
        return True

    def complete(
        self,
        *,
        prompt: str,
        system: str,  # noqa: ARG002 - the signature must match the interface
        spec: ModelSpec,  # noqa: ARG002
        prompt_version: str,
    ) -> Completion:
        self.seen_prompt = prompt
        return Completion(
            text=self.text,
            model_version="granite4.1:3b",
            transport=Transport.LOCAL,
            prompt_version=prompt_version,
            latency_ms=10,
        )


GOOD = """## RF_ACS_001 — challenge

**Verdict:** every branch requires chest pain, so the diabetic silent
presentation does not fire.

### Misses
**58-year-old woman, diabetic 12 years.** Nausea and sweating she calls
indigestion. No chest pain. Fires nothing.

### Questions for the verifying clinician
1. Should this fire on diaphoresis without chest pain in a known diabetic?
"""


class TestBrief:
    def test_the_criteria_are_shown_as_encoded(self) -> None:
        """The label says the intent; the criteria say what fires."""
        brief = build_brief(rule())
        assert "chest_pain_present AND diaphoresis_present" in brief

    def test_the_escalation_modifier_is_shown(self) -> None:
        assert "age_over_60" in build_brief(rule())

    def test_the_authors_note_is_carried(self) -> None:
        """The note is the previous reviewer's work and should not be re-derived."""
        brief = build_brief(rule(notes="Diabetes argues for a lower threshold."))
        assert "Diabetes argues for a lower threshold." in brief

    def test_unused_vocabulary_is_offered(self) -> None:
        """A criticism needing a missing predicate is a schema finding."""
        brief = build_brief(rule(), vocabulary=frozenset({"vomiting_present"}))
        assert "vomiting_present" in brief

    def test_predicates_the_rule_already_uses_are_not_offered_as_unused(self) -> None:
        brief = build_brief(rule(), vocabulary=frozenset({"chest_pain_present"}))
        assert "BUT NOT USED BY THIS RULE" in brief
        assert "(none)" in brief

    def test_an_empty_corpus_is_stated_rather_than_left_blank(self) -> None:
        assert "the corpus does not cover this rule" in build_brief(rule())

    def test_passages_carry_their_own_health_warning(self) -> None:
        """The corpus holds facility standards and is often irrelevant."""
        brief = build_brief(rule(), passages=("A district hospital shall treat.",))
        assert "may be irrelevant" in brief


class TestApprovingLanguage:
    @pytest.mark.parametrize(
        "text",
        [
            "This rule is clinically sound.",
            "The rule is correct as written.",
            "No changes are required.",
            "It is safe to ship.",
            "This can be verified.",
            "Set verify_before_ship: false",
        ],
    )
    def test_approval_is_caught(self, text: str) -> None:
        assert find_approving_language(text)

    @pytest.mark.parametrize(
        "text",
        [
            "The rule misses the diabetic presentation.",
            "The case for leaving it alone is that false positives stay low.",
            "This needs a specialist in rheumatology.",
        ],
    )
    def test_real_criticism_is_not_flagged(self, text: str) -> None:
        assert not find_approving_language(text)


class TestProposedThresholds:
    @pytest.mark.parametrize(
        "text",
        [
            "Consider pain lasting more than 20 minutes.",
            "An ESR above 50 mm/hr would support this.",
            "Add a criterion for heart rate over 100 bpm.",
            "Potassium less than 3.0 mmol should fire.",
        ],
    )
    def test_an_invented_cut_off_is_found(self, text: str) -> None:
        assert find_proposed_thresholds(text)

    @pytest.mark.parametrize(
        "text",
        [
            "A 58-year-old woman with diabetes.",
            "NICE CG95 stratifies with an ECG.",
            "The rule has 4 branches.",
            "age_over_40 is already a predicate.",
        ],
    )
    def test_ordinary_numbers_are_not_thresholds(self, text: str) -> None:
        """A patient's age and a guideline number are not proposed cut-offs."""
        assert not find_proposed_thresholds(text)

    def test_the_threshold_is_returned_not_stripped(self) -> None:
        """A reviewer needs to see what the model reached for."""
        found = find_proposed_thresholds("Consider more than 20 minutes of pain.")
        assert "more than 20 minutes" in found[0]


class TestChallenging:
    def test_a_critique_is_returned(self) -> None:
        built = challenge_rule(rule(), StubProvider(GOOD), prompt(), "m")
        assert "58-year-old woman" in built.text

    def test_the_rule_stays_unverified(self) -> None:
        """The guarantee this module exists to make."""
        built = challenge_rule(rule(), StubProvider(GOOD), prompt(), "m")
        assert built.still_unverified

    def test_an_already_verified_rule_is_refused(self) -> None:
        """Re-opening a signed rule is a clinical decision, not an automated one."""
        with pytest.raises(ValueError, match="already verified"):
            challenge_rule(rule(verify=False), StubProvider(GOOD), prompt(), "m")

    def test_an_approving_critique_is_flagged_not_discarded(self) -> None:
        provider = StubProvider("This rule is clinically sound. No changes required.")
        built = challenge_rule(rule(), provider, prompt(), "m")
        assert built.approving_verdict_rejected
        assert not built.is_trustworthy
        assert built.text

    def test_an_invented_threshold_is_flagged(self) -> None:
        provider = StubProvider("Add a criterion for pain lasting more than 20 minutes.")
        built = challenge_rule(rule(), provider, prompt(), "m")
        assert built.proposed_thresholds
        assert not built.is_trustworthy

    def test_a_clean_critique_is_trustworthy(self) -> None:
        built = challenge_rule(rule(), StubProvider(GOOD), prompt(), "m")
        assert built.is_trustworthy

    def test_the_model_version_is_recorded(self) -> None:
        built = challenge_rule(rule(), StubProvider(GOOD), prompt(), "m")
        assert built.model_version == "granite4.1:3b"

    def test_the_brief_reaches_the_model(self) -> None:
        provider = StubProvider(GOOD)
        challenge_rule(rule(), provider, prompt(), "m")
        assert "RF_ACS_001" in provider.seen_prompt


class TestRendering:
    def test_the_unverified_notice_leads(self) -> None:
        """The likeliest misreading is that a critique is a review."""
        text = render(challenge_rule(rule(), StubProvider(GOOD), prompt(), "m"))
        assert text.index("remains unverified") < text.index("58-year-old")

    def test_an_approval_warning_appears_above_the_text(self) -> None:
        provider = StubProvider("This rule is clinically sound.")
        text = render(challenge_rule(rule(), provider, prompt(), "m"))
        assert "contains approving language" in text

    def test_a_threshold_warning_names_the_number(self) -> None:
        provider = StubProvider("Consider pain lasting more than 20 minutes.")
        text = render(challenge_rule(rule(), provider, prompt(), "m"))
        assert "20 minutes" in text
        assert "not sourced" in text

    def test_a_clean_critique_carries_no_warning(self) -> None:
        text = render(challenge_rule(rule(), StubProvider(GOOD), prompt(), "m"))
        assert "Warning" not in text

    def test_the_model_is_named(self) -> None:
        """A critique's author is a model, and the reader should know which."""
        text = render(challenge_rule(rule(), StubProvider(GOOD), prompt(), "m"))
        assert "granite4.1:3b" in text


class TestChallengeIsInert:
    def test_nothing_on_a_challenge_can_clear_a_flag(self) -> None:
        """There is no field that could be read as a verification."""
        built = Challenge(
            rule_id="RF_X",
            rule_label="Test",
            text="anything at all",
            model_version="m",
            approving_verdict_rejected=False,
            proposed_thresholds=(),
        )
        assert built.still_unverified


class TestTruncation:
    """A critique cut at the token limit loses the part a reviewer acts on.

    Worse than losing it: truncation usually happens partway through the
    concession section, so what survives reads more one-sided than the critic
    actually was, and a reviewer would take a harsher verdict at face value.
    """

    def test_a_complete_critique_is_not_flagged(self) -> None:
        assert not looks_truncated(
            "### Questions for the verifying clinician\n1. Should this fire on pain alone?"
        )

    def test_a_missing_questions_section_is_truncation(self) -> None:
        assert looks_truncated("### Misses\nA 58-year-old woman.")

    def test_stopping_mid_sentence_is_truncation(self) -> None:
        assert looks_truncated(
            "### Questions for the verifying clinician\n1. Should this fire on respir"
        )

    def test_empty_text_is_truncation(self) -> None:
        assert looks_truncated("")

    def test_a_truncated_critique_is_not_trustworthy(self) -> None:
        provider = StubProvider("### Misses\nA 58-year-old woman.")
        built = challenge_rule(rule(), provider, prompt(), "m")
        assert built.truncated
        assert not built.is_trustworthy

    def test_the_warning_explains_the_one_sidedness(self) -> None:
        provider = StubProvider("### Misses\nA 58-year-old woman.")
        text = render(challenge_rule(rule(), provider, prompt(), "m"))
        assert "incomplete" in text
        assert "one-sided" in text


class TestTheSpecComesFromThePrompt:
    """The bug this class exists to prevent.

    model_spec() defaults to 512 output tokens. A critique needs several times
    that, and at 512 it stops partway through the concession section — leaving
    a document that reads more one-sided than the critic was, with the
    questions a reviewer acts on missing entirely. It looked like a model
    limitation for a while; it was a default.
    """

    def test_the_token_budget_is_the_prompts_not_a_default(self) -> None:
        captured: list[ModelSpec] = []

        class Recording(StubProvider):
            def complete(
                self,
                *,
                prompt: str,
                system: str,
                spec: ModelSpec,
                prompt_version: str,
            ) -> Completion:
                captured.append(spec)
                return super().complete(
                    prompt=prompt, system=system, spec=spec, prompt_version=prompt_version
                )

        written = prompt()
        challenge_rule(rule(), Recording(GOOD), written, "granite4.1:3b")
        assert captured[0].max_output_tokens == written.max_output_tokens
        assert captured[0].max_output_tokens > 512

    def test_the_temperature_is_the_prompts(self) -> None:
        """Reasoning runs deterministic; a critique is reasoning."""
        assert prompt().temperature == 0.0
