"""The Rx reading gate.

Two steps, and the order is the point. Every claimed line must be found in the
OCR text, and only then is its brand resolved against the index.

A line the model invented would otherwise resolve confidently to a real
molecule, and every downstream check would run against a drug nobody
prescribed.
"""

from __future__ import annotations

from services.rx.agents.line_builder import build
from services.rx.agents.resolver import Brand, BrandIndex
from spine.schemas.medication import (
    DraftLine,
    PrescriptionDraft,
    ResolutionStatus,
    Route,
)

OCR = """Dr A Sharma MBBS
1. Tab Crocin 500mg  1-0-1  x5 days
2. Tab Dolo 650 SOS
3. T@b ~~~~ 25o  BD
"""

INDEX = BrandIndex(
    (
        Brand(name="Crocin", molecules=("paracetamol",)),
        Brand(name="Dolo", molecules=("paracetamol",)),
    )
)


def draft(*lines: DraftLine) -> PrescriptionDraft:
    return PrescriptionDraft(lines=lines)


class TestGroundedness:
    def test_a_line_in_the_text_is_kept(self) -> None:
        result = build(
            draft(DraftLine(written_as="Tab Dolo", source_span="Tab Dolo 650 SOS")),
            OCR,
            "rx-1",
            INDEX,
        )
        assert len(result.medications.medications) == 1
        assert result.fabrication_count == 0

    def test_a_line_not_in_the_text_is_dropped(self) -> None:
        """An invented line would resolve confidently and be checked as real."""
        result = build(
            draft(DraftLine(written_as="Tab Amoxil", source_span="Tab Amoxil 500")),
            OCR,
            "rx-1",
            INDEX,
        )
        assert not result.medications.medications
        assert result.fabrication_count == 1

    def test_an_empty_draft_produces_nothing(self) -> None:
        result = build(PrescriptionDraft(), OCR, "rx-1", INDEX)
        assert result.medications.medications == ()


class TestResolution:
    def test_a_known_brand_resolves_to_its_molecule(self) -> None:
        result = build(
            draft(DraftLine(written_as="Tab Dolo", source_span="Tab Dolo 650 SOS")),
            OCR,
            "rx-1",
            INDEX,
        )
        medication = result.medications.medications[0]
        assert medication.resolution is ResolutionStatus.RESOLVED
        assert "paracetamol" in medication.molecule_names

    def test_an_unknown_brand_refuses_rather_than_guessing(self) -> None:
        """A refusal a pharmacist resolves beats a confident wrong molecule."""
        text = "1. Tab Zyxwv 100 OD"
        result = build(
            draft(DraftLine(written_as="Tab Zyxwv", source_span="Tab Zyxwv 100 OD")),
            text,
            "rx-2",
            INDEX,
        )
        assert result.medications.medications[0].resolution is not ResolutionStatus.RESOLVED

    def test_an_unresolved_line_is_counted_separately_from_a_fabrication(self) -> None:
        """A line the pharmacist must confirm is a working outcome, not a failure."""
        text = "1. Tab Zyxwv 100 OD"
        result = build(
            draft(DraftLine(written_as="Tab Zyxwv", source_span="Tab Zyxwv 100 OD")),
            text,
            "rx-2",
            INDEX,
        )
        assert result.fabrication_count == 0
        assert result.unresolved_count == 1


class TestIllegibleLines:
    def test_an_illegible_line_is_recorded_rather_than_dropped(self) -> None:
        """A dropped line is a drug nobody checked."""
        result = build(
            draft(
                DraftLine(
                    written_as="T@b ~~~~ 25o",
                    source_span="T@b ~~~~ 25o  BD",
                    legible=False,
                )
            ),
            OCR,
            "rx-1",
            INDEX,
        )
        assert len(result.medications.medications) == 1
        assert result.fabrication_count == 0

    def test_an_illegible_line_is_marked_unreadable(self) -> None:
        result = build(
            draft(
                DraftLine(
                    written_as="T@b ~~~~ 25o",
                    source_span="T@b ~~~~ 25o  BD",
                    legible=False,
                )
            ),
            OCR,
            "rx-1",
            INDEX,
        )
        medication = result.medications.medications[0]
        assert medication.resolution is ResolutionStatus.UNREADABLE
        assert medication.resolution_confidence == 0.0

    def test_an_illegible_line_still_needs_its_span(self) -> None:
        """Marking a line unreadable is not a way around provenance."""
        result = build(
            draft(
                DraftLine(
                    written_as="something",
                    source_span="not in the prescription",
                    legible=False,
                )
            ),
            OCR,
            "rx-1",
            INDEX,
        )
        assert not result.medications.medications
        assert result.fabrication_count == 1


class TestDosingIsCarriedThrough:
    def test_the_frequency_is_kept_as_written(self) -> None:
        """'1-0-1' is not converted to 'BD'; the pharmacist reads the original."""
        result = build(
            draft(
                DraftLine(
                    written_as="Tab Crocin",
                    source_span="Tab Crocin 500mg  1-0-1  x5 days",
                    frequency="1-0-1",
                )
            ),
            OCR,
            "rx-1",
            INDEX,
        )
        assert result.medications.medications[0].frequency == "1-0-1"

    def test_the_route_is_kept(self) -> None:
        result = build(
            draft(
                DraftLine(
                    written_as="Tab Dolo",
                    source_span="Tab Dolo 650 SOS",
                    route=Route.ORAL,
                )
            ),
            OCR,
            "rx-1",
            INDEX,
        )
        assert result.medications.medications[0].route is Route.ORAL

    def test_an_unstated_route_stays_unknown(self) -> None:
        result = build(
            draft(DraftLine(written_as="Tab Dolo", source_span="Tab Dolo 650 SOS")),
            OCR,
            "rx-1",
            INDEX,
        )
        assert result.medications.medications[0].route is Route.UNKNOWN
