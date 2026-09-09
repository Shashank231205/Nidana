"""Rule loading, atom resolution, and the release gate.

Two gates live in the loader. Atom resolution is ADR 0005. The verification gate
is what stops an unverified clinical criterion reaching a patient by being
forgotten: a release build refuses to start while any active rule still carries
verify_before_ship.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from services.consult.clinical.actions import RedFlagAction
from spine.rules.predicate_loader import load_predicates
from spine.rules.rule_loader import (
    RuleLoadError,
    UnverifiedRulesError,
    all_rules,
    load_rule_set,
    load_rule_sets,
    require_verified,
    resolve_atoms,
    rules_dir,
)
from spine.schemas.predicate import Comparator, Predicate
from spine.schemas.rule import (
    AiReview,
    Clause,
    ModelAttestation,
    Rule,
    VerificationState,
)

UNVERIFIED_SET = """
name: test_rules
version: 0.1.0
rules:
  - id: RF_TEST_001
    label: A test criterion
    any_of:
      - all_of: [atom_one, atom_two]
      - all_of: [atom_three]
    modifiers:
      escalate_if: [atom_four]
    action: TERMINATE_EMERGENCY
    source: PLACEHOLDER pending clinician review.
    verify_before_ship: true
"""

VERIFIED_SET = """
name: verified_rules
version: 1.0.0
rules:
  - id: RF_SCOPE_001
    label: A scope boundary, not a clinical threshold
    any_of:
      - all_of: [atom_one]
    action: ANNOTATE
    source: Product scope decision.
    verified_on: 2026-09-06
    verified_by: Dr Test Reviewer
    verify_before_ship: false
"""


@pytest.fixture
def rule_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "red_flags"
    directory.mkdir()
    return directory


@pytest.fixture
def atoms() -> dict[str, Predicate]:
    return {
        name: Predicate(id=name, field="diaphoresis", comparator=Comparator.IS_TRUE)
        for name in ("atom_one", "atom_two", "atom_three", "atom_four")
    }


def write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


class TestLoadingOneSet:
    def test_loads_a_valid_rule_set(self, rule_dir: Path) -> None:
        path = write(rule_dir, "test.yaml", UNVERIFIED_SET)
        loaded = load_rule_set(path, RedFlagAction)
        assert loaded.name == "test_rules"
        assert len(loaded.rules) == 1

    def test_a_missing_file_names_the_path(self, tmp_path: Path) -> None:
        with pytest.raises(RuleLoadError, match="no rule set at"):
            load_rule_set(tmp_path / "absent.yaml", RedFlagAction)

    def test_malformed_yaml_names_the_file(self, rule_dir: Path) -> None:
        path = write(rule_dir, "bad.yaml", "rules: [unclosed")
        with pytest.raises(RuleLoadError, match="not valid YAML"):
            load_rule_set(path, RedFlagAction)

    def test_a_non_mapping_document_is_rejected(self, rule_dir: Path) -> None:
        path = write(rule_dir, "bad.yaml", "- a\n- list\n")
        with pytest.raises(RuleLoadError, match="must contain a mapping"):
            load_rule_set(path, RedFlagAction)

    def test_an_unknown_action_is_rejected_at_load(self, rule_dir: Path) -> None:
        """The service's vocabulary is checked here, not when the rule fires."""
        path = write(
            rule_dir, "bad.yaml", UNVERIFIED_SET.replace("TERMINATE_EMERGENCY", "SEND_A_LETTER")
        )
        with pytest.raises(RuleLoadError, match="not a valid rule set"):
            load_rule_set(path, RedFlagAction)

    def test_a_rule_without_a_source_is_rejected(self, rule_dir: Path) -> None:
        path = write(
            rule_dir,
            "bad.yaml",
            "name: n\nversion: 1\nrules:\n  - id: RF_X\n    label: x\n"
            "    any_of:\n      - all_of: [atom_one]\n    action: ANNOTATE\n",
        )
        with pytest.raises(RuleLoadError, match="not a valid rule set"):
            load_rule_set(path, RedFlagAction)


