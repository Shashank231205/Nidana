"""Pairwise drug interaction checking, against whatever dataset a deployment has.

The dataset is deliberately not chosen here. The best free option, DDInter, is
CC BY-NC-SA 4.0: usable in a non-commercial deployment, not usable in a
commercial one without permission. DrugBank is licensed. Whether either fits is
the repository owner's decision, and `services/rx/rules/interactions/
CANDIDATES.md` records what each answer implies.

So this module takes an index and asks it questions. Swapping the source means
writing a different loader, not touching the checker.

**What is not checked is reported.** This is the property the module is built
around. An interaction dataset knows some molecules and not others, and a
molecule it does not know has not been cleared — it has been skipped. A
pharmacist reading "no interactions found" against a prescription where two of
five molecules were never in the dataset has been told something false. Every
answer therefore carries the molecules that were not covered, and `run_all`
raises a finding when any exist.

**Severity comes from the dataset, not from here.** What counts as a major
interaction differs between sources, the same disagreement the critical value
thresholds have. Mapping a source's grades onto Severity is the loader's job
and its mapping is recorded with the index, so a pharmacist can see whose
judgement they are reading.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from services.rx.clinical.checks import CheckKind, Finding, Severity
from spine.schemas.medication import MedicationList

UNCOVERED_SEVERITY: Final[Severity] = Severity.MODERATE
"""How much it matters that a molecule was not in the dataset.

