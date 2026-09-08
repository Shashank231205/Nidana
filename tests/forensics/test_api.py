"""The Forensics HTTP boundary.

The custody chain runs for real. Every access appends an entry, and a record
whose chain does not verify is refused rather than served with a warning.

Skipped where FastAPI is not installed, since it is an optional extra.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")
from fastapi.testclient import TestClient  # noqa: E402

from services.forensics.api import app as api  # noqa: E402
from spine.schemas.forensic import (  # noqa: E402
    Injury,
    InjuryType,
    MedicoLegalReport,
)
from spine.schemas.provenance import ExaminerEntry  # noqa: E402

EXAMINER = "dr_forensic_1"


def client() -> TestClient:
    """A fresh client with an empty store.

    The context manager is deliberately not entered: this service has no
    startup hook to fire, and the store is per-test.
    """
    api._examinations.clear()
    return TestClient(api.app)


def report(examination_id: UUID | None = None) -> MedicoLegalReport:
    identifier = examination_id or uuid4()
    injury = Injury(
        injury_type=InjuryType.ABRASION,
        site="left forearm",
        provenance=ExaminerEntry(
            source_id=str(identifier),
            examiner_id=EXAMINER,
            text="Abrasion on the left forearm, 3cm",
            field_path="injuries",
        ),
    )
    return MedicoLegalReport(
        examination_id=identifier,
        examiner_id=EXAMINER,
        examined_at=datetime.now(timezone.utc),
        injuries=(injury,),
    )


def create(test_client: TestClient, document: MedicoLegalReport) -> dict[str, object]:
    response = test_client.post(
        "/v1/examinations",
        json={"report": document.model_dump(mode="json"), "actor": EXAMINER},
    )
    assert response.status_code == 201
    body: dict[str, object] = response.json()
    return body


class TestHealth:
    def test_reports_healthy(self) -> None:
        assert client().get("/health").json()["status"] == "healthy"


class TestCreation:
    def test_creating_starts_the_chain(self) -> None:
        body = create(client(), report())
        assert body["chain_length"] == 1
        assert body["chain_verified"] is True

    def test_a_new_examination_is_not_amended(self) -> None:
        assert create(client(), report())["amended_after_finalisation"] is False


class TestAccessIsLogged:
    def test_reading_appends_to_the_chain(self) -> None:
        """A record read by someone with no role in the case is a custody problem."""
        test_client = client()
        document = report()
        create(test_client, document)
        body = test_client.post(
            f"/v1/examinations/{document.examination_id}/access",
            json={"actor": "dr_someone_else"},
        ).json()
        assert body["chain_length"] == 2

    def test_each_read_appends_again(self) -> None:
        test_client = client()
        document = report()
        create(test_client, document)
        for _ in range(3):
            test_client.post(
                f"/v1/examinations/{document.examination_id}/access",
                json={"actor": EXAMINER},
            )
        state = test_client.post(
            f"/v1/examinations/{document.examination_id}/chain",
            json={"actor": EXAMINER},
        ).json()
        assert len(state["entries"]) == 5

    def test_reading_the_chain_is_itself_logged(self) -> None:
        test_client = client()
        document = report()
        create(test_client, document)
        first = test_client.post(
            f"/v1/examinations/{document.examination_id}/chain",
            json={"actor": EXAMINER},
        ).json()
        second = test_client.post(
            f"/v1/examinations/{document.examination_id}/chain",
            json={"actor": EXAMINER},
        ).json()
        assert len(second["entries"]) > len(first["entries"])

    def test_an_unknown_examination_names_the_remedy(self) -> None:
        response = client().post(
            f"/v1/examinations/{uuid4()}/access", json={"actor": EXAMINER}
        )
        assert response.status_code == 404
        assert "POST /v1/examinations" in response.json()["detail"]

    def test_an_unattributed_access_is_rejected(self) -> None:
        """An unattributed access in a custody log is the same as no log."""
        test_client = client()
        document = report()
        create(test_client, document)
        response = test_client.post(
            f"/v1/examinations/{document.examination_id}/access", json={"actor": ""}
        )
        assert response.status_code == 422


class TestAmendment:
    def test_an_amendment_requires_a_reason(self) -> None:
        """A correction with no stated reason is indistinguishable from tampering."""
        test_client = client()
        document = report()
        create(test_client, document)
        response = test_client.post(
            f"/v1/examinations/{document.examination_id}/amend",
            json={"report": document.model_dump(mode="json"), "actor": EXAMINER},
        )
        assert response.status_code == 422

    def test_an_amendment_with_a_reason_is_recorded(self) -> None:
        test_client = client()
        document = report()
        create(test_client, document)
        body = test_client.post(
            f"/v1/examinations/{document.examination_id}/amend",
            json={
                "report": document.model_dump(mode="json"),
                "actor": EXAMINER,
                "reason": "Measurement corrected after re-examination",
            },
        ).json()
        assert body["chain_length"] == 2

    def test_a_report_for_another_examination_is_refused(self) -> None:
        test_client = client()
        document = report()
        create(test_client, document)
        response = test_client.post(
            f"/v1/examinations/{document.examination_id}/amend",
            json={
                "report": report().model_dump(mode="json"),
                "actor": EXAMINER,
                "reason": "Wrong record",
            },
        )
        assert response.status_code == 409


class TestFinalisation:
    def test_finalising_marks_the_report(self) -> None:
        test_client = client()
        document = report()
        create(test_client, document)
        body = test_client.post(
            f"/v1/examinations/{document.examination_id}/finalise",
            json={"actor": EXAMINER, "signature": "Dr Forensic, MBBS"},
        ).json()
        assert body["report"]["status"] == "finalised"

    def test_an_amendment_after_finalisation_is_visible(self) -> None:
        """A court reads 'amended after finalisation' differently from 'amended'."""
        test_client = client()
        document = report()
        create(test_client, document)
        test_client.post(
            f"/v1/examinations/{document.examination_id}/finalise",
            json={"actor": EXAMINER, "signature": "Dr Forensic, MBBS"},
        )
        body = test_client.post(
            f"/v1/examinations/{document.examination_id}/amend",
            json={
                "report": document.model_dump(mode="json"),
                "actor": EXAMINER,
                "reason": "Photograph attached late",
            },
        ).json()
        assert body["amended_after_finalisation"] is True