class TestLoadingADirectory:
    def test_loads_every_file(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        write(rule_dir, "b.yaml", VERIFIED_SET)
        assert len(load_rule_sets(rule_dir, RedFlagAction)) == 2

    def test_a_missing_directory_names_itself(self, tmp_path: Path) -> None:
        with pytest.raises(RuleLoadError, match="does not exist"):
            load_rule_sets(tmp_path / "absent", RedFlagAction)

    def test_an_empty_directory_is_rejected(self, rule_dir: Path) -> None:
        with pytest.raises(RuleLoadError, match="no rule files"):
            load_rule_sets(rule_dir, RedFlagAction)

    def test_a_duplicate_rule_id_across_files_names_both(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        write(rule_dir, "b.yaml", UNVERIFIED_SET.replace("name: test_rules", "name: other_rules"))
        with pytest.raises(RuleLoadError, match="exactly one rule"):
            load_rule_sets(rule_dir, RedFlagAction)

    def test_all_rules_flattens_across_sets(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        write(rule_dir, "b.yaml", VERIFIED_SET)
        assert len(all_rules(load_rule_sets(rule_dir, RedFlagAction))) == 2


class TestAtomResolution:
    def test_resolved_atoms_pass(self, rule_dir: Path, atoms: dict[str, Predicate]) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        resolve_atoms(load_rule_sets(rule_dir, RedFlagAction), atoms)

    def test_an_unresolved_atom_fails_the_load(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        with pytest.raises(RuleLoadError, match="cannot fire"):
            resolve_atoms(load_rule_sets(rule_dir, RedFlagAction), {})

    def test_the_error_names_the_rule_and_the_atom(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        with pytest.raises(RuleLoadError) as caught:
            resolve_atoms(load_rule_sets(rule_dir, RedFlagAction), {})
        message = str(caught.value)
        assert "RF_TEST_001" in message
        assert "atom_one" in message

    def test_modifier_atoms_are_resolved_too(
        self, rule_dir: Path, atoms: dict[str, Predicate]
    ) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        without_modifier = {k: v for k, v in atoms.items() if k != "atom_four"}
        with pytest.raises(RuleLoadError, match="atom_four"):
            resolve_atoms(load_rule_sets(rule_dir, RedFlagAction), without_modifier)

    def test_every_unresolved_atom_is_reported_at_once(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        with pytest.raises(RuleLoadError) as caught:
            resolve_atoms(load_rule_sets(rule_dir, RedFlagAction), {})
        assert "4 rule atom(s)" in str(caught.value)


class TestVerificationGate:
    """An unverified criterion cannot ship by being forgotten."""

    def test_development_proceeds_with_unverified_rules(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        require_verified(load_rule_sets(rule_dir, RedFlagAction), allow_unverified=True)

    def test_release_refuses_unverified_rules(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        with pytest.raises(UnverifiedRulesError, match="cannot ship"):
            require_verified(load_rule_sets(rule_dir, RedFlagAction), allow_unverified=False)

    def test_the_refusal_names_each_pending_rule_and_its_source(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        with pytest.raises(UnverifiedRulesError) as caught:
            require_verified(load_rule_sets(rule_dir, RedFlagAction), allow_unverified=False)
        message = str(caught.value)
        assert "RF_TEST_001" in message
        assert "PLACEHOLDER" in message
        assert "NIDANA_ALLOW_UNVERIFIED_RULES" in message

    def test_a_verified_rule_set_ships(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", VERIFIED_SET)
        require_verified(load_rule_sets(rule_dir, RedFlagAction), allow_unverified=False)

    def test_one_unverified_rule_blocks_a_mixed_set(self, rule_dir: Path) -> None:
        write(rule_dir, "a.yaml", UNVERIFIED_SET)
        write(rule_dir, "b.yaml", VERIFIED_SET)
        with pytest.raises(UnverifiedRulesError, match="1 rule"):
            require_verified(load_rule_sets(rule_dir, RedFlagAction), allow_unverified=False)


class TestShippedRules:
    def test_the_shipped_red_flags_load_and_resolve(self) -> None:
        sets = load_rule_sets(rules_dir("consult", "red_flags"), RedFlagAction)
        resolve_atoms(sets, load_predicates())

    def test_the_shipped_rules_cannot_ship_to_production_yet(self) -> None:
        """Thirty of thirty-one criteria await clinician verification."""
        sets = load_rule_sets(rules_dir("consult", "red_flags"), RedFlagAction)
        with pytest.raises(UnverifiedRulesError):
            require_verified(sets, allow_unverified=False)

    def test_rules_dir_points_into_the_named_service(self) -> None:
        assert rules_dir("consult", "red_flags").parts[-3:] == ("consult", "rules", "red_flags")


class TestTheThreeVerificationStates:
    """Unreviewed, AI-reviewed, clinician-verified.

    The middle state exists because "a panel of models read this rule and
    refers it to a clinician" is a real thing that happened and is worth
    recording. It is not verification, and the tests here pin both halves of
    that: it is visible as progress, and it opens nothing.
    """

    def rule(
        self,
        *,
        verified: bool = False,
        review: AiReview | None = None,
    ) -> Rule[RedFlagAction]:
        return Rule[RedFlagAction](
            id="RF_TEST_001",
            label="Test rule",
            any_of=(Clause(all_of=("chest_pain_present",)),),
            action=RedFlagAction.TERMINATE_EMERGENCY,
            source="PLACEHOLDER",
            verify_before_ship=not verified,
            verified_on=date(2026, 1, 1) if verified else None,
            verified_by="Dr A Reviewer" if verified else None,
            review=review,
        )

    def review(self) -> AiReview:
        return AiReview(
            reviewed_on=date(2026, 9, 9),
            models=("granite4.1:3b",),
            panel_version="1.0.0",
            concerns=("Every branch requires chest pain.",),
            refer_to="emergency physician",
        )

    def test_an_untouched_rule_is_unreviewed(self) -> None:
        assert self.rule().state is VerificationState.UNREVIEWED

    def test_a_reviewed_rule_says_so(self) -> None:
        assert self.rule(review=self.review()).state is VerificationState.AI_REVIEWED

    def test_a_signed_rule_is_clinician_verified(self) -> None:
        assert self.rule(verified=True).state is VerificationState.CLINICIAN_VERIFIED

    def test_an_ai_review_does_not_clear_a_release(self) -> None:
        """The point of the middle state. A gate that accepted it gates nothing."""
        assert self.rule(review=self.review()).blocks_release

    def test_an_ai_review_carries_no_verdict_field(self) -> None:
        """There is nothing on it a caller could mistake for approval."""
        assert not self.review().clears_release

    @pytest.mark.parametrize(
        "referral",
        [
            "Emergency Medicine / Critical Care \N{EN DASH} to evaluate the impact",
            "Urology \N{EM DASH} to decide whether sensitivity is adequate",
            "cardiology - to review the threshold",
            "a specialist who understands Indian practice",
            "allergy specialist (e.g. an immunologist)",
        ],
    )
    def test_a_referral_that_is_a_sentence_is_rejected(self, referral: str) -> None:
        """A cut-off sentence reads as a specialty and is not one.

        These are real strings a panel run wrote before the extractor was
        fixed. The extractor is not the only guard, because a long-running
        panel process holds the module it imported at start.
        """
        with pytest.raises(ValidationError):
            AiReview(
                reviewed_on=date(2026, 9, 9),
                models=("granite4.1:3b",),
                panel_version="1.0.0",
                refer_to=referral,
            )

    def test_a_referral_that_is_a_label_is_rejected(self) -> None:
        """"Specialty: Obstetrics/Gynecology" names the field, not the doctor."""
        with pytest.raises(ValidationError):
            AiReview(
                reviewed_on=date(2026, 9, 9),
                models=("granite4.1:3b",),
                panel_version="1.0.0",
                refer_to="Specialty: Obstetrics/Gynecology",
            )

    @pytest.mark.parametrize(
        "referral",
        ["emergency physician", "Obstetrics/Gynecology", "Urology / Emergency Medicine"],
    )
    def test_a_bare_specialty_is_accepted(self, referral: str) -> None:
        assert AiReview(
            reviewed_on=date(2026, 9, 9),
            models=("granite4.1:3b",),
            panel_version="1.0.0",
            refer_to=referral,
        ).refer_to == referral

    def test_a_review_names_who_should_look_at_it(self) -> None:
        """The most useful thing a panel can offer is the right specialist."""
        assert self.review().refer_to == "emergency physician"

    def test_a_clinician_verified_rule_must_name_the_clinician(self) -> None:
        """verify_before_ship false asserts a person accepted responsibility.

        Without a name the audit trail says a doctor approved this and cannot
        say which, which is worse than saying nobody has.
        """
        with pytest.raises(ValidationError, match="names no clinician"):
            Rule[RedFlagAction](
                id="RF_TEST_002",
                label="Test",
                any_of=(Clause(all_of=("chest_pain_present",)),),
                action=RedFlagAction.TERMINATE_EMERGENCY,
                source="s",
                verify_before_ship=False,
                verified_on=date(2026, 1, 1),
            )

    def test_a_reviewed_rule_can_later_be_verified(self) -> None:
        """The review survives the signature; it is how the work is traceable."""
        signed = self.rule(verified=True, review=self.review())
        assert signed.state is VerificationState.CLINICIAN_VERIFIED
        assert signed.review is not None


class TestModelAttestation:
    """A deployment running a rule on a model's reading, and saying so.

    This state exists because the alternative to admitting it is worse:
    pretending a doctor signed, or refusing to start at all. It is only
    defensible while the admission is load-bearing, which is what these tests
    hold in place.
    """

    def attestation(self, *, drift: tuple[str, ...] = ()) -> ModelAttestation:
        return ModelAttestation(
            attested_on=date(2026, 9, 10),
            attested_by=("granite4.1:3b",),
            accepted_by="S Shashank, CTO",
            panel_version="1.0.0",
            drift=drift,
        )

    def rule(self, **fields: object) -> Rule[RedFlagAction]:
        return Rule[RedFlagAction](
            id="RF_TEST_003",
            label="Test rule",
            any_of=(Clause(all_of=("chest_pain_present",)),),
            action=RedFlagAction.TERMINATE_EMERGENCY,
            source="PLACEHOLDER",
            verify_before_ship=True,
            **fields,
        )

    def test_an_attested_rule_reports_that_state(self) -> None:
        assert (
            self.rule(attestation=self.attestation()).state
            is VerificationState.MODEL_ATTESTED
        )

    def test_an_attested_rule_does_not_block_a_release(self) -> None:
        """The deployment accepted this risk with a name against it."""
        assert not self.rule(attestation=self.attestation()).blocks_release

    def test_an_attested_rule_discloses_on_every_output(self) -> None:
        """The admission is what makes the state defensible.

        A rule that ran on a model's reading and said nothing about it would
        be indistinguishable, in the record, from one a clinician signed.
        """
        disclosure = self.rule(attestation=self.attestation()).disclosure
        assert disclosure is not None
        assert "not reviewed by a clinician" in disclosure
        assert "granite4.1:3b" in disclosure

    def test_a_clinician_verified_rule_discloses_nothing(self) -> None:
        signed = Rule[RedFlagAction](
            id="RF_TEST_004",
            label="Test",
            any_of=(Clause(all_of=("chest_pain_present",)),),
            action=RedFlagAction.TERMINATE_EMERGENCY,
            source="s",
            verify_before_ship=False,
            verified_on=date(2026, 1, 1),
            verified_by="Dr A Reviewer",
        )
        assert signed.disclosure is None

    def test_an_attestation_can_never_claim_to_be_a_clinician(self) -> None:
        """A property, not a field, so no YAML or payload can set it true."""
        assert not self.attestation().is_clinician

    def test_the_drift_count_travels_with_the_label(self) -> None:
        """The panel invented four clinical thresholds on its first eight rules.

        Whoever reads an attested rule needs that number beside it, not in a
        log they will not open.
        """
        attested = self.rule(
            attestation=self.attestation(drift=("proposed unsourced thresholds",))
        )
        assert attested.disclosure is not None
        assert "1 drift warning" in attested.disclosure

    def test_an_unattested_reviewed_rule_still_blocks(self) -> None:
        """A panel review alone changes nothing about the gate."""
        reviewed = self.rule(
            review=AiReview(
                reviewed_on=date(2026, 9, 9),
                models=("granite4.1:3b",),
                panel_version="1.0.0",
                refer_to="emergency physician",
            )
        )
        assert reviewed.blocks_release
        assert reviewed.state is VerificationState.AI_REVIEWED

    def test_an_attestation_names_who_accepted_the_risk(self) -> None:
        assert self.attestation().accepted_by == "S Shashank, CTO"
