"""The HTTP boundary. No clinical reasoning happens here.

Every endpoint delegates to the session orchestrator and serialises what comes
back. The one thing this layer decides is the shape of a response, and it does
that by reading `TurnShape` rather than inspecting the result.

Startup is where a misconfigured deployment fails. Rules load and resolve,
prompts load and their temperatures are checked, the inference provider is
reached, and the release gate refuses unverified clinical criteria in
production. A deployment that cannot triage safely does not start serving.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from services.consult.clinical.actions import RedFlagAction
from services.consult.session import (
    Dependencies,
    Session,
    SessionStatus,
    TurnResult,
    TurnShape,
    complete,
    submit_turn,
)
from spine.inference.config import InferenceConfig, build_provider, model_spec
from spine.inference.prompts import assert_clinical_prompts_are_deterministic, load_all
from spine.rules.predicate_loader import (
    check_enum_operands,
    load_predicates,
    resolve_against_registries,
)
from spine.rules.registry_loader import load_all as load_registries
from spine.rules.rule_loader import (
    load_rule_sets,
    require_verified,
    resolve_atoms,
    rules_dir,
)

CONVERSATIONAL_AGENTS: Final[frozenset[str]] = frozenset({"intake_agent"})
"""Agents whose job is phrasing rather than reasoning.

Only these may run above temperature 0. Named explicitly so adding an agent
forces the decision rather than defaulting it.
"""

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load and validate everything before the first request, or refuse to serve.

    Rules load and resolve, prompts load and their temperatures are checked, the
    inference provider is reached, and the release gate refuses unverified
    clinical criteria in production. A deployment that cannot triage safely does
    not start serving.
    """
    # Module-level state is how startup publishes what it loaded. Request
    # handlers read it; nothing else writes it.
    global _dependencies  # noqa: PLW0603
    _dependencies = build_dependencies()
    yield


app = FastAPI(
    title="Nidana Consult",
    description="Conversational triage and routing. Triages; does not diagnose.",
    version="0.1.0",
    lifespan=lifespan,
)

_sessions: dict[UUID, Session] = {}
_dependencies: Dependencies | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _allow_unverified() -> bool:
    return os.environ.get("NIDANA_ALLOW_UNVERIFIED_RULES", "true").strip().lower() == "true"


def build_dependencies() -> Dependencies:
    """Load and validate everything, or refuse to start.

    Order matters: rules are checked before the model is reached, because a
    deployment with a dead rule is unsafe whether or not inference works.
    """
    registries = load_registries()
    predicates = load_predicates()
    resolve_against_registries(predicates, registries)
    check_enum_operands(predicates, registries)

    rule_sets = load_rule_sets(rules_dir("consult", "red_flags"), RedFlagAction)
    resolve_atoms(rule_sets, predicates)
    require_verified(rule_sets, allow_unverified=_allow_unverified())

    prompts = load_all("consult")
    assert_clinical_prompts_are_deterministic(prompts, CONVERSATIONAL_AGENTS)

    config = InferenceConfig.from_environment()
    provider = build_provider(config)
    model_spec(config)

    return Dependencies(
        provider=provider,
        prompts=prompts,
        registries=registries,
        predicates=predicates,
        rule_sets=rule_sets,
    )




def _deps() -> Dependencies:
    if _dependencies is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; rules and prompts are not loaded yet",
        )
    return _dependencies


def _session(session_id: UUID) -> Session:
    found = _sessions.get(session_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no session {session_id}; create one with POST /v1/sessions",
        )
    return found


class TurnRequest(BaseModel):
    utterance: str = Field(min_length=1)


class TurnResponse(BaseModel):
    """One of three shapes. The client renders on `shape`, never on a status."""

    shape: TurnShape
    session_id: UUID
    turn_index: int
    question: str | None = None
    emergency: dict[str, object] | None = None
    triage: dict[str, object] | None = None


class SessionResponse(BaseModel):
    session_id: UUID
    status: SessionStatus
    turn_index: int
    complaint_family: str | None
    finding_count: int


def _to_response(result: TurnResult) -> TurnResponse:
    return TurnResponse(
        shape=result.shape,
        session_id=result.session_id,
        turn_index=result.turn_index,
        question=result.question,
        emergency=result.emergency.model_dump(mode="json") if result.emergency else None,
        triage=result.triage.model_dump(mode="json") if result.triage else None,
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Whether this instance can serve.

    Reports degraded rather than healthy when dependencies did not load, so a
    container that started but cannot triage fails its healthcheck.
    """
    ready = _dependencies is not None
    return {
        "status": "healthy" if ready else "degraded",
        "rules_loaded": ready,
        "active_sessions": len(_sessions),
    }


@app.post("/v1/sessions", status_code=status.HTTP_201_CREATED)
def create_session() -> SessionResponse:
    _deps()
    session = Session()
    _sessions[session.id] = session
    return SessionResponse(
        session_id=session.id,
        status=session.status,
        turn_index=0,
        complaint_family=None,
        finding_count=0,
    )


@app.post("/v1/sessions/{session_id}/turns")
def submit(session_id: UUID, request: TurnRequest) -> TurnResponse:
    session = _session(session_id)
    if session.status is not SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"session is {session.status.value} and takes no further turns; "
                f"read its outcome at GET /v1/sessions/{session_id}"
            ),
        )
    return _to_response(submit_turn(session, _deps(), request.utterance, _now()))


@app.post("/v1/sessions/{session_id}/complete")
def force_complete(session_id: UUID) -> TurnResponse:
    """Triage the record as it stands, before sufficiency is met.

    The triage agent bands up on an incomplete history, so this is safe to
    offer rather than a shortcut around the questions.
    """
    session = _session(session_id)
    if session.status is not SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is already {session.status.value}",
        )
    return _to_response(complete(session, _deps(), _now()))


@app.get("/v1/sessions/{session_id}")
def read_session(session_id: UUID) -> SessionResponse:
    session = _session(session_id)
    family = session.record.consult.complaint_family
    return SessionResponse(
        session_id=session.id,
        status=session.status,
        turn_index=session.turn_index,
        complaint_family=family.value if family else None,
        finding_count=len(session.record.findings),
    )


@app.get("/v1/sessions/{session_id}/audit")
def read_audit(session_id: UUID) -> dict[str, object]:
    """The decision trail.

    The M5 gate requires every decision in a session to be reconstructable from
    the audit log alone, so the chain is exposed rather than kept internal.
    """
    session = _session(session_id)
    return {
        "session_id": str(session.id),
        "entries": [entry.model_dump(mode="json") for entry in session.audit],
    }
