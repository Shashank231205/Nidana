"""Medications, resolved from what a prescription actually says.

S3 Rx writes these. In the spine because Scribe reads the medication list when
documenting, Labs reads it when interpreting a result, and Consult reads it
when triaging. A medication list assembled from every prescription photographed
is the thing no single-prescription tool can produce.

The core problem this shape exists for: one molecule, fifty brand names, and a
prescription written by hand. Resolution can fail, and a failed resolution must
be visible rather than guessed.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.primitives import Coding
from spine.schemas.provenance import Provenance

MINIMUM_AMBIGUOUS_CANDIDATES = 2
"""Ambiguity means more than one reading, and a pharmacist needs to see them."""


class ResolutionStatus(str, Enum):
    """How confident the brand-to-molecule resolution is.

    REFUSED is a success state, not a failure. Below the confidence threshold
    Rx refuses rather than guesses, and a refusal a pharmacist resolves is
    safer than a confident wrong molecule they do not question.
    """

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    REFUSED = "refused"
    UNREADABLE = "unreadable"


class Route(str, Enum):
    ORAL = "oral"
    TOPICAL = "topical"
    INHALED = "inhaled"
    INJECTION = "injection"
    OPHTHALMIC = "ophthalmic"
    NASAL = "nasal"
    RECTAL = "rectal"
    UNKNOWN = "unknown"


class Molecule(BaseModel):
    """An active ingredient, with its strength where one was legible."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1, description="Generic name, lowercase")
    strength_mg: float | None = Field(default=None, gt=0)
    codings: tuple[Coding, ...] = ()


class PrescribedMedication(BaseModel):
    """One line of a prescription, as read and resolved.

    `written_as` is what the prescription said. `molecules` is what that
    resolved to. Keeping both is what lets a pharmacist check the resolution
    rather than trust it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    written_as: str = Field(min_length=1, description="The brand or name as written")
    molecules: tuple[Molecule, ...] = ()
    resolution: ResolutionStatus
    resolution_confidence: float = Field(ge=0.0, le=1.0)
    route: Route = Route.UNKNOWN
    frequency: str | None = Field(default=None, description="As written, not normalised")
    duration_days: int | None = Field(default=None, gt=0)
    provenance: Provenance
    prescriber: str | None = None
    candidates: tuple[str, ...] = Field(
        default=(),
        description="Other molecules this could be, when resolution was ambiguous",
    )

    @model_validator(mode="after")
    def _a_resolved_medication_names_its_molecule(self) -> PrescribedMedication:
        if self.resolution is ResolutionStatus.RESOLVED and not self.molecules:
            raise ValueError(
                f"{self.written_as!r} is marked resolved but names no molecule; a "
                f"resolution that produced nothing is REFUSED, not RESOLVED"
            )
        return self

    @model_validator(mode="after")
    def _an_ambiguous_resolution_lists_what_it_could_be(self) -> PrescribedMedication:
        if (
            self.resolution is ResolutionStatus.AMBIGUOUS
            and len(self.candidates) < MINIMUM_AMBIGUOUS_CANDIDATES
        ):
            raise ValueError(
                f"{self.written_as!r} is marked ambiguous but lists "
                f"{len(self.candidates)} candidate(s); ambiguity means more than one "
                f"reading, and a pharmacist needs to see them"
            )
        return self

    @model_validator(mode="after")
    def _a_refusal_carries_no_molecule(self) -> PrescribedMedication:
        if self.resolution in {ResolutionStatus.REFUSED, ResolutionStatus.UNREADABLE} and (
            self.molecules
        ):
            raise ValueError(
                f"{self.written_as!r} is {self.resolution.value} but names a molecule; a "
                f"refusal that still asserts an answer is not a refusal"
            )
        return self

    @property
    def needs_human_confirmation(self) -> bool:
        """Whether a pharmacist or clinician must look at this line.

        Anything not cleanly resolved. Rx surfaces these rather than silently
        best-guessing, which is the design assumption for handwritten input.
        """
        return self.resolution is not ResolutionStatus.RESOLVED

    @property
    def molecule_names(self) -> frozenset[str]:
        return frozenset(molecule.name for molecule in self.molecules)


class MedicationList(BaseModel):
    """Everything a patient is taking, from every source.

    This is why Rx belongs in a platform. A single prescription cannot be
    checked in isolation, and every standalone tool tries to.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    medications: tuple[PrescribedMedication, ...] = ()

    @property
    def all_molecules(self) -> frozenset[str]:
        return frozenset().union(*(m.molecule_names for m in self.medications)) if (
            self.medications
        ) else frozenset()

    @property
    def unresolved(self) -> tuple[PrescribedMedication, ...]:
        return tuple(m for m in self.medications if m.needs_human_confirmation)

    def duplicate_molecules(self) -> frozenset[str]:
        """Molecules appearing on more than one line.

        Two prescribers, same molecule, different brands. Common, dangerous,
        and invisible to a patient reading two brand names.
        """
        seen: dict[str, int] = {}
        for medication in self.medications:
            for name in medication.molecule_names:
                seen[name] = seen.get(name, 0) + 1
        return frozenset(name for name, count in seen.items() if count > 1)

    def lines_containing(self, molecule: str) -> tuple[PrescribedMedication, ...]:
        return tuple(m for m in self.medications if molecule in m.molecule_names)
