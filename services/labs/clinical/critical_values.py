"""Critical value detection. Deterministic, no model.

Same safety status as Consult's red flags: a value here means contact someone
now, and the release gate is 100% sensitivity.

Two things separate this from ordinary range checking.

A critical value is not merely outside the reference range. A potassium can sit
outside its range without being critical, and a glucose can be critical while
inside a range printed for a different population. The two answer different
questions, so critical thresholds are their own table.

Thresholds live in `rules/critical_values/`, cited and versioned, never in this
file. Nothing here contains a number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from spine.rules.registry_loader import rules_root
from spine.schemas.lab import Flag, LabReport, LabResult


class CriticalValueLoadError(RuntimeError):
    """Raised when a threshold file is malformed or self-contradictory."""


class UnverifiedThresholdsError(RuntimeError):
    """Raised when a release build would ship an unverified critical threshold."""


class CriticalThreshold(BaseModel):
    """One analyte's critical bounds.

    At least one bound is required. Some analytes are critical only when low,
    some only when high, and declaring both where only one applies invents a
    threshold.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analyte: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    critical_low: float | None = None
    critical_high: float | None = None
    source: str = Field(min_length=1)
    verified_on: str | None = None
    verify_before_ship: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def _a_threshold_bounds_something(self) -> CriticalThreshold:
        if self.critical_low is None and self.critical_high is None:
            raise ValueError(
                f"{self.analyte} declares neither a critical low nor a critical high; a "
                f"threshold bounding nothing can never fire"
            )
        if (
            self.critical_low is not None
            and self.critical_high is not None
            and self.critical_low >= self.critical_high
        ):
            raise ValueError(
                f"{self.analyte} critical low ({self.critical_low}) is not below its "
                f"critical high ({self.critical_high})"
            )
        return self

    @model_validator(mode="after")
    def _verification_state_is_coherent(self) -> CriticalThreshold:
        if not self.verify_before_ship and self.verified_on is None:
            raise ValueError(
                f"{self.analyte} is marked verified but carries no verified_on date; "
                f"record when a clinician signed the threshold off"
            )
        return self

    def classify(self, value: float) -> Flag | None:
        """Whether `value` is critical, and which way."""
        if self.critical_low is not None and value <= self.critical_low:
            return Flag.CRITICAL_LOW
        if self.critical_high is not None and value >= self.critical_high:
            return Flag.CRITICAL_HIGH
        return None


@dataclass(frozen=True)
class CriticalFinding:
    """One result that crossed a critical threshold."""

    analyte: str
    value: float
    unit: str
    flag: Flag
    threshold: float
    source: str
    unverified: bool

    @property
    def message(self) -> str:
        direction = "at or below" if self.flag is Flag.CRITICAL_LOW else "at or above"
        return (
            f"{self.analyte} is {self.value} {self.unit}, {direction} the critical "
            f"threshold of {self.threshold} {self.unit}"
        )


CRITICAL_VALUES_KIND: Final[str] = "critical_values"


def thresholds_dir(service: str = "labs") -> Path:
    return rules_root(service) / CRITICAL_VALUES_KIND


def load_thresholds(directory: Path | None = None) -> dict[str, CriticalThreshold]:
    """Load every critical threshold, keyed by lowercased analyte name.

    A duplicate analyte across files is a load failure: two thresholds for one
    analyte means one of them is silently ignored, and which one depends on file
    ordering.
    """
    base = directory if directory is not None else thresholds_dir()
    if not base.is_dir():
        raise CriticalValueLoadError(
            f"critical value directory {base} does not exist; it holds the thresholds "
            f"that trigger immediate escalation"
        )
    paths = sorted(base.glob("*.yaml"))
    if not paths:
        raise CriticalValueLoadError(f"no threshold files found in {base}")

    loaded: dict[str, CriticalThreshold] = {}
    origin: dict[str, Path] = {}
    for path in paths:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as error:
            raise CriticalValueLoadError(f"{path} is not valid YAML: {error}") from error
        if not isinstance(raw, dict) or "thresholds" not in raw:
            raise CriticalValueLoadError(
                f"{path} must contain a top-level 'thresholds' list"
            )
        for entry in raw["thresholds"]:
            try:
                threshold = CriticalThreshold.model_validate(entry)
            except ValidationError as error:
                raise CriticalValueLoadError(
                    f"invalid threshold in {path}: {error}"
                ) from error
            key = threshold.analyte.strip().lower()
            if key in loaded:
                raise CriticalValueLoadError(
                    f"{threshold.analyte} has thresholds in both {origin[key]} and "
                    f"{path}; one would be silently ignored"
                )
            loaded[key] = threshold
            origin[key] = path
    return loaded


def require_verified(
    thresholds: dict[str, CriticalThreshold],
    allow_unverified: bool,
) -> None:
    """Refuse to proceed when a release build would ship an unverified threshold.

    The same gate Consult applies to red flag rules, for the same reason: a
    critical value threshold decides whether someone is contacted immediately.
    """
    if allow_unverified:
        return
    pending = sorted(t.analyte for t in thresholds.values() if t.verify_before_ship)
    if pending:
        raise UnverifiedThresholdsError(
            f"{len(pending)} critical threshold(s) carry verify_before_ship and cannot "
            f"ship: {', '.join(pending)}. A qualified clinician must verify each against "
            f"its cited source, then set verify_before_ship false with the verified_on "
            f"date. To run anyway in development, set NIDANA_ALLOW_UNVERIFIED_RULES=true"
        )


def _check_result(
    result: LabResult, thresholds: dict[str, CriticalThreshold]
) -> CriticalFinding | None:
    threshold = thresholds.get(result.analyte.strip().lower())
    if threshold is None:
        return None
    if threshold.unit != result.unit:
        return None
    flag = threshold.classify(result.value)
    if flag is None:
        return None
    bound = threshold.critical_low if flag is Flag.CRITICAL_LOW else threshold.critical_high
    return CriticalFinding(
        analyte=result.analyte,
        value=result.value,
        unit=result.unit,
        flag=flag,
        threshold=bound if bound is not None else 0.0,
        source=threshold.source,
        unverified=threshold.verify_before_ship,
    )


def check(
    report: LabReport, thresholds: dict[str, CriticalThreshold]
) -> tuple[CriticalFinding, ...]:
    """Every critical value in a report.

    Pure. Report and thresholds in, findings out.
    """
    found = (_check_result(result, thresholds) for result in report.results)
    return tuple(finding for finding in found if finding is not None)


def unit_mismatches(
    report: LabReport, thresholds: dict[str, CriticalThreshold]
) -> tuple[str, ...]:
    """Analytes with a threshold that could not be applied, because units differ.

    Reported separately and loudly. A silent skip here is a missed critical
    value, which is the one failure this module exists to prevent, so a caller
    that ignores this list has a gap it does not know about.
    """
    mismatched: list[str] = []
    for result in report.results:
        threshold = thresholds.get(result.analyte.strip().lower())
        if threshold is not None and threshold.unit != result.unit:
            mismatched.append(
                f"{result.analyte} reported in {result.unit}, threshold in {threshold.unit}"
            )
    return tuple(mismatched)
