"""Repositories: rows in, rows out. No business logic.

Almost every write here is an insert. There is no update or delete on the
append-only tables, because the application role has no grant for either — a
repository offering one would fail at the database rather than at review, and
offering it at all invites a call site that expects it to work.

The connection is a protocol rather than a concrete driver, so the clinical
layer stays testable without a database and the driver choice stays a
deployment concern.
"""

from __future__ import annotations

import json
from typing import Any, Protocol
from uuid import UUID

from spine.audit.events import AuditEvent
from spine.schemas.finding import Finding
from spine.schemas.triage import RedFlagOutcome, TriageResult


class Cursor(Protocol):
    """The subset of DB-API a repository uses."""

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> object: ...

    def executemany(self, query: str, parameters: list[tuple[Any, ...]]) -> object: ...

    def fetchone(self) -> tuple[Any, ...] | None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _dumped(value: object) -> object:
    """A pydantic value as JSON-ready data, or the value itself."""
    dump = getattr(value, "model_dump", None)
    return dump(mode="json") if callable(dump) else value


class SessionRepository:
    """Sessions and their turns."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def create(
        self,
        session_id: UUID,
        *,
        rule_set_version: str,
        prompt_versions: dict[str, str],
        locale: str = "en",
    ) -> None:
        self._connection.cursor().execute(
            "INSERT INTO clinical.sessions "
            "(id, rule_set_version, prompt_versions, locale) VALUES (%s, %s, %s, %s)",
            (str(session_id), rule_set_version, _json(prompt_versions), locale),
        )

    def record_turn(
        self,
        session_id: UUID,
        *,
        turn_index: int,
        patient_utterance: str,
        agent_utterance: str | None = None,
        language: str | None = None,
    ) -> None:
        self._connection.cursor().execute(
            "INSERT INTO clinical.session_turns "
            "(session_id, turn_index, patient_utterance, agent_utterance, language) "
            "VALUES (%s, %s, %s, %s, %s)",
            (str(session_id), turn_index, patient_utterance, agent_utterance, language),
        )

    def set_outcome(
        self,
        session_id: UUID,
        *,
        status: str,
        band: str | None = None,
        specialty: str | None = None,
        complaint_family: str | None = None,
    ) -> None:
        """Write the terminal state of a session.

        The only statement in this layer that updates a row. `sessions` is
        deliberately not append-only: it is the current-state table, and how it
        got there lives in the audit chain, which is.
        """
        self._connection.cursor().execute(
            "UPDATE clinical.sessions SET status = %s, band = %s, specialty = %s, "
            "complaint_family = %s WHERE id = %s",
            (status, band, specialty, complaint_family, str(session_id)),
        )


class FindingRepository:
    """Findings. Insert only."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, session_id: UUID, findings: tuple[Finding, ...]) -> None:
        """Store findings.

        Provenance is serialised whole rather than flattened into columns, so a
        span variant added by another service needs no migration here.
        """
        if not findings:
            return
        self._connection.cursor().executemany(
            "INSERT INTO clinical.findings "
            "(session_id, turn_index, field, value, provenance, confidence, negated, codings) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    str(session_id),
                    finding.turn_index if finding.turn_index is not None else 0,
                    finding.field,
                    _json(_dumped(finding.value)),
                    _json(finding.provenance.model_dump(mode="json")),
                    finding.confidence.value,
                    finding.negated,
                    _json([coding.model_dump(mode="json") for coding in finding.codings]),
                )
                for finding in findings
            ],
        )


def _action_for(rule_id: str, terminating: frozenset[str], escalating: frozenset[str]) -> str:
    if rule_id in terminating:
        return "TERMINATE_EMERGENCY"
    if rule_id in escalating:
        return "ESCALATE_BAND"
    return "ANNOTATE"


class TriageRepository:
    """Triage results and red flag firings. Insert only."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def store(self, session_id: UUID, result: TriageResult) -> None:
        self._connection.cursor().execute(
            "INSERT INTO clinical.triage_results "
            "(session_id, band, specialty, payload, critic_adjusted, critic_from_band) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                str(session_id),
                result.band.value,
                result.specialty.value,
                _json(result.model_dump(mode="json")),
                result.was_escalated_by_critic,
                result.critic_raised_from.value if result.critic_raised_from else None,
            ),
        )

    def store_firings(
        self,
        session_id: UUID,
        turn_index: int,
        outcome: RedFlagOutcome,
    ) -> None:
        """Record each firing as its own row.

        Queryable rather than buried in an audit payload, because red flag
        sensitivity is a release gate and reconstructing it from JSON is how a
        gate becomes unmeasurable.
        """
        if not outcome.fired:
            return
        terminating = frozenset(outcome.terminating_rule_ids)
        escalating = frozenset(outcome.escalating_rule_ids)
        self._connection.cursor().executemany(
            "INSERT INTO clinical.red_flag_events "
            "(session_id, turn_index, rule_id, action, matched_atoms, capabilities, unverified) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    str(session_id),
                    turn_index,
                    rule_id,
                    _action_for(rule_id, terminating, escalating),
                    list(outcome.matched_atoms),
                    [capability.value for capability in outcome.required_capabilities],
                    rule_id in outcome.unverified_rule_ids,
                )
                for rule_id in outcome.rule_ids
            ],
        )


class AuditRepository:
    """The chain. Insert only, and the one table where that is load-bearing."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def append(self, entries: tuple[AuditEvent, ...]) -> None:
        if not entries:
            return
        self._connection.cursor().executemany(
            "INSERT INTO clinical.audit_events "
            "(subject_type, subject_id, sequence, event_type, actor, payload, "
            "prompt_version, model_version, rule_set_version, transport, "
            "corrects_sequence, previous_hash, entry_hash, occurred_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            [
                (
                    entry.subject_type.value,
                    str(entry.subject_id),
                    entry.sequence,
                    entry.event_type.value,
                    entry.actor,
                    _json(entry.payload),
                    entry.prompt_version,
                    entry.model_version,
                    entry.rule_set_version,
                    entry.transport,
                    entry.corrects_sequence,
                    entry.previous_hash,
                    entry.entry_hash,
                    entry.occurred_at,
                )
                for entry in entries
            ],
        )

    def last_sequence(self, subject_type: str, subject_id: UUID) -> int | None:
        """The sequence of the most recent entry, or None for an empty chain."""
        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT max(sequence) FROM clinical.audit_events "
            "WHERE subject_type = %s AND subject_id = %s",
            (subject_type, str(subject_id)),
        )
        row = cursor.fetchone()
        return None if row is None or row[0] is None else int(row[0])


class ConsentRepository:
    """Consent records. Withdrawal is a new row, never an update."""

    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def record(
        self,
        session_id: UUID,
        *,
        purpose: str,
        granted: bool,
        consent_text_version: str,
    ) -> None:
        self._connection.cursor().execute(
            "INSERT INTO clinical.session_consents "
            "(session_id, purpose, granted, consent_text_version) VALUES (%s, %s, %s, %s)",
            (str(session_id), purpose, granted, consent_text_version),
        )

    def withdraw(self, session_id: UUID, *, purpose: str, consent_text_version: str) -> None:
        self.record(
            session_id,
            purpose=purpose,
            granted=False,
            consent_text_version=consent_text_version,
        )
