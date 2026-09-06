"""Red flag rules: positive, negative, and boundary cases for each.

The M1 gate requires every rule to have all three. The most important test in
this file is `test_every_rule_can_fire`: it caught a live defect where
RF_ACS_001 referenced a field that existed only in a different complaint
family's registry, so the atom resolved, every negative test passed, and the
rule was dead. Atom resolution alone does not prove a rule is reachable.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from services.consult.clinical import red_flags, routing
from services.consult.clinical.actions import RedFlagAction
from spine.rules.predicate_loader import load_predicates
from spine.rules.predicates import DEMOGRAPHIC_FIELDS
from spine.rules.registry_loader import known_fields, load_all
from spine.rules.rule_loader import all_rules, load_rule_sets, resolve_atoms, rules_dir
from spine.schemas.finding import Finding
from spine.schemas.predicate import Predicate
from spine.schemas.primitives import Band, Confidence, PregnancyStatus, Quantity, Sex
from spine.schemas.provenance import locate_utterance
from spine.schemas.record import ConsultContext, Demographics, Record, SubjectType
from spine.schemas.registry import ComplaintFamily
from spine.schemas.rule import RuleSet
from spine.schemas.triage import Capability

SOURCE = (
    "chest pain two hours goes to my jaw sweating a lot cannot breathe "
    "worst headache stiff neck vomiting bleeding fainting confused "
    "no strength in my arm face is drooping cannot speak properly"
)

FindingValue = str | float | int | bool | Quantity


@pytest.fixture(scope="module")
def predicates() -> dict[str, Predicate]:
    return load_predicates()


@pytest.fixture(scope="module")
def rule_sets() -> tuple[RuleSet[RedFlagAction], ...]:
    return load_rule_sets(rules_dir("consult", "red_flags"), RedFlagAction)


def fact(field: str, value: FindingValue, quote: str = "chest pain") -> Finding:
    return Finding(
        field=field,
        value=value,
        confidence=Confidence.HIGH,
        provenance=locate_utterance(
            source_id="u1", source_text=SOURCE, quote=quote, turn_index=1
        ),
    )


def denial(field: str, quote: str = "chest pain") -> Finding:
    return Finding(
        field=field,
        value=False,
        negated=True,
        confidence=Confidence.HIGH,
        provenance=locate_utterance(
            source_id="u1", source_text=SOURCE, quote=quote, turn_index=1
        ),
    )


def session(
    family: ComplaintFamily | None = None,
    age: int | None = 40,
    sex: Sex = Sex.MALE,
    pregnancy: PregnancyStatus = PregnancyStatus.UNKNOWN,
    *facts: Finding,
) -> Record:
    return Record(
        subject_type=SubjectType.SESSION,
        subject_id=uuid4(),
        demographics=Demographics(age_years=age, sex=sex),
        consult=ConsultContext(complaint_family=family, pregnancy_status=pregnancy),
    ).with_findings(*facts)


class TestRuleSetIntegrity:
    def test_every_atom_resolves(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        resolve_atoms(rule_sets, predicates)

    def test_every_rule_carries_a_source(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...]
    ) -> None:
        for rule in all_rules(rule_sets):
            assert rule.source.strip(), f"{rule.id} has no source citation"

    def test_unverified_rules_are_marked_as_such(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...]
    ) -> None:
        for rule in all_rules(rule_sets):
            if rule.verify_before_ship:
                assert rule.verified_on is None

    def test_every_terminating_rule_declares_facility_capabilities(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...]
    ) -> None:
        for rule in all_rules(rule_sets):
            if rule.action is RedFlagAction.TERMINATE_EMERGENCY:
                assert rule.id in red_flags.RULE_CAPABILITIES, (
                    f"{rule.id} ends the session but names no required capability; "
                    f"routing would then match on distance alone"
                )

    def test_every_rule_has_a_routing_destination(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...]
    ) -> None:
        for rule in all_rules(rule_sets):
            assert rule.id in routing.RULE_SPECIALTY, f"{rule.id} routes nowhere"

    def test_capability_and_routing_tables_name_only_real_rules(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...]
    ) -> None:
        known = {rule.id for rule in all_rules(rule_sets)}
        assert set(red_flags.RULE_CAPABILITIES) <= known
        assert set(routing.RULE_SPECIALTY) <= known


class TestEveryRuleIsReachable:
    """The defect that atom resolution does not catch.

    A rule whose atoms all resolve can still be dead, if an atom tests a field
    that only a different complaint family declares. RF_ACS_001 was dead this
    way: chest_pain_present tested presenting_complaint_text, which only the
    general family declares, so no chest pain record ever satisfied it.
    """

    def test_every_predicate_used_by_a_rule_can_be_true(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        declared = known_fields(load_all()) | DEMOGRAPHIC_FIELDS
        for rule in all_rules(rule_sets):
            for atom in sorted(rule.atoms):
                field = predicates[atom].field
                assert field in declared, (
                    f"{rule.id} uses {atom}, which tests {field!r}. No registry declares "
                    f"it, so the atom is always false and the rule is dead"
                )

    @pytest.mark.parametrize(
        ("rule_id", "record_builder"),
        [
            (
                "RF_ACS_001",
                lambda: session(
                    ComplaintFamily.CHEST_PAIN,
                    62,
                    Sex.MALE,
                    PregnancyStatus.UNKNOWN,
                    fact("radiation", "jaw", "goes to my jaw"),
                ),
            ),
            (
                "RF_STROKE_001",
                lambda: session(
                    ComplaintFamily.NEUROLOGICAL_DEFICIT,
                    70,
                    Sex.MALE,
                    PregnancyStatus.UNKNOWN,
                    fact("face_asymmetry", True, "face is drooping"),
                    fact("onset_speed", "sudden", "chest pain"),
                ),
            ),
            (
                "RF_ECTOPIC_001",
                lambda: session(
                    ComplaintFamily.ABDOMINAL_PAIN, 28, Sex.FEMALE, PregnancyStatus.POSSIBLE
                ),
            ),
            (
                "RF_MENINGISM_001",
                lambda: session(
                    ComplaintFamily.HEADACHE,
                    30,
                    Sex.FEMALE,
                    PregnancyStatus.UNKNOWN,
                    fact("neck_stiffness", True, "stiff neck"),
                    fact("fever_reported", True, "vomiting"),
                ),
            ),
            (
                "RF_SUICIDE_RISK_001",
                lambda: session(
                    ComplaintFamily.MENTAL_HEALTH,
                    30,
                    Sex.MALE,
                    PregnancyStatus.UNKNOWN,
                    fact("suicidal_ideation", True, "chest pain"),
                    fact("suicidal_plan", True, "vomiting"),
                ),
            ),
            ("RF_UNDER_TWO_001", lambda: session(ComplaintFamily.FEVER, 1)),
        ],
    )
    def test_named_rules_fire_on_a_matching_record(
        self,
        rule_id: str,
        record_builder: object,
        rule_sets: tuple[RuleSet[RedFlagAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        record = record_builder()  # type: ignore[operator]
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert rule_id in outcome.rule_ids


class TestAcuteCoronarySyndrome:
    def test_fires_on_radiation_to_jaw(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            55,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("radiation", "jaw", "goes to my jaw"),
        )
        assert "RF_ACS_001" in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_fires_on_diaphoresis(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            55,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("diaphoresis", True, "sweating a lot"),
        )
        assert "RF_ACS_001" in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_does_not_fire_on_chest_pain_alone(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(ComplaintFamily.CHEST_PAIN, 55)
        assert "RF_ACS_001" not in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_does_not_fire_when_features_are_denied(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            55,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            denial("diaphoresis", "sweating a lot"),
            fact("radiation", "none", "chest pain"),
        )
        assert "RF_ACS_001" not in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_dyspnoea_route_requires_age_over_forty(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        young = session(
            ComplaintFamily.CHEST_PAIN,
            39,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("dyspnoea", True, "cannot breathe"),
        )
        older = session(
            ComplaintFamily.CHEST_PAIN,
            41,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("dyspnoea", True, "cannot breathe"),
        )
        assert "RF_ACS_001" not in red_flags.evaluate(young, rule_sets, predicates).rule_ids
        assert "RF_ACS_001" in red_flags.evaluate(older, rule_sets, predicates).rule_ids

    def test_age_boundary_is_strictly_over_forty(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        exactly_forty = session(
            ComplaintFamily.CHEST_PAIN,
            40,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("dyspnoea", True, "cannot breathe"),
        )
        assert (
            "RF_ACS_001" not in red_flags.evaluate(exactly_forty, rule_sets, predicates).rule_ids
        )

    def test_requires_a_cath_lab_and_emergency_cover(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            55,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("radiation", "jaw", "goes to my jaw"),
        )
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert Capability.CATH_LAB in outcome.required_capabilities
        assert Capability.EMERGENCY_24X7 in outcome.required_capabilities

    def test_escalates_over_sixty(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            72,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("radiation", "jaw", "goes to my jaw"),
        )
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert "age_over_60" in outcome.matched_atoms


class TestPregnancyModifiers:
    """Tested separately, as the M1 gate requires."""

    def test_ectopic_fires_on_possible_pregnancy_not_only_confirmed(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        possible = session(
            ComplaintFamily.ABDOMINAL_PAIN, 28, Sex.FEMALE, PregnancyStatus.POSSIBLE
        )
        assert "RF_ECTOPIC_001" in red_flags.evaluate(possible, rule_sets, predicates).rule_ids

    def test_ectopic_does_not_fire_when_pregnancy_is_not_applicable(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.ABDOMINAL_PAIN, 28, Sex.MALE, PregnancyStatus.NOT_APPLICABLE
        )
        assert "RF_ECTOPIC_001" not in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_unknown_pregnancy_status_does_not_suppress_the_female_route(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.ABDOMINAL_PAIN,
            28,
            Sex.FEMALE,
            PregnancyStatus.UNKNOWN,
            fact("vaginal_bleeding", True, "bleeding"),
        )
        assert "RF_ECTOPIC_001" in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_obstetric_bleeding_requires_moderate_or_heavy(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        spotting = session(
            ComplaintFamily.OBSTETRIC,
            30,
            Sex.FEMALE,
            PregnancyStatus.CONFIRMED,
            fact("vaginal_bleeding", "spotting", "bleeding"),
        )
        heavy = session(
            ComplaintFamily.OBSTETRIC,
            30,
            Sex.FEMALE,
            PregnancyStatus.CONFIRMED,
            fact("vaginal_bleeding", "heavy", "bleeding"),
        )
        assert (
            "RF_OBSTETRIC_BLEED_001"
            not in red_flags.evaluate(spotting, rule_sets, predicates).rule_ids
        )
        assert (
            "RF_OBSTETRIC_BLEED_001"
            in red_flags.evaluate(heavy, rule_sets, predicates).rule_ids
        )


class TestPaediatricModifiers:
    """Tested separately, as the M1 gate requires."""

    def test_under_two_always_fires(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(ComplaintFamily.FEVER, 1)
        assert "RF_UNDER_TWO_001" in red_flags.evaluate(record, rule_sets, predicates).rule_ids

    def test_under_two_routes_to_a_human(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(ComplaintFamily.FEVER, 1)
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert routing.resolve_specialty(record, outcome, Band.U1).value == "human_review"

    def test_the_under_two_boundary_is_strict(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        two_years = session(ComplaintFamily.FEVER, 2)
        assert (
            "RF_UNDER_TWO_001"
            not in red_flags.evaluate(two_years, rule_sets, predicates).rule_ids
        )

    def test_paediatric_danger_signs_fire_under_five(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.FEVER,
            4,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("altered_consciousness", True, "confused"),
        )
        assert (
            "RF_PAEDIATRIC_DANGER_001"
            in red_flags.evaluate(record, rule_sets, predicates).rule_ids
        )

    def test_paediatric_danger_signs_do_not_fire_at_five(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.FEVER,
            5,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("altered_consciousness", True, "confused"),
        )
        assert (
            "RF_PAEDIATRIC_DANGER_001"
            not in red_flags.evaluate(record, rule_sets, predicates).rule_ids
        )

    def test_an_unknown_age_does_not_fire_paediatric_rules(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.FEVER,
            None,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("altered_consciousness", True, "confused"),
        )
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert "RF_UNDER_TWO_001" not in outcome.rule_ids
        assert "RF_PAEDIATRIC_DANGER_001" not in outcome.rule_ids


class TestOutcomeShape:
    def test_a_quiet_record_fires_nothing(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        outcome = red_flags.evaluate(session(ComplaintFamily.HEADACHE, 24), rule_sets, predicates)
        assert not outcome.fired
        assert not outcome.terminates_session
        assert outcome.required_capabilities == ()

    def test_terminating_rules_end_the_session(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            55,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("radiation", "jaw", "goes to my jaw"),
        )
        assert red_flags.evaluate(record, rule_sets, predicates).terminates_session

    def test_an_escalating_rule_does_not_end_the_session(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.OBSTETRIC,
            30,
            Sex.FEMALE,
            PregnancyStatus.CONFIRMED,
            fact("fetal_movements", "reduced", "chest pain"),
        )
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert "RF_REDUCED_FETAL_MOVEMENT_001" in outcome.escalating_rule_ids
        assert not outcome.terminates_session

    def test_unverified_firings_are_reported(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.CHEST_PAIN,
            55,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("radiation", "jaw", "goes to my jaw"),
        )
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert "RF_ACS_001" in outcome.unverified_rule_ids

    def test_multiple_firings_union_their_capabilities(
        self, rule_sets: tuple[RuleSet[RedFlagAction], ...], predicates: dict[str, Predicate]
    ) -> None:
        record = session(
            ComplaintFamily.NEUROLOGICAL_DEFICIT,
            70,
            Sex.MALE,
            PregnancyStatus.UNKNOWN,
            fact("face_asymmetry", True, "face is drooping"),
            fact("onset_speed", "sudden", "chest pain"),
            fact("seizure_activity", True, "confused"),
        )
        outcome = red_flags.evaluate(record, rule_sets, predicates)
        assert len(outcome.rule_ids) >= 2
        assert Capability.CT_SCANNER in outcome.required_capabilities
        assert Capability.EMERGENCY_24X7 in outcome.required_capabilities
