"""Vignette loading.

A vignette is a scripted patient encounter with a clinician-assigned reference
band. The reference label is what makes the eval numbers mean anything, and it
is the one part of this file that cannot be written by an engineer.

`docs/BUILD_SPEC.md` section 8 lists the clinician reviewer as blocking and
unresolved. Until it is answered, a vignette may carry `reference_band: null`,
which excludes it from the scored metrics and is counted separately in the
report. That is honest; assigning a band ourselves and calling it a reference
would not be.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from spine.schemas.primitives import Band, PregnancyStatus, Sex
from spine.schemas.registry import ComplaintFamily
from spine.schemas.triage import Specialty

VIGNETTES_ROOT: Final[Path] = Path(__file__).resolve().parent / "cases"


class VignetteLoadError(RuntimeError):
    """Raised when a vignette file is malformed or self-contradictory."""


class Turn(BaseModel):
    """One scripted patient utterance.

    Written in the language and script a real patient would use, including
    code-switched forms, because an eval that only tests English measures the
    easy half of the problem.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    patient: str = Field(min_length=1)
    language: str = Field(default="en", min_length=2)


class Vignette(BaseModel):
    """One reference case.

    `reference_band` and `reference_specialty` are clinician-assigned. A
    vignette without them still runs — it exercises the pipeline and can catch
    a crash or a fabrication — but it does not score.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    description: str = Field(min_length=1)
    complaint_family: ComplaintFamily
    age_years: int | None = Field(default=None, ge=0, le=130)
    sex: Sex = Sex.UNKNOWN
    pregnancy_status: PregnancyStatus = PregnancyStatus.UNKNOWN
    is_proxy: bool = False
    turns: tuple[Turn, ...] = Field(min_length=1)

    reference_band: Band | None = None
    reference_specialty: Specialty | None = None
    expected_red_flags: tuple[str, ...] = ()
    reviewed_by: str | None = None
    reviewed_on: str | None = None

    source: str = Field(
        min_length=1,
        description="Where this case came from: a published source, or the clinician who wrote it",
    )
    adversarial: tuple[str, ...] = Field(
        default=(),
        description="Which adversarial patterns this case exercises, if any",
    )

    @model_validator(mode="after")
    def _a_reference_label_names_its_reviewer(self) -> Vignette:
        if self.reference_band is not None and not self.reviewed_by:
            raise ValueError(
                f"vignette {self.id} carries a reference band but names no reviewer. A "
                f"reference label written by an engineer is not a reference label; "
                f"record the clinician who assigned it in reviewed_by"
            )
        return self

    @model_validator(mode="after")
    def _expected_red_flags_imply_urgency(self) -> Vignette:
        if self.expected_red_flags and self.reference_band is None:
            raise ValueError(
                f"vignette {self.id} expects red flags to fire but carries no reference "
                f"band; a case testing an emergency rule needs a clinician-assigned band"
            )
        return self

    @property
    def is_scorable(self) -> bool:
        return self.reference_band is not None


def _read(path: Path) -> list[object]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise VignetteLoadError(f"{path} is not valid YAML: {error}") from error
    if not isinstance(raw, dict) or "vignettes" not in raw:
        raise VignetteLoadError(
            f"{path} must contain a top-level 'vignettes' list; found "
            f"{sorted(raw) if isinstance(raw, dict) else type(raw).__name__}"
        )
    entries = raw["vignettes"]
    if not isinstance(entries, list):
        raise VignetteLoadError(f"{path} 'vignettes' must be a list")
    return entries


def load_all(directory: Path | None = None) -> tuple[Vignette, ...]:
    """Every vignette, rejecting duplicate ids across files.

    An empty set is not an error. The vignette set is unwritten until a
    clinician is available, and pretending otherwise by shipping invented cases
    would make every downstream number meaningless.
    """
    base = directory if directory is not None else VIGNETTES_ROOT
    if not base.is_dir():
        return ()
    loaded: dict[str, Vignette] = {}
    origin: dict[str, Path] = {}
    for path in sorted(base.glob("*.yaml")):
        for entry in _read(path):
            try:
                vignette = Vignette.model_validate(entry)
            except ValidationError as error:
                raise VignetteLoadError(f"invalid vignette in {path}: {error}") from error
            if vignette.id in loaded:
                raise VignetteLoadError(
                    f"vignette {vignette.id} is defined in both {origin[vignette.id]} and "
                    f"{path}; each case has one definition"
                )
            loaded[vignette.id] = vignette
            origin[vignette.id] = path
    return tuple(loaded.values())


def scorable(vignettes: tuple[Vignette, ...]) -> tuple[Vignette, ...]:
    return tuple(vignette for vignette in vignettes if vignette.is_scorable)
