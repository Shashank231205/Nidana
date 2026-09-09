"""Declarative rules over predicates.

One engine, several rule sets. Consult contributes red flags, Rx interaction and
duplicate therapy checks, Labs critical value thresholds, Scribe note
completeness, Forensics protocol compliance. Only the rule content and the
action vocabulary differ, so the engine is generic over both.

ADR 0005. A rule references predicates by name. Resolution happens at load time,
and an unresolved atom is a hard failure: a rule that evaluates false forever is
invisible to every gate except a positive vignette that happens to target it.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

ActionT = TypeVar("ActionT", bound=str)


class Clause(BaseModel):
    """A conjunction of predicate ids. Every atom must hold for the clause to.

    An empty clause is rejected rather than treated as vacuously true: a rule
    whose condition is trivially satisfied fires on every record, and one that
    is trivially unsatisfiable fires on none. Both are load-time defects.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    all_of: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _atoms_are_distinct(self) -> Clause:
        if len(set(self.all_of)) != len(self.all_of):
            duplicated = sorted({a for a in self.all_of if self.all_of.count(a) > 1})
            raise ValueError(
                f"clause repeats {', '.join(duplicated)}; a conjunction gains nothing "
                f"from a repeated atom and the duplication is usually a typo for a "
                f"different one"
            )
        return self


class Modifiers(BaseModel):
    """Conditions that change a rule's severity without changing whether it fires.

    `escalate_if` names predicates that make an already-firing rule more urgent.
    It never causes a rule to fire on its own.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    escalate_if: tuple[str, ...] = ()

    @property
    def atoms(self) -> tuple[str, ...]:
        return self.escalate_if


class VerificationState(str, Enum):
    """How far a rule has got toward being safe to ship.

    UNREVIEWED and AI_REVIEWED both block a release. The distinction between
    them is for the humans doing the work — it says whether the reading has
    been done — and never for the gate.
    """

    UNREVIEWED = "unreviewed"
    AI_REVIEWED = "ai_reviewed"
    CLINICIAN_VERIFIED = "clinician_verified"


class AiReview(BaseModel):
    """What an AI panel concluded, and who still has to sign.

    Deliberately carries no field that could be read as approval. There is no
    verdict, no score and no recommendation to ship: a reviewer reads the
    concerns and decides. `refer_to` names the specialty the panel thinks
    should look at it, which is the most useful thing it can offer.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    reviewed_on: date
    models: tuple[str, ...] = Field(min_length=1)
    panel_version: str = Field(min_length=1)
    concerns: tuple[str, ...] = ()
    refer_to: str = Field(
        min_length=1,
        description="The kind of clinician who should review this rule",
    )
    dossier_path: str | None = None

    @property
    def clears_release(self) -> bool:
        """Always false. An AI review is not a signature.

        Stated as a property so that any code tempted to treat a review as
        clearance has to read the word false.
        """
        return False


class Rule(BaseModel, Generic[ActionT]):
    """One declarative rule, generic over its service's action vocabulary.

    Fires when any clause in `any_of` holds. Within a clause, every atom must
    hold. This two-level shape is deliberately shallow: arbitrary nesting makes
    a rule hard to read at 3am and hard to test exhaustively, and no clinical
    criterion so far has needed more depth.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[A-Z][A-Z0-9_]*$")
    label: str = Field(min_length=1)
    any_of: tuple[Clause, ...] = Field(min_length=1)
    modifiers: Modifiers = Modifiers()
    action: ActionT
    source: str = Field(
        min_length=1,
        description="Citation for the clinical criterion this rule encodes",
    )
    verified_on: date | None = Field(
        default=None,
        description="When a qualified clinician last verified this against the source",
    )
    verified_by: str | None = Field(
        default=None,
        description="The named clinician who accepted responsibility for this criterion",
    )
    verify_before_ship: bool = Field(
        default=True,
        description="True until a clinician has signed the criterion off",
    )
    review: AiReview | None = Field(
        default=None,
        description="An AI panel review, which refers the rule to a clinician",
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _verification_state_is_coherent(self) -> Rule[ActionT]:
        if not self.verify_before_ship and self.verified_on is None:
            raise ValueError(
                f"rule {self.id} is marked verified but carries no verified_on date; "
                f"record when a clinician signed the criterion off, or leave "
                f"verify_before_ship true"
            )
        if not self.verify_before_ship and not (self.verified_by or "").strip():
            raise ValueError(
                f"rule {self.id} is marked verified but names no clinician. "
                f"verify_before_ship false means a named, qualified person accepted "
                f"responsibility for this criterion; record who in verified_by"
            )
        return self

    @property
    def atoms(self) -> frozenset[str]:
        """Every predicate id this rule references, condition and modifiers."""
        return frozenset(
            atom for clause in self.any_of for atom in clause.all_of
        ) | frozenset(self.modifiers.atoms)

    @property
    def is_unverified(self) -> bool:
        return self.verify_before_ship

    @property
    def state(self) -> VerificationState:
        """Where this rule sits between untouched and signed off.

        Three states rather than two, because "an AI panel reviewed this and
        refers it to a clinician" is a real and useful thing to have recorded,
        and it is not verification. Collapsing it into either neighbour loses
        information: into UNREVIEWED and the review looks undone, into
        CLINICIAN_VERIFIED and the audit trail claims a doctor approved
        something no doctor read.
        """
        if not self.verify_before_ship:
            return VerificationState.CLINICIAN_VERIFIED
        if self.review is not None:
            return VerificationState.AI_REVIEWED
        return VerificationState.UNREVIEWED

    @property
    def blocks_release(self) -> bool:
        """Whether this rule stops a production build.

        AI_REVIEWED blocks exactly as UNREVIEWED does. The panel shortens a
        clinician's work; it does not stand in for their signature, and a
        release gate that accepted it would be a gate on nothing.
        """
        return self.verify_before_ship


class RuleSet(BaseModel, Generic[ActionT]):
    """A named, versioned collection of rules sharing one action vocabulary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    rules: tuple[Rule[ActionT], ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _rule_ids_are_unique(self) -> RuleSet[ActionT]:
        seen: set[str] = set()
        for rule in self.rules:
            if rule.id in seen:
                raise ValueError(
                    f"rule id {rule.id} appears twice in rule set {self.name}; a firing "
                    f"must identify exactly one rule"
                )
            seen.add(rule.id)
        return self

    @property
    def atoms(self) -> frozenset[str]:
        return frozenset().union(*(rule.atoms for rule in self.rules))

    @property
    def unverified(self) -> tuple[Rule[ActionT], ...]:
        return tuple(rule for rule in self.rules if rule.is_unverified)

    def by_id(self, rule_id: str) -> Rule[ActionT] | None:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None
