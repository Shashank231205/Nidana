"""Lab results, reference ranges, and critical value detection.

Critical value detection has the same release gate as Consult's red flags:
100% sensitivity. That makes a wrong threshold more dangerous than a missing
one, because a threshold set too wide reports full sensitivity against a
vignette set that never tests the gap.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from services.labs.clinical.critical_values import (
    CriticalThreshold,
    CriticalValueLoadError,
    UnverifiedThresholdsError,
    check,
    load_thresholds,
    require_verified,
    thresholds_dir,
    unit_mismatches,
)
from spine.schemas.lab import Flag, LabReport, LabResult, ReferenceRange, Trend, TrendDirection
from spine.schemas.provenance import locate_document

SOURCE = "Haemoglobin 7.2 g/dL Potassium 6.9 mmol/L Sodium 139 mmol/L Ferritin 12 ng/mL"

VALID_THRESHOLDS = """
thresholds:
  - analyte: potassium
    unit: mmol/L
    critical_low: 2.5
    critical_high: 6.5
    source: "PLACEHOLDER pending clinician review"
    verify_before_ship: true
  - analyte: haemoglobin
    unit: g/dL
    critical_low: 7.0
    source: "PLACEHOLDER pending clinician review"
    verify_before_ship: true
"""


def result(
    analyte: str,
    value: float,
    unit: str,
    quote: str,
    *,
    low: float | None = None,
    high: float | None = None,
) -> LabResult:
    reference = (
        ReferenceRange(low=low, high=high, unit=unit)
        if low is not None or high is not None
        else None
    )
    return LabResult(
        analyte=analyte,
        value=value,
        unit=unit,
        reference_range=reference,
        provenance=locate_document(
            source_id="lab.pdf", source_text=SOURCE, quote=quote, page=1
        ),
    )


@pytest.fixture
def thresholds(tmp_path: Path) -> dict[str, CriticalThreshold]:
    (tmp_path / "core.yaml").write_text(VALID_THRESHOLDS, encoding="utf-8")
    return load_thresholds(tmp_path)


class TestReferenceRanges:
    def test_a_value_inside_the_range_is_normal(self) -> None:
        assert result("Sodium", 139, "mmol/L", "139", low=135, high=145).flag is Flag.NORMAL

    def test_a_value_below_the_range_is_low(self) -> None:
        assert result("Haemoglobin", 7.2, "g/dL", "7.2", low=12, high=16).flag is Flag.LOW

    def test_a_value_above_the_range_is_high(self) -> None:
        assert result("Potassium", 6.9, "mmol/L", "6.9", low=3.5, high=5.1).flag is Flag.HIGH

    def test_the_bounds_are_inclusive(self) -> None:
        """A value at the limit is normal, not abnormal."""
        assert result("Sodium", 135, "mmol/L", "139", low=135, high=145).flag is Flag.NORMAL
        assert result("Sodium", 145, "mmol/L", "139", low=135, high=145).flag is Flag.NORMAL

    def test_a_result_without_a_range_is_unknown_not_normal(self) -> None:
        """A result nobody could judge was not assessed as normal."""
        assert result("Ferritin", 12, "ng/mL", "12").flag is Flag.UNKNOWN

    def test_an_unknown_result_is_not_reported_as_abnormal(self) -> None:
        assert not result("Ferritin", 12, "ng/mL", "12").is_abnormal

    def test_a_range_bounding_nothing_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot judge a value"):
            ReferenceRange(unit="mmol/L")

    def test_an_inverted_range_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not below high"):
            ReferenceRange(low=10, high=5, unit="mmol/L")

    def test_a_one_sided_range_is_valid(self) -> None:
        """Some analytes are only ever judged in one direction."""
        assert ReferenceRange(low=7.0, unit="g/dL").classify(6.0) is Flag.LOW

    def test_a_unit_mismatch_between_value_and_range_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="would misjudge the result"):
            LabResult(
                analyte="Potassium",
                value=5.0,
                unit="mmol/L",
                reference_range=ReferenceRange(low=3.5, high=5.1, unit="mEq/L"),
                provenance=locate_document(
                    source_id="lab.pdf", source_text=SOURCE, quote="6.9", page=1
                ),
            )

    def test_the_printed_range_is_marked_as_such(self) -> None:
        """The report's own range is authoritative; a table is a fallback."""
        assert ReferenceRange(low=1, high=2, unit="x").printed_on_report
        table = ReferenceRange(low=1, high=2, unit="x", printed_on_report=False)
        assert not table.printed_on_report


