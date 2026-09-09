"""Pairwise interaction checking against a swappable dataset.

The property every test here circles is the one that makes this check honest:
a molecule the dataset does not know has not been cleared, it has been skipped.
"No interactions found" over a prescription where two molecules were never in
the dataset is a false statement, and it is the kind a pharmacist would act on.

The dataset itself is not chosen in this repository — DDInter is CC BY-NC-SA
and DrugBank is licensed — so these tests build small indexes by hand. That is
also what a deployment swapping sources would do.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.rx.clinical.checks import CheckKind, Severity
from services.rx.clinical.interactions import (
    UNCOVERED_SEVERITY,
    Interaction,
    InteractionIndex,
    InteractionIndexError,
    check_interactions,
    findings_from,
    load_interaction_index,
)
from spine.schemas.medication import (
    MedicationList,
    Molecule,
    PrescribedMedication,
    ResolutionStatus,
)
from spine.schemas.provenance import BoundingBox, OcrRegion

HEADER = "first,second,severity,mechanism,management\n"


def region() -> OcrRegion:
    return OcrRegion(
        source_id="rx.jpg",
        box=BoundingBox(x=1, y=1, width=9, height=9),
        text="line",
        ocr_confidence=0.9,
    )


def prescribed(written: str, *molecules: str) -> PrescribedMedication:
    return PrescribedMedication(
        written_as=written,
        molecules=tuple(Molecule(name=name) for name in molecules),
        resolution=ResolutionStatus.RESOLVED,
        resolution_confidence=0.95,
        provenance=region(),
    )


def unresolved(written: str) -> PrescribedMedication:
    return PrescribedMedication(
        written_as=written,
        resolution=ResolutionStatus.REFUSED,
        resolution_confidence=0.2,
        provenance=region(),
    )


def interaction(
    first: str = "warfarin",
    second: str = "aspirin",
    severity: Severity = Severity.SEVERE,
) -> Interaction:
    return Interaction(
        first=first,
        second=second,
        severity=severity,
        mechanism="additive bleeding risk",
        management="Contact the prescriber.",
    )


def index(*interactions: Interaction, covered: frozenset[str] = frozenset()) -> InteractionIndex:
    return InteractionIndex(interactions, covered, "test dataset")


class TestFindingInteractions:
    def test_a_documented_pair_is_found(self) -> None:
        medications = MedicationList(
            medications=(prescribed("Warf", "warfarin"), prescribed("Asp", "aspirin"))
        )
        report = check_interactions(medications, index(interaction()))
        assert len(report.found) == 1

    def test_prescribing_order_does_not_matter(self) -> None:
        """A prescription writes the drugs in whatever order the prescriber thought."""
        medications = MedicationList(
            medications=(prescribed("Asp", "aspirin"), prescribed("Warf", "warfarin"))
        )
        assert check_interactions(medications, index(interaction())).found

    def test_a_pair_with_no_documented_interaction_is_clear(self) -> None:
        medications = MedicationList(
            medications=(prescribed("Para", "paracetamol"), prescribed("Amox", "amoxicillin"))
        )
        report = check_interactions(
            medications, index(covered=frozenset({"paracetamol", "amoxicillin"}))
        )
        assert report.found == ()
        assert report.is_complete

    def test_a_combination_products_molecules_are_both_checked(self) -> None:
        """Indian formulations are combination-heavy; one line can be two molecules."""
        medications = MedicationList(
            medications=(
                prescribed("Combi", "warfarin", "paracetamol"),
                prescribed("Asp", "aspirin"),
            )
        )
        assert check_interactions(medications, index(interaction())).found

    def test_the_most_severe_comes_first(self) -> None:
        medications = MedicationList(
            medications=(
                prescribed("A", "warfarin"),
                prescribed("B", "aspirin"),
                prescribed("C", "ibuprofen"),
            )
        )
        built = index(
            interaction("warfarin", "aspirin", Severity.MINOR),
            interaction("aspirin", "ibuprofen", Severity.CONTRAINDICATED),
        )
        report = check_interactions(medications, built)
        assert report.found[0].severity is Severity.CONTRAINDICATED

    def test_one_molecule_alone_has_no_pairs(self) -> None:
        medications = MedicationList(medications=(prescribed("Warf", "warfarin"),))
        assert check_interactions(medications, index(interaction())).checked_pairs == 0

    def test_an_empty_prescription_is_clear(self) -> None:
        assert check_interactions(MedicationList(medications=()), index()).found == ()


class TestUncoveredMoleculesAreNotCleared:
    """The property this module exists for.

    A molecule absent from the dataset has not been examined. Reporting it as
    clear tells a pharmacist something false about a prescription they are
    about to dispense.
    """

    def test_an_unknown_molecule_is_reported_uncovered(self) -> None:
        medications = MedicationList(medications=(prescribed("Xy", "obscuramol"),))
        report = check_interactions(medications, index(covered=frozenset({"warfarin"})))
        assert report.uncovered == ("obscuramol",)

    def test_a_report_with_an_uncovered_molecule_is_not_complete(self) -> None:
        medications = MedicationList(medications=(prescribed("Xy", "obscuramol"),))
        assert not check_interactions(medications, index()).is_complete

    def test_a_pair_is_not_checked_when_either_side_is_unknown(self) -> None:
        """Half a pair is not a check."""
        medications = MedicationList(
            medications=(prescribed("Warf", "warfarin"), prescribed("Xy", "obscuramol"))
        )
        report = check_interactions(medications, index(interaction()))
        assert report.checked_pairs == 0
        assert "obscuramol" in report.uncovered

    def test_a_molecule_the_dataset_cleared_is_covered(self) -> None:
        """Examined and clear is different from never seen, and the coverage
        list is the only thing that can tell them apart."""
        medications = MedicationList(medications=(prescribed("Para", "paracetamol"),))
        report = check_interactions(medications, index(covered=frozenset({"paracetamol"})))
        assert report.is_complete

    def test_a_molecule_in_the_interaction_table_is_covered_without_the_list(self) -> None:
        medications = MedicationList(medications=(prescribed("Warf", "warfarin"),))
        assert check_interactions(medications, index(interaction())).is_complete

    def test_unresolved_lines_are_not_counted_here(self) -> None:
        """check_unresolved already reports them; twice would read as two problems."""
        medications = MedicationList(medications=(unresolved("scribble"),))
        assert check_interactions(medications, index()).uncovered == ()


class TestFindings:
    def test_an_interaction_becomes_a_finding(self) -> None:
        medications = MedicationList(
            medications=(prescribed("Warf", "warfarin"), prescribed("Asp", "aspirin"))
        )
        report = check_interactions(medications, index(interaction()))
        findings = findings_from(report, medications)
        assert findings[0].kind is CheckKind.INTERACTION
        assert findings[0].severity is Severity.SEVERE

    def test_the_finding_names_the_line_as_written(self) -> None:
        """A pharmacist works from the prescription, not a molecule list."""
        medications = MedicationList(
            medications=(prescribed("Warf 5", "warfarin"), prescribed("Asp 75", "aspirin"))
        )
        report = check_interactions(medications, index(interaction()))
        written = findings_from(report, medications)[0].written_as
        assert "Warf 5" in written

    def test_the_mechanism_and_management_survive(self) -> None:
        """A severity grade does not tell a pharmacist whether to phone."""
        medications = MedicationList(
            medications=(prescribed("Warf", "warfarin"), prescribed("Asp", "aspirin"))
        )
        report = check_interactions(medications, index(interaction()))
        message = findings_from(report, medications)[0].message
        assert "additive bleeding risk" in message
        assert "Contact the prescriber." in message

    def test_uncovered_molecules_raise_their_own_finding(self) -> None:
        medications = MedicationList(medications=(prescribed("Xy", "obscuramol"),))
        report = check_interactions(medications, index())
        findings = findings_from(report, medications)
        assert findings[0].severity is UNCOVERED_SEVERITY
        assert "Not checked for interactions" in findings[0].message

    def test_the_uncovered_message_says_nothing_was_ruled_out(self) -> None:
        """The wording matters: a pharmacist must not read silence as safety."""
        medications = MedicationList(medications=(prescribed("Xy", "obscuramol"),))
        report = check_interactions(medications, index())
        assert "rules out" in findings_from(report, medications)[0].message

    def test_a_complete_clear_report_raises_nothing(self) -> None:
        medications = MedicationList(medications=(prescribed("Para", "paracetamol"),))
        report = check_interactions(medications, index(covered=frozenset({"paracetamol"})))
        assert findings_from(report, medications) == ()

    def test_every_finding_credits_the_dataset(self) -> None:
        """CC BY-NC-SA attribution is not satisfied by a README nobody reads."""
        medications = MedicationList(
            medications=(prescribed("Warf", "warfarin"), prescribed("Asp", "aspirin"))
        )
        report = check_interactions(medications, index(interaction()))
        assert findings_from(report, medications)[0].source == "test dataset"


class TestLoading:
    def test_a_csv_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "ddi.csv"
        path.write_text(
            HEADER + "warfarin,aspirin,severe,bleeding,Contact prescriber\n", encoding="utf-8"
        )
        assert len(load_interaction_index(path, attribution="test")) == 1

    def test_the_attribution_is_carried(self, tmp_path: Path) -> None:
        path = tmp_path / "ddi.csv"
        path.write_text(HEADER + "warfarin,aspirin,severe,x,y\n", encoding="utf-8")
        built = load_interaction_index(path, attribution="DDInter (CC BY-NC-SA 4.0)")
        assert "CC BY-NC-SA" in built.attribution

    def test_a_coverage_list_widens_what_counts_as_checked(self, tmp_path: Path) -> None:
        path = tmp_path / "ddi.csv"
        path.write_text(HEADER + "warfarin,aspirin,severe,x,y\n", encoding="utf-8")
        covered = tmp_path / "covered.txt"
        covered.write_text("warfarin\naspirin\nparacetamol\n", encoding="utf-8")
        built = load_interaction_index(path, attribution="t", covered_path=covered)
        assert built.covers("paracetamol")

    def test_a_missing_file_points_at_the_licence_note(self, tmp_path: Path) -> None:
        with pytest.raises(InteractionIndexError, match=r"CANDIDATES\.md"):
            load_interaction_index(tmp_path / "absent.csv", attribution="t")

    def test_a_missing_coverage_list_explains_why_it_matters(self, tmp_path: Path) -> None:
        path = tmp_path / "ddi.csv"
        path.write_text(HEADER + "warfarin,aspirin,severe,x,y\n", encoding="utf-8")
        with pytest.raises(InteractionIndexError, match="unexamined"):
            load_interaction_index(
                path, attribution="t", covered_path=tmp_path / "absent.txt"
            )

    def test_an_unknown_severity_lists_the_permitted_ones(self, tmp_path: Path) -> None:
        """A source's own grades must be mapped by its loader, not guessed here."""
        path = tmp_path / "ddi.csv"
        path.write_text(HEADER + "warfarin,aspirin,major,x,y\n", encoding="utf-8")
        with pytest.raises(InteractionIndexError, match="Known severities are"):
            load_interaction_index(path, attribution="t")

    def test_a_missing_column_is_named(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text("first,second\nwarfarin,aspirin\n", encoding="utf-8")
        with pytest.raises(InteractionIndexError, match="missing column"):
            load_interaction_index(path, attribution="t")

    def test_a_self_interaction_is_refused(self, tmp_path: Path) -> None:
        """A molecule interacting with itself is duplicate therapy, not an interaction."""
        path = tmp_path / "ddi.csv"
        path.write_text(HEADER + "warfarin,warfarin,severe,x,y\n", encoding="utf-8")
        with pytest.raises(InteractionIndexError, match="interacts with itself"):
            load_interaction_index(path, attribution="t")

    def test_a_blank_molecule_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "ddi.csv"
        path.write_text(HEADER + "warfarin,,severe,x,y\n", encoding="utf-8")
        with pytest.raises(InteractionIndexError, match="both molecules must be named"):
            load_interaction_index(path, attribution="t")

    def test_an_absent_mechanism_gets_a_placeholder_rather_than_a_claim(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "ddi.csv"
        path.write_text("first,second,severity\nwarfarin,aspirin,severe\n", encoding="utf-8")
        built = load_interaction_index(path, attribution="t")
        found = built.between("warfarin", "aspirin")
        assert found is not None
        assert "not recorded" in found.mechanism
