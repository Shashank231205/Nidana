"""Scoring an extraction agent on whether it made things up.

Rx, Labs, Forensics and Scribe share one measurable property: every claim they
produce carries a span, and that span either occurs in the source or does not.
Nothing about that needs a clinician to judge, which makes it the one thing
about these agents that can be evaluated before the vignette sets exist.

What this measures, precisely:

- **Fabrication rate.** Claims whose span was not in the source, over all
  claims. The gates drop these, so a non-zero rate is not a safety failure —
  it is a measure of how hard the gate is working, and a rising number means
  the prompt is drifting toward invention.
- **Recall.** Of the claims a reference says the source contains, how many the
  agent found. A gate that drops everything scores a perfect fabrication rate
  and is useless, so the two are always read together.

This lives in the spine because four services need it and the alternative is
four copies that drift apart.

It does not score clinical correctness. Whether the potassium value is the
right one to worry about, or the injury the right type, needs a clinician and
a reference set that does not exist yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaseResult:
    """What one agent run produced, and how it scored.

    `expected_spans` comes from a reference; where it is empty the case scores
    fabrication but not recall, and says so rather than reporting recall as
    zero or as one.
    """

    case_id: str
    kept: int
    dropped: int
    expected_spans: tuple[str, ...] = ()
    found_spans: tuple[str, ...] = ()

    @property
    def claimed(self) -> int:
        return self.kept + self.dropped

    @property
    def fabrication_rate(self) -> float:
        """Claims the source did not support, over all claims."""
        return self.dropped / self.claimed if self.claimed else 0.0

    @property
    def is_scored_for_recall(self) -> bool:
        return bool(self.expected_spans)

    @property
    def missed_spans(self) -> tuple[str, ...]:
        """Reference spans the agent did not find."""
        found = set(self.found_spans)
        return tuple(span for span in self.expected_spans if span not in found)

    @property
    def recall(self) -> float | None:
        """Of what the reference says is there, how much was found.

        None where there is no reference, rather than 0.0. An unscored case
        reporting zero recall would drag the aggregate down and look like a
        failure.
        """
        if not self.expected_spans:
            return None
        found = len(self.expected_spans) - len(self.missed_spans)
        return found / len(self.expected_spans)


@dataclass
class Report:
    """The numbers across a case set."""

    agent: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def scored_for_recall(self) -> tuple[CaseResult, ...]:
        return tuple(case for case in self.cases if case.is_scored_for_recall)

    @property
    def unscored_count(self) -> int:
        """Cases with no reference spans.

        Reported rather than hidden. A high number means the eval is measuring
        less than it appears to.
        """
        return len(self.cases) - len(self.scored_for_recall)

    @property
    def total_claimed(self) -> int:
        return sum(case.claimed for case in self.cases)

    @property
    def total_dropped(self) -> int:
        return sum(case.dropped for case in self.cases)

    @property
    def fabrication_rate(self) -> float:
        """Over every claim in the set, not the mean of per-case rates.

        A case with one claim and a case with thirty should not weigh the same.
        """
        return self.total_dropped / self.total_claimed if self.total_claimed else 0.0

    @property
    def recall(self) -> float | None:
        """Over every reference span in the set."""
        scored = self.scored_for_recall
        if not scored:
            return None
        expected = sum(len(case.expected_spans) for case in scored)
        missed = sum(len(case.missed_spans) for case in scored)
        return (expected - missed) / expected if expected else None

    def summary(self) -> str:
        """One line per number, for the eval report and the changelog.

        No table. A changelog entry is read in a terminal and a diff.
        """
        recall = self.recall
        lines = [
            f"agent: {self.agent}",
            f"cases: {len(self.cases)}",
            f"claims: {self.total_claimed}",
            f"dropped: {self.total_dropped}",
            f"fabrication rate: {self.fabrication_rate:.3f}",
            f"recall: {recall:.3f}" if recall is not None else "recall: not scored",
            f"unscored for recall: {self.unscored_count}",
        ]
        if not self.cases:
            lines.append(
                "NOTE: no cases. Every number above is zero because nothing ran, "
                "not because the agent is perfect."
            )
        return "\n".join(lines)
