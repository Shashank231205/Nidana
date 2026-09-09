"""The Forensics HTTP boundary. No clinical reasoning happens here.

This service is evidentially isolated: it imports nothing from another service
and reads no shared record. Contamination from another source is an attack
surface in cross-examination, and the boundary is enforced in CI rather than
trusted.

Two things this layer does that the others do not.

Every read is logged. GET is not a safe method here — a record viewed by
someone with no role in the case is a chain-of-custody problem whether or not
they changed anything, so reading appends a VIEWED entry to the chain.

The chain is verified before a record is served, not after. Serving a report
whose custody chain is broken, and mentioning the break in a field the reader
may not look at, is worse than refusing to serve it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Final
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from services.forensics.agents.structuring_agent import (
    DictationTooLongError,
    structure,
)
from services.forensics.clinical.custody import (
    CustodyAction,
    CustodyChainError,
    record,
    verify_chain,
    was_amended_after_finalisation,
)
from services.forensics.clinical.statutes import Correspondence, statute_map
from spine.audit.events import AuditEvent
from spine.inference.adapter import InferenceProvider
from spine.inference.config import InferenceConfig, build_provider, model_spec
from spine.inference.prompts import (
    Prompt,
    assert_clinical_prompts_are_deterministic,
    load_all,
)
from spine.schemas.forensic import ExaminationStatus, MedicoLegalReport

CONVERSATIONAL_AGENTS: Final[frozenset[str]] = frozenset()
"""Forensics has no conversational agent.

Structuring a dictation is a transcription task, so every prompt here runs at
temperature 0. Named explicitly so adding one forces the decision.
"""

_provider: InferenceProvider | None = None
_prompts: dict[str, Prompt] = {}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load the prompts and reach the provider before the first request."""
    # Module-level state is how startup publishes what it loaded.
    global _provider, _prompts  # noqa: PLW0603
    _prompts = load_all("forensics")
    assert_clinical_prompts_are_deterministic(_prompts, CONVERSATIONAL_AGENTS)
    config = InferenceConfig.from_environment()
    _provider = build_provider(config)
    model_spec(config)
    yield


app = FastAPI(
    title="Nidana Forensics",
    description="Medico-legal documentation. Tamper-evident and evidentially isolated.",
    version="0.1.0",
    lifespan=lifespan,
)


@dataclass
class Examination:
    """One medico-legal examination and its custody chain."""

    report: MedicoLegalReport
    chain: tuple[AuditEvent, ...] = field(default_factory=tuple)


_examinations: dict[UUID, Examination] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append(
    examination: Examination,
    action: CustodyAction,
    actor: str,
    reason: str | None = None,
) -> None:
    previous = examination.chain[-1] if examination.chain else None
    entry = record(
        previous,
        examination_id=examination.report.examination_id,
        action=action,
        actor=actor,
        occurred_at=_now(),
        reason=reason,
    )
    examination.chain = (*examination.chain, entry)


def _examination(examination_id: UUID) -> Examination:
    found = _examinations.get(examination_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"no examination {examination_id}; create one with POST /v1/examinations"
            ),
        )
    return found


def _verified(examination: Examination) -> Examination:
    """Refuse to serve a record whose chain does not hold."""
    try:
        verify_chain(examination.chain)
    except CustodyChainError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"the custody chain for this examination does not verify: {error}. "
                f"The record is not served; preserve the store and investigate"
            ),
        ) from error
    return examination


class CreateRequest(BaseModel):
    report: MedicoLegalReport
    actor: str = Field(min_length=1)


class AccessRequest(BaseModel):
    """Who is reading, and why.

    The actor is required rather than inferred, because an unattributed access
    in a custody log is the same as no log.
    """

    actor: str = Field(min_length=1)


class FinaliseRequest(BaseModel):
    """Who is closing the record, and their signature.

    A finalised report carries the examiner's signature: without it the chain
    cannot be shown to have been closed by the person who examined.
    """

    actor: str = Field(min_length=1)
    signature: str = Field(min_length=1)


