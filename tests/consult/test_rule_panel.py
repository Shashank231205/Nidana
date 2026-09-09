"""A panel of reviewers converging to one brief.

The model is mocked. What is tested is what must hold whatever the models say:
that a panel run produces a record of work done and never a clearance, that a
seat writing approving language is caught rather than believed, and that the
chair's disagreements survive into the brief a clinician reads.

The last one is the reason a panel beats a single critic. If the chair
flattened three reviews into one agreeable paragraph, the extra seats would
cost three model calls and buy nothing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from services.consult.agents.rule_panel import (
    DEFAULT_REFERRAL,
    PANEL_VERSION,
    SEATS,
    extract_concerns,
    extract_referral,
    render,
    review_rule,
)
from services.consult.clinical.actions import RedFlagAction
from spine.inference.adapter import Completion, InferenceProvider, ModelSpec, Transport
from spine.inference.prompts import Prompt
from spine.schemas.rule import Clause, Modifiers, Rule, VerificationState

BRIEF = """## RF_ACS_001 — panel brief

**The panel has not verified this rule.**

### What the panel agrees on
1. Every branch requires chest pain, so the diabetic presentation is missed.
2. Duration appears in no branch.

### Where the panel disagrees
- The practice reviewer wants chest pain dropped; the safety engineer says that
  fires on most febrile illness. What turns on it: local capacity.

### Refer to
Emergency physician. Every branch of this rule fires in an emergency context.

### Questions for the verifying clinician
1. Should this fire on diaphoresis alone in a known diabetic?
"""

SEAT_TEXT = """## RF_ACS_001 — emergency physician

**Headline:** the diabetic silent presentation fires no branch.

### Misses
**58-year-old woman, diabetic 12 years.** Nausea and sweating, no chest pain.

### The one decision I would put to a clinician
Should chest pain be required at all?
"""


def rule(*, verify: bool = True) -> Rule[RedFlagAction]:
    return Rule[RedFlagAction](
        id="RF_ACS_001",
        label="Possible acute coronary syndrome",
        any_of=(Clause(all_of=("chest_pain_present", "diaphoresis_present")),),
        modifiers=Modifiers(escalate_if=("age_over_60",)),
        action=RedFlagAction.TERMINATE_EMERGENCY,
        source="PLACEHOLDER pending clinician review.",
        verify_before_ship=verify,
        verified_on=None if verify else date(2026, 1, 1),
        verified_by=None if verify else "Dr A Reviewer",
    )


def prompt() -> Prompt:
    return Prompt(
        name="rule_panel",
        version="1.0.0",
        module="nidana-consult",
        model_class="local instruct",
        temperature=0.0,
        max_output_tokens=3072,
        owner="clinical",
        body="You are one seat on a panel.",
        path=Path("services/consult/prompts/rule_panel.md"),
    )


class ScriptedProvider(InferenceProvider):
    """Returns each response in turn: three seats, then the chair."""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

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
        self.prompts.append(prompt)
        text = self.responses.pop(0) if self.responses else BRIEF
        return Completion(
            text=text,
            model_version="granite4.1:3b",
            transport=Transport.LOCAL,
            prompt_version=prompt_version,
            latency_ms=10,
        )


def panel(*responses: str, today: date = date(2026, 9, 9)):  # type: ignore[no-untyped-def]
    provider = ScriptedProvider(*responses)
    return review_rule(rule(), provider, prompt(), "granite4.1:3b", today=today), provider


class TestTheSeatsAreDistinct:
    def test_every_seat_is_run(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert len(result.seats) == len(SEATS)

    def test_each_seat_is_told_which_seat_it_is(self) -> None:
        """A panel whose seats all reason identically is one critic run thrice."""
        _, provider = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert "emergency physician" in provider.prompts[0]
        assert "safety engineer" in provider.prompts[1]
        assert "Indian practice reviewer" in provider.prompts[2]

    def test_the_chair_is_shown_the_reviews_not_asked_to_review(self) -> None:
        _, provider = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        chair_prompt = provider.prompts[3]
        assert "You did not review the rule" in chair_prompt
        assert "THE THREE REVIEWS" in chair_prompt

    def test_every_seat_sees_the_same_rule(self) -> None:
        _, provider = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert all("RF_ACS_001" in p for p in provider.prompts[:3])


class TestTheReviewIsNotAClearance:
    """The property the whole module is arranged around."""

    def test_a_panel_run_still_blocks_release(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert result.still_blocks_release

    def test_the_review_itself_clears_nothing(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert not result.review.clears_release

    def test_a_rule_carrying_the_review_is_still_blocked(self) -> None:
        """The gate ignores the review entirely, which is the point."""
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        reviewed = rule().model_copy(update={"review": result.review})
        assert reviewed.blocks_release
        assert reviewed.state is VerificationState.AI_REVIEWED

    def test_an_already_verified_rule_is_refused(self) -> None:
        """Reopening a signed rule is a clinical decision too."""
        provider = ScriptedProvider(BRIEF)
        with pytest.raises(ValueError, match="already verified"):
            review_rule(rule(verify=False), provider, prompt(), "m")

    def test_the_review_records_who_should_look_at_it(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert "mergency physician" in result.review.refer_to

    def test_the_review_records_the_models_and_panel_version(self) -> None:
        """A critique's authors are models, and the reader should know which."""
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert result.review.models == ("granite4.1:3b",)
        assert result.review.panel_version == PANEL_VERSION


