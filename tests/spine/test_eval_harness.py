"""Driving the groundedness scorer over a case set.

The scorer has existed since it was written and nothing ran it. What is tested
here is the harness that does, and specifically the places where it could
report a number that is not true:

An empty case set must fail rather than score perfectly, because a perfect
score over nothing looks like evidence.

A span the agent kept but that is not in the source counts as a fabrication,
even though the agent's own gate passed it. Trusting the agent's arithmetic
would let a broken gate score perfectly against itself.

A case with no reference spans reports recall as None, not zero. An unscored
case reporting zero would drag the aggregate down and read as failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spine.eval.harness import (
    AgentOutcome,
    Case,
    EvalCaseError,
    as_json,
    load_cases,
    run,
    verify_spans,
)

SOURCE = "Tab Crocin 500mg BD for five days. Tab Pan 40 OD."


def case(case_id: str = "c1", *, expected: tuple[str, ...] = ()) -> Case:
    return Case(case_id=case_id, source=SOURCE, expected_spans=expected)


def written(tmp_path: Path, *entries: dict[str, object]) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(list(entries)), encoding="utf-8")
    return path


class TestLoading:
    def test_a_case_set_loads(self, tmp_path: Path) -> None:
        path = written(tmp_path, {"case_id": "c1", "source": SOURCE})
        assert len(load_cases(path)) == 1

    def test_expected_spans_are_optional(self, tmp_path: Path) -> None:
        """Nobody has written reference labels yet, and that is honest."""
        path = written(tmp_path, {"case_id": "c1", "source": SOURCE})
        assert load_cases(path)[0].expected_spans == ()

    def test_expected_spans_are_read_when_present(self, tmp_path: Path) -> None:
        path = written(
            tmp_path,
            {"case_id": "c1", "source": SOURCE, "expected_spans": ["Tab Crocin 500mg BD"]},
        )
        assert load_cases(path)[0].expected_spans == ("Tab Crocin 500mg BD",)

    def test_an_empty_set_is_refused(self, tmp_path: Path) -> None:
        """A perfect score over zero cases looks like evidence."""
        path = written(tmp_path)
        with pytest.raises(EvalCaseError, match="looks like"):
            load_cases(path)

    def test_a_missing_file_explains_the_format(self, tmp_path: Path) -> None:
        with pytest.raises(EvalCaseError, match="case_id and source"):
            load_cases(tmp_path / "absent.json")

    def test_malformed_json_is_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("[{", encoding="utf-8")
        with pytest.raises(EvalCaseError, match="not valid JSON"):
            load_cases(path)

    def test_a_case_missing_its_source_is_named(self, tmp_path: Path) -> None:
        path = written(tmp_path, {"case_id": "c1"})
        with pytest.raises(EvalCaseError, match="case 1 is missing: source"):
            load_cases(path)

    def test_a_non_list_document_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text('{"case_id": "c1"}', encoding="utf-8")
        with pytest.raises(EvalCaseError, match="list of cases"):
            load_cases(path)


class TestSpanVerification:
    def test_a_span_in_the_source_is_kept(self) -> None:
        assert verify_spans(SOURCE, ("Tab Crocin 500mg BD",)) == ("Tab Crocin 500mg BD",)

    def test_a_span_not_in_the_source_is_dropped(self) -> None:
        assert verify_spans(SOURCE, ("Tab Metformin 500mg",)) == ()

    def test_an_empty_span_is_dropped(self) -> None:
        assert verify_spans(SOURCE, ("",)) == ()


class TestScoring:
    def test_a_clean_run_fabricates_nothing(self) -> None:
        report = run(
            "reading_agent",
            (case(),),
            lambda _case: AgentOutcome(kept_spans=("Tab Crocin 500mg BD",), dropped=0),
        )
        assert report.fabrication_rate == 0.0

    def test_the_agents_own_drops_are_counted(self) -> None:
        report = run(
            "reading_agent",
            (case(),),
            lambda _case: AgentOutcome(kept_spans=("Tab Pan 40 OD",), dropped=1),
        )
        assert report.total_dropped == 1
        assert report.fabrication_rate == pytest.approx(0.5)

    def test_a_kept_span_that_is_not_in_the_source_counts_as_fabrication(self) -> None:
        """The agent's own gate passed it, and the gate was wrong.

        Trusting the agent's arithmetic would let a broken span verifier score
        perfectly against itself, which is the one thing this eval exists to
        catch.
        """
        report = run(
            "reading_agent",
            (case(),),
            lambda _case: AgentOutcome(kept_spans=("Tab Metformin 500mg",), dropped=0),
        )
        assert report.total_dropped == 1
        assert report.fabrication_rate == 1.0

    def test_recall_is_measured_against_the_reference(self) -> None:
        report = run(
            "reading_agent",
            (case(expected=("Tab Crocin 500mg BD", "Tab Pan 40 OD")),),
            lambda _case: AgentOutcome(kept_spans=("Tab Crocin 500mg BD",), dropped=0),
        )
        assert report.recall == pytest.approx(0.5)

    def test_a_case_with_no_reference_is_unscored_for_recall(self) -> None:
        """Not zero. Zero would read as a failure to find anything."""
        report = run(
            "reading_agent",
            (case(),),
            lambda _case: AgentOutcome(kept_spans=("Tab Pan 40 OD",), dropped=0),
        )
        assert report.cases[0].recall is None
        assert report.unscored_count == 1

    def test_a_missed_reference_span_is_named(self) -> None:
        report = run(
            "reading_agent",
            (case(expected=("Tab Pan 40 OD",)),),
            lambda _case: AgentOutcome(kept_spans=("Tab Crocin 500mg BD",), dropped=0),
        )
        assert report.cases[0].missed_spans == ("Tab Pan 40 OD",)

    def test_a_failing_case_does_not_abort_the_run(self) -> None:
        """One broken case in thirty should not cost the other twenty-nine."""

        def runner(c: Case) -> AgentOutcome:
            if c.case_id == "bad":
                raise RuntimeError("the model refused")
            return AgentOutcome(kept_spans=("Tab Pan 40 OD",), dropped=0)

        report = run("reading_agent", (case("bad"), case("good")), runner)
        assert len(report.cases) == 2
        assert report.cases[0].claimed == 0

    def test_an_empty_run_reports_zero_not_a_division_error(self) -> None:
        report = run(
            "reading_agent", (case(),), lambda _case: AgentOutcome(kept_spans=(), dropped=0)
        )
        assert report.fabrication_rate == 0.0


class TestReportJson:
    def test_the_numbers_survive(self) -> None:
        report = run(
            "reading_agent",
            (case(expected=("Tab Pan 40 OD",)),),
            lambda _case: AgentOutcome(kept_spans=("Tab Pan 40 OD",), dropped=1),
        )
        doc = as_json(report)
        assert doc["agent"] == "reading_agent"
        assert doc["total_dropped"] == 1
        assert doc["recall"] == 1.0

    def test_unscored_recall_stays_null(self) -> None:
        report = run(
            "reading_agent", (case(),), lambda _case: AgentOutcome(kept_spans=(), dropped=0)
        )
        assert as_json(report)["recall"] is None

    def test_the_report_says_what_it_does_not_measure(self) -> None:
        """A perfect score here is not a clinical claim, and must not read as one."""
        report = run(
            "reading_agent", (case(),), lambda _case: AgentOutcome(kept_spans=(), dropped=0)
        )
        assert "not that what it found was the right thing" in str(as_json(report)["measures"])
