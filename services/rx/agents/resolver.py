"""Brand-to-molecule resolution.

The core dataset problem in Rx: one molecule, fifty brand names, written by
hand. Resolution runs against a brand index rather than a model, because a
model asked "what molecule is Glycomet" will answer confidently for a brand it
has never seen.

Refusal is the design centre. Below the confidence floor this returns REFUSED
rather than a best guess, and a refusal a pharmacist resolves is safer than a
confident wrong molecule they do not question.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Final

from spine.schemas.medication import Molecule, PrescribedMedication, ResolutionStatus
from spine.schemas.provenance import Provenance

RESOLUTION_FLOOR: Final[float] = 0.85
"""Below this similarity, resolution refuses.

Deliberately high. The cost of a refusal is a pharmacist reading the
prescription themselves, which they can do; the cost of a wrong molecule is a
dispensing error nobody catches.
"""

UNREADABLE_PLACEHOLDER: Final[str] = "[illegible]"
"""What an unreadable line is called.

A line the OCR could not read still occupies a row on the prescription, and the
pharmacist needs to see that it exists. Dropping it would make a five-line
prescription look like a four-line one.
"""

AMBIGUITY_MARGIN: Final[float] = 0.05
"""How close a second candidate must be to make a match ambiguous.

Two brands scoring within this of each other is not a match to the higher one.
It is a question for a human, and the candidates are shown.
"""


class BrandIndexError(RuntimeError):
    """Raised when the brand index is missing or malformed."""


@dataclass(frozen=True)
class Brand:
    """One brand name and what it contains.

    A brand may carry several molecules: combination products are the norm in
    Indian prescribing, and a resolver that assumes one molecule per brand
    silently drops half of a combination.
    """

    name: str
    molecules: tuple[str, ...]
    strength_mg: float | None = None

    def __post_init__(self) -> None:
        if not self.molecules:
            raise BrandIndexError(f"brand {self.name!r} lists no molecules")


FORM_WORDS: Final[frozenset[str]] = frozenset(
    {
        "mg", "ml", "mcg", "gm", "g", "iu",
        "tab", "tabs", "tablet", "tablets",
        "cap", "caps", "capsule", "capsules",
        "syp", "syrup", "susp", "suspension", "solution", "soln",
        "inj", "injection", "drops", "drop",
        "cream", "ointment", "gel", "lotion", "powder", "sachet",
        "kit", "spray", "duo", "forte", "plus", "xr", "sr", "cr", "od",
    }
)
"""Words that name a form or pack rather than a brand.

'Augmentin 625 Duo Tablet' and 'Augmentin' are the same brand, and a
prescription writes whichever the prescriber had in mind. Stripping these is
what lets an exact match succeed; without it the written name falls through to
the fuzzy path and is refused for want of a word the pharmacist did not intend
as part of the name.

