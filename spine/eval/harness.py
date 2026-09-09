"""Running the extraction agents against the groundedness scorer.

`spine/eval/groundedness.py` has scored fabrication and recall since it was
written and nothing has ever driven it. This is the missing half: it takes a
case set, runs an agent over each case, and produces the report.

Four services share this because they share the property being measured. Rx
reads a prescription, Labs reads a report, Forensics structures a dictation and
Scribe drafts a note; each proposes claims, each verifies every span against
its source, and each drops what it cannot support. Whether a dropped claim
should have been dropped is a question about the source text, not about
medicine, which is why this can run before any clinician has looked at
anything.

**What it does not measure.** Whether the potassium value is the one to worry
about, whether the injury is the right type, whether the note said the
important thing. All of that needs a clinician and a reference set that does
not exist. A service scoring perfectly here has been shown to invent nothing;
it has not been shown to be useful.

Cases are JSON, one file per service, holding a source text and optionally the
spans a reference says are in it. A case with no reference spans still scores
fabrication — which is the number that matters most for a gate — and is counted
separately so a reader can see how much of the set is unscored for recall.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from spine.eval.groundedness import CaseResult, Report


class EvalCaseError(RuntimeError):
    """Raised when a case set is missing or malformed."""


@dataclass(frozen=True)
class Case:
    """One source document, and what a reference says is in it.

    `expected_spans` is optional and its absence is honest rather than
    convenient: nobody has written reference labels for these yet, and a case
    that scores only fabrication says so instead of claiming a recall number it
    cannot support.
    """

    case_id: str
    source: str
    expected_spans: tuple[str, ...] = ()
    note: str | None = None


@dataclass(frozen=True)
class AgentOutcome:
    """What an agent produced for one case.

    Every agent in this repository already returns this shape in its own
    vocabulary — kept claims with verified spans, and dropped claims counted
    rather than hidden. The adapter for each service translates into this.
    """

    kept_spans: tuple[str, ...]
    dropped: int


AgentRunner = Callable[[Case], AgentOutcome]


def load_cases(path: Path) -> tuple[Case, ...]:
    """Read a case set from JSON.

    Raises on an empty set rather than returning one. A harness that reports
    perfect scores over zero cases is worse than one that fails, because the
    number looks like evidence.
    """
    if not path.is_file():
        raise EvalCaseError(
            f"no case set at {path}. A case set is JSON: a list of objects with "
            f"case_id and source, and optionally expected_spans naming what a "
            f"reference says the source contains"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise EvalCaseError(f"{path} is not valid JSON: {error}") from error

    if not isinstance(raw, list):
        raise EvalCaseError(f"{path} must hold a list of cases")

    cases: list[Case] = []
    for index, entry in enumerate(raw, start=1):
        if not isinstance(entry, dict):
            raise EvalCaseError(f"{path} case {index} is not an object")
        missing = {"case_id", "source"} - set(entry)
        if missing:
            raise EvalCaseError(
                f"{path} case {index} is missing: {', '.join(sorted(missing))}"
            )
        cases.append(
            Case(
                case_id=str(entry["case_id"]),
                source=str(entry["source"]),
                expected_spans=tuple(str(s) for s in entry.get("expected_spans", ())),
                note=entry.get("note"),
            )
        )
    if not cases:
        raise EvalCaseError(
            f"{path} holds no cases. An eval reporting perfect scores over zero "
            f"cases is worse than one that fails, because the number looks like "
            f"evidence"
        )
    return tuple(cases)


def verify_spans(source: str, spans: tuple[str, ...]) -> tuple[str, ...]:
    """The spans that actually occur in the source.

    The same check the builders make, repeated here rather than trusted. An
    agent whose own span verification had a bug would otherwise score
    perfectly against itself.
    """
    return tuple(span for span in spans if span and span in source)


def run(agent: str, cases: tuple[Case, ...], runner: AgentRunner) -> Report:
    """Run one agent over a case set and score it.

    A case that raises is recorded as having claimed nothing rather than
    aborting the run: one broken case in thirty should not cost the other
    twenty-nine, and a case that produced nothing is visible in the totals.
    """
    report = Report(agent=agent)
    for case in cases:
        try:
            outcome = runner(case)
        except (RuntimeError, ValueError, OSError):
            # A case the agent could not process at all: a malformed source, a
            # model that refused, a transport failure. Recorded as claiming
            # nothing rather than aborting the run, and visible in the totals.
            report.cases.append(
                CaseResult(
                    case_id=case.case_id,
                    kept=0,
                    dropped=0,
                    expected_spans=case.expected_spans,
                )
            )
            continue

        found = verify_spans(case.source, outcome.kept_spans)
        report.cases.append(
            CaseResult(
                case_id=case.case_id,
                kept=len(found),
                # A span the agent kept but that is not in the source is a
                # fabrication its own gate failed to catch, and counts as one.
                dropped=outcome.dropped + (len(outcome.kept_spans) - len(found)),
                expected_spans=case.expected_spans,
                found_spans=found,
            )
        )
    return report


def as_json(report: Report) -> dict[str, object]:
    """The report as a dict, for writing beside the others in eval/reports."""
    return {
        "agent": report.agent,
        "cases": len(report.cases),
        "unscored_for_recall": report.unscored_count,
        "total_claimed": report.total_claimed,
        "total_dropped": report.total_dropped,
        "fabrication_rate": round(report.fabrication_rate, 4),
        "recall": None if report.recall is None else round(report.recall, 4),
        "per_case": [
            {
                "case_id": case.case_id,
                "kept": case.kept,
                "dropped": case.dropped,
                "fabrication_rate": round(case.fabrication_rate, 4),
                "recall": None if case.recall is None else round(case.recall, 4),
                "missed_spans": list(case.missed_spans),
            }
            for case in report.cases
        ],
        "measures": (
            "Fabrication and recall of source spans only. Not clinical "
            "correctness: a perfect score shows the agent invented nothing, "
            "not that what it found was the right thing to find."
        ),
    }
