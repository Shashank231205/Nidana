"""Evaluating rule sets against a record.

Pure. Record and rule set in, firings out. No I/O, no clock reads, no
randomness, which is what makes the rules exhaustively testable.

The engine knows nothing about red flags, urgency, or drug interactions. It
resolves atoms, evaluates clauses, and reports which rules fired and why. What a
firing means is the service's to decide.
"""

from __future__ import annotations

from typing import Generic

from pydantic import BaseModel, ConfigDict

from spine.rules.predicates import evaluate
from spine.schemas.predicate import Predicate
from spine.schemas.record import Record
from spine.schemas.rule import ActionT, Clause, Rule, RuleSet


class UnresolvedAtomError(RuntimeError):
    """Raised when a rule references a predicate that was never loaded.

    This is a load-time failure surfaced at evaluation time. It never returns
    False, because a rule that silently cannot fire is the defect ADR 0005
    exists to prevent.
    """


class Firing(BaseModel, Generic[ActionT]):
    """One rule that held, with the evidence for why.

    `matched_atoms` records which predicates were true, so the audit log can
    reconstruct the decision rather than asserting it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    label: str
    action: ActionT
    matched_atoms: tuple[str, ...]
    escalating_atoms: tuple[str, ...] = ()
    source: str
    unverified: bool

    @property
    def is_escalated(self) -> bool:
        return bool(self.escalating_atoms)


def _resolve(atom: str, predicates: dict[str, Predicate], rule_id: str) -> Predicate:
    predicate = predicates.get(atom)
    if predicate is None:
        raise UnresolvedAtomError(
            f"rule {rule_id} references predicate {atom!r}, which is not loaded. The "
            f"rule cannot fire and would report green on its negative tests. Define it "
            f"in the service's rules/predicates/, or correct the atom name"
        )
    return predicate


def _clause_holds(
    clause: Clause,
    record: Record,
    predicates: dict[str, Predicate],
    rule_id: str,
) -> bool:
    return all(
        evaluate(_resolve(atom, predicates, rule_id), record) for atom in clause.all_of
    )


def _matched_atoms(
    clause: Clause,
    record: Record,
    predicates: dict[str, Predicate],
    rule_id: str,
) -> tuple[str, ...]:
    return tuple(
        atom
        for atom in clause.all_of
        if evaluate(_resolve(atom, predicates, rule_id), record)
    )


def _escalating_atoms(
    rule: Rule[ActionT],
    record: Record,
    predicates: dict[str, Predicate],
) -> tuple[str, ...]:
    return tuple(
        atom
        for atom in rule.modifiers.escalate_if
        if evaluate(_resolve(atom, predicates, rule.id), record)
    )


def evaluate_rule(
    rule: Rule[ActionT],
    record: Record,
    predicates: dict[str, Predicate],
) -> Firing[ActionT] | None:
    """Whether `rule` holds for `record`, and the atoms that made it hold.

    Returns the first satisfied clause's atoms. A rule that fires by two routes
    is still one firing; the clause that matched first is the one recorded.
    """
    for clause in rule.any_of:
        if _clause_holds(clause, record, predicates, rule.id):
            return Firing[ActionT](
                rule_id=rule.id,
                label=rule.label,
                action=rule.action,
                matched_atoms=_matched_atoms(clause, record, predicates, rule.id),
                escalating_atoms=_escalating_atoms(rule, record, predicates),
                source=rule.source,
                unverified=rule.is_unverified,
            )
    return None


def evaluate_rule_set(
    rule_set: RuleSet[ActionT],
    record: Record,
    predicates: dict[str, Predicate],
) -> tuple[Firing[ActionT], ...]:
    """Every rule in `rule_set` that holds for `record`, in rule-set order.

    Every rule is evaluated. There is no short-circuit on the first firing,
    because a second firing may require a capability the first does not.
    """
    firings = (evaluate_rule(rule, record, predicates) for rule in rule_set.rules)
    return tuple(firing for firing in firings if firing is not None)
