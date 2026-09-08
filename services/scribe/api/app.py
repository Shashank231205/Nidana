"""The Scribe HTTP boundary. No clinical reasoning happens here.

A note is built across a consultation rather than in one call, so this service
holds encounters: create one, post the transcript, read the draft, sign it.

The invariant this layer must not route around is that the note agent proposes
and the builder disposes. Nothing a model writes reaches a note without its
span being found character-for-character in what was recorded, and the count of
what was dropped is reported rather than hidden — a non-zero `fabrication_count`
means the model tried and the gate held.

Signing is refused while a blocking omission is outstanding. That check lives in
the ClinicalNote validator, not here; this layer turns its refusal into a 409.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from services.scribe.agents.note_agent import TranscriptTooLongError, draft_note
from services.scribe.clinical.actions import NoteCheckAction
from services.scribe.clinical.completeness import check
from spine.inference.adapter import InferenceProvider
from spine.inference.config import InferenceConfig, build_provider, model_spec
from spine.inference.prompts import (
    Prompt,
    assert_clinical_prompts_are_deterministic,
    load_all,
)
from spine.rules.predicate_loader import load_predicates, predicates_dir
from spine.rules.rule_loader import (
    load_rule_sets,
    require_verified,
    resolve_atoms,
    rules_dir,
)
from spine.schemas.note import ClinicalNote, NoteStatus
from spine.schemas.predicate import Predicate
from spine.schemas.record import Record
from spine.schemas.rule import RuleSet
from spine.schemas.transcript import Transcript

CONVERSATIONAL_AGENTS: Final[frozenset[str]] = frozenset()
"""Scribe has no conversational agent.

Every prompt here reasons over a transcript, so every one of them runs at
temperature 0. Named explicitly so adding a conversational agent forces the
decision rather than defaulting it.
"""

app = FastAPI(
    title="Nidana Scribe",
    description="Ambient consultation notes. Grounded in the transcript, or dropped.",
    version="0.1.0",
)


@dataclass(frozen=True)
class Dependencies:
    provider: InferenceProvider
    prompts: dict[str, Prompt]
    predicates: dict[str, Predicate]
    rule_sets: tuple[RuleSet[NoteCheckAction], ...]


@dataclass
class Encounter:
    """One consultation being documented."""

    id: UUID = field(default_factory=uuid4)
    note: ClinicalNote | None = None
    fabrication_count: int = 0
    dropped: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_encounters: dict[UUID, Encounter] = {}
_dependencies: Dependencies | None = None


def _allow_unverified() -> bool:
    return os.environ.get("NIDANA_ALLOW_UNVERIFIED_RULES", "true").strip().lower() == "true"


def build_dependencies() -> Dependencies:
    """Load and validate everything, or refuse to start.

    Order matters: rules are checked before the model is reached, because a
    deployment with a dead completeness rule is unsafe whether or not inference
    works.
    """
    # Scribe's own predicates. The default is Consult's, and loading those here
    # leaves every completeness rule referencing an atom that is not present.
    predicates = load_predicates(predicates_dir("scribe"))

    rule_sets = load_rule_sets(rules_dir("scribe", "completeness"), NoteCheckAction)
    resolve_atoms(rule_sets, predicates)
    require_verified(rule_sets, allow_unverified=_allow_unverified())

    prompts = load_all("scribe")
    assert_clinical_prompts_are_deterministic(prompts, CONVERSATIONAL_AGENTS)

    config = InferenceConfig.from_environment()
    provider = build_provider(config)
    model_spec(config)

    return Dependencies(
        provider=provider,
        prompts=prompts,
        predicates=predicates,
        rule_sets=rule_sets,
    )


@app.on_event("startup")
def _startup() -> None:
    # Module-level state is how the startup hook publishes what it loaded.
    global _dependencies  # noqa: PLW0603
    _dependencies = build_dependencies()


def _deps() -> Dependencies:
    if _dependencies is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; rules and prompts are not loaded yet",
        )
    return _dependencies


def _encounter(encounter_id: UUID) -> Encounter:
    found = _encounters.get(encounter_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no encounter {encounter_id}; create one with POST /v1/encounters",
        )
    return found


class EncounterResponse(BaseModel):
    encounter_id: UUID
    status: NoteStatus
    statement_count: int
    omission_count: int
    blocking_omission_count: int
    fabrication_count: int


class DraftRequest(BaseModel):
    transcript: Transcript
    record: Record


class SignRequest(BaseModel):
    signed_by: str = Field(min_length=1)


class NoteResponse(BaseModel):
    """The note, plus what the groundedness gate dropped.

    `fabrication_count` is reported rather than hidden. A non-zero value means
    the model claimed something the transcript did not support and the gate
    caught it, which is information a clinician reviewing the note should have.
    """

    encounter_id: UUID
    note: ClinicalNote
    fabrication_count: int
    dropped: tuple[str, ...]


def _summarise(encounter: Encounter) -> EncounterResponse:
    note = encounter.note
    omissions = note.omissions if note else ()
    return EncounterResponse(
        encounter_id=encounter.id,
        status=note.status if note else NoteStatus.DRAFT,
        statement_count=len(note.statements) if note else 0,
        omission_count=len(omissions),
        blocking_omission_count=sum(
            1 for omission in omissions if omission.blocking and not omission.dismissed_reason
        ),
        fabrication_count=encounter.fabrication_count,
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Whether this instance can serve."""
    ready = _dependencies is not None
    return {
        "status": "healthy" if ready else "degraded",
        "rules_loaded": ready,
        "active_encounters": len(_encounters),
    }


