"""The groundedness eval.

The number this exists to prevent: an empty case set reporting a perfect
fabrication rate. Zero over zero is zero, which reads as flawless and means
nothing ran.

Fabrication rate and recall are always read together. A gate that drops
everything scores perfectly on the first and uselessly on the second.
"""

from __future__ import annotations

from spine.eval.groundedness import CaseResult, Report


class TestCaseResult:
    def test_a_clean_case_fabricates_nothing(self) -> None:
        case = CaseResult(case_id="C1", kept=3, dropped=0)
        assert case.fabrication_rate == 0.0
        assert case.claimed == 3

    def test_the_rate_is_dropped_over_claimed(self) -> None:
        case = CaseResult(case_id="C1", kept=3, dropped=1)
        assert case.fabrication_rate == 0.25

    def test_a_case_that_claimed_nothing_is_not_a_failure(self) -> None:
        """Nothing claimed is nothing fabricated, not a division by zero."""
        case = CaseResult(case_id="C1", kept=0, dropped=0)
        assert case.fabrication_rate == 0.0

    def test_recall_is_none_without_a_reference(self) -> None:
        """None, not zero: an unscored case must not read as a failure."""
        case = CaseResult(case_id="C1", kept=3, dropped=0)
        assert case.recall is None
        assert not case.is_scored_for_recall

    def test_recall_counts_reference_spans_that_were_found(self) -> None:
        case = CaseResult(
            case_id="C1",
            kept=1,
            dropped=0,
            expected_spans=("potassium 6.8", "haemoglobin 9.2"),
            found_spans=("potassium 6.8",),
        )
        assert case.recall == 0.5
        assert case.missed_spans == ("haemoglobin 9.2",)

    def test_full_recall_misses_nothing(self) -> None:
        case = CaseResult(
            case_id="C1",
            kept=2,
            dropped=0,
            expected_spans=("a", "b"),
            found_spans=("a", "b"),
        )
        assert case.recall == 1.0
        assert case.missed_spans == ()


class TestReport:
    def test_an_empty_report_says_nothing_ran(self) -> None:
        """The number this whole module exists to prevent being misread."""
        report = Report(agent="extraction_agent")
        assert report.fabrication_rate == 0.0
        assert "nothing ran" in report.summary()

    def test_a_populated_report_does_not_carry_the_note(self) -> None:
        report = Report(
            agent="extraction_agent", cases=[CaseResult(case_id="C1", kept=1, dropped=0)]
        )
        assert "nothing ran" not in report.summary()

    def test_the_rate_weights_by_claim_not_by_case(self) -> None:
        """A case with one claim should not weigh the same as one with thirty."""
        report = Report(
            agent="a",
            cases=[
                CaseResult(case_id="C1", kept=0, dropped=1),
                CaseResult(case_id="C2", kept=29, dropped=1),
            ],
        )
        # Per-case mean would be 0.517; per-claim is 2/31.
        assert abs(report.fabrication_rate - 2 / 31) < 1e-9

    def test_recall_is_none_when_no_case_carries_a_reference(self) -> None:
        report = Report(
            agent="a", cases=[CaseResult(case_id="C1", kept=2, dropped=0)]
        )
        assert report.recall is None
        assert "not scored" in report.summary()

    def test_unscored_cases_are_counted(self) -> None:
        report = Report(
            agent="a",
            cases=[
                CaseResult(case_id="C1", kept=1, dropped=0),
                CaseResult(
                    case_id="C2", kept=1, dropped=0, expected_spans=("a",), found_spans=("a",)
                ),
            ],
        )
        assert report.unscored_count == 1
        assert report.recall == 1.0

    def test_the_summary_has_no_table(self) -> None:
        """A changelog entry is read in a terminal and a diff."""
        report = Report(
            agent="a", cases=[CaseResult(case_id="C1", kept=1, dropped=0)]
        )
        assert "|" not in report.summary()

    def test_the_summary_names_the_agent(self) -> None:
        report = Report(agent="reading_agent")
        assert "reading_agent" in report.summary()
