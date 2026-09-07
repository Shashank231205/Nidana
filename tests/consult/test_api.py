"""The HTTP boundary.

The model is scripted; the clinical layer runs for real. A turn that fires a
red flag ends the session through the actual rule engine, not a stub.

Skipped where FastAPI is not installed, since it is an optional extra.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="API extra not installed")
from fastapi.testclient import TestClient  # noqa: E402

from services.consult.api import app as api  # noqa: E402
from services.consult.clinical.actions import RedFlagAction  # noqa: E402
from services.consult.session import Dependencies  # noqa: E402
from spine.audit.chain import verify  # noqa: E402
from spine.audit.events import AuditEvent  # noqa: E402
from spine.inference.adapter import (  # noqa: E402
    Completion,
    InferenceProvider,
    ModelSpec,
    Transport,
)
from spine.inference.config import UnsafeConfigurationError  # noqa: E402
from spine.inference.prompts import load_all  # noqa: E402
from spine.rules.predicate_loader import load_predicates  # noqa: E402
from spine.rules.registry_loader import load_all as load_registries  # noqa: E402
from spine.rules.rule_loader import (  # noqa: E402
    UnverifiedRulesError,
    load_rule_sets,
    rules_dir,
)

STRUCTURED_CHEST_PAIN = (
    '{"findings":[{"field":"radiation","value":"jaw",'
    '"source_span":"jabde mein ja raha hai","confidence":"high","negated":false}]}'
)
NEXT_QUESTION = '{"utterance":"Since when?","language":"en","complaint_family":"chest_pain"}'
NOTHING_EXTRACTED = '{"findings":[]}'


class ScriptedProvider(InferenceProvider):
    """Answers in a fixed order, cycling the last response if it runs out."""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0
        self.seen: list[tuple[str, str]] = []

    @property
    def transport(self) -> Transport:
        return Transport.LOCAL

    def is_available(self) -> bool:
        return True

    def complete(
        self, *, prompt: str, system: str, spec: ModelSpec, prompt_version: str
    ) -> Completion:
        self.calls += 1
        self.seen.append((prompt, system))
        text = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return Completion(
            text=text,
            model_version=spec.name,
            transport=Transport.LOCAL,
            prompt_version=prompt_version,
        )


def dependencies_with(provider: InferenceProvider) -> Dependencies:
    return Dependencies(
        provider=provider,
        prompts=load_all("consult"),
        registries=load_registries(),
        predicates=load_predicates(),
        rule_sets=load_rule_sets(rules_dir("consult", "red_flags"), RedFlagAction),
    )


def client_with(
    monkeypatch: pytest.MonkeyPatch, provider: InferenceProvider
) -> TestClient:
    """A client with dependencies injected and the startup hook bypassed.

    The hook reads NIDANA_MODEL_PRIMARY and reaches for a provider. These tests
    supply both directly, so running it would only assert that the environment
    happens to name a model — which is a deployment concern, covered separately
    in TestStartupChecks.
    """
    monkeypatch.setattr(api, "_dependencies", dependencies_with(provider))
    monkeypatch.setattr(api, "_sessions", {})
    return TestClient(api.app)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A client whose model is scripted and whose clinical layer is real."""
    return client_with(monkeypatch, ScriptedProvider(NEXT_QUESTION))


