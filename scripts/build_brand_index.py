"""Build the Rx brand-to-molecule index from the open Indian medicine dataset.

The dependency this closes is recorded in docs/BUILD_SPEC.md section 8: Indian
brand-to-molecule mapping, previously listed as unresolved because the
commercial drug databases are licensed. The dataset used here is MIT-licensed
and names its fields plainly, which makes it usable and auditable in a way a
scraped price list would not be.

What this script does not do is decide anything clinical. It transcribes brand
names to the molecules the source lists, drops what it cannot parse, and counts
the drops. A brand whose composition does not parse is left out of the index
rather than guessed at, because a brand missing from the index REFUSES at
resolution time, and a brand present with the wrong molecule does not.

Run:
    python scripts/build_brand_index.py --source <csv> --out services/rx/rules/brands/index.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.rx.agents.resolver import normalise_brand

# "Amoxycillin  (500mg) " -> name, amount, unit. The unit is captured because
# a strength means nothing without it, and the source mixes mg with mg/5ml.
#
# The name may itself contain parentheses: "Progesterone (Natural Micronized)
# (200mg)" is one molecule with a qualifier, and only the last group is the
# strength. The unit runs to the closing bracket so that "% w/w" and "mg/5ml"
# are both captured whole rather than truncated at the first space.
#
# Anchored on the LAST bracketed group rather than searching for the first, so
# neither half needs a lazy quantifier that backtracks across the whole string.
COMPOSITION: Final[re.Pattern[str]] = re.compile(
    r"^(?P<name>.*)\(\s*(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>[^()\d][^()]*)\)\s*$"
)

# A composition with no parenthesised strength at all: "Amoxycillin".
BARE_NAME: Final[re.Pattern[str]] = re.compile(r"^(?P<name>[A-Za-z][A-Za-z0-9\s\-,'+.]*)$")

SHORTEST_MOLECULE_NAME: Final[int] = 3
"""Below this a parsed name is treated as debris rather than a drug.

The source's composition column contains stray fragments — a lone unit, a
bracket, a dash. Two characters is shorter than any molecule name, so anything
shorter is a parse that went wrong rather than a drug nobody has heard of.
"""

MG_UNITS: Final[frozenset[str]] = frozenset({"mg"})
"""Units convertible to the index's strength_mg column.

Only plain mg. A concentration such as 30mg/5ml is a different quantity from a
dose and collapsing the two would put a syrup's per-5ml figure in a column
every caller reads as a tablet strength. Those brands keep their molecules and
carry no strength.
"""


@dataclass(frozen=True)
class ParsedComposition:
    molecule: str
    strength_mg: float | None


ABSENT_STRENGTH: Final[re.Pattern[str]] = re.compile(r"\(\s*(?:NA|N/A|-{1,2})\s*\)\s*$", re.I)
"""How the source writes 'no strength recorded'.

