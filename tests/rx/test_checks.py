"""Rx safety checks.

Deterministic throughout. No model decides whether two drugs interact, and
nothing here computes a dose.

The check that most justifies Rx being part of a platform is duplicate therapy:
it only works against the patient's full list, and it is invisible to a patient
reading two different brand names.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from services.rx.clinical import checks
from services.rx.clinical.checks import CheckKind, Severity
from spine.schemas.medication import (
    MedicationList,
    Molecule,
    PrescribedMedication,
    ResolutionStatus,
    Route,
)
from spine.schemas.primitives import PregnancyStatus, Sex
from spine.schemas.provenance import BoundingBox, OcrRegion
from spine.schemas.record import Allergy, ConsultContext, Demographics, Record, SubjectType


def region(line: int = 1) -> OcrRegion:
    return OcrRegion(
        source_id="rx.jpg",
        box=BoundingBox(x=10, y=line * 30, width=200, height=25),
        text=f"line {line}",
        ocr_confidence=0.8,
    )


def medication(
    written: str,
    molecules: tuple[str, ...] = (),
    *,
    resolution: ResolutionStatus = ResolutionStatus.RESOLVED,
    confidence: float = 0.95,
    candidates: tuple[str, ...] = (),
) -> PrescribedMedication:
    return PrescribedMedication(
        written_as=written,
        molecules=tuple(Molecule(name=name) for name in molecules),
        resolution=resolution,
        resolution_confidence=confidence,
        provenance=region(len(written)),
        candidates=candidates,
        route=Route.ORAL,
    )


def patient(
    *allergies: str,
    pregnancy: PregnancyStatus = PregnancyStatus.NOT_APPLICABLE,
    sex: Sex = Sex.MALE,
) -> Record:
    return Record(
        subject_type=SubjectType.PRESCRIPTION,
        subject_id=uuid4(),
        demographics=Demographics(age_years=52, sex=sex),
        allergies=tuple(Allergy(substance=name) for name in allergies),
        consult=ConsultContext(pregnancy_status=pregnancy),
    )


class TestMedicationShape:
    def test_a_resolved_line_must_name_a_molecule(self) -> None:
        with pytest.raises(ValueError, match="REFUSED, not RESOLVED"):
            medication("Glycomet", ())

    def test_a_refusal_may_not_still_assert_an_answer(self) -> None:
        with pytest.raises(ValueError, match="not a refusal"):
            medication("Ecosprin", ("aspirin",), resolution=ResolutionStatus.REFUSED)

    def test_ambiguity_must_list_more_than_one_candidate(self) -> None:
        with pytest.raises(ValueError, match="more than one reading"):
            medication(
                "Zyloric?",
                (),
                resolution=ResolutionStatus.AMBIGUOUS,
                candidates=("allopurinol",),
            )

    def test_an_ambiguous_line_listing_its_candidates_is_valid(self) -> None:
        line = medication(
            "Zyloric?",
            (),
            resolution=ResolutionStatus.AMBIGUOUS,
            candidates=("allopurinol", "zolpidem"),
        )
        assert line.needs_human_confirmation

    def test_the_written_form_is_kept_alongside_the_resolution(self) -> None:
        """A pharmacist checks the resolution rather than trusting it."""
        line = medication("Glycomet 500", ("metformin",))
        assert line.written_as == "Glycomet 500"
        assert line.molecule_names == frozenset({"metformin"})

    def test_a_resolved_line_needs_no_confirmation(self) -> None:
        assert not medication("Glycomet 500", ("metformin",)).needs_human_confirmation


class TestDuplicateTherapy:
    def test_the_same_molecule_under_two_brands_is_caught(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet 500", ("metformin",)),
                medication("Metsmall 500", ("metformin",)),
            )
        )
        found = checks.check_duplicate_therapy(medications)
        assert len(found) == 1
        assert found[0].kind is CheckKind.DUPLICATE_THERAPY

    def test_the_finding_names_both_brands(self) -> None:
        """A pharmacist works from the prescription, not a molecule list."""
        medications = MedicationList(
            medications=(
                medication("Glycomet 500", ("metformin",)),
                medication("Metsmall 500", ("metformin",)),
            )
        )
        message = checks.check_duplicate_therapy(medications)[0].message
        assert "Glycomet 500" in message
        assert "Metsmall 500" in message

    def test_different_molecules_are_not_duplicates(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet", ("metformin",)),
                medication("Amoxil", ("amoxicillin",)),
            )
        )
        assert checks.check_duplicate_therapy(medications) == ()

    def test_a_combination_product_sharing_a_molecule_is_caught(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet", ("metformin",)),
                medication("Glycomet-GP", ("metformin", "glimepiride")),
            )
        )
        assert checks.check_duplicate_therapy(medications)[0].molecules == ("metformin",)

    def test_an_empty_list_produces_nothing(self) -> None:
        assert checks.check_duplicate_therapy(MedicationList()) == ()


class TestAllergies:
    def test_a_matching_allergy_is_contraindicated(self) -> None:
        medications = MedicationList(medications=(medication("Amoxil", ("amoxicillin",)),))
        found = checks.check_allergies(medications, patient("Amoxicillin"))
        assert found[0].severity is Severity.CONTRAINDICATED

    def test_matching_is_case_insensitive(self) -> None:
        medications = MedicationList(medications=(medication("Amoxil", ("amoxicillin",)),))
        assert checks.check_allergies(medications, patient("AMOXICILLIN"))

    def test_an_unrelated_allergy_does_not_fire(self) -> None:
        medications = MedicationList(medications=(medication("Amoxil", ("amoxicillin",)),))
        assert checks.check_allergies(medications, patient("sulfa")) == ()

    def test_no_recorded_allergies_produces_nothing(self) -> None:
        medications = MedicationList(medications=(medication("Amoxil", ("amoxicillin",)),))
        assert checks.check_allergies(medications, patient()) == ()

    def test_the_finding_names_the_line_and_the_molecule(self) -> None:
        medications = MedicationList(medications=(medication("Amoxil", ("amoxicillin",)),))
        message = checks.check_allergies(medications, patient("Amoxicillin"))[0].message
        assert "Amoxil" in message
        assert "amoxicillin" in message


class TestUnresolved:
    def test_a_refusal_is_reported_rather_than_ignored(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Ecosprin", (), resolution=ResolutionStatus.REFUSED, confidence=0.3),
            )
        )
        found = checks.check_unresolved(medications)
        assert len(found) == 1
        assert found[0].kind is CheckKind.UNRESOLVED

    def test_an_unresolved_line_blocks_dispensing(self) -> None:
        """Every other check ran without it, so nothing here is cleared."""
        medications = MedicationList(
            medications=(
                medication("Ecosprin", (), resolution=ResolutionStatus.REFUSED, confidence=0.3),
            )
        )
        assert checks.blocks_dispensing(checks.check_unresolved(medications))

    def test_the_message_says_no_check_has_run_against_it(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Ecosprin", (), resolution=ResolutionStatus.REFUSED, confidence=0.3),
            )
        )
        assert "no interaction or" in checks.check_unresolved(medications)[0].message

    def test_an_ambiguous_line_lists_what_it_could_be(self) -> None:
        medications = MedicationList(
            medications=(
                medication(
                    "Zyloric?",
                    (),
                    resolution=ResolutionStatus.AMBIGUOUS,
                    candidates=("allopurinol", "zolpidem"),
                ),
            )
        )
        message = checks.check_unresolved(medications)[0].message
        assert "allopurinol" in message
        assert "zolpidem" in message

    def test_a_resolved_line_is_not_reported(self) -> None:
        medications = MedicationList(medications=(medication("Glycomet", ("metformin",)),))
        assert checks.check_unresolved(medications) == ()


class TestPregnancy:
    def test_unknown_pregnancy_status_is_flagged_when_dispensing(self) -> None:
        medications = MedicationList(medications=(medication("Glycomet", ("metformin",)),))
        found = checks.check_pregnancy(
            medications, patient(pregnancy=PregnancyStatus.UNKNOWN, sex=Sex.FEMALE)
        )
        assert found[0].kind is CheckKind.PREGNANCY

    def test_a_known_status_is_not_flagged(self) -> None:
        medications = MedicationList(medications=(medication("Glycomet", ("metformin",)),))
        assert (
            checks.check_pregnancy(
                medications, patient(pregnancy=PregnancyStatus.NOT_APPLICABLE)
            )
            == ()
        )

    def test_nothing_dispensed_means_nothing_to_flag(self) -> None:
        assert (
            checks.check_pregnancy(
                MedicationList(), patient(pregnancy=PregnancyStatus.UNKNOWN)
            )
            == ()
        )

    def test_it_flags_rather_than_blocks(self) -> None:
        """Whether a molecule is safe in pregnancy needs a dataset, not a guess."""
        medications = MedicationList(medications=(medication("Glycomet", ("metformin",)),))
        found = checks.check_pregnancy(
            medications, patient(pregnancy=PregnancyStatus.UNKNOWN, sex=Sex.FEMALE)
        )
        assert found[0].severity is Severity.MODERATE


class TestRunAll:
    def test_findings_are_ordered_most_severe_first(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet 500", ("metformin",)),
                medication("Metsmall 500", ("metformin",)),
                medication("Amoxil", ("amoxicillin",)),
            )
        )
        found = checks.run_all(medications, patient("Amoxicillin"))
        assert found[0].severity is Severity.CONTRAINDICATED
        assert found[-1].severity is not Severity.CONTRAINDICATED

    def test_a_clean_prescription_produces_nothing(self) -> None:
        medications = MedicationList(medications=(medication("Glycomet", ("metformin",)),))
        assert checks.run_all(medications, patient()) == ()

    def test_a_contraindication_blocks_dispensing(self) -> None:
        medications = MedicationList(medications=(medication("Amoxil", ("amoxicillin",)),))
        assert checks.blocks_dispensing(checks.run_all(medications, patient("Amoxicillin")))

    def test_a_duplicate_alone_does_not_block_dispensing(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet 500", ("metformin",)),
                medication("Metsmall 500", ("metformin",)),
            )
        )
        found = checks.run_all(medications, patient())
        assert found
        assert not checks.blocks_dispensing(found)

    def test_every_finding_names_its_source(self) -> None:
        """A check with no stated source cannot be defended later."""
        medications = MedicationList(
            medications=(
                medication("Glycomet 500", ("metformin",)),
                medication("Metsmall 500", ("metformin",)),
                medication("Amoxil", ("amoxicillin",)),
            )
        )
        for finding in checks.run_all(medications, patient("Amoxicillin")):
            assert finding.source.strip()


class TestMedicationList:
    def test_all_molecules_collects_across_lines(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet", ("metformin",)),
                medication("Amoxil", ("amoxicillin",)),
            )
        )
        assert medications.all_molecules == frozenset({"metformin", "amoxicillin"})

    def test_an_empty_list_has_no_molecules(self) -> None:
        assert MedicationList().all_molecules == frozenset()

    def test_lines_containing_finds_every_occurrence(self) -> None:
        medications = MedicationList(
            medications=(
                medication("Glycomet 500", ("metformin",)),
                medication("Metsmall 500", ("metformin",)),
            )
        )
        assert len(medications.lines_containing("metformin")) == 2
