"""The custody chain.

Every access to a medico-legal record is logged, and the log is hash-chained
like the audit trail — but with a difference that matters in court: this chain
records *reads* as well as writes.

A clinical audit log answers "what did the system decide". A custody log
answers "who has touched this evidence", and an unexplained gap in it is what
a defence lawyer looks for.

Forensics reuses the spine's chain construction rather than reimplementing it.
What differs is what gets logged and who may read it.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from spine.audit.chain import ChainIntegrityError, append, verify
from spine.audit.events import AuditEvent, EventType, SubjectType


class CustodyAction(str, Enum):
    """What someone did to a record.

    VIEWED is here and is the reason this is a custody log rather than an audit
    log. A record read by someone with no role in the case is a chain-of-custody
    problem whether or not they changed anything.
    """

    CREATED = "created"
    VIEWED = "viewed"
    AMENDED = "amended"
    PHOTOGRAPH_ATTACHED = "photograph_attached"
    FINALISED = "finalised"
    EXPORTED = "exported"
    DISCLOSED = "disclosed"


class CustodyChainError(RuntimeError):
    """Raised when the custody chain does not hold."""


def record(
    previous: AuditEvent | None,
    *,
    examination_id: UUID,
    action: CustodyAction,
    actor: str,
    occurred_at: datetime,
    reason: str | None = None,
    detail: dict[str, object] | None = None,
) -> AuditEvent:
    """Log one access.

    `reason` is required for an amendment. A correction with no stated reason
    is indistinguishable from tampering when read back years later, which is
    the situation this whole chain exists for.
    """
    if action is CustodyAction.AMENDED and not reason:
        raise CustodyChainError(
            "an amendment must state its reason. A correction with no reason cannot be "
            "distinguished from tampering when the record is read back in court"
        )
    payload: dict[str, object] = {"action": action.value}
    if reason:
        payload["reason"] = reason
    if detail:
        payload.update(detail)
    return append(
        previous,
        subject_type=SubjectType.EXAMINATION,
        subject_id=examination_id,
        event_type=_event_for(action),
        actor=actor,
        occurred_at=occurred_at,
        payload=payload,
    )


def _event_for(action: CustodyAction) -> EventType:
    if action is CustodyAction.AMENDED:
        return EventType.CORRECTION
    if action is CustodyAction.FINALISED:
        return EventType.HANDED_OFF
    if action is CustodyAction.CREATED:
        return EventType.SESSION_STARTED
    return EventType.TURN_RECORDED


def verify_chain(chain: tuple[AuditEvent, ...]) -> None:
    """Confirm the custody chain is unbroken.

    Raises with the sequence where the break was found. In a medico-legal
    context this is not a diagnostic — it is the answer to whether the record
    can be produced as evidence at all.
    """
    try:
        verify(chain)
    except ChainIntegrityError as error:
        raise CustodyChainError(
            f"custody chain broken at entry {error.sequence}: {error}. This record "
            f"cannot be shown to be unaltered and should not be produced as evidence "
            f"without explaining the break"
        ) from error


def accesses_by(chain: tuple[AuditEvent, ...], actor: str) -> tuple[AuditEvent, ...]:
    return tuple(entry for entry in chain if entry.actor == actor)


def actors(chain: tuple[AuditEvent, ...]) -> tuple[str, ...]:
    """Everyone who has touched this record, in order of first access."""
    seen: list[str] = []
    for entry in chain:
        if entry.actor not in seen:
            seen.append(entry.actor)
    return tuple(seen)


def amendments(chain: tuple[AuditEvent, ...]) -> tuple[AuditEvent, ...]:
    return tuple(entry for entry in chain if entry.event_type is EventType.CORRECTION)


def was_amended_after_finalisation(chain: tuple[AuditEvent, ...]) -> bool:
    """Whether anything changed after the report was signed.

    Not forbidden — a genuine correction after finalisation happens — but it is
    the first thing to disclose, so it is computed rather than left to be
    noticed.
    """
    finalised_at: int | None = None
    for entry in chain:
        if entry.event_type is EventType.HANDED_OFF:
            finalised_at = entry.sequence
        elif finalised_at is not None and entry.event_type is EventType.CORRECTION:
            return True
    return False
