"""The append-only, hash-chained audit log.

NIDANA.md section 9. Consult needs this to defend a triage decision; Forensics
needs it to survive cross-examination. Same guarantees, different consumers.

No UPDATE, no DELETE, no soft-delete flag. A correction is a new entry
referencing the one it corrects. The database role the application uses lacks
the grants to do otherwise, so this is not a convention.

Each entry hashes the previous one. Any retroactive alteration breaks the chain
and is provable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

GENESIS_HASH: Final[str] = "0" * 64
"""The previous_hash of the first entry in a chain."""


class EventType(str, Enum):
    """What happened. Shared across services; not every service emits every one."""

    SESSION_STARTED = "session_started"
    TURN_RECORDED = "turn_recorded"
    FINDING_EXTRACTED = "finding_extracted"
    RULE_FIRED = "rule_fired"
    RULES_EVALUATED = "rules_evaluated"
    BAND_ASSIGNED = "band_assigned"
    BAND_ESCALATED = "band_escalated"
    ROUTING_RESOLVED = "routing_resolved"
    MODEL_CALLED = "model_called"
    OUTPUT_FILTERED = "output_filtered"
    SESSION_TERMINATED = "session_terminated"
    HANDED_OFF = "handed_off"
    CONSENT_RECORDED = "consent_recorded"
    CORRECTION = "correction"


class SubjectType(str, Enum):
    """What the entry is about. Polymorphic per ADR 0006.

    Rx works from a prescription and Labs from a report; neither is a session.
    """

    SESSION = "session"
    ENCOUNTER = "encounter"
    PRESCRIPTION = "prescription"
    REPORT = "report"
    EXAMINATION = "examination"


class AuditEvent(BaseModel):
    """One entry in the chain.

    `payload` is the decision's own data. `previous_hash` and `entry_hash` are
    what make the sequence tamper-evident.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence: int = Field(ge=0)
    subject_type: SubjectType
    subject_id: UUID
    event_type: EventType
    actor: str = Field(min_length=1, description="Agent name, rule id, or 'system'")
    occurred_at: datetime
    payload: dict[str, object] = Field(default_factory=dict)
    prompt_version: str | None = None
    model_version: str | None = None
    rule_set_version: str | None = None
    transport: str | None = Field(
        default=None, description="local or hosted; identifies a session run off-machine"
    )
    corrects_sequence: int | None = Field(
        default=None, description="The entry this one corrects, never an update"
    )
    previous_hash: str = Field(min_length=64, max_length=64)
    entry_hash: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def _hash_matches_content(self) -> AuditEvent:
        expected = compute_hash(
            sequence=self.sequence,
            subject_type=self.subject_type,
            subject_id=self.subject_id,
            event_type=self.event_type,
            actor=self.actor,
            occurred_at=self.occurred_at,
            payload=self.payload,
            prompt_version=self.prompt_version,
            model_version=self.model_version,
            rule_set_version=self.rule_set_version,
            transport=self.transport,
            corrects_sequence=self.corrects_sequence,
            previous_hash=self.previous_hash,
        )
        if self.entry_hash != expected:
            raise ValueError(
                f"entry {self.sequence} carries hash {self.entry_hash[:12]}... but its "
                f"content hashes to {expected[:12]}...; the entry has been altered since "
                f"it was written"
            )
        return self

    @model_validator(mode="after")
    def _a_correction_points_backwards(self) -> AuditEvent:
        if self.corrects_sequence is not None and self.corrects_sequence >= self.sequence:
            raise ValueError(
                f"entry {self.sequence} claims to correct entry {self.corrects_sequence}, "
                f"which is not earlier than itself; corrections reference prior entries"
            )
        return self


def compute_hash(
    *,
    sequence: int,
    subject_type: SubjectType,
    subject_id: UUID,
    event_type: EventType,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, object],
    prompt_version: str | None,
    model_version: str | None,
    rule_set_version: str | None,
    transport: str | None,
    corrects_sequence: int | None,
    previous_hash: str,
) -> str:
    """The SHA-256 of an entry's content plus the hash before it.

    Serialisation is canonical: sorted keys, no whitespace variation, explicit
    separators. Two entries with the same content hash the same on any machine,
    which is what makes the chain verifiable somewhere other than where it was
    written.
    """
    canonical = json.dumps(
        {
            "sequence": sequence,
            "subject_type": subject_type.value,
            "subject_id": str(subject_id),
            "event_type": event_type.value,
            "actor": actor,
            "occurred_at": occurred_at.isoformat(),
            "payload": payload,
            "prompt_version": prompt_version,
            "model_version": model_version,
            "rule_set_version": rule_set_version,
            "transport": transport,
            "corrects_sequence": corrects_sequence,
            "previous_hash": previous_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
