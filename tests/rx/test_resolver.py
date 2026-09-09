"""Brand-to-molecule resolution.

Refusal is the design centre. A refusal a pharmacist resolves is safer than a
confident wrong molecule they do not question, so the floor is high and a near
tie refuses rather than picking the higher score.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.rx.agents.resolver import (
    AMBIGUITY_MARGIN,
    RESOLUTION_FLOOR,
    UNREADABLE_PLACEHOLDER,
    Brand,
    BrandIndex,
    BrandIndexError,
    load_brand_index,
    normalise_brand,
    resolve_line,
)
from spine.schemas.medication import ResolutionStatus
from spine.schemas.provenance import BoundingBox, OcrRegion

CSV_HEADER = "brand,molecules,strength_mg\n"


def region() -> OcrRegion:
    return OcrRegion(
        source_id="rx.jpg",
        box=BoundingBox(x=1, y=1, width=9, height=9),
        text="line",
        ocr_confidence=0.9,
    )


@pytest.fixture
def index() -> BrandIndex:
    return BrandIndex(
        (
            Brand("Glycomet", ("metformin",), 500.0),
            Brand("Glycomet-GP", ("metformin", "glimepiride")),
            Brand("Amoxil", ("amoxicillin",), 500.0),
            Brand("Zyloric", ("allopurinol",)),
        )
    )


class TestNormalisation:
    def test_strength_is_stripped(self) -> None:
        assert normalise_brand("Glycomet 500") == "glycomet"

    def test_dosage_form_is_stripped(self) -> None:
        assert normalise_brand("Glycomet 500 tab") == "glycomet"

    def test_case_is_flattened(self) -> None:
        assert normalise_brand("GLYCOMET") == "glycomet"

    def test_punctuation_becomes_a_separator(self) -> None:
        assert normalise_brand("Glycomet-GP") == "glycomet gp"


class TestResolution:
    def test_an_exact_brand_resolves(self, index: BrandIndex) -> None:
        line = resolve_line("Glycomet", index, region())
        assert line.resolution is ResolutionStatus.RESOLVED
        assert line.molecule_names == frozenset({"metformin"})

    def test_a_strength_suffix_does_not_prevent_resolution(self, index: BrandIndex) -> None:
        line = resolve_line("Glycomet 500 tab", index, region())
        assert line.resolution is ResolutionStatus.RESOLVED

    def test_a_combination_product_resolves_to_every_molecule(
        self, index: BrandIndex
    ) -> None:
        """A resolver assuming one molecule per brand drops half a combination."""
        line = resolve_line("Glycomet-GP", index, region())
        assert line.molecule_names == frozenset({"metformin", "glimepiride"})

    def test_a_close_misspelling_resolves(self, index: BrandIndex) -> None:
        line = resolve_line("Glycomett", index, region())
        assert line.resolution is ResolutionStatus.RESOLVED

    def test_an_unrecognised_name_refuses(self, index: BrandIndex) -> None:
        line = resolve_line("Qqzzxx", index, region())
        assert line.resolution is ResolutionStatus.REFUSED
        assert line.molecules == ()

    def test_a_refusal_asserts_no_molecule(self, index: BrandIndex) -> None:
        """A refusal that still asserts an answer is not a refusal."""
        assert resolve_line("Qqzzxx", index, region()).molecule_names == frozenset()

    def test_an_empty_line_is_unreadable_not_an_error(self, index: BrandIndex) -> None:
        """A line the OCR could not read still occupies a row."""
        line = resolve_line("", index, region())
        assert line.resolution is ResolutionStatus.UNREADABLE
        assert line.written_as == UNREADABLE_PLACEHOLDER

    def test_whitespace_alone_is_unreadable(self, index: BrandIndex) -> None:
        assert resolve_line("   ", index, region()).resolution is ResolutionStatus.UNREADABLE

    def test_an_empty_index_refuses_everything(self) -> None:
        line = resolve_line("Glycomet", BrandIndex(), region())
        assert line.resolution is ResolutionStatus.REFUSED


class TestOcrConfidence:
    def test_a_low_ocr_confidence_refuses_a_perfect_match(self, index: BrandIndex) -> None:
        """A perfect match against a badly-read word is not confident."""
        line = resolve_line("Amoxil", index, region(), ocr_confidence=0.4)
        assert line.resolution is ResolutionStatus.REFUSED

    def test_a_high_ocr_confidence_preserves_the_match(self, index: BrandIndex) -> None:
        line = resolve_line("Amoxil", index, region(), ocr_confidence=1.0)
        assert line.resolution is ResolutionStatus.RESOLVED

    def test_the_confidence_carries_the_ocr_factor(self, index: BrandIndex) -> None:
        line = resolve_line("Amoxil", index, region(), ocr_confidence=0.9)
        assert line.resolution_confidence == pytest.approx(0.9)


class TestAmbiguity:
    def test_two_close_candidates_refuse_rather_than_pick(self) -> None:
        """A near tie is a question for a human, not a match to the higher one.

        Zylori scores identically against both brands, which is exactly the
        case a pharmacist must resolve rather than the resolver guessing.
        """
        index = BrandIndex((Brand("Zyloric", ("allopurinol",)), Brand("Zylorix", ("zolpidem",))))
        line = resolve_line("Zylori", index, region())
        assert line.resolution is ResolutionStatus.AMBIGUOUS

    def test_an_ambiguous_line_lists_its_candidates(self) -> None:
        index = BrandIndex((Brand("Zyloric", ("allopurinol",)), Brand("Zylorix", ("zolpidem",))))
        line = resolve_line("Zylori", index, region())
        assert "allopurinol" in line.candidates
        assert "zolpidem" in line.candidates

    def test_the_margin_is_where_it_is_claimed(self) -> None:
        assert 0.0 < AMBIGUITY_MARGIN < 0.5

    def test_the_floor_is_deliberately_high(self) -> None:
        assert RESOLUTION_FLOOR >= 0.8


class TestNeedsConfirmation:
    @pytest.mark.parametrize(
        ("written", "confirmed"),
        [("Glycomet", False), ("Qqzzxx", True), ("", True)],
    )
    def test_anything_not_cleanly_resolved_needs_a_human(
        self, written: str, confirmed: bool, index: BrandIndex
    ) -> None:
        line = resolve_line(written, index, region())
        assert line.needs_human_confirmation is confirmed


class TestBrandIndexLoading:
    def test_a_csv_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "brands.csv"
        path.write_text(CSV_HEADER + "Glycomet,metformin,500\n", encoding="utf-8")
        assert len(load_brand_index(path)) == 1

    def test_combination_molecules_are_pipe_separated(self, tmp_path: Path) -> None:
        path = tmp_path / "brands.csv"
        path.write_text(CSV_HEADER + "Glycomet-GP,metformin|glimepiride,\n", encoding="utf-8")
        index = load_brand_index(path)
        line = resolve_line("Glycomet-GP", index, region())
        assert len(line.molecules) == 2

    def test_a_missing_file_names_the_command_that_builds_one(self, tmp_path: Path) -> None:
        """The index is derived, not shipped, so a deployment can rebuild it."""
        with pytest.raises(BrandIndexError, match=r"build_brand_index\.py"):
            load_brand_index(tmp_path / "absent.csv")

    def test_a_missing_column_is_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text("brand\nGlycomet\n", encoding="utf-8")
        with pytest.raises(BrandIndexError, match="missing column"):
            load_brand_index(path)

    def test_a_brand_with_no_molecules_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(CSV_HEADER + "Glycomet,,500\n", encoding="utf-8")
        with pytest.raises(BrandIndexError, match="no molecules"):
            load_brand_index(path)

    def test_a_duplicate_brand_is_rejected(self) -> None:
        with pytest.raises(BrandIndexError, match="silently ignored"):
            BrandIndex((Brand("Glycomet", ("metformin",)), Brand("Glycomet", ("x",))))

    def test_a_brand_declaring_no_molecule_is_rejected(self) -> None:
        with pytest.raises(BrandIndexError, match="lists no molecules"):
            Brand("Glycomet", ())

    def test_no_brand_index_ships(self) -> None:
        """The Indian brand-to-molecule mapping is an unresolved dependency."""
        assert not (Path("data") / "brands.csv").exists()
