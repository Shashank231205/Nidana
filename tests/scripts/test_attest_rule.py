"""Attesting a rule is the one action that lets an unverified criterion ship.

These pin what the record must say when it happens. The danger is not that the
state exists; it is that the record reads as more than it was, so every test
here is about the attestation refusing to overstate itself.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.attest_rule import attest
from services.consult.clinical.actions import RedFlagAction
from spine.rules.rule_loader import all_rules, load_rule_sets
from spine.schemas.rule import VerificationState

RULE = """name: test
version: "1.0.0"
rules:
  - id: RF_TEST_001
    label: A rule under test
    any_of:
      - all_of: [chest_pain_present]
    action: TERMINATE_EMERGENCY
    source: PLACEHOLDER pending clinician review.
    verify_before_ship: true
    review:
      reviewed_on: 2026-09-09
      models: [granite4.1:3b]
      panel_version: 1.0.0
      refer_to: "emergency physician"
"""


@pytest.fixture
def rules(tmp_path: Path) -> Path:
    directory = tmp_path / "red_flags"
    directory.mkdir()
    (directory / "test.yaml").write_text(RULE, encoding="utf-8")
    return directory


def only_rule(directory: Path) -> object:
    loaded = all_rules(load_rule_sets(directory, RedFlagAction))
    return next(rule for rule in loaded if rule.id == "RF_TEST_001")


def attest_it(directory: Path, accepted_by: str, drift: tuple[str, ...] = ()) -> None:
    written = attest(
        directory / "test.yaml",
        "RF_TEST_001",
        accepted_by=accepted_by,
        models=("granite4.1:3b",),
        panel_version="1.0.0",
        drift=drift,
        on=date(2026, 9, 10),
    )
    assert written


class TestBeforeAttesting:
    def test_a_reviewed_rule_still_blocks(self, rules: Path) -> None:
        """A panel reading shortens a clinician's work; it does not replace it."""
        rule = only_rule(rules)
        assert rule.state is VerificationState.AI_REVIEWED  # type: ignore[attr-defined]
        assert rule.blocks_release  # type: ignore[attr-defined]


class TestAfterAttesting:
    def test_the_rule_ships(self, rules: Path) -> None:
        attest_it(rules, "Model (granite4.1:3b)")
        rule = only_rule(rules)
        assert rule.state is VerificationState.MODEL_ATTESTED  # type: ignore[attr-defined]
        assert not rule.blocks_release  # type: ignore[attr-defined]

    def test_it_never_claims_a_clinician(self, rules: Path) -> None:
        """The whole state rests on this staying false."""
        attest_it(rules, "Model (granite4.1:3b)")
        rule = only_rule(rules)
        assert rule.attestation is not None  # type: ignore[attr-defined]
        assert rule.attestation.is_clinician is False  # type: ignore[attr-defined]
        assert rule.verified_by is None  # type: ignore[attr-defined]

    def test_a_model_acceptor_is_labelled_a_model(self, rules: Path) -> None:
        """Where nobody signs, the record says a model decided.

        The prefix matters: "granite4.1:3b" alone in a field describing who
        accepted a risk could be read as an identifier for a person or a team.
        """
        attest_it(rules, "Model (granite4.1:3b)")
        rule = only_rule(rules)
        assert rule.attestation.accepted_by.startswith("Model (")  # type: ignore[attr-defined]

    def test_the_disclosure_names_the_model_and_the_absence(self, rules: Path) -> None:
        attest_it(rules, "Model (granite4.1:3b)")
        disclosure = only_rule(rules).disclosure  # type: ignore[attr-defined]
        assert "granite4.1:3b" in disclosure
        assert "not reviewed by a clinician" in disclosure

    def test_the_disclosure_carries_the_drift_count(self, rules: Path) -> None:
        """A deployment reading this back sees what the panel got wrong."""
        attest_it(rules, "Model (granite4.1:3b)", drift=("invented a threshold",))
        assert "1 drift warning" in only_rule(rules).disclosure  # type: ignore[attr-defined]

    def test_a_named_person_is_recorded_as_given(self, rules: Path) -> None:
        attest_it(rules, "S Shashank, CTO")
        rule = only_rule(rules)
        assert rule.attestation.accepted_by == "S Shashank, CTO"  # type: ignore[attr-defined]
        assert rule.attestation.is_clinician is False  # type: ignore[attr-defined]
