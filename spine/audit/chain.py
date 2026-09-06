"""Building and verifying an audit chain.

Appending is the only write. Verification is what makes the guarantee real: a
chain that cannot be checked is a claim, not evidence.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from spine.audit.events import (
    GENESIS_HASH,
    AuditEvent,
    EventType,
    SubjectType,
    compute_hash,
)


def _recompute(entry: AuditEvent) -> str:
    return compute_hash(
        sequence=entry.sequence,
        subject_type=entry.subject_type,
        subject_id=entry.subject_id,
        event_type=entry.event_type,
        actor=entry.actor,
        occurred_at=entry.occurred_at,
        payload=entry.payload,
        prompt_version=entry.prompt_version,
        model_version=entry.model_version,
        rule_set_version=entry.rule_set_version,
        transport=entry.transport,
        corrects_sequence=entry.corrects_sequence,
        previous_hash=entry.previous_hash,
    )


class ChainIntegrityError(RuntimeError):
    """Raised when a chain does not verify.

    Carries the sequence number where the break was found, because the entry
    after a break is not necessarily the altered one.
    """

    def __init__(self, message: str, sequence: int) -> None:
        super().__init__(message)
        self.sequence = sequence


def append(
    previous: AuditEvent | None,
    *,
    subject_type: SubjectType,
    subject_id: UUID,
    event_type: EventType,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, object] | None = None,
    prompt_version: str | None = None,
    model_version: str | None = None,
    rule_set_version: str | None = None,
    transport: str | None = None,
    corrects_sequence: int | None = None,
) -> AuditEvent:
    """The next entry in a chain.

    `occurred_at` is passed in rather than read from the clock, so that callers
    stay testable and the timestamp is the moment the thing happened rather than
    the moment it was logged.
    """
    sequence = 0 if previous is None else previous.sequence + 1
    previous_hash = GENESIS_HASH if previous is None else previous.entry_hash
    body = payload if payload is not None else {}
    entry_hash = compute_hash(
        sequence=sequence,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        actor=actor,
        occurred_at=occurred_at,
        payload=body,
        prompt_version=prompt_version,
        model_version=model_version,
        rule_set_version=rule_set_version,
        transport=transport,
        corrects_sequence=corrects_sequence,
        previous_hash=previous_hash,
    )
    return AuditEvent(
        sequence=sequence,
        subject_type=subject_type,
        subject_id=subject_id,
        event_type=event_type,
        actor=actor,
        occurred_at=occurred_at,
        payload=body,
        prompt_version=prompt_version,
        model_version=model_version,
        rule_set_version=rule_set_version,
        transport=transport,
        corrects_sequence=corrects_sequence,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )


def verify(chain: tuple[AuditEvent, ...]) -> None:
    """Confirm a chain is unbroken, contiguous, and internally consistent.

    Every entry's hash is recomputed from its content rather than trusted.
    Constructing an AuditEvent validates its hash, but model_copy and ORM
    hydration both bypass validators, so a stored entry could carry a payload
    that no longer matches its hash. Recomputing here is what makes tampering
    detectable rather than merely declared.

    Raises at the first break, naming what is wrong. An empty chain verifies:
    nothing has been claimed, so nothing can be false.
    """
    if not chain:
        return
    if chain[0].sequence != 0:
        raise ChainIntegrityError(
            f"chain starts at sequence {chain[0].sequence}, not 0; entries are missing "
            f"from the beginning",
            chain[0].sequence,
        )
    if chain[0].previous_hash != GENESIS_HASH:
        raise ChainIntegrityError(
            f"the first entry links to {chain[0].previous_hash[:12]}... rather than the "
            f"genesis hash; it is not the first entry of this chain",
            0,
        )
    for index, entry in enumerate(chain):
        recomputed = _recompute(entry)
        if recomputed != entry.entry_hash:
            raise ChainIntegrityError(
                f"entry {entry.sequence} carries hash {entry.entry_hash[:12]}... but its "
                f"content hashes to {recomputed[:12]}...; this entry has been altered "
                f"since it was written",
                entry.sequence,
            )
        if entry.sequence != index:
            raise ChainIntegrityError(
                f"entry at position {index} carries sequence {entry.sequence}; the chain "
                f"is not contiguous and an entry has been removed or reordered",
                entry.sequence,
            )
        if index > 0 and entry.previous_hash != chain[index - 1].entry_hash:
            raise ChainIntegrityError(
                f"entry {entry.sequence} links to {entry.previous_hash[:12]}... but entry "
                f"{chain[index - 1].sequence} hashes to "
                f"{chain[index - 1].entry_hash[:12]}...; the chain is broken here, and "
                f"the alteration is at or before this point",
                entry.sequence,
            )


def is_intact(chain: tuple[AuditEvent, ...]) -> bool:
    try:
        verify(chain)
    except ChainIntegrityError:
        return False
    return True


def entries_for(chain: tuple[AuditEvent, ...], subject_id: UUID) -> tuple[AuditEvent, ...]:
    return tuple(entry for entry in chain if entry.subject_id == subject_id)


def corrections_of(chain: tuple[AuditEvent, ...], sequence: int) -> tuple[AuditEvent, ...]:
    """Every entry correcting `sequence`, oldest first.

    A corrected entry is never removed. Reading the record means reading the
    original and the corrections that followed it.
    """
    return tuple(entry for entry in chain if entry.corrects_sequence == sequence)
