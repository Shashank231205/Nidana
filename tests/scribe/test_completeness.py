"""Note completeness checking.

The same rule engine Consult uses, with Scribe's vocabulary and Scribe's
actions. Nothing here terminates anything: a documentation tool that blocks a
clinician mid-clinic gets switched off.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from services.scribe.clinical.actions import NoteCheckAction
from services.scribe.clinical.completeness import (
    REPRODUCTIVE_AGE_CEILING,
    REPRODUCTIVE_AGE_FLOOR,
    RULE_SECTIONS,
    as_record,
    check,
)
from spine.rules.predicate_loader import load_predicates
from spine.rules.registry_loader import rules_root
from spine.rules.rule_loader import all_rules, load_rule_sets, resolve_atoms, rules_dir
from spine.schemas.note import ClinicalNote, NoteSection, Omission, Statement
from spine.schemas.predicate import Predicate
from spine.schemas.primitives import Sex
from spine.schemas.provenance import locate_transcript
from spine.schemas.record import Demographics
from spine.schemas.rule import RuleSet

SOURCE = "clinician said something here for the span"


@pytest.fixture(scope="module")
def predicates() -> dict[str, Predicate]:
    return load_predicates(rules_root("scribe") / "predicates")


@pytest.fixture(scope="module")
def rule_sets() -> tuple[RuleSet[NoteCheckAction], ...]:
    return load_rule_sets(rules_dir("scribe", "completeness"), NoteCheckAction)


def statement(section: NoteSection, text: str) -> Statement:
    return Statement(
        section=section,
        text=text,
        provenance=locate_transcript(
            source_id="e1",
            source_text=SOURCE,
            quote="something here",
            audio_start_ms=100,
            audio_end_ms=900,
        ),
    )


def note(*sections: NoteSection) -> ClinicalNote:
    return ClinicalNote(
        encounter_id=uuid4(),
        statements=tuple(statement(section, "recorded") for section in sections),
    )


def flags(
    a_note: ClinicalNote,
    rule_sets: tuple[RuleSet[NoteCheckAction], ...],
    predicates: dict[str, Predicate],
    *,
    age: int | None = 40,
    sex: Sex = Sex.MALE,
    prescription: bool = False,
    allergy: bool = True,
    pregnancy: bool = True,
) -> tuple[Omission, ...]:
    record = as_record(
        a_note,
        Demographics(age_years=age, sex=sex),
        prescription_issued=prescription,
        allergy_documented=allergy,
        pregnancy_documented=pregnancy,
    )
    return check(record, rule_sets, predicates)


class TestRuleSetIntegrity:
    def test_every_atom_resolves(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        resolve_atoms(rule_sets, predicates)

    def test_every_rule_carries_a_source(
        self, rule_sets: tuple[RuleSet[NoteCheckAction], ...]
    ) -> None:
        for rule in all_rules(rule_sets):
            assert rule.source.strip()

    def test_every_rule_is_unverified_pending_clinical_review(
        self, rule_sets: tuple[RuleSet[NoteCheckAction], ...]
    ) -> None:
        """Which elements are clinically expected is not an engineering call."""
        assert all(rule.is_unverified for rule in all_rules(rule_sets))

    def test_every_rule_has_a_section_to_surface_in(
        self, rule_sets: tuple[RuleSet[NoteCheckAction], ...]
    ) -> None:
        for rule in all_rules(rule_sets):
            assert rule.id in RULE_SECTIONS, f"{rule.id} has nowhere to surface"

    def test_no_rule_terminates_anything(
        self, rule_sets: tuple[RuleSet[NoteCheckAction], ...]
    ) -> None:
        """Scribe's actions are advisory. Nothing here ends a consultation."""
        permitted = {action.value for action in NoteCheckAction}
        assert all(rule.action in permitted for rule in all_rules(rule_sets))


