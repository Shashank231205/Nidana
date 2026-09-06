"""Evaluating predicates against a record.

Pure: record and predicate in, boolean out. No I/O, no clock, no randomness.

Every predicate evaluates over the record's *latest* statement about a field.
A patient who revises an answer leaves both findings, and rules act on the
correction rather than the superseded original.
"""

from __future__ import annotations

from packages.schemas.finding import Finding
from packages.schemas.predicate import Comparator, Predicate, PredicateOperand
from packages.schemas.primitives import Quantity
from packages.schemas.record import Record

DEMOGRAPHIC_FIELDS = frozenset({"age_years", "sex", "pregnancy_status", "is_proxy"})


class PredicateEvaluationError(ValueError):
    """Raised when a predicate cannot be evaluated against the value it found."""


def _comparable_value(finding: Finding) -> PredicateOperand:
    """The scalar a predicate compares against.

    A Quantity compares by magnitude. Unit reconciliation is the registry's job:
    a field declares one unit and findings for it carry that unit.
    """
    if isinstance(finding.value, Quantity):
        return finding.value.value
    return finding.value


def _record_value(record: Record, field: str) -> PredicateOperand | None:
    """The current value of `field`, from demographics or the findings.

    Returns None when the field was never recorded, which is the derived
    'never asked' of ADR 0003.
    """
    if field in DEMOGRAPHIC_FIELDS:
        return _demographic_value(record, field)
    latest = record.latest_finding_for(field)
    if latest is None:
        return None
    if latest.negated:
        return False
    return _comparable_value(latest)


def _demographic_value(record: Record, field: str) -> PredicateOperand | None:
    if field == "age_years":
        return record.demographics.age_years
    if field == "sex":
        return record.demographics.sex.value
    if field == "is_proxy":
        return record.consult.is_proxy
    return record.consult.pregnancy_status.value


def _as_number(value: PredicateOperand, predicate: Predicate) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PredicateEvaluationError(
            f"predicate {predicate.id!r} compares {predicate.field!r} numerically but the "
            f"record holds {value!r}; check the field type in its registry file"
        )
    return float(value)


def evaluate(predicate: Predicate, record: Record) -> bool:
    """Whether `predicate` holds for `record`.

    A field the record does not carry evaluates False for every comparator
    except is_false, which is also False: absence is not a denial. Only an
    explicit negated finding makes is_false true.
    """
    value = _record_value(record, predicate.field)
    if value is None:
        return False
    if predicate.comparator is Comparator.IS_PRESENT:
        return True
    if predicate.comparator is Comparator.IS_TRUE:
        return value is True
    if predicate.comparator is Comparator.IS_FALSE:
        return value is False
    if predicate.comparator is Comparator.EQUALS:
        return value == predicate.value
    if predicate.comparator is Comparator.IN:
        return value in predicate.values
    operand = _as_number(predicate.value, predicate) if predicate.value is not None else 0.0
    number = _as_number(value, predicate)
    if predicate.comparator is Comparator.GREATER_THAN:
        return number > operand
    if predicate.comparator is Comparator.LESS_THAN:
        return number < operand
    if predicate.comparator is Comparator.AT_LEAST:
        return number >= operand
    return number <= operand


def evaluate_any(predicates: tuple[Predicate, ...], record: Record) -> bool:
    return any(evaluate(p, record) for p in predicates)


def evaluate_all(predicates: tuple[Predicate, ...], record: Record) -> bool:
    """Whether every predicate holds. Vacuously true for an empty set.

    Rule loading rejects an empty clause, so this never runs on one in practice.
    """
    return all(evaluate(p, record) for p in predicates)