The molecule is still known, and that is what resolution needs; dropping the
brand entirely would make it REFUSE for want of a number nobody has.
"""


def _with_strength(text: str) -> ParsedComposition | None:
    """'Amoxycillin (500mg)' — a name and a parenthesised quantity."""
    match = COMPOSITION.match(text)
    if not match:
        return None
    name = _clean_molecule(match["name"])
    if not name:
        return None
    unit = match["unit"].strip().lower()
    return ParsedComposition(
        molecule=name,
        strength_mg=float(match["amount"]) if unit in MG_UNITS else None,
    )


def _bare(text: str) -> ParsedComposition | None:
    """'Paracetamol' — a name with no quantity at all."""
    match = BARE_NAME.match(text)
    if not match:
        return None
    name = _clean_molecule(match["name"])
    return ParsedComposition(molecule=name, strength_mg=None) if name else None


def _qualified(text: str) -> ParsedComposition | None:
    """'Snake Venom Antiserum (Polyvalent)' — a name with a bracketed qualifier.

    Vaccines and antisera carry qualifiers containing commas and ampersands
    that BARE_NAME rejects. Losing these would take antivenom out of the index.
    """
    name = _clean_molecule(text)
    return ParsedComposition(molecule=name, strength_mg=None) if name else None


def parse_composition(raw: str) -> ParsedComposition | None:
    """One composition field, or None if it cannot be read.

    Returning None is a real outcome and the caller counts it. The source is
    community-maintained and contains free text in this column; a parser that
    guessed at the unparseable would be inventing the molecule name.
    """
    text = ABSENT_STRENGTH.sub("", raw.strip()).strip()
    if not text:
        return None
    for strategy in (_with_strength, _bare, _qualified):
        parsed = strategy(text)
        if parsed is not None:
            return parsed
    return None


def _clean_molecule(raw: str) -> str:
    """Normalise a molecule name to lowercase, single-spaced.

    Matches what services/rx/agents/resolver.py stores, so a molecule read from
    this index compares equal to one written by hand.
    """
    # A parenthesised qualifier is part of the source's name, not of the
    # molecule: "Progesterone (Natural Micronized)" is prescribed, dispensed
    # and interaction-checked as progesterone.
    without_qualifier = re.sub(r"\([^()]*\)", " ", raw)
    cleaned = " ".join(without_qualifier.split()).strip(" ,.-").lower()
    if len(cleaned) < SHORTEST_MOLECULE_NAME or not any(c.isalpha() for c in cleaned):
        return ""
    return cleaned


def brand_key(name: str) -> str:
    """The brand name with its strength and form stripped.

    This is the resolver's own normaliser, imported rather than reimplemented.
    A second definition that drifted from it by one word would build an index
    whose keys the resolver cannot look up, and the symptom would be a refusal
    rather than an error — the hardest kind of bug to notice, because refusing
    is a legitimate outcome.
    """
    return normalise_brand(name)


@dataclass
class BuildStats:
    rows_read: int = 0
    discontinued_skipped: int = 0
    unparseable_composition: int = 0
    no_brand_key: int = 0
    brands_written: int = 0
    conflicts_dropped: int = 0

    def report(self) -> str:
        return (
            f"read {self.rows_read} rows\n"
            f"  skipped, discontinued:        {self.discontinued_skipped}\n"
            f"  skipped, composition unread:  {self.unparseable_composition}\n"
            f"  skipped, no usable brand key: {self.no_brand_key}\n"
            f"  dropped, conflicting molecules for one brand: {self.conflicts_dropped}\n"
            f"  brands written:               {self.brands_written}"
        )


def build(source: Path, out: Path, *, include_discontinued: bool = False) -> BuildStats:
    """Read the source dataset and write the resolver's index."""
    if not source.is_file():
        raise SystemExit(
            f"no dataset at {source}. Download it from "
            f"https://github.com/junioralive/Indian-Medicine-Dataset "
            f"(DATA/indian_medicine_data.csv)"
        )

    stats = BuildStats()
    # brand key -> (display name, frozenset of molecules, strength or None)
    collected: dict[str, tuple[str, frozenset[str], float | None]] = {}
    conflicted: set[str] = set()

    with source.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            stats.rows_read += 1
            discontinued = row.get("Is_discontinued", "").strip().upper() == "TRUE"
            if discontinued and not include_discontinued:
                stats.discontinued_skipped += 1
                continue

            parsed = [
                p
                for p in (
                    parse_composition(row.get("short_composition1", "")),
                    parse_composition(row.get("short_composition2", "")),
                )
                if p is not None
            ]
            if not parsed:
                stats.unparseable_composition += 1
                continue

            key = brand_key(row.get("name", ""))
            if not key:
                stats.no_brand_key += 1
                continue

            molecules = frozenset(p.molecule for p in parsed)
            # A strength is only meaningful for a single-molecule brand; for a
            # combination the resolver would attach one number to both.
            strength = parsed[0].strength_mg if len(parsed) == 1 else None

            if key in conflicted:
                continue
            existing = collected.get(key)
            if existing is None:
                collected[key] = (row["name"].strip(), molecules, strength)
            elif existing[1] != molecules:
                # The same brand name mapping to different molecules across
                # rows is a real ambiguity in the source. Keeping either one
                # would resolve confidently to a molecule that may be wrong,
                # so the brand is dropped and will REFUSE at resolution.
                conflicted.add(key)
                del collected[key]
            elif existing[2] != strength:
                collected[key] = (existing[0], molecules, None)

    stats.conflicts_dropped = len(conflicted)
    stats.brands_written = len(collected)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["brand", "molecules", "strength_mg"])
        for key in sorted(collected):
            _display, molecules, strength = collected[key]
            writer.writerow(
                [key, "|".join(sorted(molecules)), "" if strength is None else f"{strength:g}"]
            )
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="the dataset CSV")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("services/rx/rules/brands/index.csv"),
        help="where to write the resolver's index",
    )
    parser.add_argument(
        "--include-discontinued",
        action="store_true",
        help="keep brands the source marks discontinued; a prescription may still name one",
    )
    args = parser.parse_args()

    stats = build(args.source, args.out, include_discontinued=args.include_discontinued)
    print(stats.report())
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
