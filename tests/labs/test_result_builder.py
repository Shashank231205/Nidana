"""The Labs extraction gate.

Two failures matter more here than the general fabrication case. A misread
value is worse than a missing one, because a tenfold error reads as plausible.
And a missing unit cannot be inferred, because the same number in mmol/L and
mg/dL crosses different critical thresholds.
"""

from __future__ import annotations

from services.labs.agents.result_builder import build
from spine.schemas.lab import DraftResult, ReportDraft

REPORT = """SRL DIAGNOSTICS
COMPLETE BLOOD COUNT
Haemoglobin      9.2   g/dL    (13.0 - 17.0)
Potassium        6.8   mmol/L  (3.5 - 5.1)
Troponin I       <0.01 ng/mL
Creatinine       1.4
"""


def draft(*claims: DraftResult) -> ReportDraft:
    return ReportDraft(results=claims)


def result(
    analyte: str,
    value: str,
    unit: str,
    span: str,
    *,
    low: str | None = None,
    high: str | None = None,
) -> DraftResult:
    return DraftResult(
        analyte=analyte,
        value=value,
        unit=unit,
        source_span=span,
        reference_low=low,
        reference_high=high,
    )


class TestGroundedness:
    def test_a_supported_result_is_kept(self) -> None:
        built = build(
            draft(result("Haemoglobin", "9.2", "g/dL", "Haemoglobin      9.2   g/dL")),
            REPORT,
            "lab-1",
        )
        assert len(built.results) == 1
        assert built.fabrication_count == 0

    def test_a_result_not_in_the_report_is_dropped(self) -> None:
        built = build(
            draft(result("Sodium", "140", "mmol/L", "Sodium 140 mmol/L")),
            REPORT,
            "lab-1",
        )
        assert not built.results
        assert built.fabrication_count == 1

    def test_the_analyte_is_lowercased_for_threshold_matching(self) -> None:
        """The critical value table keys on lowercase analyte names."""
        built = build(
            draft(result("Potassium", "6.8", "mmol/L", "Potassium        6.8   mmol/L")),
            REPORT,
            "lab-1",
        )
        assert built.results[0].analyte == "potassium"

    def test_the_unit_is_carried_through_unchanged(self) -> None:
        built = build(
            draft(result("Potassium", "6.8", "mmol/L", "Potassium        6.8   mmol/L")),
            REPORT,
            "lab-1",
        )
        assert built.results[0].unit == "mmol/L"

    def test_an_empty_draft_produces_nothing(self) -> None:
        built = build(ReportDraft(), REPORT, "lab-1")
        assert built.results == ()
        assert built.fabrication_count == 0


class TestValueParsing:
    def test_a_qualified_value_is_dropped_rather_than_coerced(self) -> None:
        """'<0.01' and '0.01' are different results for troponin."""
        built = build(
            draft(result("Troponin I", "<0.01", "ng/mL", "Troponin I       <0.01 ng/mL")),
            REPORT,
            "lab-1",
        )
        assert not built.results
        assert "not a plain number" in built.dropped[0].reason

    def test_the_drop_reason_names_manual_entry(self) -> None:
        built = build(
            draft(result("Troponin I", "<0.01", "ng/mL", "Troponin I       <0.01 ng/mL")),
            REPORT,
            "lab-1",
        )
        assert "by hand" in built.dropped[0].reason

    def test_a_negative_value_parses(self) -> None:
        """Base excess is routinely negative."""
        text = "Base excess     -3.2   mmol/L"
        built = build(
            draft(result("Base excess", "-3.2", "mmol/L", "Base excess     -3.2   mmol/L")),
            text,
            "lab-2",
        )
        assert built.results[0].value == -3.2

    def test_an_implausible_value_is_kept_rather_than_corrected(self) -> None:
        """68 mmol/L is impossible, and silently making it 6.8 is worse."""
        text = "Potassium 68 mmol/L"
        built = build(
            draft(result("Potassium", "68", "mmol/L", "Potassium 68 mmol/L")), text, "lab-3"
        )
        assert built.results[0].value == 68.0


class TestReferenceRange:
    def test_a_printed_range_is_carried_through(self) -> None:
        built = build(
            draft(
                result(
                    "Haemoglobin",
                    "9.2",
                    "g/dL",
                    "Haemoglobin      9.2   g/dL",
                    low="13.0",
                    high="17.0",
                )
            ),
            REPORT,
            "lab-1",
        )
        assert built.results[0].reference_range is not None
        assert built.results[0].reference_range.low == 13.0

    def test_no_range_is_absent_rather_than_zero(self) -> None:
        built = build(
            draft(result("Creatinine", "1.4", "mg/dL", "Creatinine       1.4")),
            REPORT,
            "lab-1",
        )
        assert built.results[0].reference_range is None

    def test_a_half_parsed_range_is_dropped_entirely(self) -> None:
        """A range with one bound silently missing reports that side as normal."""
        built = build(
            draft(
                result(
                    "Haemoglobin",
                    "9.2",
                    "g/dL",
                    "Haemoglobin      9.2   g/dL",
                    low="thirteen",
                    high="17.0",
                )
            ),
            REPORT,
            "lab-1",
        )
        assert built.results[0].reference_range is None

    def test_a_one_sided_range_is_kept(self) -> None:
        """'< 200' is a real reference range with only an upper bound."""
        text = "Cholesterol 210 mg/dL"
        built = build(
            draft(result("Cholesterol", "210", "mg/dL", "Cholesterol 210 mg/dL", high="200")),
            text,
            "lab-4",
        )
        assert built.results[0].reference_range is not None
        assert built.results[0].reference_range.low is None
        assert built.results[0].reference_range.high == 200.0