class AmendRequest(BaseModel):
    report: MedicoLegalReport
    actor: str = Field(min_length=1)
    reason: str = Field(
        min_length=1,
        description="Why the record is being amended. Required; a correction with no "
        "stated reason is indistinguishable from tampering when read back years later.",
    )


class ReportResponse(BaseModel):
    report: MedicoLegalReport
    chain_length: int
    chain_verified: bool
    amended_after_finalisation: bool


class ChainResponse(BaseModel):
    examination_id: UUID
    verified: bool
    entries: tuple[dict[str, object], ...]


def _to_response(examination: Examination) -> ReportResponse:
    return ReportResponse(
        report=examination.report,
        chain_length=len(examination.chain),
        chain_verified=True,
        amended_after_finalisation=was_amended_after_finalisation(examination.chain),
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Whether this instance can serve."""
    return {"status": "healthy", "examinations": len(_examinations)}


@app.post("/v1/examinations", status_code=status.HTTP_201_CREATED)
def create_examination(request: CreateRequest) -> ReportResponse:
    examination = Examination(report=request.report)
    _append(examination, CustodyAction.CREATED, request.actor)
    _examinations[request.report.examination_id] = examination
    return _to_response(examination)


@app.post("/v1/examinations/{examination_id}/access")
def read_report(examination_id: UUID, request: AccessRequest) -> ReportResponse:
    """Read the report, logging the access.

    A POST rather than a GET because reading appends to the custody chain. A GET
    that mutates would be wrong, and a read that does not log would defeat the
    purpose of the chain.
    """
    examination = _verified(_examination(examination_id))
    _append(examination, CustodyAction.VIEWED, request.actor)
    return _to_response(examination)


@app.post("/v1/examinations/{examination_id}/amend")
def amend(examination_id: UUID, request: AmendRequest) -> ReportResponse:
    """Amend the record, with a stated reason.

    The previous version is not overwritten in the chain: the amendment is a new
    entry referencing what came before, so the history of the record remains
    readable years later.
    """
    examination = _verified(_examination(examination_id))
    if request.report.examination_id != examination_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"the submitted report is for examination "
                f"{request.report.examination_id}, not {examination_id}"
            ),
        )
    _append(examination, CustodyAction.AMENDED, request.actor, reason=request.reason)
    examination.report = request.report
    return _to_response(examination)


@app.post("/v1/examinations/{examination_id}/finalise")
def finalise(examination_id: UUID, request: FinaliseRequest) -> ReportResponse:
    """Finalise the examination.

    Finalisation does not close the chain. An amendment after this point is
    permitted and recorded as such, because a court reads "amended after
    finalisation" differently from "amended", and hiding it would be the
    tampering the chain exists to make visible.
    """
    examination = _verified(_examination(examination_id))
    # Revalidated rather than model_copy'd straight in: model_copy bypasses the
    # validators, and the two that matter here are the ones requiring a
    # signature and a finalisation time on a closed report.
    finalised = MedicoLegalReport.model_validate(
        examination.report.model_copy(
            update={
                "status": ExaminationStatus.FINALISED,
                "signature": request.signature,
                "finalised_at": _now(),
            }
        ).model_dump()
    )
    examination.report = finalised
    _append(examination, CustodyAction.FINALISED, request.actor)
    return _to_response(examination)


@app.post("/v1/examinations/{examination_id}/chain")
def read_chain(examination_id: UUID, request: AccessRequest) -> ChainResponse:
    """The custody chain itself.

    Reading the chain is also an access and is logged as one.
    """
    examination = _verified(_examination(examination_id))
    _append(examination, CustodyAction.VIEWED, request.actor)
    return ChainResponse(
        examination_id=examination_id,
        verified=True,
        entries=tuple(entry.model_dump(mode="json") for entry in examination.chain),
    )


class StructureRequest(BaseModel):
    """An examiner's dictation, and who dictated it."""

    dictation: str = Field(min_length=1)
    actor: str = Field(min_length=1)


class StructureResponse(BaseModel):
    """What the structuring agent recorded, and what the gate refused.

    `dropped` is returned rather than logged. An injury the gate refused is one
    the examiner must record by hand, and a report that silently lost one is
    the incompleteness this service exists to make visible.
    """

    report: MedicoLegalReport
    fabrication_count: int
    dropped: tuple[str, ...]
    chain_length: int


@app.post("/v1/examinations/{examination_id}/structure")
def structure_dictation(
    examination_id: UUID, request: StructureRequest
) -> StructureResponse:
    """Structure an examiner's dictation into injuries on the record.

    Amending rather than replacing: the injuries are added under the examiner's
    own provenance, and the custody chain records who did it and why. A
    finalised examination is not restructured, because a change after
    finalisation is an amendment with a stated reason.
    """
    examination = _verified(_examination(examination_id))
    if examination.report.status is ExaminationStatus.FINALISED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"examination {examination_id} is finalised; add findings through "
                f"POST /v1/examinations/{examination_id}/amend with a stated reason"
            ),
        )
    if _provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; prompts are not loaded yet",
        )
    prompt = _prompts.get("structuring_agent")
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "structuring_agent prompt is not loaded; check "
                "services/forensics/prompts/"
            ),
        )
    try:
        built = structure(
            _provider,
            prompt,
            request.dictation,
            str(examination_id),
            examination.report.examiner_id,
        )
    except DictationTooLongError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error

    examination.report = examination.report.model_copy(
        update={"injuries": (*examination.report.injuries, *built.injuries)}
    )
    _append(examination, CustodyAction.AMENDED, request.actor, reason="Dictation structured")
    return StructureResponse(
        report=examination.report,
        fabrication_count=built.fabrication_count,
        dropped=tuple(dropped.reason for dropped in built.dropped),
        chain_length=len(examination.chain),
    )