class TestOmissionDetection:
    def test_a_complete_note_flags_nothing(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        complete = note(
            NoteSection.SUBJECTIVE,
            NoteSection.EXAMINATION,
            NoteSection.ASSESSMENT,
            NoteSection.PLAN,
            NoteSection.FOLLOW_UP,
        )
        assert flags(complete, rule_sets, predicates) == ()

    def test_a_plan_without_a_follow_up_is_flagged(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.SUBJECTIVE, NoteSection.ASSESSMENT, NoteSection.PLAN),
            rule_sets,
            predicates,
        )
        assert "NC_FOLLOWUP_002" in {omission.rule_id for omission in found}

    def test_a_plan_without_an_assessment_is_flagged(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.SUBJECTIVE, NoteSection.PLAN, NoteSection.FOLLOW_UP),
            rule_sets,
            predicates,
        )
        assert "NC_ASSESSMENT_005" in {omission.rule_id for omission in found}

    def test_an_assessment_without_an_examination_flags_rather_than_blocks(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        """A silent examination is not an absent one."""
        found = flags(
            note(
                NoteSection.SUBJECTIVE,
                NoteSection.ASSESSMENT,
                NoteSection.PLAN,
                NoteSection.FOLLOW_UP,
            ),
            rule_sets,
            predicates,
        )
        examination = next(o for o in found if o.rule_id == "NC_EXAMINATION_003")
        assert not examination.blocking


class TestPrescriptionGatedChecks:
    def test_prescribing_without_a_documented_allergy_check_blocks_signing(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.PLAN), rule_sets, predicates, prescription=True, allergy=False
        )
        allergy = next(o for o in found if o.rule_id == "NC_ALLERGY_001")
        assert allergy.blocking

    def test_no_prescription_means_no_allergy_flag(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.PLAN), rule_sets, predicates, prescription=False, allergy=False
        )
        assert "NC_ALLERGY_001" not in {omission.rule_id for omission in found}

    def test_pregnancy_check_applies_to_a_woman_of_reproductive_age(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.PLAN),
            rule_sets,
            predicates,
            age=30,
            sex=Sex.FEMALE,
            prescription=True,
            pregnancy=False,
        )
        assert "NC_PREGNANCY_004" in {omission.rule_id for omission in found}

    def test_the_pregnancy_check_does_not_apply_to_a_man(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.PLAN),
            rule_sets,
            predicates,
            age=30,
            sex=Sex.MALE,
            prescription=True,
            pregnancy=False,
        )
        assert "NC_PREGNANCY_004" not in {omission.rule_id for omission in found}

    @pytest.mark.parametrize(
        ("age", "applies"),
        [
            (REPRODUCTIVE_AGE_FLOOR - 1, False),
            (REPRODUCTIVE_AGE_FLOOR, True),
            (REPRODUCTIVE_AGE_CEILING, True),
            (REPRODUCTIVE_AGE_CEILING + 1, False),
        ],
    )
    def test_the_reproductive_age_boundaries(
        self,
        age: int,
        applies: bool,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.PLAN),
            rule_sets,
            predicates,
            age=age,
            sex=Sex.FEMALE,
            prescription=True,
            pregnancy=False,
        )
        fired = "NC_PREGNANCY_004" in {omission.rule_id for omission in found}
        assert fired is applies

    def test_an_unknown_age_does_not_ask_the_pregnancy_question(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        """A documentation gap, unlike Consult, where absence escalates."""
        found = flags(
            note(NoteSection.PLAN),
            rule_sets,
            predicates,
            age=None,
            sex=Sex.FEMALE,
            prescription=True,
            pregnancy=False,
        )
        assert "NC_PREGNANCY_004" not in {omission.rule_id for omission in found}


class TestSigningInteraction:
    def test_a_blocking_omission_makes_a_note_unsignable(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.PLAN), rule_sets, predicates, prescription=True, allergy=False
        )
        assert not ClinicalNote(encounter_id=uuid4(), omissions=found).is_signable

    def test_flags_alone_never_prevent_signing(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.SUBJECTIVE, NoteSection.ASSESSMENT, NoteSection.PLAN),
            rule_sets,
            predicates,
        )
        assert found
        assert ClinicalNote(encounter_id=uuid4(), omissions=found).is_signable

    def test_an_omission_surfaces_in_the_section_it_belongs_to(
        self,
        rule_sets: tuple[RuleSet[NoteCheckAction], ...],
        predicates: dict[str, Predicate],
    ) -> None:
        found = flags(
            note(NoteSection.SUBJECTIVE, NoteSection.ASSESSMENT, NoteSection.PLAN),
            rule_sets,
            predicates,
        )
        follow_up = next(o for o in found if o.rule_id == "NC_FOLLOWUP_002")
        assert follow_up.section is NoteSection.FOLLOW_UP
