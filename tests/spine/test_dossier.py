"""Assembling a reviewing clinician's reading for an unverified rule.

The dossier exists to shorten a clinician's work, and every test here is
really about the ways that could go wrong. A dossier that reads as a review,
that implies the corpus endorsed a rule it never mentions, or that quietly
turns an outage into silence would each be worse than no dossier at all,
because a reviewer skimming thirty of them would take any of the three at face
value.

The index is stubbed. What is tested is what the dossier does with what
retrieval returns, which is where those failures live.
"""

from __future__ import annotations

from datetime import date

import pytest

from services.consult.clinical.actions import RedFlagAction
from spine.knowledge.index import KnowledgeIndex, Passage
from spine.knowledge.retrieval import RetrievalUnavailableError
from spine.knowledge.sources import Source, Tier
from spine.rules import dossier as dossier_module
from spine.rules.dossier import build_dossier, questions_for, render
from spine.schemas.rule import Clause, Modifiers, Rule


def source() -> Source:
    return Source(
        id="iphs_i",
        title="IPHS 2022 Volume I",
        publisher="MoHFW",
        tier=Tier.NATIONAL_GUIDELINE,
        version="2022",
        url="https://example.invalid/iphs",
        covers=("facility standards",),
        licence="Government of India",
    )


def passage(text: str, start: int = 0) -> Passage:
    return Passage(
        chunk_id=f"iphs_i:{start}",
        source=source(),
        text=text,
        score=0.74,
        char_start=start,
        char_end=start + len(text),
    )


def rule(
    *,
    rule_id: str = "RF_TEST_001",
    verify: bool = True,
    notes: str | None = None,
) -> Rule[RedFlagAction]:
    return Rule[RedFlagAction](
        id=rule_id,
        label="Possible acute coronary syndrome",
        any_of=(Clause(all_of=("chest_pain_present", "diaphoresis_present")),),
        modifiers=Modifiers(escalate_if=("age_over_60",)),
        action=RedFlagAction.TERMINATE_EMERGENCY,
        source="PLACEHOLDER pending clinician review.",
        verify_before_ship=verify,
        verified_on=None if verify else date(2026, 1, 1),
        verified_by=None if verify else "Dr Test Reviewer",
        notes=notes,
    )


class StubIndex:
    """Stands in for a built index, returning whatever the test needs."""

    def __init__(self, passages: list[Passage] | None = None) -> None:
        self.passages = passages or []
        self.questions: list[str] = []


def patch_ask(monkeypatch: pytest.MonkeyPatch, stub: StubIndex) -> None:
    def fake_ask(_index: object, question: str, **_: object) -> object:
        stub.questions.append(question)

        class _Answer:
            passages = tuple(stub.passages)

        return _Answer()

    monkeypatch.setattr(dossier_module, "ask", fake_ask)


def patch_ask_failing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_ask(_index: object, _question: str, **_: object) -> object:
        raise RetrievalUnavailableError("ollama is not running")

    monkeypatch.setattr(dossier_module, "ask", fake_ask)


class TestQuestions:
    def test_questions_come_from_the_rule_not_a_hand_written_list(self) -> None:
        """A rule added later must be covered without anyone remembering it."""
        questions = questions_for(rule())
        assert any("acute coronary syndrome" in q for q in questions)

    def test_the_criteria_are_asked_about(self) -> None:
        assert any("chest pain present" in q for q in questions_for(rule()))

    def test_underscores_become_words(self) -> None:
        """The corpus is prose; predicate ids are not."""
        assert not any("chest_pain_present" in q for q in questions_for(rule()))


