"""The Rx HTTP boundary.

The clinical layer runs for real. A prescription that duplicates a molecule is
caught by the actual check, not a stub.

Skipped where FastAPI is not installed, since it is an optional extra.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")
from fastapi.testclient import TestClient  # noqa: E402

from services.rx.api import app as api  # noqa: E402
from spine.schemas.medication import (  # noqa: E402
    MedicationList,
    Molecule,
    PrescribedMedication,
    ResolutionStatus,
)
from spine.schemas.provenance import locate_document  # noqa: E402
from spine.schemas.record import Allergy, Record, SubjectType  # noqa: E402

PRESCRIPTION_TEXT = "Tab Crocin 500mg BD\nTab Dolo 650mg SOS\nTab Amoxil 500mg TDS"


def empty_record(**overrides: object) -> Record:
    """A record for one prescription.

    Rx works from a prescription rather than a session, which is why
    SubjectType has a value for it.
    """
    return Record(
        subject_type=SubjectType.PRESCRIPTION,
        subject_id=uuid4(),
        **overrides,
    )


def span(quote: str) -> object:
    return locate_document(
        source_id="rx-1", source_text=PRESCRIPTION_TEXT, quote=quote, page=1
    )


def medication(
    written_as: str,
    molecule: str | None,
    resolution: ResolutionStatus = ResolutionStatus.RESOLVED,
) -> PrescribedMedication:
    return PrescribedMedication(
        written_as=written_as,
        molecules=(Molecule(name=molecule),) if molecule else (),
        resolution=resolution,
        resolution_confidence=1.0 if molecule else 0.0,
        provenance=span(written_as),
    )


def client_with() -> TestClient:
    """A client whose startup has already run.

    The context manager is deliberately not entered: entering it fires the real
    startup hook, and these tests set the loaded state directly.
    """
    api._brand_index = None
    api._started = True
    return TestClient(api.app)


class TestHealth:
    def test_reports_healthy_once_started(self) -> None:
        response = client_with().get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_reports_brand_resolution_unavailable_without_an_index(self) -> None:
        body = client_with().get("/health").json()
        assert body["brand_resolution_available"] is False

    def test_degraded_before_startup(self) -> None:
        api._started = False
        try:
            assert TestClient(api.app).get("/health").json()["status"] == "degraded"
        finally:
            api._started = True


class TestChecks:
    def test_a_clean_list_blocks_nothing(self) -> None:
        payload = {
            "medications": MedicationList(
                medications=(medication("Tab Crocin 500mg BD", "paracetamol"),)
            ).model_dump(mode="json"),
            "record": empty_record().model_dump(mode="json"),
        }
        response = client_with().post("/v1/checks", json=payload)
        assert response.status_code == 201
        assert response.json()["blocks_dispensing"] is False

    def test_duplicate_therapy_is_reported(self) -> None:
        """Two brands, one molecule. Invisible to a patient reading the labels."""
        payload = {
            "medications": MedicationList(
                medications=(
                    medication("Tab Crocin 500mg BD", "paracetamol"),
                    medication("Tab Dolo 650mg SOS", "paracetamol"),
                )
            ).model_dump(mode="json"),
            "record": empty_record().model_dump(mode="json"),
        }
        body = client_with().post("/v1/checks", json=payload).json()
        kinds = {finding["kind"] for finding in body["findings"]}
        assert "duplicate_therapy" in kinds

    def test_an_unresolved_line_blocks_dispensing(self) -> None:
        """A line the system could not identify means every other check ran without it."""
        payload = {
            "medications": MedicationList(
                medications=(
                    medication("Tab Unknown", None, ResolutionStatus.REFUSED),
                )
            ).model_dump(mode="json"),
            "record": empty_record().model_dump(mode="json"),
        }
        body = client_with().post("/v1/checks", json=payload).json()
        assert body["blocks_dispensing"] is True

    def test_an_allergy_is_reported(self) -> None:
        """The allergy names the molecule.

        Class matching -- that a penicillin allergy covers amoxicillin -- needs
        a real dataset and is deliberately not attempted, so the test does not
        assert it.
        """
        record = empty_record(allergies=(Allergy(substance="amoxicillin"),))
        payload = {
            "medications": MedicationList(
                medications=(medication("Tab Amoxil 500mg TDS", "amoxicillin"),)
            ).model_dump(mode="json"),
            "record": record.model_dump(mode="json"),
        }
        body = client_with().post("/v1/checks", json=payload).json()
        assert any(finding["kind"] == "allergy" for finding in body["findings"])

    def test_findings_are_most_severe_first(self) -> None:
        payload = {
            "medications": MedicationList(
                medications=(
                    medication("Tab Crocin 500mg BD", "paracetamol"),
                    medication("Tab Dolo 650mg SOS", "paracetamol"),
                    medication("Tab Unknown", None, ResolutionStatus.REFUSED),
                )
            ).model_dump(mode="json"),
            "record": empty_record().model_dump(mode="json"),
        }
        body = client_with().post("/v1/checks", json=payload).json()
        assert body["findings"][0]["severity"] == "contraindicated"

    def test_an_empty_list_is_accepted(self) -> None:
        payload = {
            "medications": MedicationList().model_dump(mode="json"),
            "record": empty_record().model_dump(mode="json"),
        }
        response = client_with().post("/v1/checks", json=payload)
        assert response.status_code == 201
        assert response.json()["findings"] == []

    def test_checks_are_refused_before_startup(self) -> None:
        api._started = False
        try:
            payload = {
                "medications": MedicationList().model_dump(mode="json"),
                "record": empty_record().model_dump(mode="json"),
            }
            response = TestClient(api.app).post("/v1/checks", json=payload)
            assert response.status_code == 503
            assert "starting" in response.json()["detail"]
        finally:
            api._started = True


class TestBrandIndexConfiguration:
    def test_no_configured_path_means_no_index(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(api.BRAND_INDEX_PATH, raising=False)
        assert api.build_dependencies() is None

    def test_a_missing_index_file_names_the_remedy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(api.BRAND_INDEX_PATH, "does/not/exist.csv")
        with pytest.raises(RuntimeError, match="Unset it to run without"):
            api.build_dependencies()
