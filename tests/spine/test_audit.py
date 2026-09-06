"""The audit chain, including tampering it is meant to detect.

The M5 gate requires every decision in a sample session to be reconstructable
from the audit log alone, and Forensics requires the chain to survive
cross-examination. Both need verification to actually catch alteration rather
than merely declare that it would.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from spine.audit.chain import (
    ChainIntegrityError,
    append,
    corrections_of,
    entries_for,
    is_intact,
    verify,
)
from spine.audit.events import GENESIS_HASH, AuditEvent, EventType, SubjectType

WHEN = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)


def chain_of(count: int, subject_id: UUID | None = None) -> tuple[AuditEvent, ...]:
    subject = subject_id if subject_id is not None else uuid4()
    entries: list[AuditEvent] = []
    previous: AuditEvent | None = None
    for index in range(count):
        previous = append(
            previous,
            subject_type=SubjectType.SESSION,
            subject_id=subject,
            event_type=EventType.TURN_RECORDED,
            actor="intake_agent",
            occurred_at=WHEN,
            payload={"turn": index},
        )
        entries.append(previous)
    return tuple(entries)


class TestAppending:
    def test_the_first_entry_links_to_genesis(self) -> None:
        first = chain_of(1)[0]
        assert first.sequence == 0
        assert first.previous_hash == GENESIS_HASH

    def test_each_entry_links_to_the_one_before(self) -> None:
        entries = chain_of(4)
        for index in range(1, len(entries)):
            assert entries[index].previous_hash == entries[index - 1].entry_hash

    def test_sequences_are_contiguous(self) -> None:
        assert [entry.sequence for entry in chain_of(5)] == [0, 1, 2, 3, 4]

    def test_identical_content_hashes_identically(self) -> None:
        subject = uuid4()
        one = chain_of(3, subject)
        two = chain_of(3, subject)
        assert [e.entry_hash for e in one] == [e.entry_hash for e in two]

    def test_differing_content_hashes_differently(self) -> None:
        base = append(
            None,
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            event_type=EventType.BAND_ASSIGNED,
            occurred_at=WHEN,
            actor="triage_agent",
            payload={"band": "U2"},
        )
        other = append(
            None,
            subject_type=SubjectType.SESSION,
            subject_id=base.subject_id,
            event_type=EventType.BAND_ASSIGNED,
            occurred_at=WHEN,
            actor="triage_agent",
            payload={"band": "U1"},
        )
        assert base.entry_hash != other.entry_hash

    def test_model_and_prompt_versions_are_recorded(self) -> None:
        entry = append(
            None,
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            event_type=EventType.MODEL_CALLED,
            actor="triage_agent",
            occurred_at=WHEN,
            prompt_version="1.2.0",
            model_version="llama3.1:8b",
            transport="local",
            rule_set_version="0.1.0",
        )
        assert entry.prompt_version == "1.2.0"
        assert entry.model_version == "llama3.1:8b"
        assert entry.transport == "local"
        assert entry.rule_set_version == "0.1.0"


class TestVerification:
    def test_a_clean_chain_verifies(self) -> None:
        verify(chain_of(6))

    def test_an_empty_chain_verifies(self) -> None:
        verify(())

    def test_a_single_entry_verifies(self) -> None:
        verify(chain_of(1))


class TestTamperDetection:
    """Constructing an event validates its hash, but model_copy and ORM
    hydration both bypass validators. Verification recomputes rather than
    trusting, which is what makes these detectable."""

    def test_an_altered_payload_is_caught(self) -> None:
        entries = chain_of(3)
        tampered = (
            entries[0],
            entries[1].model_copy(update={"payload": {"turn": 99}}),
            entries[2],
        )
        assert not is_intact(tampered)

    def test_an_altered_actor_is_caught(self) -> None:
        entries = chain_of(3)
        tampered = (entries[0], entries[1].model_copy(update={"actor": "someone_else"}), entries[2])
        assert not is_intact(tampered)

    def test_an_altered_timestamp_is_caught(self) -> None:
        entries = chain_of(3)
        moved = datetime(2020, 1, 1, tzinfo=timezone.utc)
        tampered = (entries[0], entries[1].model_copy(update={"occurred_at": moved}), entries[2])
        assert not is_intact(tampered)

    def test_the_break_is_reported_at_the_altered_entry(self) -> None:
        entries = chain_of(4)
        tampered = (
            entries[0],
            entries[1],
            entries[2].model_copy(update={"payload": {"turn": 99}}),
            entries[3],
        )
        with pytest.raises(ChainIntegrityError) as caught:
            verify(tampered)
        assert caught.value.sequence == 2

    def test_a_removed_entry_is_caught(self) -> None:
        entries = chain_of(4)
        assert not is_intact((entries[0], entries[2], entries[3]))

    def test_a_reordered_chain_is_caught(self) -> None:
        entries = chain_of(3)
        assert not is_intact((entries[0], entries[2], entries[1]))

    def test_a_chain_not_starting_at_zero_is_caught(self) -> None:
        entries = chain_of(3)
        with pytest.raises(ChainIntegrityError, match="missing"):
            verify(entries[1:])

    def test_a_relinked_first_entry_is_caught(self) -> None:
        entries = chain_of(2)
        forged = entries[0].model_copy(update={"previous_hash": "a" * 64})
        with pytest.raises(ChainIntegrityError, match="genesis"):
            verify((forged, entries[1]))

    def test_an_appended_forgery_breaks_the_link(self) -> None:
        entries = chain_of(2)
        orphan = append(
            None,
            subject_type=SubjectType.SESSION,
            subject_id=entries[0].subject_id,
            event_type=EventType.BAND_ASSIGNED,
            actor="attacker",
            occurred_at=WHEN,
        ).model_copy(update={"sequence": 2})
        assert not is_intact((*entries, orphan))


class TestCorrections:
    def test_a_correction_is_a_new_entry(self) -> None:
        entries = chain_of(3)
        corrected = append(
            entries[-1],
            subject_type=SubjectType.SESSION,
            subject_id=entries[0].subject_id,
            event_type=EventType.CORRECTION,
            actor="clinician",
            occurred_at=WHEN,
            payload={"band": "U2", "reason": "reviewed"},
            corrects_sequence=1,
        )
        full = (*entries, corrected)
        verify(full)
        assert corrections_of(full, 1) == (corrected,)

    def test_the_corrected_entry_survives(self) -> None:
        entries = chain_of(2)
        corrected = append(
            entries[-1],
            subject_type=SubjectType.SESSION,
            subject_id=entries[0].subject_id,
            event_type=EventType.CORRECTION,
            actor="clinician",
            occurred_at=WHEN,
            corrects_sequence=0,
        )
        assert (*entries, corrected)[0] is entries[0]

    def test_a_correction_cannot_point_forwards(self) -> None:
        entries = chain_of(2)
        with pytest.raises(ValueError, match="not earlier than itself"):
            append(
                entries[-1],
                subject_type=SubjectType.SESSION,
                subject_id=entries[0].subject_id,
                event_type=EventType.CORRECTION,
                actor="clinician",
                occurred_at=WHEN,
                corrects_sequence=5,
            )

    def test_a_correction_cannot_point_at_itself(self) -> None:
        entries = chain_of(2)
        with pytest.raises(ValueError, match="not earlier than itself"):
            append(
                entries[-1],
                subject_type=SubjectType.SESSION,
                subject_id=entries[0].subject_id,
                event_type=EventType.CORRECTION,
                actor="clinician",
                occurred_at=WHEN,
                corrects_sequence=2,
            )


class TestSubjectPolymorphism:
    """ADR 0006. Rx works from a prescription and Labs from a report."""

    @pytest.mark.parametrize("subject_type", list(SubjectType))
    def test_every_subject_type_can_be_logged(self, subject_type: SubjectType) -> None:
        entry = append(
            None,
            subject_type=subject_type,
            subject_id=uuid4(),
            event_type=EventType.SESSION_STARTED,
            actor="system",
            occurred_at=WHEN,
        )
        verify((entry,))

    def test_entries_can_be_filtered_by_subject(self) -> None:
        wanted = uuid4()
        mine = chain_of(2, wanted)
        theirs = chain_of(2, uuid4())
        combined = (*mine, *theirs)
        assert len(entries_for(combined, wanted)) == 2
