"""Building the brand index from the open Indian medicine dataset.

The dataset is community-maintained and its composition column is free text.
What is tested here is the parsing of that text and, more importantly, the
things the builder refuses to do with it: guess a molecule it could not read,
keep a brand whose rows disagree about what is in it, or put a concentration in
a column that every caller reads as a tablet strength.

The last test in this file is the one that matters most. The builder and the
resolver must agree on what a brand key is, and they agree by sharing one
function rather than by both being careful.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.build_brand_index import (
    ParsedComposition,
    brand_key,
    build,
    parse_composition,
)
from services.rx.agents.resolver import load_brand_index, normalise_brand

HEADER = (
    "id,name,price(₹),Is_discontinued,manufacturer_name,type,pack_size_label,"
    "short_composition1,short_composition2"
)


def dataset(tmp_path: Path, *rows: tuple[str, str, str, str]) -> Path:
    """A source CSV holding `rows` of (name, discontinued, comp1, comp2)."""
    path = tmp_path / "source.csv"
    lines = [HEADER]
    for index, (name, discontinued, first, second) in enumerate(rows, start=1):
        lines.append(
            f'{index},"{name}",10.0,{discontinued},Maker,allopathy,strip,"{first}","{second}"'
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def written(path: Path) -> dict[str, tuple[str, str]]:
    """The built index, keyed by brand."""
    with path.open(encoding="utf-8", newline="") as handle:
        return {r["brand"]: (r["molecules"], r["strength_mg"]) for r in csv.DictReader(handle)}


class TestCompositionParsing:
    def test_a_plain_strength_is_read(self) -> None:
        assert parse_composition("Azithromycin (500mg)") == ParsedComposition(
            molecule="azithromycin", strength_mg=500.0
        )

    def test_surrounding_whitespace_is_ignored(self) -> None:
        """The source pads this column inconsistently."""
        assert parse_composition("  Amoxycillin  (500mg) ") == ParsedComposition(
            molecule="amoxycillin", strength_mg=500.0
        )

    def test_a_concentration_keeps_the_molecule_but_not_the_strength(self) -> None:
        """30mg/5ml is a concentration, not a dose.

        Recording 30 in strength_mg would tell a pharmacist the syrup is a
        30mg preparation, which is a different quantity from what a 5ml spoon
        delivers.
        """
        assert parse_composition("Ambroxol (30mg/5ml)") == ParsedComposition(
            molecule="ambroxol", strength_mg=None
        )

    def test_a_percentage_keeps_the_molecule(self) -> None:
        """Topicals are written as % w/w and are still real drugs."""
        assert parse_composition("Luliconazole (1% w/w)") == ParsedComposition(
            molecule="luliconazole", strength_mg=None
        )

    def test_a_qualifier_in_the_name_is_not_part_of_the_molecule(self) -> None:
        """'Progesterone (Natural Micronized) (200mg)' is progesterone."""
        assert parse_composition("Progesterone (Natural Micronized) (200mg)") == (
            ParsedComposition(molecule="progesterone", strength_mg=200.0)
        )

    def test_an_absent_strength_keeps_the_molecule(self) -> None:
        """The source writes (NA) where it has no figure.

        The molecule is still known, and that is what resolution needs.
        """
        assert parse_composition("Diclofenac (NA)") == ParsedComposition(
            molecule="diclofenac", strength_mg=None
        )

    def test_a_bare_name_is_read(self) -> None:
        assert parse_composition("Paracetamol") == ParsedComposition(
            molecule="paracetamol", strength_mg=None
        )

    def test_an_antiserum_with_a_bracketed_qualifier_is_kept(self) -> None:
        """Snake antivenom must survive parsing.

        India records the highest snakebite mortality in the world, and this
        row is one line in a 254,000-row file — exactly the kind of thing a
        parser drops without anyone noticing.
        """
        parsed = parse_composition("Snake Venom Antiserum (Polyvalent) (NA)")
        assert parsed is not None
        assert "snake venom antiserum" in parsed.molecule

    def test_an_empty_composition_is_unread(self) -> None:
        assert parse_composition("") is None
        assert parse_composition("   ") is None

    def test_a_strength_alone_is_not_a_molecule(self) -> None:
        """A number with no name must not become a drug called '500'."""
        assert parse_composition("(500mg)") is None


class TestBuilding:
    def test_a_single_molecule_brand_carries_its_strength(self, tmp_path: Path) -> None:
        source = dataset(tmp_path, ("Crocin 500 Tablet", "FALSE", "Paracetamol (500mg)", ""))
        out = tmp_path / "index.csv"
        build(source, out)
        assert written(out)["crocin"] == ("paracetamol", "500")

    def test_a_combination_lists_both_molecules(self, tmp_path: Path) -> None:
        source = dataset(
            tmp_path,
            ("Augmentin 625 Duo Tablet", "FALSE", "Amoxycillin (500mg)", "Clavulanic Acid (125mg)"),
        )
        out = tmp_path / "index.csv"
        build(source, out)
        assert written(out)["augmentin"] == ("amoxycillin|clavulanic acid", "")

    def test_a_combination_carries_no_strength(self, tmp_path: Path) -> None:
        """One number cannot describe two molecules.

        Attaching 500mg to a brand containing 500mg of one and 125mg of
        another would misstate the second.
        """
        source = dataset(
            tmp_path, ("Combi Tablet", "FALSE", "Amoxycillin (500mg)", "Clavulanic Acid (125mg)")
        )
        out = tmp_path / "index.csv"
        build(source, out)
        assert written(out)["combi"][1] == ""

    def test_discontinued_brands_are_skipped_by_default(self, tmp_path: Path) -> None:
        source = dataset(tmp_path, ("Olddrug Tablet", "TRUE", "Paracetamol (500mg)", ""))
        out = tmp_path / "index.csv"
        stats = build(source, out)
        assert stats.discontinued_skipped == 1
        assert written(out) == {}

    def test_discontinued_brands_can_be_kept(self, tmp_path: Path) -> None:
        """A prescription may still name a brand the market has dropped."""
        source = dataset(tmp_path, ("Olddrug Tablet", "TRUE", "Paracetamol (500mg)", ""))
        out = tmp_path / "index.csv"
        build(source, out, include_discontinued=True)
        assert "olddrug" in written(out)

    def test_rows_of_the_same_brand_collapse(self, tmp_path: Path) -> None:
        """250mg and 500mg of the same brand are one brand."""
        source = dataset(
            tmp_path,
            ("Azithral 250 Tablet", "FALSE", "Azithromycin (250mg)", ""),
            ("Azithral 500 Tablet", "FALSE", "Azithromycin (500mg)", ""),
        )
        out = tmp_path / "index.csv"
        build(source, out)
        index = written(out)
        assert index["azithral"][0] == "azithromycin"

    def test_a_collapsed_brand_with_two_strengths_reports_neither(self, tmp_path: Path) -> None:
        """Picking one would tell the pharmacist a dose nobody prescribed."""
        source = dataset(
            tmp_path,
            ("Azithral 250 Tablet", "FALSE", "Azithromycin (250mg)", ""),
            ("Azithral 500 Tablet", "FALSE", "Azithromycin (500mg)", ""),
        )
        out = tmp_path / "index.csv"
        build(source, out)
        assert written(out)["azithral"][1] == ""

    def test_a_brand_whose_rows_disagree_is_dropped(self, tmp_path: Path) -> None:
        """The source contains one brand name used for different drugs.

        Keeping either row resolves confidently to a molecule that may be the
        wrong one. Dropping the brand makes it REFUSE, which a pharmacist
        catches; a confident wrong molecule is what they do not.
        """
        source = dataset(
            tmp_path,
            ("Zenith Tablet", "FALSE", "Paracetamol (500mg)", ""),
            ("Zenith Tablet", "FALSE", "Metformin (500mg)", ""),
        )
        out = tmp_path / "index.csv"
        stats = build(source, out)
        assert stats.conflicts_dropped == 1
        assert "zenith" not in written(out)

    def test_a_conflict_stays_dropped_when_a_third_row_agrees(self, tmp_path: Path) -> None:
        """Two against one is not a vote. The brand is ambiguous either way."""
        source = dataset(
            tmp_path,
            ("Zenith Tablet", "FALSE", "Paracetamol (500mg)", ""),
            ("Zenith Tablet", "FALSE", "Metformin (500mg)", ""),
            ("Zenith Tablet", "FALSE", "Paracetamol (500mg)", ""),
        )
        out = tmp_path / "index.csv"
        build(source, out)
        assert "zenith" not in written(out)

    def test_an_unreadable_composition_is_counted_not_guessed(self, tmp_path: Path) -> None:
        source = dataset(tmp_path, ("Mystery Tablet", "FALSE", "", ""))
        out = tmp_path / "index.csv"
        stats = build(source, out)
        assert stats.unparseable_composition == 1
        assert written(out) == {}

    def test_a_missing_source_names_where_to_get_it(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit, match="Indian-Medicine-Dataset"):
            build(tmp_path / "absent.csv", tmp_path / "out.csv")

    def test_the_output_is_sorted(self, tmp_path: Path) -> None:
        """A stable order makes a rebuild diffable."""
        source = dataset(
            tmp_path,
            ("Zebra Tablet", "FALSE", "Paracetamol (500mg)", ""),
            ("Alpha Tablet", "FALSE", "Metformin (500mg)", ""),
        )
        out = tmp_path / "index.csv"
        build(source, out)
        assert list(written(out)) == ["alpha", "zebra"]


class TestTheBuilderAndResolverAgree:
    """The bug class this file exists to prevent.

    The builder writes keys and the resolver looks them up. If the two
    normalise differently by even one word, every affected brand REFUSES —
    and a refusal is a legitimate outcome, so nothing fails, nothing logs,
    and the index simply appears to be missing drugs it contains.
    """

    def test_the_builder_uses_the_resolvers_normaliser(self) -> None:
        for name in [
            "Augmentin 625 Duo Tablet",
            "Crocin 500",
            "Ascoril LS Syrup",
            "Pan 40 Tablet",
            "A Lith SR",
        ]:
            assert brand_key(name) == normalise_brand(name)

    def test_a_built_index_resolves_the_names_it_was_built_from(self, tmp_path: Path) -> None:
        """End to end: the written name a prescriber uses finds its molecule."""
        source = dataset(
            tmp_path,
            ("Augmentin 625 Duo Tablet", "FALSE", "Amoxycillin (500mg)", "Clavulanic Acid (125mg)"),
            ("Crocin 500 Tablet", "FALSE", "Paracetamol (500mg)", ""),
            ("Glycomet 500 Tablet", "FALSE", "Metformin (500mg)", ""),
        )
        out = tmp_path / "index.csv"
        build(source, out)
        index = load_brand_index(out)

        for name, expected in [
            ("Augmentin 625 Duo Tablet", {"amoxycillin", "clavulanic acid"}),
            ("Augmentin", {"amoxycillin", "clavulanic acid"}),
            ("Crocin 500", {"paracetamol"}),
            ("Glycomet", {"metformin"}),
        ]:
            status, candidates = index.resolve(name)
            assert status.value == "resolved", f"{name} did not resolve"
            assert set(candidates[0].brand.molecules) == expected
