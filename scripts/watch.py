"""Watch a long background job in plain words.

The panel takes hours and writes a technical log. Someone checking on it wants
three things and none of them are in that log: what is it doing, how far
through is it, and when will it be done.

Reads state from the files the job actually produces rather than from a status
the job would have to remember to write. A job that dies mid-write leaves a
directory that is still true; a status line it never got to update does not.

    python scripts/watch.py            once, then exit
    python scripts/watch.py --follow   redraw until it finishes
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PANEL_BRIEFS = ROOT / "docs" / "verification" / "panel"
TOTAL_RULES = 30

BAR_WIDTH = 32
MINUTES_PER_HOUR = 60
MIN_SAMPLES_TO_TIME = 2
"""Two completions bound one interval. One completion times nothing."""


@dataclass(frozen=True)
class Progress:
    """What a job has finished, and how fast it got there."""

    name: str
    doing: str
    done: int
    total: int
    started_at: float | None
    last_at: float | None
    measured: int
    """How many of this run's completions the timing is based on."""

    @property
    def remaining(self) -> int:
        return max(self.total - self.done, 0)

    @property
    def seconds_each(self) -> float | None:
        """Measured from this run's own completions, not a fixed estimate.

        Needs two completions to measure an interval. One tells you when
        something finished, not how long it took, so this returns None and the
        screen says it is still measuring rather than showing a made-up figure.
        """
        if self.started_at is None or self.last_at is None or self.measured < MIN_SAMPLES_TO_TIME:
            return None
        span = self.last_at - self.started_at
        if span <= 0:
            return None
        # The first file bounds the span rather than sitting inside it.
        return span / (self.measured - 1)

    @property
    def eta(self) -> timedelta | None:
        each = self.seconds_each
        if each is None or self.remaining == 0:
            return None
        return timedelta(seconds=int(each * self.remaining))


def _bar(done: int, total: int) -> str:
    if total <= 0:
        return ""
    filled = round(BAR_WIDTH * done / total)
    return "#" * filled + "." * (BAR_WIDTH - filled)


def _plain(delta: timedelta) -> str:
    """A duration as someone would say it out loud."""
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "less than a minute"
    if minutes < MINUTES_PER_HOUR:
        return f"about {minutes} minute{'s' if minutes != 1 else ''}"
    hours, rest = divmod(minutes, MINUTES_PER_HOUR)
    if rest == 0:
        return f"about {hours} hour{'s' if hours != 1 else ''}"
    return f"about {hours}h {rest}m"


def _default_log() -> Path:
    """Where the panel writes when started by scripts/run_panel.py."""
    return ROOT / ".local" / "panel.log"


def _current_rule(log: Path | None) -> tuple[str, int, int] | None:
    """The rule the panel named last, and its position in this run."""
    if log is None or not log.is_file():
        return None
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            marker, _, rule = stripped.partition("]")
            position, _, run_total = marker.lstrip("[").partition("/")
            if position.isdigit() and run_total.isdigit():
                return rule.strip(), int(position), int(run_total)
    return None


def panel_progress(log: Path | None) -> Progress:
    briefs = sorted(PANEL_BRIEFS.glob("*.md"), key=lambda p: p.stat().st_mtime)
    times = [path.stat().st_mtime for path in briefs]

    current = _current_rule(log)
    doing = (
        f"reading {current[0]}  (number {current[1]} of {current[2]} this run)"
        if current is not None
        else "starting up"
    )

    # Only this run's completions time this run. Briefs from an earlier run
    # were written at a different time of day on a machine doing other things.
    if current is None:
        # No readable log means no way to tell this run's briefs from an
        # earlier run's. Timing across both gave "96 min per rule" and a
        # 24-hour ETA on a job averaging eight minutes. Better to say nothing.
        run_times: list[float] = []
    else:
        finished_this_run = max(current[1] - 1, 0)
        run_times = times[-finished_this_run:] if finished_this_run > 0 else []

    return Progress(
        name="Red flag rule review",
        doing=doing,
        done=len(briefs),
        total=TOTAL_RULES,
        started_at=run_times[0] if run_times else None,
        last_at=run_times[-1] if run_times else None,
        measured=len(run_times),
    )


def render(progress: Progress) -> str:
    lines: list[str] = []
    lines.append(progress.name)
    lines.append("")
    lines.append(f"  [{_bar(progress.done, progress.total)}]  {progress.done} of {progress.total}")
    lines.append("")
    lines.append(f"  Right now:   {progress.doing}")
    plural = "s" if progress.remaining != 1 else ""
    lines.append(f"  Still to do: {progress.remaining} rule{plural}")

    eta = progress.eta
    if eta is None:
        if progress.remaining == 0:
            lines.append("  Finished.")
        else:
            lines.append("  Time left:   measuring, ask again in a few minutes")
    else:
        done_at = datetime.now() + eta
        lines.append(f"  Time left:   {_plain(eta)}, so done around {done_at.strftime('%H:%M')}")

    each = progress.seconds_each
    if each is not None:
        lines.append(f"  Pace:        about {int(each // 60)} min per rule")

    lines.append("")
    lines.append("  Nothing to do while this runs. It saves as it goes, so")
    lines.append("  stopping it loses at most the rule it is on.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--follow", action="store_true", help="redraw until it finishes")
    parser.add_argument("--every", type=int, default=30, help="seconds between redraws")
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="the job's log file; without it, progress shows but not the pace",
    )
    args = parser.parse_args()

    log = args.log if args.log is not None else _default_log()
    while True:
        progress = panel_progress(log)
        if args.follow:
            print("\033[2J\033[H", end="")
        print(render(progress))
        if not args.follow or progress.remaining == 0:
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    sys.exit(main())
