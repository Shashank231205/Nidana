"""The watch screen's job is to be honest about what it does not know.

An ETA is a promise. A wrong one sends someone away for four hours on a job
that finishes in twenty minutes, or has them checking every five on one that
takes all day. These tests pin the cases where it must decline to guess.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from scripts.watch import Progress, _bar, _current_rule, _plain, render


def progress(**overrides: object) -> Progress:
    defaults: dict[str, object] = {
        "name": "Red flag rule review",
        "doing": "reading RF_TIA_001",
        "done": 15,
        "total": 30,
        "started_at": 1000.0,
        "last_at": 3400.0,
        "measured": 5,
    }
    defaults.update(overrides)
    return Progress(**defaults)  # type: ignore[arg-type]


class TestPace:
    def test_one_completion_times_nothing(self) -> None:
        """One file says when something finished, not how long it took."""
        assert progress(measured=1, started_at=1000.0, last_at=1000.0).seconds_each is None

    def test_no_completions_times_nothing(self) -> None:
        assert progress(measured=0, started_at=None, last_at=None).seconds_each is None

    def test_the_first_completion_bounds_the_span(self) -> None:
        """Five files span four intervals, not five.

        Dividing by the file count understates the pace by a fifth here, and
        by half when only two are in.
        """
        measured = progress(measured=5, started_at=1000.0, last_at=3400.0)
        assert measured.seconds_each == pytest.approx(600.0)

    def test_a_clock_that_went_backwards_times_nothing(self) -> None:
        assert progress(started_at=3400.0, last_at=1000.0).seconds_each is None


class TestEta:
    def test_an_unmeasured_run_has_no_eta(self) -> None:
        assert progress(measured=1).eta is None

    def test_a_finished_run_has_no_eta(self) -> None:
        assert progress(done=30).eta is None

    def test_the_eta_covers_what_is_left(self) -> None:
        assert progress().eta == timedelta(seconds=9000)


class TestRendering:
    def test_it_says_it_is_measuring_rather_than_guessing(self) -> None:
        assert "measuring" in render(progress(measured=1))

    def test_it_never_shows_a_pace_it_could_not_measure(self) -> None:
        assert "Pace" not in render(progress(measured=1))

    def test_a_finished_run_says_so(self) -> None:
        assert "Finished." in render(progress(done=30))

    def test_it_counts_one_remaining_rule_in_the_singular(self) -> None:
        assert "1 rule\n" in render(progress(done=29)) + "\n"

    def test_it_names_what_is_running_now(self) -> None:
        assert "RF_TIA_001" in render(progress())


class TestBar:
    def test_an_empty_run_fills_nothing(self) -> None:
        assert set(_bar(0, 30)) == {"."}

    def test_a_finished_run_fills_everything(self) -> None:
        assert set(_bar(30, 30)) == {"#"}

    def test_a_zero_total_draws_no_bar(self) -> None:
        """Guards a division by zero on a job with nothing to do."""
        assert _bar(0, 0) == ""


class TestPlainWords:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (30, "less than a minute"),
            (60, "about 1 minute"),
            (600, "about 10 minutes"),
            (3600, "about 1 hour"),
            (5400, "about 1h 30m"),
        ],
    )
    def test_durations_read_as_someone_would_say_them(
        self, seconds: int, expected: str
    ) -> None:
        assert _plain(timedelta(seconds=seconds)) == expected


class TestReadingTheLog:
    def test_no_log_reports_nothing_rather_than_guessing(self) -> None:
        """A stale copy is worse than no log: it looks current."""
        assert _current_rule(None) is None

    def test_a_missing_file_reports_nothing(self, tmp_path: Path) -> None:
        assert _current_rule(tmp_path / "absent.log") is None

    def test_it_reads_the_last_position_not_the_first(self, tmp_path: Path) -> None:
        log = tmp_path / "panel.log"
        log.write_text(
            "[1/16] RF_STROKE_001\n[8/16] RF_VISION_LOSS_001\n", encoding="utf-8"
        )
        assert _current_rule(log) == ("RF_VISION_LOSS_001", 8, 16)

    def test_a_log_with_no_position_lines_reports_nothing(self, tmp_path: Path) -> None:
        log = tmp_path / "panel.log"
        log.write_text("starting\nloading model\n", encoding="utf-8")
        assert _current_rule(log) is None
