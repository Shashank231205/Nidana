"""Laboratory results, parsed from a report.

S4 Labs writes these. In the spine because Consult reads a result when
triaging, Rx reads renal and hepatic status before checking a prescription, and
Scribe records results discussed in a consultation.

The rule that shapes everything here: the printed reference range on the report
is authoritative. Ranges are age, sex and method dependent, and a lab's own
range for its own assay beats any internal table.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spine.schemas.primitives import Coding
from spine.schemas.provenance import Provenance


class Flag(str, Enum):
    """Where a value sits relative to its reference range.

    UNKNOWN is distinct from NORMAL. A value with no reference range has not
    been assessed, and reporting it as normal would be a claim nobody made.
    """

    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    CRITICAL_LOW = "critical_low"
    CRITICAL_HIGH = "critical_high"
    UNKNOWN = "unknown"


class ReferenceRange(BaseModel):
    """The range a result is judged against.

    `printed_on_report` records whether this came from the report itself. The
    report's own range is authoritative because it reflects the assay the lab
    actually ran; an internal table is a fallback and is flagged as one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    low: float | None = None
    high: float | None = None
    unit: str = Field(min_length=1)
    printed_on_report: bool = True
    qualifier: str | None = Field(
        default=None, description="Age, sex, or method the range applies to"
    )

    @model_validator(mode="after")
    def _a_range_bounds_something(self) -> ReferenceRange:
        if self.low is None and self.high is None:
            raise ValueError(
                "a reference range must carry a low bound, a high bound, or both; one "
                "bounding nothing cannot judge a value"
            )
        if self.low is not None and self.high is not None and self.low >= self.high:
            raise ValueError(
                f"reference range low ({self.low}) is not below high ({self.high})"
            )
        return self

    def classify(self, value: float) -> Flag:
        """Where `value` sits. Bounds are inclusive: a value at the limit is normal."""
        if self.low is not None and value < self.low:
            return Flag.LOW
        if self.high is not None and value > self.high:
            return Flag.HIGH
        return Flag.NORMAL


class LabResult(BaseModel):
    """One analyte from one report.

    `analyte` is the name as the report gave it. Normalising it to a standard
    vocabulary is the terminology layer's job, and keeping the original is what
    lets a patient match the line to their own paper.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analyte: str = Field(min_length=1)
    value: float
    unit: str = Field(min_length=1)
    reference_range: ReferenceRange | None = None
    provenance: Provenance
    collected_on: date | None = None
    codings: tuple[Coding, ...] = ()
    critical_flag: Flag | None = Field(
        default=None,
        description="Set by the critical value check, which overrides range classification",
    )

    @model_validator(mode="after")
    def _units_agree_with_the_range(self) -> LabResult:
        if self.reference_range and self.reference_range.unit != self.unit:
            raise ValueError(
                f"{self.analyte} is reported in {self.unit} but its reference range is in "
                f"{self.reference_range.unit}; comparing them would misjudge the result"
            )
        return self

    @property
    def flag(self) -> Flag:
        """How this result reads.

        A critical flag overrides range classification, because a value can sit
        inside a printed range and still be critical — the ranges answer
        different questions.
        """
        if self.critical_flag is not None:
            return self.critical_flag
        if self.reference_range is None:
            return Flag.UNKNOWN
        return self.reference_range.classify(self.value)

    @property
    def is_critical(self) -> bool:
        return self.flag in {Flag.CRITICAL_LOW, Flag.CRITICAL_HIGH}

    @property
    def is_abnormal(self) -> bool:
        return self.flag not in {Flag.NORMAL, Flag.UNKNOWN}

    @property
    def has_reference_range(self) -> bool:
        return self.reference_range is not None


class LabReport(BaseModel):
    """One report, parsed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    results: tuple[LabResult, ...] = ()
    laboratory: str | None = None
    reported_on: date | None = None

    @property
    def critical(self) -> tuple[LabResult, ...]:
        return tuple(result for result in self.results if result.is_critical)

    @property
    def abnormal(self) -> tuple[LabResult, ...]:
        return tuple(result for result in self.results if result.is_abnormal)

    @property
    def unassessed(self) -> tuple[LabResult, ...]:
        """Results with no reference range.

        Reported rather than hidden. A result nobody could judge is a gap in the
        interpretation, and saying so is more useful than implying it was normal.
        """
        return tuple(result for result in self.results if not result.has_reference_range)

    def find(self, analyte: str) -> tuple[LabResult, ...]:
        wanted = analyte.strip().lower()
        return tuple(r for r in self.results if r.analyte.strip().lower() == wanted)


class TrendDirection(str, Enum):
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    INSUFFICIENT_DATA = "insufficient_data"


class Trend(BaseModel):
    """One analyte across reports.

    Direction of travel matters more than any single value, and no consumer
    product does this because none holds the history.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    analyte: str = Field(min_length=1)
    values: tuple[tuple[date, float], ...] = ()
    unit: str = Field(min_length=1)

    @model_validator(mode="after")
    def _points_run_forwards(self) -> Trend:
        dates = [when for when, _ in self.values]
        if dates != sorted(dates):
            raise ValueError(
                f"{self.analyte} trend points are not in date order; a trend read "
                f"backwards reports the opposite direction"
            )
        return self

    def direction(self, tolerance: float) -> TrendDirection:
        """Which way this is moving.

        `tolerance` is the change below which a difference is noise, and it is
        supplied by the caller rather than assumed: what counts as a meaningful
        change differs by analyte and is a clinical judgement.
        """
        min_points = 2
        if len(self.values) < min_points:
            return TrendDirection.INSUFFICIENT_DATA
        change = self.values[-1][1] - self.values[0][1]
        if abs(change) <= tolerance:
            return TrendDirection.STABLE
        return TrendDirection.RISING if change > 0 else TrendDirection.FALLING


class DraftResult(BaseModel):
    """One result the extraction agent claims the report contained.

    The value is a string rather than a float because the agent transcribes
    what is printed. "<0.01" and "5.4" are both things a report prints, and
    coercing the first to a number here would invent a precision the lab did
    not state. Parsing happens in the builder, which drops what it cannot read
    rather than guessing.
    """

    model_config = ConfigDict(extra="forbid")

    analyte: str = Field(min_length=1)
    value: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    source_span: str = Field(
        min_length=1,
        description="Exact substring of the report that this result was read from",
    )
    reference_low: str | None = None
    reference_high: str | None = None
    page: int = Field(default=1, ge=1)


class ReportDraft(BaseModel):
    """What the extraction agent returns for one report."""

    model_config = ConfigDict(extra="forbid")

    results: tuple[DraftResult, ...] = ()
    laboratory: str | None = None