class StatuteResponse(BaseModel):
    """What a section is called under the other numbering.

    `legally_reviewed` is false on every response and is returned rather than
    documented, because a caller rendering this into a report needs the caveat
    beside the number. The correspondence table is a police reference document
    and carries no legal force of its own.

    `needs_legal_check` marks a row that is more than a renumbering: a section
    the table records as changed has different wording, so a clinical finding
    that satisfied the old test may not satisfy the new one.
    """

    query: str
    numbering: str
    matches: tuple[dict[str, object], ...]
    legally_reviewed: bool = False


@app.get("/v1/statutes/{numbering}/{section}")
def translate_section(numbering: str, section: str) -> StatuteResponse:
    """Translate a section number across the 2024 renumbering.

    Answers "what is this section called now", which a reader of an archived
    report needs because the BNS renumbered comprehensively and no section kept
    its number. It does not answer which section applies to an injury: that is
    a legal classification, it needs a lawyer, and the service README lists it
    as blocked.

    The BNS direction can return more than one match, because the BNS merged
    provisions. Returning only the first would drop a section from the record.
    """
    wanted = numbering.lower()
    if wanted not in {"ipc", "bns"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"numbering must be 'ipc' or 'bns', not {numbering!r}",
        )

    table = statute_map()
    if wanted == "ipc":
        found = table.from_ipc(section)
        matches: tuple[Correspondence, ...] = (found,) if found is not None else ()
    else:
        matches = table.from_bns(section)

    return StatuteResponse(
        query=section,
        numbering=wanted,
        matches=tuple(
            {
                "ipc": entry.ipc,
                "bns": entry.bns,
                "title": entry.title,
                "changed": entry.changed,
                "repealed": entry.repealed,
                "needs_legal_check": entry.needs_legal_check,
                "note": entry.note,
            }
            for entry in matches
        ),
    )
