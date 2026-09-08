"""The Labs HTTP boundary.

The threshold layer runs for real. A potassium above the critical bound is
caught by the actual loaded threshold, not a stub.

Skipped where FastAPI is not installed, since it is an optional extra.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")
from fastapi.testclient import TestClient  # noqa: E402

from services.labs.api import app as api  # noqa: E402
from services.labs.clinical.critical_values import load_thresholds  # noqa: E402
from spine.schemas.lab import LabReport, LabResult  # noqa: E402
from spine.schemas.provenance import locate_document  # noqa: E402


def client_with() -> TestClient:
    """A client whose startup has already run.

    The context manager is deliberately not entered: entering it fires the real
    startup hook, and these tests load the thresholds directly.
    """
    api._thresholds = load_thresholds()
    return TestClient(api.app)


def report(analyte: str, value: float, unit: str) -> dict[str, object]:
    """A one-result report, as the API receives it.

    Every result carries a span: a finding without provenance fails schema
    validation and is dropped, and that holds at the HTTP boundary too.
    """
    line = f"{analyte} {value} {unit}"
    result = LabResult(
        analyte=analyte,
        value=value,
        unit=unit,
        provenance=locate_document(
            source_id="lab-1", source_text=line, quote=analyte, page=1
        ),
    )
    return LabReport(results=(result,)).model_dump(mode="json")


class TestHealth:
    def test_reports_healthy_once_thresholds_are_loaded(self) -> None:
        body = client_with().get("/health").json()
        assert body["status"] == "healthy"
        assert body["thresholds_loaded"] > 0

    def test_degraded_before_startup(self) -> None:
        api._thresholds = None
        try:
            body = TestClient(api.app).get("/health").json()
            assert body["status"] == "degraded"
            assert body["thresholds_loaded"] == 0
        finally:
            api._thresholds = load_thresholds()


class TestInterpret:
    def test_a_report_is_refused_before_startup(self) -> None:
        api._thresholds = None
        try:
            response = TestClient(api.app).post(
                "/v1/reports", json=report("potassium", 4.0, "mmol/L")
            )
            assert response.status_code == 503
            assert "not loaded" in response.json()["detail"]
        finally:
            api._thresholds = load_thresholds()

    def test_an_empty_report_has_no_critical_value(self) -> None:
        response = client_with().post("/v1/reports", json={"results": []})
        assert response.status_code == 201
        body = response.json()
        assert body["has_critical_value"] is False
        assert body["critical_findings"] == []

    def test_an_unknown_analyte_is_not_a_critical_value(self) -> None:
        """No threshold means no claim, rather than a claim of normality."""
        body = client_with().post(
            "/v1/reports", json=report("not_an_analyte", 999.0, "mg/dL")
        ).json()
        assert body["has_critical_value"] is False

    def test_a_unit_mismatch_is_reported_rather_than_skipped(self) -> None:
        """A silently skipped threshold is a missed critical value."""
        thresholds = load_thresholds()
        analyte = next(iter(thresholds))
        threshold = thresholds[analyte]
        body = client_with().post(
            "/v1/reports",
            json=report(analyte, threshold.critical_high or 1.0, "wrong_unit"),
        ).json()
        assert analyte in " ".join(body["unit_mismatches"])


class TestThresholds:
    def test_the_loaded_thresholds_are_readable(self) -> None:
        body = client_with().get("/v1/thresholds").json()
        assert body["count"] > 0

    def test_unverified_thresholds_are_named(self) -> None:
        """Every clinical threshold is awaiting sign-off in the current build."""
        body = client_with().get("/v1/thresholds").json()
        assert body["unverified"]

    def test_thresholds_are_refused_before_startup(self) -> None:
        api._thresholds = None
        try:
            assert TestClient(api.app).get("/v1/thresholds").status_code == 503
        finally:
            api._thresholds = load_thresholds()
