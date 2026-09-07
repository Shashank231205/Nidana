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


def normalise_brand(text: str) -> str:
    """Reduce a written brand name for comparison.

    Strength and form are stripped: 'Glycomet 500 tab' and 'Glycomet' are the
    same brand, and the strength is captured separately rather than treated as
    part of the name.
    """
    decomposed = unicodedata.normalize("NFKC", text).lower()
    kept = "".join(c if c.isalnum() or c.isspace() else " " for c in decomposed)
    tokens = [
        token
        for token in kept.split()
        if not token.isdigit() and token not in {"mg", "ml", "tab", "tabs", "cap", "caps", "syp"}
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
        for brand in brands:
            key = normalise_brand(brand.name)
            if key in self._exact:
                raise BrandIndexError(
                    f"brand {brand.name!r} is defined twice; one definition would be "
                    f"silently ignored"
                )
            self._exact[key] = brand

    def __len__(self) -> int:
        return len(self._brands)

    def score_all(self, written: str) -> tuple[Scored, ...]:
        """Every brand, scored against `written`, best first."""
        target = normalise_brand(written)
        if not target:
            return ()
        scored = [
            Scored(
                brand=brand,
                score=SequenceMatcher(None, target, normalise_brand(brand.name)).ratio(),
            )
            for brand in self._brands
        ]
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
            f"no brand index at {path}. The Indian brand-to-molecule mapping is not "
            f"publicly maintained in usable form and is listed as an unresolved "
            f"dependency in docs/BUILD_SPEC.md section 8"
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