@app.post("/v1/encounters", status_code=status.HTTP_201_CREATED)
def create_encounter() -> EncounterResponse:
    _deps()
    encounter = Encounter()
    _encounters[encounter.id] = encounter
    return _summarise(encounter)


@app.post("/v1/encounters/{encounter_id}/draft")
def draft(encounter_id: UUID, request: DraftRequest) -> NoteResponse:
    """Draft the note from the transcript.

    Re-drafting replaces the previous draft. A signed note is not redrafted:
    corrections to a signed record are amendments, which are new rows rather
    than a rewrite of what was signed.
    """
    encounter = _encounter(encounter_id)
    dependencies = _deps()

    if encounter.note is not None and encounter.note.status is NoteStatus.SIGNED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"encounter {encounter_id} is signed and is not redrafted; a correction "
                f"to a signed note is an amendment referencing it"
            ),
        )

    prompt = dependencies.prompts.get("note_agent")
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="note_agent prompt is not loaded; check services/scribe/prompts/",
        )

    try:
        result = draft_note(
            dependencies.provider, prompt, request.transcript, str(encounter_id)
        )
    except TranscriptTooLongError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error

    omissions = check(request.record, dependencies.rule_sets, dependencies.predicates)
    note = ClinicalNote(
        encounter_id=encounter_id,
        statements=result.statements,
        omissions=omissions,
    )
    encounter.note = note
    encounter.fabrication_count = result.fabrication_count
    encounter.dropped = tuple(dropped.reason for dropped in result.dropped)

    return NoteResponse(
        encounter_id=encounter_id,
        note=note,
        fabrication_count=encounter.fabrication_count,
        dropped=encounter.dropped,
    )


@app.post("/v1/encounters/{encounter_id}/sign")
def sign(encounter_id: UUID, request: SignRequest) -> NoteResponse:
    """Sign the note.

    The refusal to sign over an outstanding blocking omission lives in the
    ClinicalNote validator. This handler turns that refusal into a 409 carrying
    the validator's message, which names the omission rather than saying the
    note is invalid.
    """
    encounter = _encounter(encounter_id)
    if encounter.note is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"encounter {encounter_id} has no draft to sign; draft it with "
                f"POST /v1/encounters/{encounter_id}/draft"
            ),
        )

    try:
        signed = ClinicalNote(
            encounter_id=encounter.note.encounter_id,
            status=NoteStatus.SIGNED,
            statements=encounter.note.statements,
            omissions=encounter.note.omissions,
            signed_by=request.signed_by,
            consult_session_id=encounter.note.consult_session_id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    encounter.note = signed
    return NoteResponse(
        encounter_id=encounter_id,
        note=signed,
        fabrication_count=encounter.fabrication_count,
        dropped=encounter.dropped,
    )


@app.get("/v1/encounters/{encounter_id}")
def read_encounter(encounter_id: UUID) -> EncounterResponse:
    return _summarise(_encounter(encounter_id))
