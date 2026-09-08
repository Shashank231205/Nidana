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
from spine.inference.adapter import (  # noqa: E402
    Completion,
    InferenceProvider,
    ModelSpec,
    Transport,
)
from spine.inference.prompts import load_all  # noqa: E402
from spine.schemas.lab import LabReport, LabResult  # noqa: E402
from spine.schemas.provenance import locate_document  # noqa: E402


class ScriptedProvider(InferenceProvider):
    """Answers with fixed text. The threshold layer runs for real."""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses) or ['{"results":[]}']
        self.seen: list[tuple[str, str]] = []

    @property
    def transport(self) -> Transport:
        return Transport.LOCAL

    def is_available(self) -> bool:
        return True

    def complete(
        self, *, prompt: str, system: str, spec: ModelSpec, prompt_version: str
    ) -> Completion:
        self.seen.append((prompt, system))
        text = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return Completion(
            text=text,
            model_version=spec.name,
            transport=Transport.LOCAL,
            prompt_version=prompt_version,
        )


def dependencies(*responses: str) -> api.Dependencies:
    return api.Dependencies(
        thresholds=load_thresholds(),
        provider=ScriptedProvider(*responses),
        prompts=load_all("labs"),
    )


def client_with(*responses: str) -> TestClient:
    """A client whose startup has already run.

    The context manager is deliberately not entered: entering it fires the real
    startup hook, and these tests load the thresholds directly.
    """
    api._dependencies = dependencies(*responses)
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
        api._dependencies = None
        try:
            body = TestClient(api.app).get("/health").json()
            assert body["status"] == "degraded"
            assert body["thresholds_loaded"] == 0
        finally:
            api._dependencies = dependencies()


class TestInterpret:
    def test_a_report_is_refused_before_startup(self) -> None:
        api._dependencies = None
        try:
            response = TestClient(api.app).post(
                "/v1/reports", json=report("potassium", 4.0, "mmol/L")
            )
            assert response.status_code == 503
            assert "not loaded" in response.json()["detail"]
        finally:
            api._dependencies = dependencies()

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
        api._dependencies = None
        try:
            assert TestClient(api.app).get("/v1/thresholds").status_code == 503
        finally:
            api._dependencies = dependencies()


class TestExtraction:
    """The extraction endpoint reads a report, then thresholds what it read."""

    REPORT = "Potassium        6.8   mmol/L  (3.5 - 5.1)\n"

    def _draft(self, span: str, value: str = "6.8") -> str:
        return (
            '{"results":[{"analyte":"Potassium","value":"' + value + '",'
            '"unit":"mmol/L","source_span":"' + span + '"}]}'
        )

    def test_a_grounded_result_reaches_the_report(self) -> None:
        client = client_with(self._draft("Potassium        6.8   mmol/L"))
        body = client.post(
            "/v1/reports/extract",
            json={"report_text": self.REPORT, "source_id": "lab-1"},
        ).json()
        assert len(body["report"]["results"]) == 1
        assert body["fabrication_count"] == 0

    def test_a_result_not_in_the_report_is_dropped_and_counted(self) -> None:
        client = client_with(self._draft("Sodium 140 mmol/L"))
        body = client.post(
            "/v1/reports/extract",
            json={"report_text": self.REPORT, "source_id": "lab-1"},
        ).json()
        assert body["report"]["results"] == []
        assert body["fabrication_count"] == 1
        assert body["dropped"]

    def test_extraction_and_thresholding_happen_in_one_call(self) -> None:
        """A report read but not checked is the failure this service prevents."""
        client = client_with(self._draft("Potassium        6.8   mmol/L"))
        body = client.post(
            "/v1/reports/extract",
            json={"report_text": self.REPORT, "source_id": "lab-1"},
        ).json()
        assert "has_critical_value" in body
        assert "unit_mismatches" in body

    def test_a_qualified_value_is_dropped_rather_than_coerced(self) -> None:
        client = client_with(self._draft("Potassium        6.8   mmol/L", value="<0.01"))
        body = client.post(
            "/v1/reports/extract",
            json={"report_text": self.REPORT, "source_id": "lab-1"},
        ).json()
        assert body["report"]["results"] == []
        assert "not a plain number" in body["dropped"][0]

    def test_an_empty_report_text_is_rejected(self) -> None:
        response = client_with().post(
            "/v1/reports/extract", json={"report_text": "", "source_id": "lab-1"}
        )
        assert response.status_code == 422

    def test_extraction_is_refused_before_startup(self) -> None:
        api._dependencies = None
        try:
            response = TestClient(api.app).post(
                "/v1/reports/extract",
                json={"report_text": self.REPORT, "source_id": "lab-1"},
            )
            assert response.status_code == 503
        finally:
            api._dependencies = dependencies()