class TestConcerns:
    def test_agreements_become_concerns(self) -> None:
        assert extract_concerns(BRIEF)

    def test_disagreements_are_kept_too(self) -> None:
        """The disagreement is the finding, not a problem to be resolved."""
        concerns = extract_concerns(BRIEF)
        assert any("practice reviewer wants" in c for c in concerns)

    def test_prose_outside_the_sections_is_not_a_concern(self) -> None:
        assert not any("has not verified" in c for c in extract_concerns(BRIEF))

    def test_an_empty_brief_yields_no_concerns(self) -> None:
        assert extract_concerns("") == ()


class TestReferral:
    def test_the_named_specialty_is_taken(self) -> None:
        assert "mergency physician" in extract_referral(BRIEF)

    def test_a_brief_with_no_referral_falls_back(self) -> None:
        """Not 'a clinician': the field exists to route to the right desk."""
        assert extract_referral("## Something\ntext") == DEFAULT_REFERRAL

    def test_the_word_is_not_taken_from_anywhere_in_the_text(self) -> None:
        """'cardiology' appears many times in a cardiology brief."""
        brief = "## What the panel agrees on\ncardiology cardiology\n\n### Refer to\nNephrologist"
        assert extract_referral(brief) == "Nephrologist"


class TestWarnings:
    def test_an_approving_seat_is_flagged(self) -> None:
        result, _ = panel("This rule is clinically sound.", SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert not result.is_clean
        assert result.seats[0].approving

    def test_an_invented_threshold_is_flagged(self) -> None:
        result, _ = panel(
            "Consider pain lasting more than 20 minutes.", SEAT_TEXT, SEAT_TEXT, BRIEF
        )
        assert result.seats[0].proposed_thresholds

    def test_a_truncated_seat_is_flagged(self) -> None:
        result, _ = panel("### Misses\nA 58-year-old", SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert result.seats[0].truncated

    def test_a_clean_panel_carries_no_warnings(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert result.is_clean


class TestRendering:
    def test_the_blocked_notice_leads(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        text = render(result)
        assert text.index("remains blocked from release") < text.index("panel brief")

    def test_the_referral_is_shown(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert "Referred to:" in render(result)

    def test_a_warning_appears_above_the_brief(self) -> None:
        result, _ = panel("This rule is clinically sound.", SEAT_TEXT, SEAT_TEXT, BRIEF)
        text = render(result)
        assert text.index("Warning") < text.index("panel brief")

    def test_the_seat_reviews_are_kept_below_the_brief(self) -> None:
        """A clinician who doubts the summary can read what a seat said."""
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        text = render(result)
        assert "The reviews behind this brief" in text
        assert text.count("58-year-old woman") >= 1

    def test_a_clean_panel_renders_no_warning(self) -> None:
        result, _ = panel(SEAT_TEXT, SEAT_TEXT, SEAT_TEXT, BRIEF)
        assert "Warning" not in render(result)


class TestTheReferralIsReadable:
    """What a real model wrote on the first run, and why it needed cutting back.

    The chair writes this as a sentence. Truncating it at a character count
    produced "A **clinical-epidemiology / emergency medicine** specialist (e"
    in the review record — which looks like a specialty, is not one, and would
    have been read as the panel's considered answer.
    """

    def test_a_prose_referral_is_reduced_to_the_specialty(self) -> None:
        brief = (
            "### Refer to\n"
            "A **clinical\N{NON-BREAKING HYPHEN}epidemiology / emergency medicine** specialist "
            "(e.g., emergency physician or allergy specialist) should review the rule."
        )
        assert extract_referral(brief) == "clinical-epidemiology / emergency medicine specialist"

    def test_a_leading_article_is_dropped(self) -> None:
        assert extract_referral("### Refer to\nAn allergy specialist.") == "allergy specialist"

    def test_a_trailing_clause_is_dropped(self) -> None:
        brief = "### Refer to\nEmergency physician, who should confirm the criteria."
        assert extract_referral(brief) == "Emergency physician"

    def test_a_bare_specialty_survives_unchanged(self) -> None:
        assert extract_referral("### Refer to\nNephrologist") == "Nephrologist"

    def test_nothing_usable_falls_back_rather_than_returning_a_fragment(self) -> None:
        assert extract_referral("### Refer to\n(") == DEFAULT_REFERRAL


class TestConcernsSurviveRealFormatting:
    """What the model actually wrote on the first full run.

    The prompt asks for "### What the panel agrees on". The model wrote
    "**Agreement (All Seats)**". A parser recognising only Markdown headings
    found zero concerns in a brief that was full of them, and the review
    recorded on the rule would have said the panel raised nothing.
    """

    BOLD_HEADINGS = """**=== RF_PERITONISM_001 - Panel Brief ===**

**Headline:** the rule misses patients who do not report pain on movement.

**Agreement (All Seats)**
1. **Missed Patient Profile** - a 45-year-old with diffuse epigastric pain.
2. **Edge-Case Miss** - absent bowel sounds without vomiting fires nothing.

**Disagreement (Where Seats Conflict)**
- Emergency physician versus Indian practice reviewer on pain description.

**Refer to**
Emergency physician.
"""

    def test_bold_headings_are_recognised(self) -> None:
        assert extract_concerns(self.BOLD_HEADINGS)

    def test_both_agreements_and_disagreements_are_collected(self) -> None:
        """A disagreement is a finding, often the most useful one."""
        concerns = extract_concerns(self.BOLD_HEADINGS)
        assert any("Missed Patient Profile" in c for c in concerns)
        assert any("versus Indian practice reviewer" in c for c in concerns)

    def test_the_headline_is_not_collected_as_a_concern(self) -> None:
        assert not any("misses patients who do not report" in c for c in extract_concerns(
            self.BOLD_HEADINGS
        ))

    def test_bold_markers_do_not_survive_into_the_record(self) -> None:
        """A concern reading '**Missed Profile** - ...' is broken markup."""
        assert not any("**" in c for c in extract_concerns(self.BOLD_HEADINGS))

    def test_a_bold_referral_heading_is_found(self) -> None:
        assert extract_referral(self.BOLD_HEADINGS) == "Emergency physician"


class TestReferralsFromTheRealRun:
    """Shapes the chair actually produced over thirty rules.

    Each of these was recorded verbatim on a rule before the tidier handled
    it. The field is meant to route a rule to the right desk, and a sentence
    fragment in it does not.
    """

    def test_a_specialty_label_keeps_only_the_specialty(self) -> None:
        brief = "### Refer to\nSpecialty: Urology / Emergency Medicine"
        assert extract_referral(brief) == "Urology / Emergency Medicine"

    def test_an_em_dash_clause_is_dropped(self) -> None:
        brief = (
            "### Refer to\nSpecialty: Emergency Medicine \N{EM DASH} to evaluate "
            "the clinical impact of missed occult bleeding"
        )
        assert extract_referral(brief) == "Emergency Medicine"

    def test_a_hyphen_clause_is_dropped(self) -> None:
        brief = "### Refer to\nCardiology - to confirm the criteria are wide enough"
        assert extract_referral(brief) == "Cardiology"

    def test_a_purpose_clause_is_dropped(self) -> None:
        brief = "### Refer to\nObstetrics for review of the bleeding threshold"
        assert extract_referral(brief) == "Obstetrics"
