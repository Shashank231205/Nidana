"""The band asymmetry, tested exhaustively rather than asserted by type.

ADR 0004. The input domain is 25 ordered pairs, so 'exhaustive' here is literal.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from itertools import product

import pytest

from services.consult.clinical.bands import (
    BandDeescalationError,
    NoChange,
    RaiseTo,
    apply_verdict,
    escalate_only,
    most_urgent,
)
from spine.schemas.primitives import Band

ALL_BANDS = tuple(Band)
ALL_PAIRS = tuple(product(ALL_BANDS, repeat=2))


def test_the_domain_is_twenty_five_pairs() -> None:
    assert len(ALL_PAIRS) == 25


@pytest.mark.parametrize(("current", "proposed"), ALL_PAIRS)
def test_escalate_only_never_returns_a_less_urgent_band(current: Band, proposed: Band) -> None:
    assert escalate_only(current, proposed).urgency >= current.urgency


@pytest.mark.parametrize(("current", "proposed"), ALL_PAIRS)
def test_escalate_only_returns_the_more_urgent_of_the_two(current: Band, proposed: Band) -> None:
    expected = current if current.urgency >= proposed.urgency else proposed
    assert escalate_only(current, proposed) is expected


@pytest.mark.parametrize(("current", "proposed"), ALL_PAIRS)
def test_escalate_only_is_idempotent(current: Band, proposed: Band) -> None:
    once = escalate_only(current, proposed)
    assert escalate_only(once, proposed) is once


def test_u1_is_the_most_urgent_band() -> None:
    for band in ALL_BANDS:
        assert escalate_only(band, Band.U1) is Band.U1
        assert escalate_only(Band.U1, band) is Band.U1


def test_u5_never_displaces_anything() -> None:
    for band in ALL_BANDS:
        assert escalate_only(band, Band.U5) is band


@pytest.mark.parametrize("band", ALL_BANDS)
def test_no_change_leaves_the_band_standing(band: Band) -> None:
    assert apply_verdict(band, NoChange(reason="critic agrees")) is band


@pytest.mark.parametrize(("current", "target"), ALL_PAIRS)
def test_raise_to_applies_only_when_it_escalates(current: Band, target: Band) -> None:
    verdict = RaiseTo(band=target, reason="critic escalates")
    if target.urgency > current.urgency:
        assert apply_verdict(current, verdict) is target
    else:
        with pytest.raises(BandDeescalationError):
            apply_verdict(current, verdict)


def test_de_escalation_error_names_both_bands_and_the_remedy() -> None:
    with pytest.raises(BandDeescalationError) as caught:
        apply_verdict(Band.U2, RaiseTo(band=Band.U4, reason="attempted downgrade"))
    message = str(caught.value)
    assert "U2" in message
    assert "U4" in message
    assert "NoChange" in message


def test_most_urgent_returns_the_floor_when_nothing_is_supplied() -> None:
    assert most_urgent((), Band.U5) is Band.U5


def test_most_urgent_picks_the_highest_urgency() -> None:
    assert most_urgent((Band.U4, Band.U2, Band.U5), Band.U5) is Band.U2


def test_most_urgent_never_falls_below_its_floor() -> None:
    assert most_urgent((Band.U5, Band.U4), Band.U3) is Band.U3


ORDERING_OPERATORS: tuple[Callable[[Band, Band], bool], ...] = (
    operator.lt,
    operator.gt,
    operator.le,
    operator.ge,
)


@pytest.mark.parametrize("band", ALL_BANDS)
def test_bands_refuse_ordering_comparison(band: Band) -> None:
    for other in ALL_BANDS:
        for compare in ORDERING_OPERATORS:
            with pytest.raises(TypeError, match="opposite directions"):
                compare(band, other)


def test_urgency_ranks_are_distinct_and_ordered_u1_highest() -> None:
    ranks = [band.urgency for band in ALL_BANDS]
    assert len(set(ranks)) == 5
    assert Band.U1.urgency > Band.U2.urgency > Band.U3.urgency
    assert Band.U3.urgency > Band.U4.urgency > Band.U5.urgency


def test_is_more_urgent_than_is_strict() -> None:
    assert not Band.U3.is_more_urgent_than(Band.U3)
    assert Band.U1.is_more_urgent_than(Band.U3)
    assert not Band.U3.is_more_urgent_than(Band.U1)