class TestBuilding:
    def test_passages_are_collected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_ask(monkeypatch, StubIndex([passage("A district hospital shall stock.")]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert len(built.evidence) == 1

    def test_a_repeated_passage_is_not_repeated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same passage answers several of a rule's questions.

        Repeating it inflates the dossier without adding evidence, and a
        reviewer counting passages would over-read the corpus's support.
        """
        patch_ask(monkeypatch, StubIndex([passage("One paragraph.")]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert len(built.evidence) == 1

    def test_each_passage_keeps_the_question_that_found_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A passage detached from its query reads as an endorsement."""
        patch_ask(monkeypatch, StubIndex([passage("Text.")]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert built.evidence[0].question in built.questions_asked

    def test_an_empty_corpus_is_reported_as_silent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert built.corpus_silent
        assert not built.retrieval_failed

    def test_an_outage_is_not_silence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The corpus not covering a rule and the model being down are
        different facts, and a reviewer would act differently on each."""
        patch_ask_failing(monkeypatch)
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert built.retrieval_failed
        assert not built.corpus_silent

    def test_an_outage_stops_asking_rather_than_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Thirty dossiers should not fail on the ninth."""
        patch_ask_failing(monkeypatch)
        assert build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)) is not None


class TestTheFlagIsNeverCleared:
    def test_an_unverified_rule_stays_unverified(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Retrieval is not a signature. This is the point of the module."""
        patch_ask(monkeypatch, StubIndex([passage("Highly relevant guidance.")]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert built.still_needs_verification
        assert built.rule.verify_before_ship

    def test_evidence_does_not_change_the_rule(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([passage("Guidance.")]))
        original = rule()
        built = build_dossier(original, KnowledgeIndex.__new__(KnowledgeIndex))
        assert built.rule == original


class TestOpenQuestions:
    def test_the_four_recurring_gaps_are_always_asked(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([passage("Guidance.")]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert len(built.open_questions) >= 4

    def test_silence_adds_a_question_rather_than_removing_them(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert any("corpus holds nothing" in q for q in built.open_questions)

    def test_the_action_is_named_as_a_decision(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trigger and action are separate clinical judgements."""
        patch_ask(monkeypatch, StubIndex([]))
        built = build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex))
        assert any("right action" in q for q in built.open_questions)


class TestRendering:
    def test_the_status_leads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The likeliest misreading is that a dossier is a review."""
        patch_ask(monkeypatch, StubIndex([passage("Guidance.")]))
        text = render(build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)))
        assert "Status: unverified" in text
        assert "not a review" in text

    def test_a_passage_is_quoted_with_its_citation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([passage("A district hospital shall stock.")]))
        text = render(build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)))
        assert "> A district hospital shall stock." in text
        assert "IPHS 2022 Volume I" in text

    def test_silence_says_so_plainly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        patch_ask(monkeypatch, StubIndex([]))
        text = render(build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)))
        assert "Nothing." in text

    def test_an_outage_warns_against_reading_it_as_silence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask_failing(monkeypatch)
        text = render(build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)))
        assert "Retrieval was unavailable" in text

    def test_the_encoded_criteria_are_shown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reviewer checks the encoding, not only the concept."""
        patch_ask(monkeypatch, StubIndex([]))
        text = render(build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)))
        assert "chest_pain_present AND diaphoresis_present" in text
        assert "age_over_60" in text

    def test_an_existing_note_is_carried_forward(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The notes already on these rules are the previous reviewer's work."""
        patch_ask(monkeypatch, StubIndex([]))
        built = build_dossier(
            rule(notes="Diabetes prevalence argues for a lower threshold."),
            KnowledgeIndex.__new__(KnowledgeIndex),
        )
        assert "Diabetes prevalence" in render(built)

    def test_the_signing_instruction_is_included(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([]))
        text = render(build_dossier(rule(), KnowledgeIndex.__new__(KnowledgeIndex)))
        assert "verify_before_ship: false" in text
        assert "verified_on" in text

    def test_a_verified_rule_renders_its_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        patch_ask(monkeypatch, StubIndex([]))
        text = render(
            build_dossier(rule(verify=False), KnowledgeIndex.__new__(KnowledgeIndex))
        )
        assert "Status: verified on 2026-01-01" in text
