"""The eval harness and vignette loading.

The harness decides whether a build ships, so its own arithmetic is tested. The
gate that matters most is red flag sensitivity: a single missed emergency
blocks release, and this file asserts that it does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from services.consult.eval.harness import (
    UNDER_TRIAGE_CEILING,
    CaseResult,
    Outcome,
    Report,
)
from services.consult.eval.vignettes import VignetteLoadError, load_all, scorable
from spine.schemas.primitives import Band
from spine.schemas.triage import Specialty

SCORABLE_VIGNETTE = """
vignettes:
  - id: CP_001
    description: Exertional chest pain in a diabetic
    complaint_family: chest_pain
    age_years: 58
    sex: male
    turns:
      - patient: "Chest mein dard ho raha hai"
        language: hi-en
    reference_band: U2
    reference_specialty: cardiology
    reviewed_by: "Dr Example, reg 12345"
    reviewed_on: "2026-01-01"
    source: "Written for this vignette set"
"""

UNSCORED_VIGNETTE = """
vignettes:
  - id: AB_001
    description: Abdominal pain, awaiting a reference label
    complaint_family: abdominal_pain
    turns:
      - patient: "Pet mein dard"
        language: hi-en
    source: "Written for this vignette set"
"""


def case(
    vignette_id: str,
    reference: Band | None,
    assigned: Band,
    *,
    expected_flags: tuple[str, ...] = (),
    fired_flags: tuple[str, ...] = (),
    fabricated: tuple[str, ...] = (),
    turns: int = 10,
) -> CaseResult:
    return CaseResult(
        vignette_id=vignette_id,
        reference_band=reference,
        assigned_band=assigned,
        reference_specialty=Specialty.CARDIOLOGY,
        assigned_specialty=Specialty.CARDIOLOGY,
        expected_red_flags=expected_flags,
        fired_red_flags=fired_flags,
        fabricated_findings=fabricated,
        turns=turns,
    )


class TestOutcomeClassification:
    def test_matching_the_reference_is_exact(self) -> None:
        assert case("A", Band.U2, Band.U2).outcome is Outcome.EXACT

    def test_a_more_urgent_band_is_over_triage(self) -> None:
        assert case("A", Band.U3, Band.U1).outcome is Outcome.OVER_TRIAGED

    def test_a_less_urgent_band_is_under_triage(self) -> None:
        assert case("A", Band.U1, Band.U3).outcome is Outcome.UNDER_TRIAGED

    def test_no_reference_label_is_unscored_not_correct(self) -> None:
        """A case with no clinician label must not count as a pass."""
        assert case("A", None, Band.U2).outcome is Outcome.UNSCORED


class TestReleaseGates:
    def test_a_clean_run_is_releasable(self) -> None:
        report = Report(cases=[case("A", Band.U2, Band.U2), case("B", Band.U3, Band.U3)])
        assert report.releasable
        assert not report.blocking_failures

    def test_one_missed_red_flag_blocks_release(self) -> None:
        report = Report(
            cases=[case("A", Band.U1, Band.U1, expected_flags=("RF_STROKE_001",))]
        )
        assert not report.releasable
        assert "red flag sensitivity" in report.blocking_failures[0]

    def test_the_blocked_message_names_the_case_and_the_rule(self) -> None:
        report = Report(
            cases=[case("ST_001", Band.U1, Band.U1, expected_flags=("RF_STROKE_001",))]
        )
        failure = report.blocking_failures[0]
        assert "ST_001" in failure
        assert "RF_STROKE_001" in failure

    def test_under_triage_above_the_ceiling_blocks_release(self) -> None:
        """Three in a hundred is 3%, above the 2% gate."""
        cases = [case(f"C{i}", Band.U2, Band.U2) for i in range(97)]
        cases.extend(case(f"BAD{i}", Band.U1, Band.U4) for i in range(3))
        report = Report(cases=cases)
        assert report.under_triage_rate == pytest.approx(0.03)
        assert report.under_triage_rate > UNDER_TRIAGE_CEILING
        assert not report.releasable

    def test_one_under_triage_in_a_hundred_is_within_the_ceiling(self) -> None:
        """1% is under the 2% gate; the boundary is where it is claimed to be."""
        cases = [case(f"C{i}", Band.U2, Band.U2) for i in range(99)]
        cases.append(case("SLIGHT", Band.U2, Band.U3))
        report = Report(cases=cases)
        assert report.under_triage_rate == pytest.approx(0.01)
        assert report.releasable

    def test_a_fabricated_finding_blocks_release(self) -> None:
        report = Report(cases=[case("A", Band.U2, Band.U2, fabricated=("invented_symptom",))])
        assert not report.releasable
        assert "structurally impossible" in report.blocking_failures[0]

    def test_every_failure_is_reported_not_just_the_first(self) -> None:
        report = Report(
            cases=[
                case("A", Band.U1, Band.U4, expected_flags=("RF_X",), fabricated=("f",)),
            ]
        )
        assert len(report.blocking_failures) == 3

    def test_over_triage_alone_never_blocks_release(self) -> None:
        """Over-triage is the direction this system is designed to err in."""
        report = Report(cases=[case(f"C{i}", Band.U4, Band.U1) for i in range(10)])
        assert report.over_triage_rate == 1.0
        assert report.releasable


class TestRedFlagSensitivity:
    def test_all_expected_rules_firing_is_one_hundred_percent(self) -> None:
        report = Report(
            cases=[case("A", Band.U1, Band.U1, expected_flags=("RF_X",), fired_flags=("RF_X",))]
        )
        assert report.red_flag_sensitivity == 1.0

    def test_sensitivity_is_computed_over_rules_not_cases(self) -> None:
        """A case expecting two rules and firing one scores half, not a pass."""
        report = Report(
            cases=[
                case(
                    "A",
                    Band.U1,
                    Band.U1,
                    expected_flags=("RF_X", "RF_Y"),
                    fired_flags=("RF_X",),
                )
            ]
        )
        assert report.red_flag_sensitivity == 0.5

    def test_extra_rules_firing_does_not_reduce_sensitivity(self) -> None:
        report = Report(
            cases=[
                case(
                    "A",
                    Band.U1,
                    Band.U1,
                    expected_flags=("RF_X",),
                    fired_flags=("RF_X", "RF_Z"),
                )
            ]
        )
        assert report.red_flag_sensitivity == 1.0

    def test_a_set_expecting_no_rules_reports_full_sensitivity(self) -> None:
        assert Report(cases=[case("A", Band.U4, Band.U4)]).red_flag_sensitivity == 1.0


class TestReporting:
    def test_unscored_cases_are_counted_separately(self) -> None:
        report = Report(cases=[case("A", Band.U2, Band.U2), case("B", None, Band.U3)])
        assert report.unscored_count == 1
        assert len(report.scored) == 1

    def test_unscored_cases_do_not_affect_the_rates(self) -> None:
        report = Report(cases=[case("A", Band.U2, Band.U2), case("B", None, Band.U1)])
        assert report.exact_rate == 1.0

    def test_an_empty_report_has_no_rates_and_no_failures(self) -> None:
        report = Report()
        assert report.under_triage_rate == 0.0
        assert report.releasable

    def test_median_turns_over_an_even_count(self) -> None:
        report = Report(
            cases=[
                case("A", Band.U2, Band.U2, turns=8),
                case("B", Band.U2, Band.U2, turns=12),
            ]
        )
        assert report.median_turns == 10.0

    def test_median_turns_over_an_odd_count(self) -> None:
        report = Report(
            cases=[
                case("A", Band.U2, Band.U2, turns=8),
                case("B", Band.U2, Band.U2, turns=9),
                case("C", Band.U2, Band.U2, turns=14),
            ]
        )
        assert report.median_turns == 9.0

    def test_routing_accuracy_ignores_unlabelled_cases(self) -> None:
        mismatched = CaseResult(
            vignette_id="A",
            reference_band=Band.U2,
            assigned_band=Band.U2,
            reference_specialty=None,
            assigned_specialty=Specialty.NEUROLOGY,
            expected_red_flags=(),
            fired_red_flags=(),
        )
        assert Report(cases=[mismatched]).routing_accuracy == 0.0

    def test_the_summary_states_the_gates(self) -> None:
        summary = Report(cases=[case("A", Band.U2, Band.U2)]).summary()
        assert "red flag sens." in summary
        assert "All release gates met" in summary

    def test_a_low_over_triage_rate_is_flagged_as_suspicious(self) -> None:
        summary = Report(cases=[case("A", Band.U2, Band.U2)]).summary()
        assert "over-confident" in summary


class TestVignetteLoading:
    def test_the_shipped_set_is_empty_pending_a_clinician(self) -> None:
        """Honest rather than convenient. See eval/cases/README.md."""
        assert load_all() == ()

    def test_a_scorable_vignette_loads(self, tmp_path: Path) -> None:
        (tmp_path / "chest_pain.yaml").write_text(SCORABLE_VIGNETTE, encoding="utf-8")
        loaded = load_all(tmp_path)
        assert len(loaded) == 1
        assert loaded[0].is_scorable

    def test_a_vignette_without_a_reference_label_still_loads(self, tmp_path: Path) -> None:
        (tmp_path / "abdominal.yaml").write_text(UNSCORED_VIGNETTE, encoding="utf-8")
        loaded = load_all(tmp_path)
        assert len(loaded) == 1
        assert not loaded[0].is_scorable

    def test_a_reference_band_without_a_reviewer_is_rejected(self, tmp_path: Path) -> None:
        """An engineer's guess is not a reference label."""
        (tmp_path / "bad.yaml").write_text(
            SCORABLE_VIGNETTE.replace('    reviewed_by: "Dr Example, reg 12345"\n', ""),
            encoding="utf-8",
        )
        with pytest.raises(VignetteLoadError, match="not a reference label"):
            load_all(tmp_path)

    def test_expected_red_flags_without_a_reference_band_are_rejected(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "bad.yaml").write_text(
            UNSCORED_VIGNETTE.replace(
                '    source: "Written for this vignette set"',
                "    expected_red_flags: [RF_ACS_001]\n"
                '    source: "Written for this vignette set"',
            ),
            encoding="utf-8",
        )
        with pytest.raises(VignetteLoadError, match="needs a clinician-assigned band"):
            load_all(tmp_path)

    def test_a_duplicate_id_across_files_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(SCORABLE_VIGNETTE, encoding="utf-8")
        (tmp_path / "b.yaml").write_text(SCORABLE_VIGNETTE, encoding="utf-8")
        with pytest.raises(VignetteLoadError, match="one definition"):
            load_all(tmp_path)

    def test_malformed_yaml_names_the_file(self, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text("vignettes: [unclosed", encoding="utf-8")
        with pytest.raises(VignetteLoadError, match="not valid YAML"):
            load_all(tmp_path)

    def test_a_missing_vignettes_key_is_rejected(self, tmp_path: Path) -> None:
        (tmp_path / "bad.yaml").write_text("cases:\n  - id: X\n", encoding="utf-8")
        with pytest.raises(VignetteLoadError, match="top-level 'vignettes'"):
            load_all(tmp_path)

    def test_scorable_filters_to_labelled_cases(self, tmp_path: Path) -> None:
        (tmp_path / "a.yaml").write_text(SCORABLE_VIGNETTE, encoding="utf-8")
        (tmp_path / "b.yaml").write_text(UNSCORED_VIGNETTE, encoding="utf-8")
        assert len(scorable(load_all(tmp_path))) == 1

    def test_a_missing_directory_returns_no_cases(self, tmp_path: Path) -> None:
        assert load_all(tmp_path / "absent") == ()