class TestCriticalDetection:
    def test_a_value_below_the_critical_low_fires(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Haemoglobin", 6.0, "g/dL", "7.2"),))
        found = check(report, thresholds)
        assert found[0].flag is Flag.CRITICAL_LOW

    def test_a_value_above_the_critical_high_fires(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Potassium", 7.5, "mmol/L", "6.9"),))
        assert check(report, thresholds)[0].flag is Flag.CRITICAL_HIGH

    def test_the_critical_boundary_is_inclusive(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        """At the threshold is critical. Erring inward costs a contact."""
        report = LabReport(results=(result("Potassium", 6.5, "mmol/L", "6.9"),))
        assert check(report, thresholds)

    def test_a_value_inside_the_critical_bounds_does_not_fire(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Potassium", 5.5, "mmol/L", "6.9"),))
        assert check(report, thresholds) == ()

    def test_an_analyte_with_no_threshold_does_not_fire(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Ferritin", 12, "ng/mL", "12"),))
        assert check(report, thresholds) == ()

    def test_matching_is_case_insensitive(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("POTASSIUM", 7.5, "mmol/L", "6.9"),))
        assert check(report, thresholds)

    def test_a_critical_value_can_sit_inside_its_reference_range(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        """The two ranges answer different questions."""
        report = LabReport(
            results=(result("Haemoglobin", 6.5, "g/dL", "7.2", low=6.0, high=16.0),)
        )
        assert report.results[0].flag is Flag.NORMAL
        assert check(report, thresholds)

    def test_the_finding_names_the_threshold_it_crossed(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Potassium", 7.5, "mmol/L", "6.9"),))
        message = check(report, thresholds)[0].message
        assert "7.5" in message
        assert "6.5" in message

    def test_an_unverified_threshold_is_marked_on_the_finding(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Potassium", 7.5, "mmol/L", "6.9"),))
        assert check(report, thresholds)[0].unverified

    def test_several_criticals_are_all_reported(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(
            results=(
                result("Potassium", 7.5, "mmol/L", "6.9"),
                result("Haemoglobin", 5.0, "g/dL", "7.2"),
            )
        )
        assert len(check(report, thresholds)) == 2


class TestUnitSafety:
    def test_a_unit_mismatch_does_not_fire_the_threshold(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        """Comparing mg/dL against mmol/L would produce a nonsense verdict."""
        report = LabReport(results=(result("Potassium", 7.5, "mEq/L", "6.9"),))
        assert check(report, thresholds) == ()

    def test_a_unit_mismatch_is_reported_loudly(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        """A silent skip here is a missed critical value."""
        report = LabReport(results=(result("Potassium", 7.5, "mEq/L", "6.9"),))
        mismatched = unit_mismatches(report, thresholds)
        assert len(mismatched) == 1
        assert "mEq/L" in mismatched[0]

    def test_matching_units_report_no_mismatch(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        report = LabReport(results=(result("Potassium", 5.0, "mmol/L", "6.9"),))
        assert unit_mismatches(report, thresholds) == ()


class TestThresholdShape:
    def test_a_threshold_bounding_nothing_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="can never fire"):
            CriticalThreshold(analyte="x", unit="u", source="s")

    def test_an_inverted_threshold_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not below its critical high"):
            CriticalThreshold(
                analyte="x", unit="u", critical_low=10, critical_high=5, source="s"
            )

    def test_a_one_sided_threshold_is_valid(self) -> None:
        threshold = CriticalThreshold(
            analyte="haemoglobin", unit="g/dL", critical_low=7, source="s"
        )
        assert threshold.classify(6.0) is Flag.CRITICAL_LOW
        assert threshold.classify(20.0) is None

    def test_a_verified_threshold_must_name_its_date(self) -> None:
        with pytest.raises(ValueError, match="verified_on date"):
            CriticalThreshold(
                analyte="x", unit="u", critical_low=1, source="s", verify_before_ship=False
            )


class TestLoading:
    def test_valid_thresholds_load(self, thresholds: dict[str, CriticalThreshold]) -> None:
        assert set(thresholds) == {"potassium", "haemoglobin"}

    def test_a_duplicate_analyte_across_files_is_rejected(self, tmp_path: Path) -> None:
        """One would be silently ignored, and which depends on file ordering."""
        (tmp_path / "a.yaml").write_text(VALID_THRESHOLDS, encoding="utf-8")
        (tmp_path / "b.yaml").write_text(VALID_THRESHOLDS, encoding="utf-8")
        with pytest.raises(CriticalValueLoadError, match="silently ignored"):
            load_thresholds(tmp_path)

    def test_a_missing_directory_names_itself(self, tmp_path: Path) -> None:
        with pytest.raises(CriticalValueLoadError, match="does not exist"):
            load_thresholds(tmp_path / "absent")

    def test_an_empty_directory_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(CriticalValueLoadError, match="no threshold files"):
            load_thresholds(tmp_path)

    def test_malformed_yaml_names_the_file(self, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text("thresholds: [unclosed", encoding="utf-8")
        with pytest.raises(CriticalValueLoadError, match="not valid YAML"):
            load_thresholds(tmp_path)


class TestReleaseGate:
    def test_development_proceeds_with_unverified_thresholds(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        require_verified(thresholds, allow_unverified=True)

    def test_release_refuses_unverified_thresholds(
        self, thresholds: dict[str, CriticalThreshold]
    ) -> None:
        with pytest.raises(UnverifiedThresholdsError, match="cannot ship"):
            require_verified(thresholds, allow_unverified=False)

    def test_the_shipped_thresholds_are_all_unverified(self) -> None:
        """Every number in the shipped file is a structural placeholder."""
        shipped = load_thresholds()
        assert all(threshold.verify_before_ship for threshold in shipped.values())

    def test_the_shipped_thresholds_cannot_ship(self) -> None:
        with pytest.raises(UnverifiedThresholdsError):
            require_verified(load_thresholds(), allow_unverified=False)

    def test_thresholds_dir_points_into_the_named_service(self) -> None:
        assert thresholds_dir().parts[-3:] == ("labs", "rules", "critical_values")


class TestTrends:
    def test_a_rising_trend_is_detected(self) -> None:
        trend = Trend(
            analyte="Creatinine",
            unit="mg/dL",
            values=((date(2026, 1, 1), 1.1), (date(2026, 6, 1), 1.9)),
        )
        assert trend.direction(tolerance=0.2) is TrendDirection.RISING

    def test_a_falling_trend_is_detected(self) -> None:
        trend = Trend(
            analyte="Haemoglobin",
            unit="g/dL",
            values=((date(2026, 1, 1), 12.0), (date(2026, 6, 1), 9.0)),
        )
        assert trend.direction(tolerance=0.5) is TrendDirection.FALLING

    def test_a_change_within_tolerance_is_stable(self) -> None:
        trend = Trend(
            analyte="Creatinine",
            unit="mg/dL",
            values=((date(2026, 1, 1), 1.1), (date(2026, 6, 1), 1.2)),
        )
        assert trend.direction(tolerance=0.2) is TrendDirection.STABLE

    def test_one_point_is_not_a_trend(self) -> None:
        trend = Trend(analyte="x", unit="u", values=((date(2026, 1, 1), 1.0),))
        assert trend.direction(tolerance=0.1) is TrendDirection.INSUFFICIENT_DATA

    def test_no_points_is_not_a_trend(self) -> None:
        assert Trend(analyte="x", unit="u").direction(tolerance=0.1) is (
            TrendDirection.INSUFFICIENT_DATA
        )

    def test_out_of_order_points_are_rejected(self) -> None:
        """A trend read backwards reports the opposite direction."""
        with pytest.raises(ValueError, match="not in date order"):
            Trend(
                analyte="x",
                unit="u",
                values=((date(2026, 6, 1), 2.0), (date(2026, 1, 1), 1.0)),
            )


class TestReport:
    def test_unassessed_results_are_reported_separately(self) -> None:
        report = LabReport(
            results=(
                result("Sodium", 139, "mmol/L", "139", low=135, high=145),
                result("Ferritin", 12, "ng/mL", "12"),
            )
        )
        assert [r.analyte for r in report.unassessed] == ["Ferritin"]

    def test_abnormal_excludes_unassessed(self) -> None:
        report = LabReport(results=(result("Ferritin", 12, "ng/mL", "12"),))
        assert report.abnormal == ()

    def test_an_analyte_can_be_found_by_name(self) -> None:
        report = LabReport(results=(result("Sodium", 139, "mmol/L", "139", low=135, high=145),))
        assert len(report.find("sodium")) == 1
        assert report.find("potassium") == ()
