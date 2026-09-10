"""Start the rule review panel in the background, and say how to watch it.

The panel is a multi-hour job. Starting it by hand means remembering the model
name, the output directory and somewhere to send the log, and getting the log
wrong is what makes `scripts/watch.py` unable to report a pace.

This puts the log where the watcher looks by default, so the two agree without
either being told.

    python scripts/run_panel.py
    python scripts/watch.py --follow
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / ".local" / "panel.log"
BRIEFS = ROOT / "docs" / "verification" / "panel"

DEFAULT_MODEL = "granite4.1:3b"
"""Small enough to finish in hours rather than days.

qwen3 does extended thinking and times out on the panel's budgets.
"""


def main() -> int:
    model = os.environ.get("NIDANA_MODEL_PRIMARY", DEFAULT_MODEL)
    LOG.parent.mkdir(parents=True, exist_ok=True)

    environment = dict(os.environ, NIDANA_MODEL_PRIMARY=model)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "review_rules.py"),
        "--out",
        str(BRIEFS),
    ]

    # Detached, with the log opened here rather than by a shell, so the path
    # is the one the watcher reads and not whatever a redirect happened to use.
    with LOG.open("a", encoding="utf-8") as sink:
        process = subprocess.Popen(
            command,
            stdout=sink,
            stderr=subprocess.STDOUT,
            cwd=str(ROOT),
            env=environment,
        )

    done = len(list(BRIEFS.glob("*.md"))) if BRIEFS.is_dir() else 0
    print(f"Panel started (process {process.pid}), reading with {model}.")
    print(f"{done} rules already reviewed; it skips those and continues.")
    print()
    print("Watch it in plain words:")
    print("    python scripts/watch.py --follow")
    print()
    print(f"Log: {LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
