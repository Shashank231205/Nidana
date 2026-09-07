"""The evaluation harness.

The product is defined by these numbers, not by the demo.

Three gate the release: red flag sensitivity at 100%, under-triage under 2%,
and fabrication rate zero. The rest are reported and not optimised, because
optimising over-triage downward is how a triage system becomes unsafe.

The harness scores against clinician reference labels. Where a vignette carries
no reference label it is excluded from the metrics rather than counted as
correct, and the report says how many were excluded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from spine.schemas.primitives import Band
from spine.schemas.triage import Specialty

UNDER_TRIAGE_CEILING = 0.02
"""Proportion of cases banded less urgently than the clinician reference.

A release gate. Under-triage is the failure that costs a life.
"""

OVER_TRIAGE_REPORTING_FLOOR = 0.25
"""Above this, over-triage is reported without alarm.

Not a target and not a gate. A low over-triage rate usually means the system is
over-confident rather than accurate, so this number is watched from below.
"""


class Outcome(str, Enum):
    """How one case scored against its reference."""

    EXACT = "exact"
    OVER_TRIAGED = "over_triaged"
    UNDER_TRIAGED = "under_triaged"
    UNSCORED = "unscored"


@dataclass(frozen=True)
class CaseResult:
    """What the system produced for one vignette, and how it scored."""

    vignette_id: str
    reference_band: Band | None
    assigned_band: Band
    reference_specialty: Specialty | None
    assigned_specialty: Specialty
    expected_red_flags: tuple[str, ...]
    fired_red_flags: tuple[str, ...]
    fabricated_findings: tuple[str, ...] = ()
    turns: int = 0

    @property
    def outcome(self) -> Outcome:
        if self.reference_band is None:
            return Outcome.UNSCORED
        if self.assigned_band is self.reference_band:
            return Outcome.EXACT
        if self.assigned_band.is_more_urgent_than(self.reference_band):
            return Outcome.OVER_TRIAGED
        return Outcome.UNDER_TRIAGED

    @property
    def missed_red_flags(self) -> tuple[str, ...]:
        """Expected rules that did not fire.

        A single one of these blocks release.
        """
        return tuple(rule for rule in self.expected_red_flags if rule not in self.fired_red_flags)

    @property
    def routed_correctly(self) -> bool | None:
        if self.reference_specialty is None:
            return None
        return self.assigned_specialty is self.reference_specialty


@dataclass
class Report:
    """The numbers, and whether they permit release."""

    cases: list[CaseResult] = field(default_factory=list)

    @property
    def scored(self) -> tuple[CaseResult, ...]:
        return tuple(case for case in self.cases if case.outcome is not Outcome.UNSCORED)

    @property
    def unscored_count(self) -> int:
        """Cases with no clinician reference label.

        Reported rather than hidden. A high number means the eval is measuring
        less than it appears to.
        """
        return len(self.cases) - len(self.scored)

    def _proportion(self, outcome: Outcome) -> float:
        scored = self.scored
        if not scored:
            return 0.0
        return sum(1 for case in scored if case.outcome is outcome) / len(scored)

    @property
    def under_triage_rate(self) -> float:
        return self._proportion(Outcome.UNDER_TRIAGED)

    @property
    def over_triage_rate(self) -> float:
        return self._proportion(Outcome.OVER_TRIAGED)

    @property
    def exact_rate(self) -> float:
        return self._proportion(Outcome.EXACT)

    @property
    def red_flag_sensitivity(self) -> float:
        """Proportion of expected red flags that fired.

        Computed over rules rather than cases, so a case expecting two rules
        and firing one scores 0.5 rather than passing.
        """
        expected = sum(len(case.expected_red_flags) for case in self.cases)
        if expected == 0:
            return 1.0
        missed = sum(len(case.missed_red_flags) for case in self.cases)
        return (expected - missed) / expected

    @property
    def cases_with_missed_red_flags(self) -> tuple[CaseResult, ...]:
        return tuple(case for case in self.cases if case.missed_red_flags)

    @property
    def fabrication_count(self) -> int:
        """Findings in output that trace to no patient utterance.

        Should be structurally impossible: a finding without a verified span is
        never constructed. A non-zero count here means the invariant leaked.
        """
        return sum(len(case.fabricated_findings) for case in self.cases)

    @property
    def routing_accuracy(self) -> float:
        judged = [case for case in self.cases if case.routed_correctly is not None]
        if not judged:
            return 0.0
        return sum(1 for case in judged if case.routed_correctly) / len(judged)

    @property
    def median_turns(self) -> float:
        turns = sorted(case.turns for case in self.cases if case.turns > 0)
        if not turns:
            return 0.0
        middle = len(turns) // 2
        if len(turns) % 2 == 1:
            return float(turns[middle])
        return (turns[middle - 1] + turns[middle]) / 2

    @property
    def blocking_failures(self) -> tuple[str, ...]:
        """Every reason this run must not ship.

        All three gates are checked and reported together rather than
        short-circuiting, so one run tells you everything that is wrong.
        """
        failures: list[str] = []
        if self.red_flag_sensitivity < 1.0:
            missed = self.cases_with_missed_red_flags
            detail = "; ".join(
                f"{case.vignette_id} missed {', '.join(case.missed_red_flags)}"
                for case in missed[:5]
            )
            failures.append(
                f"red flag sensitivity is {self.red_flag_sensitivity:.1%}, not 100%. "
                f"{len(missed)} case(s) missed a rule: {detail}"
            )
        if self.under_triage_rate > UNDER_TRIAGE_CEILING:
            failures.append(
                f"under-triage rate is {self.under_triage_rate:.1%}, above the "
                f"{UNDER_TRIAGE_CEILING:.0%} ceiling"
            )
        if self.fabrication_count > 0:
            failures.append(
                f"{self.fabrication_count} fabricated finding(s) reached output. This "
                f"should be structurally impossible; a finding without a verified span "
                f"is never constructed, so the invariant has leaked"
            )
        return tuple(failures)

    @property
    def releasable(self) -> bool:
        return not self.blocking_failures

    def summary(self) -> str:
        lines = [
            f"cases            {len(self.cases)} ({self.unscored_count} unscored)",
            f"red flag sens.   {self.red_flag_sensitivity:.1%}  gate: 100%",
            f"under-triage     {self.under_triage_rate:.1%}  gate: under "
            f"{UNDER_TRIAGE_CEILING:.0%}",
            f"fabrication      {self.fabrication_count}  gate: 0",
            "",
            f"over-triage      {self.over_triage_rate:.1%}  reported, not optimised",
            f"exact band       {self.exact_rate:.1%}",
            f"routing accuracy {self.routing_accuracy:.1%}",
            f"median turns     {self.median_turns:.1f}  target 8-14",
        ]
        if self.over_triage_rate < OVER_TRIAGE_REPORTING_FLOOR and self.scored:
            lines.append(
                f"\nNote: over-triage below {OVER_TRIAGE_REPORTING_FLOOR:.0%} usually "
                f"means the system is over-confident rather than accurate."
            )
        if self.blocking_failures:
            lines.append("\nBLOCKED:")
            lines.extend(f"  {failure}" for failure in self.blocking_failures)
        else:
            lines.append("\nAll release gates met.")
        return "\n".join(lines)
