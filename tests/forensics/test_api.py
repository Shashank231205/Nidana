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
from spine.inference.adapter import (  # noqa: E402
    Completion,
    InferenceProvider,
    ModelSpec,
    Transport,
)
from spine.inference.prompts import load_all  # noqa: E402
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


class ScriptedProvider(InferenceProvider):
    """Answers with fixed text. The custody chain and the gate run for real."""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses) or ['{"injuries":[]}']
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


DICTATION = "There is an abrasion on the left forearm measuring 3 cm by 1 cm."


def structuring_client(*responses: str) -> TestClient:
    """A client wired for the structuring endpoint."""
    api._examinations.clear()
    api._provider = ScriptedProvider(*responses)
    api._prompts = load_all("forensics")
    return TestClient(api.app)


def injury(span: str) -> str:
    return (
        '{"injuries":[{"injury_type":"abrasion","site":"left forearm",'
        '"source_span":"' + span + '"}]}'
    )


class TestStructuring:
    def test_a_dictated_injury_reaches_the_report(self) -> None:
        client = structuring_client(injury("an abrasion on the left forearm"))
        document = report()
        create(client, document)
        body = client.post(
            f"/v1/examinations/{document.examination_id}/structure",
            json={"dictation": DICTATION, "actor": EXAMINER},
        ).json()
        # One injury from the fixture, one from the dictation.
        assert len(body["report"]["injuries"]) == 2
        assert body["fabrication_count"] == 0

    def test_an_undictated_injury_is_dropped_and_counted(self) -> None:
        client = structuring_client(injury("a stab wound to the abdomen"))
        document = report()
        create(client, document)
        body = client.post(
            f"/v1/examinations/{document.examination_id}/structure",
            json={"dictation": DICTATION, "actor": EXAMINER},
        ).json()
        assert len(body["report"]["injuries"]) == 1
        assert body["fabrication_count"] == 1
        assert body["dropped"]

    def test_structuring_is_logged_to_the_custody_chain(self) -> None:
        """A change to the record that left no trace would defeat the chain."""
        client = structuring_client(injury("an abrasion on the left forearm"))
        document = report()
        created = create(client, document)
        body = client.post(
            f"/v1/examinations/{document.examination_id}/structure",
            json={"dictation": DICTATION, "actor": EXAMINER},
        ).json()
        assert body["chain_length"] > created["chain_length"]

    def test_a_finalised_examination_is_not_restructured(self) -> None:
        """After finalisation a change is an amendment with a stated reason."""
        client = structuring_client(injury("an abrasion on the left forearm"))
        document = report()
        create(client, document)
        client.post(
            f"/v1/examinations/{document.examination_id}/finalise",
            json={"actor": EXAMINER, "signature": "Dr Forensic, MBBS"},
        )
        response = client.post(
            f"/v1/examinations/{document.examination_id}/structure",
            json={"dictation": DICTATION, "actor": EXAMINER},
        )
        assert response.status_code == 409
        assert "amend" in response.json()["detail"]

    def test_an_unknown_examination_is_a_404(self) -> None:
        client = structuring_client()
        response = client.post(
            f"/v1/examinations/{uuid4()}/structure",
            json={"dictation": DICTATION, "actor": EXAMINER},
        )
        assert response.status_code == 404

    def test_an_unattributed_structuring_is_rejected(self) -> None:
        client = structuring_client()
        document = report()
        create(client, document)
        response = client.post(
            f"/v1/examinations/{document.examination_id}/structure",
            json={"dictation": DICTATION, "actor": ""},
        )
        assert response.status_code == 422


class TestStatuteTranslation:
    """Reading an archived citation across the 2024 renumbering.

    A report written in June 2024 cites IPC numbers and one written in July
    cites BNS numbers for the same provision. This endpoint answers what a
    section is called now; it does not classify an injury, and the tests below
    pin that boundary as much as the transcription.
    """

    def test_an_ipc_section_translates_forward(self) -> None:
        response = client().get("/v1/statutes/ipc/320")
        assert response.status_code == 200
        body = response.json()
        assert body["matches"][0]["bns"] == "116"
        assert body["matches"][0]["title"] == "Grievous hurt"

    def test_a_bns_section_translates_back(self) -> None:
        response = client().get("/v1/statutes/bns/114")
        assert response.json()["matches"][0]["ipc"] == "319"

    def test_a_merged_section_returns_every_source(self) -> None:
        """BNS 70(2) came from two IPC sections.

        Returning one would drop a provision from an archived report.
        """
        response = client().get("/v1/statutes/bns/70(2)")
        assert {m["ipc"] for m in response.json()["matches"]} == {"376DA", "376DB"}

    def test_a_changed_section_is_flagged_for_legal_check(self) -> None:
        """Renumbering and rewording are different problems."""
        body = client().get("/v1/statutes/ipc/320").json()
        assert body["matches"][0]["needs_legal_check"]

    def test_a_repealed_section_says_so(self) -> None:
        body = client().get("/v1/statutes/ipc/377").json()
        assert body["matches"][0]["repealed"]
        assert body["matches"][0]["bns"] is None

    def test_an_unknown_section_returns_no_match_rather_than_a_guess(self) -> None:
        body = client().get("/v1/statutes/ipc/420").json()
        assert body["matches"] == []

    def test_the_response_never_claims_legal_review(self) -> None:
        """The caveat travels with the number, not in a file nobody reads."""
        for path in ("/v1/statutes/ipc/319", "/v1/statutes/bns/116"):
            assert client().get(path).json()["legally_reviewed"] is False

    def test_an_unknown_numbering_is_refused(self) -> None:
        response = client().get("/v1/statutes/epc/319")
        assert response.status_code == 400
        assert "ipc" in response.json()["detail"]
