"""The session orchestrator: one turn, in order.

This module holds the sequence the whole product depends on. The red flag
engine runs after every patient turn and before the intake agent speaks, so an
emergency ends the conversation rather than being asked one more question.

Nothing here decides anything clinical. It calls the pieces in the order the
architecture requires and records what happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from services.consult.agents import critic, intake, structuring, triage
from services.consult.clinical import red_flags
from services.consult.clinical.actions import RedFlagAction
from spine.audit.chain import append
from spine.audit.events import AuditEvent, EventType
from spine.audit.events import SubjectType as AuditSubject
from spine.inference.adapter import InferenceProvider
from spine.inference.prompts import Prompt
from spine.schemas.predicate import Predicate
from spine.schemas.primitives import Band
from spine.schemas.record import ConsultContext, Record, SubjectType
from spine.schemas.registry import ComplaintFamily, FamilyRegistry
from spine.schemas.rule import RuleSet
from spine.schemas.sufficiency import assess
from spine.schemas.triage import RedFlagOutcome, TriageResult


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED_EMERGENCY = "terminated_emergency"
    HANDED_OFF = "handed_off"


class TurnShape(str, Enum):
    """What a turn returns.

    The client renders on shape, never on a status string it has to parse.
    """

    NEXT_QUESTION = "next_question"
    TERMINAL_EMERGENCY = "terminal_emergency"
    COMPLETED_TRIAGE = "completed_triage"


@dataclass(frozen=True)
class Dependencies:
    """Everything a session needs, supplied rather than constructed.

    Passed in so a test can substitute a scripted model while the clinical
    layer runs for real. The clinical layer is never mocked.
    """

    provider: InferenceProvider
    prompts: dict[str, Prompt]
    registries: dict[ComplaintFamily, FamilyRegistry]
    predicates: dict[str, Predicate]
    rule_sets: tuple[RuleSet[RedFlagAction], ...]


@dataclass
class Session:
    """One patient encounter from first message to final output."""

    id: UUID = field(default_factory=uuid4)
    status: SessionStatus = SessionStatus.ACTIVE
    record: Record = field(init=False)
    transcript: list[tuple[str, str]] = field(default_factory=list)
    audit: list[AuditEvent] = field(default_factory=list)
    turn_index: int = 0
    consent_granted: bool = False
    consent_text_version: str | None = None

    @property
    def has_consent(self) -> bool:
        """Whether this session may record what the patient says.

        The DPDP Act requires consent to be explicit, purpose-bound and logged.
        A checkbox in a browser satisfies none of that on its own, so the
        decision is recorded on the session and written to the audit chain.
        """
        return self.consent_granted

    def __post_init__(self) -> None:
        self.record = Record(subject_type=SubjectType.SESSION, subject_id=self.id)

    def log(
        self,
        event_type: EventType,
        *,
        actor: str,
        occurred_at: datetime,
        payload: dict[str, object] | None = None,
        prompt_version: str | None = None,
        model_version: str | None = None,
    ) -> None:
        self.audit.append(
            append(
                self.audit[-1] if self.audit else None,
                subject_type=AuditSubject.SESSION,
                subject_id=self.id,
                event_type=event_type,
                actor=actor,
                occurred_at=occurred_at,
                payload=payload,
                prompt_version=prompt_version,
                model_version=model_version,
            )
        )


@dataclass(frozen=True)
class TurnResult:
    """What one turn produced.

    Exactly one of `question`, `emergency`, or `triage` is set, and `shape` says
    which. The client switches on shape.
    """

    shape: TurnShape
    session_id: UUID
    turn_index: int
    question: str | None = None
    emergency: RedFlagOutcome | None = None
    triage: TriageResult | None = None
    dropped_claims: int = 0


def _registry_for(
    session: Session, dependencies: Dependencies
) -> FamilyRegistry | None:
    family = session.record.consult.complaint_family
    return None if family is None else dependencies.registries.get(family)


def _run_red_flags(session: Session, dependencies: Dependencies) -> RedFlagOutcome:
    return red_flags.evaluate(
        session.record, dependencies.rule_sets, dependencies.predicates
    )


def submit_turn(
    session: Session,
    dependencies: Dependencies,
    utterance: str,
    now: datetime,
) -> TurnResult:
    """Process one patient utterance.

    The order is the architecture: structure the utterance into findings, run
    the red flag engine, and only then decide whether to ask another question.
    An emergency ends the session before the intake agent is called at all.
    """
    session.turn_index += 1
    source_id = f"{session.id}:{session.turn_index}"
    session.log(
        EventType.TURN_RECORDED,
        actor="patient",
        occurred_at=now,
        payload={"turn_index": session.turn_index, "length": len(utterance)},
    )

    dropped = 0
    registry = _registry_for(session, dependencies)
    if registry is not None:
        structured = structuring.structure(
            dependencies.provider,
            dependencies.prompts["structuring_agent"],
            utterance=utterance,
            registry=registry,
            source_id=source_id,
            turn_index=session.turn_index,
        )
        dropped = len(structured.dropped)
        session.record = session.record.with_findings(*structured.findings)
        session.log(
            EventType.FINDING_EXTRACTED,
            actor="structuring_agent",
            occurred_at=now,
            payload={"kept": len(structured.findings), "dropped": dropped},
            prompt_version=dependencies.prompts["structuring_agent"].version,
        )

    outcome = _run_red_flags(session, dependencies)
    session.log(
        EventType.RULES_EVALUATED,
        actor="red_flag_engine",
        occurred_at=now,
        payload={"fired": list(outcome.rule_ids)},
    )

    if outcome.terminates_session:
        session.status = SessionStatus.TERMINATED_EMERGENCY
        session.log(
            EventType.SESSION_TERMINATED,
            actor="red_flag_engine",
            occurred_at=now,
            payload={"rules": list(outcome.terminating_rule_ids)},
        )
        return TurnResult(
            shape=TurnShape.TERMINAL_EMERGENCY,
            session_id=session.id,
            turn_index=session.turn_index,
            emergency=outcome,
            dropped_claims=dropped,
        )

    sufficiency = assess(session.record, registry) if registry else None
    if sufficiency is not None and sufficiency.complete:
        return complete(session, dependencies, now, dropped)

    prompt = dependencies.prompts["intake_agent"]
    question = intake.next_question(
        dependencies.provider,
        prompt,
        record=session.record,
        registry=registry,
        sufficiency=sufficiency,
        transcript=tuple(session.transcript),
    )
    if question.complaint_family is not None and registry is None:
        session.record = session.record.model_copy(
            update={
                "consult": ConsultContext(
                    complaint_family=question.complaint_family,
                    is_proxy=session.record.consult.is_proxy,
                    pregnancy_status=session.record.consult.pregnancy_status,
                )
            }
        )
    session.transcript.append((question.utterance, utterance))
    session.log(
        EventType.MODEL_CALLED,
        actor="intake_agent",
        occurred_at=now,
        payload={"field_targeted": question.field_targeted},
        prompt_version=prompt.version,
    )
    return TurnResult(
        shape=TurnShape.NEXT_QUESTION,
        session_id=session.id,
        turn_index=session.turn_index,
        question=question.utterance,
        dropped_claims=dropped,
    )


def complete(
    session: Session,
    dependencies: Dependencies,
    now: datetime,
    dropped: int = 0,
) -> TurnResult:
    """Run triage and the safety critic on the current record.

    Called when sufficiency is met, or forced by the caller. The critic runs on
    every case rather than only high-stakes bands, because deciding which cases
    are high-stakes is the judgement the critic exists to check.
    """
    outcome = _run_red_flags(session, dependencies)
    registry = _registry_for(session, dependencies)
    sufficiency = assess(session.record, registry) if registry else None

    triage_prompt = dependencies.prompts["triage_agent"]
    result = triage.assess(
        dependencies.provider, triage_prompt, session.record, sufficiency, outcome
    )
    session.log(
        EventType.BAND_ASSIGNED,
        actor="triage_agent",
        occurred_at=now,
        payload={"band": result.band.value, "specialty": result.specialty.value},
        prompt_version=triage_prompt.version,
    )

    critic_prompt = dependencies.prompts["safety_critic"]
    review = critic.critique(
        dependencies.provider, critic_prompt, session.record, result, outcome
    )
    if review.escalated:
        result = result.model_copy(
            update={"band": review.final_band, "critic_raised_from": review.original_band}
        )
        session.log(
            EventType.BAND_ESCALATED,
            actor="safety_critic",
            occurred_at=now,
            payload={
                "from": review.original_band.value,
                "to": review.final_band.value,
                "reason": review.reason,
            },
            prompt_version=critic_prompt.version,
        )

    session.status = (
        SessionStatus.TERMINATED_EMERGENCY
        if result.band is Band.U1
        else SessionStatus.COMPLETED
    )
    return TurnResult(
        shape=TurnShape.COMPLETED_TRIAGE,
        session_id=session.id,
        turn_index=session.turn_index,
        triage=result,
        dropped_claims=dropped,
    )
