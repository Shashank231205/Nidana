"""The Forensics structuring gate.

Stricter than the other services' gates in one respect: provenance here is the
examiner's own entry, and a model cannot author one. Every injury this builder
produces is attributed to the examiner who dictated it.

A medico-legal record is read years later by someone looking for the seam. A
measurement the model rounded, a laterality it inferred, or a wound age it
estimated is that seam, so each has a test.
"""

from __future__ import annotations

from services.forensics.agents.injury_builder import BuildResult, build
from spine.schemas.forensic import (
    DraftInjury,
    ExaminationDraft,
    InjuryType,
    WoundAge,
)
from spine.schemas.provenance import ExaminerEntry

DICTATION = (
    "On the left forearm there is an abrasion measuring 3 cm by 1 cm, situated "
    "8 cm below the olecranon. There is a contusion on the right cheek, roughly "
    "two to three centimetres across, bluish black in colour."
)

EXAMINER = "dr_forensic_1"


def draft(*claims: DraftInjury) -> ExaminationDraft:
    return ExaminationDraft(injuries=claims)


def built(*claims: DraftInjury) -> BuildResult:
    return build(draft(*claims), DICTATION, "exam-1", EXAMINER)


class TestGroundedness:
    def test_a_dictated_injury_is_kept(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
            )
        )
        assert len(result.injuries) == 1
        assert result.fabrication_count == 0

    def test_an_injury_not_dictated_is_dropped(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.STAB,
                site="abdomen",
                source_span="a stab wound to the abdomen",
            )
        )
        assert not result.injuries
        assert result.fabrication_count == 1

    def test_the_drop_reason_says_quote_rather_than_summarise(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.STAB,
                site="abdomen",
                source_span="a stab wound to the abdomen",
            )
        )
        assert "not summarise it" in result.dropped[0].reason

    def test_an_empty_draft_produces_nothing(self) -> None:
        result = build(ExaminationDraft(), DICTATION, "exam-1", EXAMINER)
        assert result.injuries == ()


class TestProvenanceIsTheExaminers:
    def test_every_injury_is_attributed_to_the_examiner(self) -> None:
        """A model cannot be the source of a medico-legal finding."""
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
            )
        )
        provenance = result.injuries[0].provenance
        assert isinstance(provenance, ExaminerEntry)
        assert provenance.examiner_id == EXAMINER

    def test_the_provenance_text_is_what_the_examiner_said(self) -> None:
        span = "an abrasion measuring 3 cm by 1 cm"
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION, site="left forearm", source_span=span
            )
        )
        assert result.injuries[0].provenance.text == span


class TestMeasurements:
    def test_a_plain_measurement_parses(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
                length_cm="3 cm",
                width_cm="1 cm",
            )
        )
        assert result.injuries[0].length_cm == 3.0
        assert result.injuries[0].width_cm == 1.0

    def test_a_written_measurement_parses(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
                length_cm="3.5 centimetres",
            )
        )
        assert result.injuries[0].length_cm == 3.5

    def test_an_approximation_is_left_absent_rather_than_averaged(self) -> None:
        """'Two to three centimetres' is not 2.5cm, and in court it would be."""
        result = built(
            DraftInjury(
                injury_type=InjuryType.CONTUSION,
                site="right cheek",
                source_span="a contusion on the right cheek",
                length_cm="two to three centimetres",
            )
        )
        assert result.injuries[0].length_cm is None

    def test_a_hedged_measurement_is_left_absent(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.CONTUSION,
                site="right cheek",
                source_span="a contusion on the right cheek",
                length_cm="about 3",
            )
        )
        assert result.injuries[0].length_cm is None


class TestLandmark:
    def test_a_distance_with_its_landmark_is_kept(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="situated 8 cm below the olecranon",
                landmark="olecranon",
                landmark_distance_cm="8 cm",
            )
        )
        assert result.injuries[0].landmark_distance_cm == 8.0
        assert result.injuries[0].landmark == "olecranon"

    def test_a_distance_without_a_landmark_is_refused(self) -> None:
        """A measurement from an unstated point cannot be reproduced."""
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
                landmark_distance_cm="5 cm",
            )
        )
        assert not result.injuries
        assert "names no landmark" in result.dropped[0].reason

    def test_an_approximate_distance_leaves_the_landmark_alone(self) -> None:
        """The distance drops out; the landmark the examiner named stays."""
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
                landmark="olecranon",
                landmark_distance_cm="about 5",
            )
        )
        assert result.injuries[0].landmark_distance_cm is None
        assert result.injuries[0].landmark == "olecranon"


class TestWoundAge:
    def test_an_unstated_age_stays_indeterminate(self) -> None:
        """Dating a bruise by colour does not survive cross-examination."""
        result = built(
            DraftInjury(
                injury_type=InjuryType.CONTUSION,
                site="right cheek",
                source_span="a contusion on the right cheek",
                margins="bluish black",
            )
        )
        assert result.injuries[0].estimated_age is WoundAge.INDETERMINATE

    def test_a_stated_age_is_carried_through(self) -> None:
        result = built(
            DraftInjury(
                injury_type=InjuryType.ABRASION,
                site="left forearm",
                source_span="an abrasion measuring 3 cm by 1 cm",
                estimated_age=WoundAge.FRESH,
            )
        )
        assert result.injuries[0].estimated_age is WoundAge.FRESH