Not contraindicated: an uncovered molecule is common and blocking on it would
make the check unusable. Not minor either — a pharmacist must know which lines
were actually checked, because "no interactions found" over an unchecked
molecule is a false reassurance rather than an absent one.
"""


class InteractionIndexError(RuntimeError):
    """Raised when an interaction index is missing or malformed."""


@dataclass(frozen=True)
class Interaction:
    """One documented interaction between two molecules.

    `mechanism` and `management` are carried through rather than summarised. A
    pharmacist deciding whether to phone the prescriber needs to know whether
    the risk is additive sedation or a QT prolongation, and a one-line severity
    grade does not say.
    """

    first: str
    second: str
    severity: Severity
    mechanism: str
    management: str

    @property
    def pair(self) -> tuple[str, str]:
        """The molecules, ordered, so lookup does not depend on prescribing order."""
        return (self.first, self.second) if self.first <= self.second else (self.second, self.first)


@dataclass(frozen=True)
class InteractionReport:
    """What was found, and what could not be looked at.

    `uncovered` is not an error condition. It is the ordinary case — no
    dataset covers every molecule in an Indian formulary — and it is returned
    on every report so a caller cannot read `found` as "these are all the
    interactions".
    """

    found: tuple[Interaction, ...]
    uncovered: tuple[str, ...]
    checked_pairs: int
    attribution: str

    @property
    def is_complete(self) -> bool:
        """Whether every molecule on the prescription was actually checked."""
        return not self.uncovered


class InteractionIndex:
    """Documented interactions, keyed by molecule pair.

    `covered` is separate from the interaction table and is the reason this
    class exists rather than a bare dict. A pair absent from the table means
    "no interaction documented" only if both molecules are in the dataset at
    all; otherwise it means "not looked at", and conflating those is how a
    checker tells a pharmacist a prescription is clear when it was never read.
    """

    def __init__(
        self,
        interactions: tuple[Interaction, ...] = (),
        covered: frozenset[str] = frozenset(),
        attribution: str = "unattributed interaction dataset",
    ) -> None:
        self._by_pair: dict[tuple[str, str], Interaction] = {}
        for interaction in interactions:
            self._by_pair[interaction.pair] = interaction
        # A molecule named in the table is covered by definition; the explicit
        # set adds those the dataset knows and found nothing for.
        self._covered = covered | {
            molecule for interaction in interactions for molecule in interaction.pair
        }
        self._attribution = attribution

    def __len__(self) -> int:
        return len(self._by_pair)

    @property
    def attribution(self) -> str:
        """Who to credit, carried into every finding.

        Licences that require attribution — CC BY-NC-SA among them — are not
        satisfied by a line in a README nobody reads at the counter.
        """
        return self._attribution

    def covers(self, molecule: str) -> bool:
        return molecule.strip().lower() in self._covered

    def between(self, first: str, second: str) -> Interaction | None:
        """The documented interaction between two molecules, if any."""
        left, right = first.strip().lower(), second.strip().lower()
        key = (left, right) if left <= right else (right, left)
        return self._by_pair.get(key)


def check_interactions(
    medications: MedicationList, index: InteractionIndex
) -> InteractionReport:
    """Every documented interaction among the prescribed molecules.

    Only resolved lines are checked, because an unresolved line has no molecule
    to check. That is already reported separately by `check_unresolved`, and
    counting it twice would tell a pharmacist there are two problems.
    """
    molecules = sorted(
        {
            molecule.name.strip().lower()
            for medication in medications.medications
            for molecule in medication.molecules
        }
    )

    found: list[Interaction] = []
    pairs = 0
    for i, first in enumerate(molecules):
        for second in molecules[i + 1 :]:
            if not (index.covers(first) and index.covers(second)):
                continue
            pairs += 1
            interaction = index.between(first, second)
            if interaction is not None:
                found.append(interaction)

    severity_order = {
        Severity.CONTRAINDICATED: 0,
        Severity.SEVERE: 1,
        Severity.MODERATE: 2,
        Severity.MINOR: 3,
    }
    return InteractionReport(
        found=tuple(sorted(found, key=lambda i: severity_order[i.severity])),
        uncovered=tuple(m for m in molecules if not index.covers(m)),
        checked_pairs=pairs,
        attribution=index.attribution,
    )


def findings_from(
    report: InteractionReport, medications: MedicationList
) -> tuple[Finding, ...]:
    """The report as findings a pharmacist reads alongside the other checks."""
    written_for = _written_names(medications)
    findings = [
        Finding(
            kind=CheckKind.INTERACTION,
            severity=interaction.severity,
            molecules=interaction.pair,
            written_as=tuple(
                written_for[molecule] for molecule in interaction.pair if molecule in written_for
            ),
            message=(
                f"{interaction.first} with {interaction.second}: {interaction.mechanism}. "
                f"{interaction.management}"
            ),
            source=report.attribution,
        )
        for interaction in report.found
    ]

    if report.uncovered:
        listed = ", ".join(report.uncovered)
        many = len(report.uncovered) > 1
        subject = "these molecules" if many else "this molecule"
        pronoun = "them" if many else "it"
        findings.append(
            Finding(
                kind=CheckKind.INTERACTION,
                severity=UNCOVERED_SEVERITY,
                molecules=report.uncovered,
                written_as=tuple(
                    written_for[molecule]
                    for molecule in report.uncovered
                    if molecule in written_for
                ),
                message=(
                    f"Not checked for interactions: {listed}. The interaction "
                    f"dataset does not cover {subject}, so nothing above rules "
                    f"out an interaction involving {pronoun}"
                ),
                source=report.attribution,
            )
        )
    return tuple(findings)


def _written_names(medications: MedicationList) -> dict[str, str]:
    """Molecule to the line it was written as, for a pharmacist reading the script."""
    written: dict[str, str] = {}
    for medication in medications.medications:
        for molecule in medication.molecules:
            written.setdefault(molecule.name.strip().lower(), medication.written_as)
    return written


def load_interaction_index(
    path: Path, *, attribution: str, covered_path: Path | None = None
) -> InteractionIndex:
    """Read an interaction index from CSV.

    Columns: first, second, severity, mechanism, management. Severity must be a
    member of `Severity`; the loader for a given source is responsible for
    having mapped that source's own grades onto it, and `attribution` records
    whose judgement those grades are.

    `covered_path` is a newline-separated list of every molecule the dataset
    knows, including those with no documented interaction. Without it, coverage
    is inferred from the interaction table alone, which understates it: a
    molecule the dataset examined and cleared looks identical to one it never
    saw.
    """
    if not path.is_file():
        raise InteractionIndexError(
            f"no interaction index at {path}. See "
            f"services/rx/rules/interactions/CANDIDATES.md for the available "
            f"datasets and what each one's licence permits"
        )

    interactions: list[Interaction] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"first", "second", "severity"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise InteractionIndexError(
                f"{path} is missing column(s): {', '.join(sorted(missing))}"
            )
        for number, row in enumerate(reader, start=2):
            interactions.append(_interaction_from(row, path, number))

    covered: frozenset[str] = frozenset()
    if covered_path is not None:
        if not covered_path.is_file():
            raise InteractionIndexError(
                f"no coverage list at {covered_path}. It names every molecule the "
                f"dataset knows, including those with no documented interaction; "
                f"without it a cleared molecule cannot be told from an unexamined one"
            )
        covered = frozenset(
            line.strip().lower()
            for line in covered_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )

    return InteractionIndex(tuple(interactions), covered, attribution)


def _interaction_from(row: dict[str, str], path: Path, line: int) -> Interaction:
    first = row["first"].strip().lower()
    second = row["second"].strip().lower()
    if not first or not second:
        raise InteractionIndexError(f"{path} line {line}: both molecules must be named")
    if first == second:
        raise InteractionIndexError(
            f"{path} line {line}: {first!r} interacts with itself; that is a duplicate "
            f"therapy finding rather than an interaction"
        )
    try:
        severity = Severity(row["severity"].strip().lower())
    except ValueError as error:
        known = ", ".join(s.value for s in Severity)
        raise InteractionIndexError(
            f"{path} line {line}: {error}. Known severities are: {known}. The loader "
            f"for a source maps that source's own grades onto these"
        ) from error
    return Interaction(
        first=first,
        second=second,
        severity=severity,
        mechanism=(row.get("mechanism") or "").strip() or "mechanism not recorded",
        management=(row.get("management") or "").strip() or "Review with the prescriber.",
    )
