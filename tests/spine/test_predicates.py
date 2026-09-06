"""Predicate evaluation, including the distinction ADR 0003 exists to protect.

The case that matters most: a field the patient denied and a field nobody asked
about must not evaluate the same way. A rule firing on the absence of a symptom
would otherwise fire on a question the conversation never reached.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from spine.rules.predicates import (
    PredicateEvaluationError,
    evaluate,
    evaluate_all,
    evaluate_any,
)
from spine.schemas.finding import Finding
from spine.schemas.predicate import Comparator, Predicate
from spine.schemas.primitives import Confidence, PregnancyStatus, Quantity, Sex
from spine.schemas.provenance import locate_utterance
from spine.schemas.record import ConsultContext, Demographics, Record, SubjectType

UTTERANCE = "chest pain since 6 hours, goes to jaw, no sweating, feeling breathless"


def finding(
    field: str,
    value: str | float | int | bool | Quantity,
    quote: str,
    turn: int = 1,
    *,
    negated: bool = False,
    confidence: Confidence = Confidence.HIGH,
) -> Finding:
    return Finding(
        field=field,
        value=value,
        provenance=locate_utterance(
            source_id="u1", source_text=UTTERANCE, quote=quote, turn_index=turn
        ),
        confidence=confidence,
        negated=negated,
    )


def record_with(*findings: Finding, age: int | None = 54, sex: Sex = Sex.MALE) -> Record:
    return Record(
        subject_type=SubjectType.SESSION,
        subject_id=uuid4(),
        demographics=Demographics(age_years=age, sex=sex),
    ).with_findings(*findings)


def predicate(comparator: Comparator, field: str = "diaphoresis", **kwargs: object) -> Predicate:
    return Predicate.model_validate({"id": "p", "field": field, "comparator": comparator, **kwargs})


class TestAbsenceIsNotDenial:
    """ADR 0003. The clinical distinction that must survive every refactor."""

    def test_denied_field_is_false(self) -> None:
        record = record_with(finding("diaphoresis", False, "no sweating", negated=True))
        assert evaluate(predicate(Comparator.IS_FALSE), record) is True

    def test_denied_field_is_not_true(self) -> None:
        record = record_with(finding("diaphoresis", False, "no sweating", negated=True))
        assert evaluate(predicate(Comparator.IS_TRUE), record) is False

    def test_never_asked_field_is_not_true(self) -> None:
        assert evaluate(predicate(Comparator.IS_TRUE), record_with()) is False

    def test_never_asked_field_is_not_false_either(self) -> None:
        assert evaluate(predicate(Comparator.IS_FALSE), record_with()) is False

    @pytest.mark.parametrize(
        "comparator",
        [
            Comparator.IS_PRESENT,
            Comparator.IS_TRUE,
            Comparator.IS_FALSE,
            Comparator.EQUALS,
            Comparator.IN,
            Comparator.GREATER_THAN,
            Comparator.LESS_THAN,
            Comparator.AT_LEAST,
            Comparator.AT_MOST,
        ],
    )
    def test_no_comparator_fires_on_an_unrecorded_field(self, comparator: Comparator) -> None:
        operands: dict[str, object] = {}
        if comparator is Comparator.IN:
            operands = {"values": ["jaw"]}
        elif comparator is Comparator.EQUALS:
            operands = {"value": "jaw"}
        elif comparator not in {
            Comparator.IS_PRESENT,
            Comparator.IS_TRUE,
            Comparator.IS_FALSE,
        }:
            operands = {"value": 1}
        unasked = predicate(comparator, "never_asked_field", **operands)
        assert evaluate(unasked, record_with()) is False


class TestComparators:
    def test_is_present_fires_on_any_recorded_value(self) -> None:
        record = record_with(finding("radiation", "jaw", "goes to jaw"))
        assert evaluate(predicate(Comparator.IS_PRESENT, "radiation"), record) is True

    def test_equals_matches_an_enum_value(self) -> None:
        record = record_with(finding("radiation", "jaw", "goes to jaw"))
        p = predicate(Comparator.EQUALS, "radiation", value="jaw")
        assert evaluate(p, record) is True

    def test_equals_rejects_a_different_value(self) -> None:
        record = record_with(finding("radiation", "back", "goes to jaw"))
        p = predicate(Comparator.EQUALS, "radiation", value="jaw")
        assert evaluate(p, record) is False

    def test_in_matches_any_listed_value(self) -> None:
        record = record_with(finding("radiation", "jaw", "goes to jaw"))
        p = predicate(Comparator.IN, "radiation", values=["jaw", "left_arm"])
        assert evaluate(p, record) is True

    def test_in_rejects_an_unlisted_value(self) -> None:
        record = record_with(finding("radiation", "back", "goes to jaw"))
        p = predicate(Comparator.IN, "radiation", values=["jaw", "left_arm"])
        assert evaluate(p, record) is False

    def test_is_true_fires_on_an_affirmed_boolean(self) -> None:
        record = record_with(finding("dyspnoea", True, "feeling breathless"))
        assert evaluate(predicate(Comparator.IS_TRUE, "dyspnoea"), record) is True


class TestNumericComparison:
    """Boundary cases. A threshold that is off by one is off by a patient."""

    @pytest.mark.parametrize(
        ("comparator", "threshold", "actual", "expected"),
        [
            (Comparator.GREATER_THAN, 40, 41, True),
            (Comparator.GREATER_THAN, 40, 40, False),
            (Comparator.GREATER_THAN, 40, 39, False),
            (Comparator.LESS_THAN, 18, 17, True),
            (Comparator.LESS_THAN, 18, 18, False),
            (Comparator.LESS_THAN, 18, 19, False),
            (Comparator.AT_LEAST, 38, 38, True),
            (Comparator.AT_LEAST, 38, 37, False),
            (Comparator.AT_LEAST, 38, 39, True),
            (Comparator.AT_MOST, 12, 12, True),
            (Comparator.AT_MOST, 12, 13, False),
            (Comparator.AT_MOST, 12, 11, True),
        ],
    )
    def test_boundaries(
        self, comparator: Comparator, threshold: float, actual: float, expected: bool
    ) -> None:
        record = record_with(age=int(actual))
        p = predicate(comparator, "age_years", value=threshold)
        assert evaluate(p, record) is expected

    def test_quantity_compares_by_magnitude(self) -> None:
        record = record_with(
            finding("onset_duration_hours", Quantity(value=6, unit="hours"), "6 hours")
        )
        p = predicate(Comparator.AT_MOST, "onset_duration_hours", value=12)
        assert evaluate(p, record) is True

    def test_comparing_a_string_field_numerically_raises_and_names_the_remedy(self) -> None:
        record = record_with(finding("radiation", "jaw", "goes to jaw"))
        p = predicate(Comparator.GREATER_THAN, "radiation", value=3)
        with pytest.raises(PredicateEvaluationError, match="registry file"):
            evaluate(p, record)

    def test_a_boolean_is_not_a_number(self) -> None:
        record = record_with(finding("dyspnoea", True, "feeling breathless"))
        p = predicate(Comparator.GREATER_THAN, "dyspnoea", value=0)
        with pytest.raises(PredicateEvaluationError):
            evaluate(p, record)


class TestDemographicFields:
    def test_age_reads_from_demographics(self) -> None:
        p = predicate(Comparator.GREATER_THAN, "age_years", value=40)
        assert evaluate(p, record_with(age=54)) is True

    def test_unrecorded_age_does_not_fire(self) -> None:
        p = predicate(Comparator.GREATER_THAN, "age_years", value=40)
        assert evaluate(p, record_with(age=None)) is False

    def test_sex_reads_from_demographics(self) -> None:
        p = predicate(Comparator.EQUALS, "sex", value="female")
        assert evaluate(p, record_with(sex=Sex.FEMALE)) is True

    def test_pregnancy_status_reads_from_the_consult_context(self) -> None:
        record = Record(
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            consult=ConsultContext(pregnancy_status=PregnancyStatus.CONFIRMED),
        )
        p = predicate(Comparator.IN, "pregnancy_status", values=["possible", "confirmed"])
        assert evaluate(p, record) is True

    def test_unknown_pregnancy_status_does_not_fire(self) -> None:
        p = predicate(Comparator.IN, "pregnancy_status", values=["possible", "confirmed"])
        assert evaluate(p, record_with()) is False

    def test_proxy_flag_reads_from_the_consult_context(self) -> None:
        record = Record(
            subject_type=SubjectType.SESSION,
            subject_id=uuid4(),
            consult=ConsultContext(is_proxy=True),
        )
        assert evaluate(predicate(Comparator.IS_TRUE, "is_proxy"), record) is True


class TestCorrections:
    """A patient who revises an answer is evaluated on the correction."""

    def test_the_latest_finding_wins(self) -> None:
        record = record_with(
            finding("radiation", "none", "goes to jaw", turn=1),
            finding("radiation", "jaw", "goes to jaw", turn=4),
        )
        p = predicate(Comparator.EQUALS, "radiation", value="jaw")
        assert evaluate(p, record) is True

    def test_the_superseded_finding_is_retained(self) -> None:
        record = record_with(
            finding("radiation", "none", "goes to jaw", turn=1),
            finding("radiation", "jaw", "goes to jaw", turn=4),
        )
        assert len(record.findings_for("radiation")) == 2

    def test_a_later_denial_overrides_an_earlier_affirmation(self) -> None:
        record = record_with(
            finding("diaphoresis", True, "no sweating", turn=1),
            finding("diaphoresis", False, "no sweating", turn=3, negated=True),
        )
        assert evaluate(predicate(Comparator.IS_TRUE), record) is False
        assert evaluate(predicate(Comparator.IS_FALSE), record) is True


class TestCombinators:
    def test_any_fires_when_one_holds(self) -> None:
        record = record_with(finding("dyspnoea", True, "feeling breathless"))
        predicates = (
            predicate(Comparator.IS_TRUE, "diaphoresis"),
            predicate(Comparator.IS_TRUE, "dyspnoea"),
        )
        assert evaluate_any(predicates, record) is True

    def test_any_is_false_when_none_hold(self) -> None:
        predicates = (
            predicate(Comparator.IS_TRUE, "diaphoresis"),
            predicate(Comparator.IS_TRUE, "dyspnoea"),
        )
        assert evaluate_any(predicates, record_with()) is False

    def test_all_requires_every_predicate(self) -> None:
        record = record_with(finding("dyspnoea", True, "feeling breathless"))
        predicates = (
            predicate(Comparator.IS_TRUE, "diaphoresis"),
            predicate(Comparator.IS_TRUE, "dyspnoea"),
        )
        assert evaluate_all(predicates, record) is False

    def test_all_holds_when_every_predicate_does(self) -> None:
        record = record_with(
            finding("dyspnoea", True, "feeling breathless"),
            finding("radiation", "jaw", "goes to jaw"),
        )
        predicates = (
            predicate(Comparator.IS_TRUE, "dyspnoea"),
            predicate(Comparator.EQUALS, "radiation", value="jaw"),
        )
        assert evaluate_all(predicates, record) is True

    def test_all_is_vacuously_true_on_an_empty_clause(self) -> None:
        assert evaluate_all((), record_with()) is True

    def test_any_is_false_on_an_empty_clause(self) -> None:
        assert evaluate_any((), record_with()) is False
