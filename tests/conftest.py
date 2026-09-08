"""Test configuration.

The one thing this file exists for: the API tests are guarded by
`pytest.importorskip("fastapi")`, so where FastAPI is missing they skip rather
than fail and the suite still reports green with 63 tests never run. That is
the failure mode this repository has already been bitten by — two real bugs in
the service APIs reached main because the tests that would have caught them
were skipping locally.

Skipping is correct for a developer who has installed only the base extra. It
is not correct in CI, where the API extra is installed and a skip means
something is wrong with the environment rather than with the developer's setup.
So CI refuses a skipped API test, and a local run reports it as a warning.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

API_TEST_FILES = "test_api.py"


def _in_ci() -> bool:
    return os.environ.get("CI", "").strip().lower() in {"1", "true", "yes"}


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
) -> None:
    """Fail the run in CI if an API test skipped.

    A skip here means FastAPI is absent from an environment that declares it,
    which makes a green suite misleading rather than reassuring.
    """
    skipped = terminalreporter.stats.get("skipped", [])
    api_skips = [
        report
        for report in skipped
        if Path(str(report.fspath)).name == API_TEST_FILES
    ]
    if not api_skips:
        return

    message = (
        f"{len(api_skips)} API test(s) skipped because FastAPI is not importable. "
        f"Install the api extra: pip install -e '.[dev]'. If pip fails with "
        f"CERTIFICATE_VERIFY_FAILED, see the TLS interception note in README.md."
    )
    if _in_ci():
        terminalreporter.write_line(f"ERROR: {message}", red=True)
        pytest.exit(message, returncode=1)
    else:
        terminalreporter.write_line(f"WARNING: {message}", yellow=True)