class TestHealth:
    def test_health_reports_healthy_when_rules_are_loaded(self, client: TestClient) -> None:
        body = client.get("/health").json()
        assert body["status"] == "healthy"
        assert body["rules_loaded"] is True

    def test_health_reports_degraded_before_dependencies_load(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A container that started but cannot triage must fail its healthcheck."""
        monkeypatch.setattr(api, "_dependencies", None)
        body = api.health()
        assert body["status"] == "degraded"
        assert body["rules_loaded"] is False

    def test_endpoints_refuse_service_before_dependencies_load(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(api, "_dependencies", None)
        with pytest.raises(fastapi.HTTPException) as caught:
            api._deps()
        assert caught.value.status_code == 503


class TestSessionLifecycle:
    def test_creating_a_session_returns_an_id(self, client: TestClient) -> None:
        response = client.post("/v1/sessions")
        assert response.status_code == 201
        assert response.json()["status"] == "active"

    def test_an_unknown_session_is_a_404_naming_the_fix(self, client: TestClient) -> None:
        response = client.get("/v1/sessions/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
        assert "POST /v1/sessions" in response.json()["detail"]

    def test_a_turn_returns_the_next_question_shape(self, client: TestClient) -> None:
        session_id = client.post("/v1/sessions").json()["session_id"]
        body = client.post(
            f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"}
        ).json()
        assert body["shape"] == "next_question"
        assert body["question"] == "Since when?"

    def test_an_empty_utterance_is_rejected(self, client: TestClient) -> None:
        session_id = client.post("/v1/sessions").json()["session_id"]
        response = client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": ""})
        assert response.status_code == 422

    def test_the_session_reports_its_findings(self, client: TestClient) -> None:
        session_id = client.post("/v1/sessions").json()["session_id"]
        client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"})
        body = client.get(f"/v1/sessions/{session_id}").json()
        assert body["turn_index"] == 1


class TestRedFlagTermination:
    """The rule engine runs for real. A firing rule ends the session."""

    def test_a_firing_rule_returns_the_emergency_shape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = client_with(
            monkeypatch,
            ScriptedProvider(NEXT_QUESTION, STRUCTURED_CHEST_PAIN, NEXT_QUESTION),
        )
        session_id = client.post("/v1/sessions").json()["session_id"]
        client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"})
        body = client.post(
            f"/v1/sessions/{session_id}/turns",
            json={"utterance": "jabde mein ja raha hai"},
        ).json()
        assert body["shape"] == "terminal_emergency"
        assert "RF_ACS_001" in body["emergency"]["rule_ids"]

    def test_a_terminated_session_refuses_further_turns(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = client_with(
            monkeypatch,
            ScriptedProvider(NEXT_QUESTION, STRUCTURED_CHEST_PAIN, NEXT_QUESTION),
        )
        session_id = client.post("/v1/sessions").json()["session_id"]
        client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"})
        client.post(
            f"/v1/sessions/{session_id}/turns",
            json={"utterance": "jabde mein ja raha hai"},
        )
        response = client.post(
            f"/v1/sessions/{session_id}/turns", json={"utterance": "anything"}
        )
        assert response.status_code == 409
        assert "terminated_emergency" in response.json()["detail"]


class TestAudit:
    def test_the_audit_trail_is_exposed(self, client: TestClient) -> None:
        session_id = client.post("/v1/sessions").json()["session_id"]
        client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"})
        entries = client.get(f"/v1/sessions/{session_id}/audit").json()["entries"]
        assert entries
        assert entries[0]["sequence"] == 0

    def test_the_chain_verifies(self, client: TestClient) -> None:
        session_id = client.post("/v1/sessions").json()["session_id"]
        client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"})
        raw = client.get(f"/v1/sessions/{session_id}/audit").json()["entries"]
        verify(tuple(AuditEvent.model_validate(entry) for entry in raw))

    def test_every_model_call_records_its_prompt_version(self, client: TestClient) -> None:
        session_id = client.post("/v1/sessions").json()["session_id"]
        client.post(f"/v1/sessions/{session_id}/turns", json={"utterance": "chest pain"})
        entries = client.get(f"/v1/sessions/{session_id}/audit").json()["entries"]
        called = [e for e in entries if e["event_type"] == "model_called"]
        assert called
        assert all(entry["prompt_version"] for entry in called)


class TestStartupChecks:
    """A deployment that cannot triage safely does not start serving."""

    def test_build_dependencies_loads_everything(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NIDANA_ALLOW_UNVERIFIED_RULES", "true")
        monkeypatch.setenv("NIDANA_MODEL_PRIMARY", "qwen2.5:7b-instruct-q4_K_M")
        dependencies = api.build_dependencies()
        assert len(dependencies.registries) == 10
        assert dependencies.rule_sets

    def test_release_mode_refuses_unverified_clinical_rules(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NIDANA_ALLOW_UNVERIFIED_RULES", "false")
        monkeypatch.setenv("NIDANA_MODEL_PRIMARY", "qwen2.5:7b-instruct-q4_K_M")
        with pytest.raises(UnverifiedRulesError, match="cannot ship"):
            api.build_dependencies()

    def test_production_with_hosted_transport_refuses_to_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("NIDANA_ALLOW_UNVERIFIED_RULES", "true")
        monkeypatch.setenv("NIDANA_MODE", "production")
        monkeypatch.setenv("NIDANA_INFERENCE_TRANSPORT", "hosted")
        with pytest.raises(UnsafeConfigurationError, match="off this machine"):
            api.build_dependencies()
