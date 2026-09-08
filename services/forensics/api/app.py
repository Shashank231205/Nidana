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

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from services.forensics.clinical.custody import (
    CustodyAction,
    CustodyChainError,
    record,
    verify_chain,
    was_amended_after_finalisation,
)
from spine.audit.events import AuditEvent
from spine.schemas.forensic import ExaminationStatus, MedicoLegalReport

app = FastAPI(
    title="Nidana Forensics",
    description="Medico-legal documentation. Tamper-evident and evidentially isolated.",
    version="0.1.0",
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
def finalise(examination_id: UUID, request: AccessRequest) -> ReportResponse:
    """Finalise the examination.

    Finalisation does not close the chain. An amendment after this point is
    permitted and recorded as such, because a court reads "amended after
    finalisation" differently from "amended", and hiding it would be the
    tampering the chain exists to make visible.
    """
    examination = _verified(_examination(examination_id))
    examination.report = examination.report.model_copy(
        update={"status": ExaminationStatus.FINALISED}
    )
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
