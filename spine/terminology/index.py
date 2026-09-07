"""Terminology lookup. Deterministic, no model.

Maps clinical text to coded concepts. Shared by every service: Consult codes
findings, Scribe codes diagnoses, Rx codes molecules, Labs codes analytes.

Two things this deliberately is not.

It is not a model. A lookup that sometimes invents a code is worse than one
that sometimes finds nothing, because a wrong code propagates into an exported
FHIR record and is indistinguishable from a right one downstream.

It is not a fuzzy matcher pretending to be a mapper. Below a confidence
threshold it returns nothing rather than a plausible neighbour. `paracetamol`
and `paroxetine` share a prefix and nothing else.
"""

from __future__ import annotations

import csv
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Final

from spine.schemas.primitives import Coding


class CodeSystem(str, Enum):
    """The systems a concept may be coded in.

    SNOMED CT licensing for India is unresolved (`docs/BUILD_SPEC.md` section
    8), so ICD-10 is the fallback and the index is system-agnostic. Nothing here
    depends on which is available.
    """

    SNOMED_CT = "http://snomed.info/sct"
    ICD_10 = "http://hl7.org/fhir/sid/icd-10"
    LOINC = "http://loinc.org"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    LOCAL = "urn:nidana:local"


class TerminologyLoadError(RuntimeError):
    """Raised when a terminology file is missing or malformed."""


@dataclass(frozen=True)
class Concept:
    """One coded concept and the terms that reach it."""

    system: CodeSystem
    code: str
    display: str
    synonyms: tuple[str, ...] = ()

    def as_coding(self) -> Coding:
        return Coding(system=self.system.value, code=self.code, display=self.display)

    @property
    def all_terms(self) -> tuple[str, ...]:
        return (self.display, *self.synonyms)


@dataclass(frozen=True)
class Match:
    """A lookup result, with how it was found.

    `exact` distinguishes a term that matched a known synonym from one that
    matched after normalisation. Both are usable; only the first is certain.
    """

    concept: Concept
    matched_term: str
    exact: bool

    @property
    def coding(self) -> Coding:
        return self.concept.as_coding()


def normalise(text: str) -> str:
    """Reduce a term to a comparable form.

    Unicode normalisation matters here rather than being ceremony: clinical
    text arrives in Devanagari, in Roman transliteration, and with combining
    marks that render identically but compare unequal.

    Case, surrounding whitespace, and internal runs of whitespace are flattened.
    Nothing else is stripped — punctuation inside a drug name is part of it.
    """
    decomposed = unicodedata.normalize("NFKC", text)
    return " ".join(decomposed.lower().split())


class TerminologyIndex:
    """An in-memory lookup over loaded concepts.

    Deliberately simple. An exact-match index with normalisation is honest
    about what it can do; a fuzzy index that scores 0.7 on an unrelated term
    is not, and the failure mode is a wrong code in an exported record.
    """

    def __init__(self, concepts: Iterable[Concept] = ()) -> None:
        self._by_code: dict[tuple[CodeSystem, str], Concept] = {}
        self._by_term: dict[str, list[Concept]] = {}
        for concept in concepts:
            self.add(concept)

    def add(self, concept: Concept) -> None:
        key = (concept.system, concept.code)
        if key in self._by_code:
            raise TerminologyLoadError(
                f"{concept.system.value} code {concept.code} is defined twice; one "
                f"definition would be silently ignored"
            )
        self._by_code[key] = concept
        for term in concept.all_terms:
            self._by_term.setdefault(normalise(term), []).append(concept)

    def __len__(self) -> int:
        return len(self._by_code)

    @property
    def systems(self) -> frozenset[CodeSystem]:
        return frozenset(system for system, _ in self._by_code)

    def by_code(self, system: CodeSystem, code: str) -> Concept | None:
        return self._by_code.get((system, code))

    def lookup(self, text: str, system: CodeSystem | None = None) -> tuple[Match, ...]:
        """Every concept `text` maps to.

        More than one is a real answer, not a failure: a term that is ambiguous
        across systems, or within one, should be reported as ambiguous rather
        than resolved by picking the first.
        """
        candidates = self._by_term.get(normalise(text), [])
        if system is not None:
            candidates = [c for c in candidates if c.system is system]
        return tuple(
            Match(concept=concept, matched_term=text, exact=text in concept.all_terms)
            for concept in candidates
        )

    def resolve(self, text: str, system: CodeSystem | None = None) -> Match | None:
        """The single concept `text` maps to, or None.

        Returns None when nothing matches and also when more than one thing
        does. An ambiguous term resolved by picking one is the failure this
        module is built to avoid; callers that can handle ambiguity use
        `lookup`.
        """
        matches = self.lookup(text, system)
        return matches[0] if len(matches) == 1 else None

    def code_for(self, text: str, system: CodeSystem | None = None) -> Coding | None:
        match = self.resolve(text, system)
        return match.coding if match else None


TERMINOLOGY_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "data" / "terminology"


def load_csv(path: Path) -> tuple[Concept, ...]:
    """Read concepts from a CSV.

    Columns: system, code, display, synonyms. Synonyms are pipe-separated,
    because a clinical display name may legitimately contain a comma.
    """
    if not path.is_file():
        raise TerminologyLoadError(
            f"no terminology file at {path}. Terminology subsets load through versioned "
            f"scripts, not manual inserts"
        )
    concepts: list[Concept] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"system", "code", "display"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise TerminologyLoadError(
                f"{path} is missing column(s): {', '.join(sorted(missing))}"
            )
        for number, row in enumerate(reader, start=2):
            try:
                system = CodeSystem(row["system"].strip())
            except ValueError as error:
                raise TerminologyLoadError(
                    f"{path} line {number}: unknown code system {row['system']!r}"
                ) from error
            raw_synonyms = (row.get("synonyms") or "").strip()
            concepts.append(
                Concept(
                    system=system,
                    code=row["code"].strip(),
                    display=row["display"].strip(),
                    synonyms=tuple(s.strip() for s in raw_synonyms.split("|") if s.strip()),
                )
            )
    return tuple(concepts)


def load_index(directory: Path | None = None) -> TerminologyIndex:
    """Build an index from every CSV in `directory`.

    An empty directory produces an empty index rather than an error. Nothing in
    this repository ships a terminology subset: SNOMED CT licensing for India is
    unresolved, and shipping an invented subset would produce codes that look
    real.
    """
    base = directory if directory is not None else TERMINOLOGY_ROOT
    index = TerminologyIndex()
    if not base.is_dir():
        return index
    for path in sorted(base.glob("*.csv")):
        for concept in load_csv(path):
            index.add(concept)
    return index
