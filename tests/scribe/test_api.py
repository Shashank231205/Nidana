"""The Scribe HTTP boundary.

The model is scripted; the groundedness gate runs for real. A statement the
transcript does not support is dropped by the actual builder, not a stub.

Skipped where FastAPI is not installed, since it is an optional extra.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")
from fastapi.testclient import TestClient  # noqa: E402

from services.scribe.api import app as api  # noqa: E402
from services.scribe.clinical.actions import NoteCheckAction  # noqa: E402
from spine.inference.adapter import (  # noqa: E402
    Completion,
    InferenceProvider,
    ModelSpec,
    Transport,
)
from spine.inference.prompts import load_all  # noqa: E402
from spine.rules.predicate_loader import load_predicates  # noqa: E402
from spine.rules.rule_loader import load_rule_sets, rules_dir  # noqa: E402
from spine.schemas.record import Record, SubjectType  # noqa: E402
from spine.schemas.transcript import (  # noqa: E402
    Speaker,
    Transcript,
    TranscriptSegment,
)

CONSULTATION = Transcript(
    segments=(
        TranscriptSegment(
            text="Since when is the pain there?",
            speaker=Speaker.CLINICIAN,
            audio_start_ms=0,
            audio_end_ms=2000,
        ),
        TranscriptSegment(
            text="do din se, chest mein",
            speaker=Speaker.PATIENT,
            audio_start_ms=2100,
            audio_end_ms=4500,
            language="hi-en",
        ),
    )
)

GROUNDED = (
    '{"statements":[{"section":"subjective","text":"Chest pain two days",'
    '"source_span":"do din se, chest mein"}]}'
)

FABRICATED = (
    '{"statements":[{"section":"assessment","text":"Patient appeared anxious",'
    '"source_span":"seemed worried"}]}'
)


class ScriptedProvider(InferenceProvider):
    """Answers in a fixed order, cycling the last response if it runs out.

    The model is scripted; the groundedness gate runs for real.
    """

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses) or ['{"statements":[]}']
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
    predicates = load_predicates()
    return api.Dependencies(
        provider=ScriptedProvider(*responses),
        prompts=load_all("scribe"),
        predicates=predicates,
        rule_sets=load_rule_sets(
            rules_dir("scribe", "completeness"), NoteCheckAction
        ),
    )


def client_with(*responses: str) -> TestClient:
    """A client whose startup has already run.

    The context manager is deliberately not entered: entering it fires the real
    startup hook, which reaches for a model this test does not want.
    """
    api._dependencies = dependencies(*responses)
    api._encounters.clear()
    return TestClient(api.app)


def empty_record() -> dict[str, object]:
    return Record(
        subject_type=SubjectType.ENCOUNTER, subject_id=uuid4()
    ).model_dump(mode="json")


def draft_payload() -> dict[str, object]:
    return {
        "transcript": CONSULTATION.model_dump(mode="json"),
        "record": empty_record(),
    }


def new_encounter(test_client: TestClient) -> str:
    response = test_client.post("/v1/encounters")
    assert response.status_code == 201
    return str(response.json()["encounter_id"])


class TestHealth:
    def test_reports_healthy_once_started(self) -> None:
        assert client_with().get("/health").json()["status"] == "healthy"

    def test_degraded_before_startup(self) -> None:
        api._dependencies = None
        try:
            assert TestClient(api.app).get("/health").json()["status"] == "degraded"
        finally:
            api._dependencies = dependencies()


class TestDrafting:
    def test_a_grounded_statement_reaches_the_note(self) -> None:
        test_client = client_with(GROUNDED)
        encounter_id = new_encounter(test_client)
        body = test_client.post(
            f"/v1/encounters/{encounter_id}/draft", json=draft_payload()
        ).json()
        assert len(body["note"]["statements"]) == 1
        assert body["fabrication_count"] == 0

    def test_a_fabricated_statement_is_dropped_and_counted(self) -> None:
        """The gate holding is reported, not hidden."""
        test_client = client_with(FABRICATED)
        encounter_id = new_encounter(test_client)
        body = test_client.post(
            f"/v1/encounters/{encounter_id}/draft", json=draft_payload()
        ).json()
        assert body["note"]["statements"] == []
        assert body["fabrication_count"] == 1
        assert body["dropped"]

    def test_the_drop_reason_says_quote_rather_than_summarise(self) -> None:
        test_client = client_with(FABRICATED)
        encounter_id = new_encounter(test_client)
        body = test_client.post(
            f"/v1/encounters/{encounter_id}/draft", json=draft_payload()
        ).json()
        assert "not summarise it" in body["dropped"][0]

    def test_an_unknown_encounter_names_the_remedy(self) -> None:
        response = client_with().post(
            f"/v1/encounters/{uuid4()}/draft", json=draft_payload()
        )
        assert response.status_code == 404
        assert "POST /v1/encounters" in response.json()["detail"]


class TestSigning:
    def test_an_undrafted_encounter_cannot_be_signed(self) -> None:
        test_client = client_with()
        encounter_id = new_encounter(test_client)
        response = test_client.post(
            f"/v1/encounters/{encounter_id}/sign", json={"signed_by": "Dr X"}
        )
        assert response.status_code == 409
        assert "draft" in response.json()["detail"]

    def test_signing_names_the_signer(self) -> None:
        test_client = client_with(GROUNDED)
        encounter_id = new_encounter(test_client)
        test_client.post(f"/v1/encounters/{encounter_id}/draft", json=draft_payload())
        body = test_client.post(
            f"/v1/encounters/{encounter_id}/sign", json={"signed_by": "Dr X"}
        ).json()
        assert body["note"]["status"] == "signed"
        assert body["note"]["signed_by"] == "Dr X"

    def test_an_anonymous_signature_is_rejected(self) -> None:
        test_client = client_with(GROUNDED)
        encounter_id = new_encounter(test_client)
        test_client.post(f"/v1/encounters/{encounter_id}/draft", json=draft_payload())
        response = test_client.post(
            f"/v1/encounters/{encounter_id}/sign", json={"signed_by": ""}
        )
        assert response.status_code == 422

    def test_a_signed_note_is_not_redrafted(self) -> None:
        """A correction to a signed record is an amendment, not a rewrite."""
        test_client = client_with(GROUNDED, GROUNDED)
        encounter_id = new_encounter(test_client)
        test_client.post(f"/v1/encounters/{encounter_id}/draft", json=draft_payload())
        test_client.post(
            f"/v1/encounters/{encounter_id}/sign", json={"signed_by": "Dr X"}
        )
        response = test_client.post(
            f"/v1/encounters/{encounter_id}/draft", json=draft_payload()
        )
        assert response.status_code == 409
        assert "amendment" in response.json()["detail"]


class TestEncounterState:
    def test_a_new_encounter_is_a_draft_with_nothing_in_it(self) -> None:
        test_client = client_with()
        encounter_id = new_encounter(test_client)
        body = test_client.get(f"/v1/encounters/{encounter_id}").json()
        assert body["status"] == "draft"
        assert body["statement_count"] == 0

    def test_state_reflects_the_draft(self) -> None:
        test_client = client_with(GROUNDED)
        encounter_id = new_encounter(test_client)
        test_client.post(f"/v1/encounters/{encounter_id}/draft", json=draft_payload())
        body = test_client.get(f"/v1/encounters/{encounter_id}").json()
        assert body["statement_count"] == 1

    def test_an_unknown_encounter_is_a_404(self) -> None:
        assert client_with().get(f"/v1/encounters/{uuid4()}").status_code == 404
