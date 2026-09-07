"""Repositories, against a recording connection rather than a database.

What is asserted is the shape of what would be written: that findings carry
their provenance, that firings become one row each, and — the point of the
layer — that nothing offers an UPDATE or DELETE on an append-only table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest

from spine.audit.chain import append as chain_append
from spine.audit.events import EventType
from spine.audit.events import SubjectType as AuditSubject
from spine.persistence.repositories import (
    AuditRepository,
    ConsentRepository,
    FindingRepository,
    SessionRepository,
    TriageRepository,
)
from spine.schemas.finding import Finding
from spine.schemas.primitives import Band, Confidence, Quantity
from spine.schemas.provenance import locate_utterance
from spine.schemas.triage import Capability, RedFlagOutcome, Specialty, TriageResult

WHEN = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
UTTERANCE = "chest pain since six hours, goes to my jaw"


class RecordingCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.next_row: tuple[Any, ...] | None = None

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> object:
        self.statements.append((query, [parameters]))
        return None

    def executemany(self, query: str, parameters: list[tuple[Any, ...]]) -> object:
        self.statements.append((query, parameters))
        return None

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.next_row


class RecordingConnection:
    def __init__(self) -> None:
        self.shared_cursor = RecordingCursor()
        self.committed = 0

    def cursor(self) -> RecordingCursor:
        return self.shared_cursor

    def commit(self) -> None:
        self.committed += 1

    def rollback(self) -> None:
        return None

    @property
    def statements(self) -> list[tuple[str, list[tuple[Any, ...]]]]:
        return self.shared_cursor.statements

    @property
    def sql(self) -> str:
        return " ".join(query for query, _ in self.statements)


@pytest.fixture
def connection() -> RecordingConnection:
    return RecordingConnection()


def finding(
    field: str,
    value: str | float | int | bool | Quantity,
    quote: str,
    *,
    negated: bool = False,
) -> Finding:
    return Finding(
        field=field,
        value=value,
        provenance=locate_utterance(
            source_id="u1", source_text=UTTERANCE, quote=quote, turn_index=2
        ),
        confidence=Confidence.HIGH,
        negated=negated,
    )


class TestAppendOnly:
    """The invariant this layer exists to hold."""

    @pytest.mark.parametrize(
        "repository",
        [FindingRepository, TriageRepository, AuditRepository, ConsentRepository],
    )
    def test_no_repository_on_an_append_only_table_offers_update_or_delete(
        self, repository: type
    ) -> None:
        methods = {name for name in dir(repository) if not name.startswith("_")}
        assert not {"update", "delete", "remove", "modify"} & methods

    def test_findings_are_written_with_insert_only(
        self, connection: RecordingConnection
    ) -> None:
        FindingRepository(connection).append(uuid4(), (finding("radiation", "jaw", "my jaw"),))
        assert "INSERT INTO" in connection.sql
        assert "UPDATE" not in connection.sql
        assert "DELETE" not in connection.sql

    def test_audit_entries_are_written_with_insert_only(
        self, connection: RecordingConnection
    ) -> None:
        entry = chain_append(
            None,
            subject_type=AuditSubject.SESSION,
            subject_id=uuid4(),
            event_type=EventType.SESSION_STARTED,
            actor="system",
            occurred_at=WHEN,
        )
        AuditRepository(connection).append((entry,))
        assert "INSERT INTO clinical.audit_events" in connection.sql
        assert "UPDATE" not in connection.sql

    def test_withdrawing_consent_writes_a_new_row(
        self, connection: RecordingConnection
    ) -> None:
        ConsentRepository(connection).withdraw(
            uuid4(), purpose="triage", consent_text_version="1.0"
        )
        query, parameters = connection.statements[0]
        assert "INSERT INTO clinical.session_consents" in query
        assert parameters[0][2] is False

    def test_the_session_table_is_the_one_that_updates(
        self, connection: RecordingConnection
    ) -> None:
        """Current state updates; the history of it lives in the audit chain."""
        SessionRepository(connection).set_outcome(uuid4(), status="completed", band="U3")
        assert "UPDATE clinical.sessions" in connection.sql


class TestFindings:
    def test_provenance_is_stored_whole(self, connection: RecordingConnection) -> None:
        FindingRepository(connection).append(uuid4(), (finding("radiation", "jaw", "my jaw"),))
        _, parameters = connection.statements[0]
        provenance = parameters[0][4]
        assert "patient_utterance" in provenance
        assert "my jaw" in provenance

    def test_a_quantity_value_serialises_with_its_unit(
        self, connection: RecordingConnection
    ) -> None:
        FindingRepository(connection).append(
            uuid4(),
            (finding("onset_duration_hours", Quantity(value=6, unit="hours"), "six hours"),),
        )
        _, parameters = connection.statements[0]
        assert "hours" in parameters[0][3]

    def test_a_denial_records_its_boolean(self, connection: RecordingConnection) -> None:
        FindingRepository(connection).append(
            uuid4(), (finding("diaphoresis", False, "my jaw", negated=True),)
        )
        _, parameters = connection.statements[0]
        assert parameters[0][6] is True

    def test_the_turn_index_comes_from_the_provenance(
        self, connection: RecordingConnection
    ) -> None:
        FindingRepository(connection).append(uuid4(), (finding("radiation", "jaw", "my jaw"),))
        _, parameters = connection.statements[0]
        assert parameters[0][1] == 2

    def test_no_findings_writes_nothing(self, connection: RecordingConnection) -> None:
        FindingRepository(connection).append(uuid4(), ())
        assert not connection.statements


class TestTriage:
    def test_a_result_stores_its_band_and_specialty_as_columns(
        self, connection: RecordingConnection
    ) -> None:
        result = TriageResult(
            band=Band.U1, specialty=Specialty.EMERGENCY, rationale="immediate"
        )
        TriageRepository(connection).store(uuid4(), result)
        _, parameters = connection.statements[0]
        assert parameters[0][1] == "U1"
        assert parameters[0][2] == "emergency"

    def test_a_critic_escalation_records_where_it_came_from(
        self, connection: RecordingConnection
    ) -> None:
        result = TriageResult(
            band=Band.U1,
            specialty=Specialty.EMERGENCY,
            rationale="escalated",
            critic_raised_from=Band.U3,
        )
        TriageRepository(connection).store(uuid4(), result)
        _, parameters = connection.statements[0]
        assert parameters[0][4] is True
        assert parameters[0][5] == "U3"

    def test_each_firing_becomes_its_own_row(self, connection: RecordingConnection) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_ACS_001", "RF_SYNCOPE_001"),
            terminating_rule_ids=("RF_ACS_001",),
            escalating_rule_ids=("RF_SYNCOPE_001",),
            required_capabilities=(Capability.CATH_LAB,),
            unverified_rule_ids=("RF_ACS_001",),
        )
        TriageRepository(connection).store_firings(uuid4(), 3, outcome)
        _, parameters = connection.statements[0]
        assert len(parameters) == 2
        assert parameters[0][3] == "TERMINATE_EMERGENCY"
        assert parameters[1][3] == "ESCALATE_BAND"

    def test_an_unverified_firing_is_marked(self, connection: RecordingConnection) -> None:
        outcome = RedFlagOutcome(
            rule_ids=("RF_ACS_001",),
            terminating_rule_ids=("RF_ACS_001",),
            unverified_rule_ids=("RF_ACS_001",),
        )
        TriageRepository(connection).store_firings(uuid4(), 1, outcome)
        _, parameters = connection.statements[0]
        assert parameters[0][6] is True

    def test_a_quiet_outcome_writes_nothing(self, connection: RecordingConnection) -> None:
        TriageRepository(connection).store_firings(uuid4(), 1, RedFlagOutcome())
        assert not connection.statements


class TestAudit:
    def test_the_chain_columns_are_written(self, connection: RecordingConnection) -> None:
        entry = chain_append(
            None,
            subject_type=AuditSubject.SESSION,
            subject_id=uuid4(),
            event_type=EventType.BAND_ASSIGNED,
            actor="triage_agent",
            occurred_at=WHEN,
            payload={"band": "U2"},
            prompt_version="1.0.0",
            model_version="qwen2.5:7b",
            transport="local",
        )
        AuditRepository(connection).append((entry,))
        _, parameters = connection.statements[0]
        row = parameters[0]
        assert row[6] == "1.0.0"
        assert row[7] == "qwen2.5:7b"
        assert row[9] == "local"
        assert row[11] == entry.previous_hash
        assert row[12] == entry.entry_hash

    def test_an_empty_chain_writes_nothing(self, connection: RecordingConnection) -> None:
        AuditRepository(connection).append(())
        assert not connection.statements

    def test_last_sequence_is_none_for_a_new_subject(
        self, connection: RecordingConnection
    ) -> None:
        connection.shared_cursor.next_row = (None,)
        assert AuditRepository(connection).last_sequence("session", uuid4()) is None

    def test_last_sequence_returns_the_stored_value(
        self, connection: RecordingConnection
    ) -> None:
        connection.shared_cursor.next_row = (7,)
        assert AuditRepository(connection).last_sequence("session", uuid4()) == 7


class TestSessions:
    def test_creating_records_the_versions_that_produced_it(
        self, connection: RecordingConnection
    ) -> None:
        """A clinical decision must be reproducible from a tag plus the log."""
        SessionRepository(connection).create(
            uuid4(), rule_set_version="0.1.0", prompt_versions={"intake_agent": "1.0.0"}
        )
        _, parameters = connection.statements[0]
        assert parameters[0][1] == "0.1.0"
        assert "intake_agent" in parameters[0][2]

    def test_a_turn_stores_the_utterance_verbatim(
        self, connection: RecordingConnection
    ) -> None:
        SessionRepository(connection).record_turn(
            uuid4(), turn_index=1, patient_utterance=UTTERANCE, language="hi-en"
        )
        _, parameters = connection.statements[0]
        assert parameters[0][2] == UTTERANCE
