"""Rx safety checks. Deterministic, no model.

No model decides whether two drugs interact. Interaction, duplicate therapy,
allergy and contraindication checking are rules over a molecule list, and every
one of them is a case where being wrong causes physical harm.

Rx never computes a dose. It range-checks a stated dose and flags implausibility
for a human, which is a different thing and stays the right side of the
regulatory boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from spine.schemas.medication import MedicationList, PrescribedMedication
from spine.schemas.primitives import PregnancyStatus
from spine.schemas.record import Allergy, Record


class Severity(str, Enum):
    """How much a finding matters.

    CONTRAINDICATED means do not dispense without prescriber contact.
    SEVERE means contact the prescriber.
    MODERATE means counsel the patient and monitor.
    MINOR means note it.
    """

    CONTRAINDICATED = "contraindicated"
    SEVERE = "severe"
    MODERATE = "moderate"
    MINOR = "minor"


UNRESOLVED_SEVERITY = Severity.CONTRAINDICATED
"""An unresolved line cannot be checked, so it cannot be cleared.

Contraindicated rather than severe: dispensing something the system could not
identify means every other check on the list ran without it.
"""


class CheckKind(str, Enum):
    INTERACTION = "interaction"
    DUPLICATE_THERAPY = "duplicate_therapy"
    ALLERGY = "allergy"
    PREGNANCY = "pregnancy"
    DOSE_RANGE = "dose_range"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Finding:
    """One thing a pharmacist or prescriber should look at.

    `molecules` names what triggered it and `written_as` names the lines it
    came from, because a pharmacist works from the prescription in front of
    them rather than from a molecule list.
    """

    kind: CheckKind
    severity: Severity
    molecules: tuple[str, ...]
    written_as: tuple[str, ...]
    message: str
    source: str

    @property
    def blocks_dispensing(self) -> bool:
        return self.severity is Severity.CONTRAINDICATED


def check_duplicate_therapy(medications: MedicationList) -> tuple[Finding, ...]:
    """Two lines carrying the same molecule.

    The check that most justifies Rx being part of a platform: it only works
    against the patient's full list, and it is invisible to a patient reading
    two different brand names.

    Deterministic and complete, unlike the interaction check, because it needs
    no external dataset — it is arithmetic over what has already been resolved.
    """
    findings: list[Finding] = []
    for molecule in sorted(medications.duplicate_molecules()):
        lines = medications.lines_containing(molecule)
        findings.append(
            Finding(
                kind=CheckKind.DUPLICATE_THERAPY,
                severity=Severity.SEVERE,
                molecules=(molecule,),
                written_as=tuple(line.written_as for line in lines),
                message=(
                    f"{molecule} appears on {len(lines)} lines: "
                    f"{', '.join(line.written_as for line in lines)}. Two prescribers may "
                    f"have prescribed the same molecule under different brand names"
                ),
                source="Derived from the resolved molecule list, not an external dataset",
            )
        )
    return tuple(findings)


def _allergy_matches(allergy: Allergy, molecule: str) -> bool:
    """Whether a recorded allergy covers a molecule.

    Substring matching in both directions, deliberately loose. A false positive
    costs a pharmacist a moment; a false negative costs an anaphylaxis. Class
    matching — that a penicillin allergy covers amoxicillin — needs a real
    dataset and is not attempted here rather than approximated badly.
    """
    substance = allergy.substance.strip().lower()
    name = molecule.strip().lower()
    if not substance or not name:
        return False
    return substance in name or name in substance


def check_allergies(medications: MedicationList, record: Record) -> tuple[Finding, ...]:
    """Prescribed molecules against recorded allergies."""
    findings: list[Finding] = []
    for medication in medications.medications:
        for molecule in sorted(medication.molecule_names):
            for allergy in record.allergies:
                if not _allergy_matches(allergy, molecule):
                    continue
                reaction = f" ({allergy.reaction})" if allergy.reaction else ""
                findings.append(
                    Finding(
                        kind=CheckKind.ALLERGY,
                        severity=Severity.CONTRAINDICATED,
                        molecules=(molecule,),
                        written_as=(medication.written_as,),
                        message=(
                            f"{medication.written_as} resolves to {molecule}, and the "
                            f"record holds an allergy to {allergy.substance}{reaction}"
                        ),
                        source="Recorded patient allergy",
                    )
                )
    return tuple(findings)


def check_unresolved(medications: MedicationList) -> tuple[Finding, ...]:
    """Lines that could not be read or resolved.

    A refusal is a finding rather than a silent omission, because a line nobody
    looked at is the one that gets dispensed wrong.
    """
    findings: list[Finding] = []
    for medication in medications.unresolved:
        findings.append(
            Finding(
                kind=CheckKind.UNRESOLVED,
                severity=UNRESOLVED_SEVERITY,
                molecules=tuple(sorted(medication.molecule_names)),
                written_as=(medication.written_as,),
                message=_unresolved_message(medication),
                source="Brand-to-molecule resolution",
            )
        )
    return tuple(findings)


def _unresolved_message(medication: PrescribedMedication) -> str:
    if medication.candidates:
        return (
            f"{medication.written_as!r} could be "
            f"{' or '.join(medication.candidates)}; it was not resolved and no "
            f"interaction or allergy check has run against it"
        )
    return (
        f"{medication.written_as!r} could not be resolved to a molecule "
        f"(confidence {medication.resolution_confidence:.0%}); no interaction or "
        f"allergy check has run against it"
    )


def check_pregnancy(medications: MedicationList, record: Record) -> tuple[Finding, ...]:
    """Flag prescribing where pregnancy status is unknown.

    This does not decide whether a molecule is safe in pregnancy — that needs a
    dataset and clinical sign-off. It flags the case where nobody asked, which
    is the failure a rule can catch.
    """
    if record.consult.pregnancy_status is not PregnancyStatus.UNKNOWN:
        return ()
    if not medications.medications:
        return ()
    return (
        Finding(
            kind=CheckKind.PREGNANCY,
            severity=Severity.MODERATE,
            molecules=tuple(sorted(medications.all_molecules)),
            written_as=tuple(m.written_as for m in medications.medications),
            message=(
                "Pregnancy status is not recorded and medication is being dispensed. "
                "Confirm before dispensing"
            ),
            source="Recorded pregnancy status",
        ),
    )


def run_all(medications: MedicationList, record: Record) -> tuple[Finding, ...]:
    """Every check, most severe first.

    Interaction checking is deliberately absent. It needs a licensed
    interaction dataset, which BUILD_SPEC lists as an unresolved dependency,
    and approximating it from general knowledge would produce a check that
    looks like it works.
    """
    findings = (
        *check_allergies(medications, record),
        *check_unresolved(medications),
        *check_duplicate_therapy(medications),
        *check_pregnancy(medications, record),
    )
    order = {
        Severity.CONTRAINDICATED: 0,
        Severity.SEVERE: 1,
        Severity.MODERATE: 2,
        Severity.MINOR: 3,
    }
    return tuple(sorted(findings, key=lambda finding: order[finding.severity]))


def blocks_dispensing(findings: tuple[Finding, ...]) -> bool:
    return any(finding.blocks_dispensing for finding in findings)