Strengths are stripped separately because they are digits, and a strength that
distinguishes two products is carried in its own column rather than in the key.
"""

STRENGTH_TOKEN: Final[re.Pattern[str]] = re.compile(r"^\d+(?:\.\d+)?(?:mg|ml|mcg|gm|g|iu)?$")


def normalise_brand(text: str) -> str:
    """Reduce a written brand name for comparison.

    Strength and form are stripped: 'Glycomet 500 tab' and 'Glycomet' are the
    same brand, and the strength is captured separately rather than treated as
    part of the name.

    This function is the single definition of a brand key. scripts/
    build_brand_index.py imports it rather than reimplementing it: two
    normalisers that disagree produce an index whose keys the resolver cannot
    look up, which fails as a refusal rather than as an error.
    """
    decomposed = unicodedata.normalize("NFKC", text).lower()
    kept = "".join(c if c.isalnum() or c.isspace() else " " for c in decomposed)
    tokens = [
        token
        for token in kept.split()
        if not STRENGTH_TOKEN.match(token) and token not in FORM_WORDS
    ]
    return " ".join(tokens)


@dataclass(frozen=True)
class Scored:
    brand: Brand
    score: float


class BrandIndex:
    """A lookup from written brand names to molecules.

    Fuzzy, unlike the terminology index, because a handwritten brand name is
    routinely misspelled by the prescriber and misread by the OCR. The
    fuzziness is bounded by a high floor and by the ambiguity margin, so a near
    tie refuses rather than picking.
    """

    def __init__(self, brands: tuple[Brand, ...] = ()) -> None:
        self._brands = brands
        self._exact: dict[str, Brand] = {}
        self._keys: dict[str, str] = {}
        self._blocks: dict[str, list[str]] = {}
        for brand in brands:
            key = normalise_brand(brand.name)
            if key in self._exact:
                raise BrandIndexError(
                    f"brand {brand.name!r} is defined twice; one definition would be "
                    f"silently ignored"
                )
            self._exact[key] = brand
            self._keys[key] = key
            if key:
                self._blocks.setdefault(key[0], []).append(key)

    def __len__(self) -> int:
        return len(self._brands)

    def _candidate_keys(self, target: str) -> list[str]:
        """The keys worth scoring against `target`.

        SequenceMatcher over every brand is O(n) in the index, which at the
        size of the real Indian index (~186,000 brands) costs seconds per
        unmatched line. A prescription with five unreadable lines would take
        twenty.

        Two blocks cut it without weakening the match. A ratio of at least
        RESOLUTION_FLOOR is arithmetically impossible unless the lengths are
        within a bounded factor, since the ratio is 2M/T and M cannot exceed
        the shorter length. And a first letter is what OCR is most likely to
        read correctly — it is the character with the most whitespace around
        it. Both are conservative: they exclude only candidates that could not
        have cleared the floor anyway.
        """
        span = len(target)
        # 2*min/(a+b) >= floor  =>  longer <= shorter * (2 - floor) / floor
        widest = max(1, int(span * (2 - RESOLUTION_FLOOR) / RESOLUTION_FLOOR) + 1)
        narrowest = max(1, int(span * RESOLUTION_FLOOR / (2 - RESOLUTION_FLOOR)))
        return [
            key
            for key in self._blocks.get(target[0], ())
            if narrowest <= len(key) <= widest
        ]

    def score_all(self, written: str) -> tuple[Scored, ...]:
        """The plausible brands, scored against `written`, best first.

        Candidates that could not reach RESOLUTION_FLOOR are not scored; see
        _candidate_keys. The result is the same as scoring every brand and
        discarding those below the floor, which is all any caller uses.
        """
        target = normalise_brand(written)
        if not target:
            return ()
        matcher = SequenceMatcher()
        matcher.set_seq2(target)
        scored = []
        for key in self._candidate_keys(target):
            matcher.set_seq1(key)
            # Two cheap upper bounds before the quadratic comparison.
            if matcher.real_quick_ratio() < RESOLUTION_FLOOR:
                continue
            if matcher.quick_ratio() < RESOLUTION_FLOOR:
                continue
            scored.append(Scored(brand=self._exact[key], score=matcher.ratio()))
        return tuple(sorted(scored, key=lambda s: s.score, reverse=True))

    def resolve(self, written: str) -> tuple[ResolutionStatus, tuple[Scored, ...]]:
        """Resolve a written name, or say why it could not be.

        Returns the status and the candidates that produced it, so a caller can
        show a pharmacist what the alternatives were rather than only that it
        failed.
        """
        target = normalise_brand(written)
        if not target:
            return ResolutionStatus.UNREADABLE, ()
        if target in self._exact:
            return ResolutionStatus.RESOLVED, (Scored(self._exact[target], 1.0),)

        scored = self.score_all(written)
        if not scored or scored[0].score < RESOLUTION_FLOOR:
            return ResolutionStatus.REFUSED, scored[:3]
        runner_up = scored[1].score if len(scored) > 1 else 0.0
        if scored[0].score - runner_up < AMBIGUITY_MARGIN:
            return ResolutionStatus.AMBIGUOUS, scored[:3]
        return ResolutionStatus.RESOLVED, (scored[0],)


def resolve_line(
    written: str,
    index: BrandIndex,
    provenance: Provenance,
    *,
    ocr_confidence: float = 1.0,
) -> PrescribedMedication:
    """One prescription line, resolved.

    `ocr_confidence` multiplies into the resolution confidence rather than
    being ignored, because a perfect match against a badly-read word is not a
    confident resolution.

    A line the OCR produced nothing for is UNREADABLE, which is a resolution
    outcome rather than an error. The pharmacist still needs to see that the
    line existed, so it is recorded rather than dropped.
    """
    if not written.strip():
        return PrescribedMedication(
            written_as=UNREADABLE_PLACEHOLDER,
            resolution=ResolutionStatus.UNREADABLE,
            resolution_confidence=0.0,
            provenance=provenance,
        )
    status, candidates = index.resolve(written)
    match_score = candidates[0].score if candidates else 0.0
    confidence = match_score * ocr_confidence

    if status is ResolutionStatus.RESOLVED and confidence < RESOLUTION_FLOOR:
        status = ResolutionStatus.REFUSED

    if status is ResolutionStatus.RESOLVED:
        brand = candidates[0].brand
        return PrescribedMedication(
            written_as=written,
            molecules=tuple(
                Molecule(name=name, strength_mg=brand.strength_mg) for name in brand.molecules
            ),
            resolution=ResolutionStatus.RESOLVED,
            resolution_confidence=confidence,
            provenance=provenance,
        )

    if status is ResolutionStatus.AMBIGUOUS:
        return PrescribedMedication(
            written_as=written,
            resolution=ResolutionStatus.AMBIGUOUS,
            resolution_confidence=confidence,
            provenance=provenance,
            candidates=tuple(
                molecule for scored in candidates for molecule in scored.brand.molecules
            ),
        )

    return PrescribedMedication(
        written_as=written,
        resolution=status,
        resolution_confidence=confidence,
        provenance=provenance,
    )


def load_brand_index(path: Path) -> BrandIndex:
    """Read a brand index from CSV.

    Columns: brand, molecules, strength_mg. Molecules are pipe-separated,
    because combination products are the norm.
    """
    if not path.is_file():
        raise BrandIndexError(
            f"no brand index at {path}. Build one with "
            f"'python scripts/build_brand_index.py --source <dataset> --out {path}'; "
            f"that script names the open dataset it reads and where to download it"
        )
    brands: list[Brand] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"brand", "molecules"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise BrandIndexError(f"{path} is missing column(s): {', '.join(sorted(missing))}")
        for number, row in enumerate(reader, start=2):
            molecules = tuple(m.strip().lower() for m in row["molecules"].split("|") if m.strip())
            if not molecules:
                raise BrandIndexError(f"{path} line {number}: no molecules listed")
            raw_strength = (row.get("strength_mg") or "").strip()
            brands.append(
                Brand(
                    name=row["brand"].strip(),
                    molecules=molecules,
                    strength_mg=float(raw_strength) if raw_strength else None,
                )
            )
    return BrandIndex(tuple(brands))
