"""Medico-legal records and the custody chain.

The only service whose primary consumer is a court. Two things are tested
harder here than anywhere else: that nothing is generated, and that the chain
detects alteration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from services.forensics.clinical.custody import (
    CustodyAction,
    CustodyChainError,
    accesses_by,
    actors,
    amendments,
    record,
    verify_chain,
    was_amended_after_finalisation,
)
from spine.schemas.forensic import (
    ExaminationStatus,
    Injury,
    InjuryType,
    MedicoLegalReport,
    Photograph,
    WoundAge,
)
from spine.schemas.provenance import ExaminerEntry

WHEN = datetime(2026, 9, 7, 14, 0, tzinfo=timezone.utc)
LATER = datetime(2026, 9, 7, 15, 0, tzinfo=timezone.utc)


def entry(examination_id: str, path: str, text: str) -> ExaminerEntry:
    return ExaminerEntry(
        source_id=examination_id, examiner_id="dr_k", text=text, field_path=path
    )


def injury(
    examination_id: str,
    *,
    complete: bool = True,
    photographs: tuple[str, ...] = (),
) -> Injury:
    described = entry(examination_id, "injuries[0]", "laceration left forearm")
    if not complete:
        return Injury(
            injury_type=InjuryType.LACERATION,
            site="left forearm",
            provenance=described,
            photograph_ids=photographs,
        )
    return Injury(
        injury_type=InjuryType.LACERATION,
        site="left forearm",
        landmark="olecranon",
        landmark_distance_cm=6.0,
        length_cm=4.2,
        width_cm=0.8,
        shape="linear",
        margins="clean-cut",
        direction="oblique",
        estimated_age=WoundAge.FRESH,
        provenance=described,
        photograph_ids=photographs,
    )


def photograph(identifier: str = "P1", *, scale: bool = True) -> Photograph:
    return Photograph(
        photograph_id=identifier,
        sha256="a" * 64,
        taken_at=WHEN,
        scale_reference_present=scale,
        taken_by="dr_k",
    )


class TestNothingIsGenerated:
    """The rule the service exists to hold."""

    def test_an_injury_traces_to_an_examiner_entry(self) -> None:
        described = injury(str(uuid4()))
        assert described.provenance.examiner_id == "dr_k"

    def test_a_measurement_must_name_what_it_was_measured_from(self) -> None:
        """A distance from an unstated point cannot be reproduced or challenged."""
        examination_id = str(uuid4())
        with pytest.raises(ValueError, match="names no landmark"):
            Injury(
                injury_type=InjuryType.LACERATION,
                site="left forearm",
                landmark_distance_cm=6.0,
                provenance=entry(examination_id, "injuries[0]", "x"),
            )

    def test_missing_fields_are_listed_rather_than_filled(self) -> None:
        thin = injury(str(uuid4()), complete=False)
        assert not thin.is_complete
        assert "length_cm" in thin.missing_fields
        assert "margins" in thin.missing_fields

    def test_an_indeterminate_wound_age_counts_as_missing(self) -> None:
        thin = injury(str(uuid4()), complete=False)
        assert "estimated_age" in thin.missing_fields

    def test_a_complete_injury_lists_nothing_missing(self) -> None:
        assert injury(str(uuid4())).missing_fields == ()


class TestReportIntegrity:
    def test_a_photograph_reference_must_resolve(self) -> None:
        """A citation to evidence not attached cannot be produced in court."""
        examination_id = uuid4()
        with pytest.raises(ValueError, match="does not carry"):
            MedicoLegalReport(
                examination_id=examination_id,
                examiner_id="dr_k",
                examined_at=WHEN,
                injuries=(injury(str(examination_id), photographs=("P1",)),),
            )

    def test_a_resolving_reference_is_accepted(self) -> None:
        examination_id = uuid4()
        report = MedicoLegalReport(
            examination_id=examination_id,
            examiner_id="dr_k",
            examined_at=WHEN,
            injuries=(injury(str(examination_id), photographs=("P1",)),),
            photographs=(photograph(),),
        )
        assert report.is_finalisable

    def test_an_incomplete_injury_blocks_finalisation(self) -> None:
        examination_id = uuid4()
        report = MedicoLegalReport(
            examination_id=examination_id,
            examiner_id="dr_k",
            examined_at=WHEN,
            injuries=(injury(str(examination_id), complete=False),),
        )
        assert not report.is_finalisable
        assert report.blocking_gaps

    def test_the_gap_names_the_injury_and_the_fields(self) -> None:
        """A missing field is what gets exploited in cross-examination."""
        examination_id = uuid4()
        report = MedicoLegalReport(
            examination_id=examination_id,
            examiner_id="dr_k",
            examined_at=WHEN,
            injuries=(injury(str(examination_id), complete=False),),
        )
        gap = report.blocking_gaps[0]
        assert "left forearm" in gap
        assert "margins" in gap

    def test_a_photograph_without_a_scale_is_flagged(self) -> None:
        examination_id = uuid4()
        report = MedicoLegalReport(
            examination_id=examination_id,
            examiner_id="dr_k",
            examined_at=WHEN,
            injuries=(injury(str(examination_id)),),
            photographs=(photograph(scale=False),),
        )
        assert report.photographs_without_scale
        assert not report.is_finalisable

    def test_a_photograph_without_a_scale_is_kept_not_discarded(self) -> None:
        """It still evidences appearance, and discarding it would lose that."""
        assert photograph(scale=False).photograph_id == "P1"

    def test_an_empty_report_cannot_be_finalised(self) -> None:
        report = MedicoLegalReport(
            examination_id=uuid4(), examiner_id="dr_k", examined_at=WHEN
        )
        assert "no injuries documented" in report.blocking_gaps

    def test_a_finalised_report_must_be_signed(self) -> None:
        with pytest.raises(ValueError, match="examiner's signature"):
            MedicoLegalReport(
                examination_id=uuid4(),
                examiner_id="dr_k",
                examined_at=WHEN,
                status=ExaminationStatus.FINALISED,
                finalised_at=LATER,
            )

    def test_a_finalised_report_records_when(self) -> None:
        with pytest.raises(ValueError, match="records when it was finalised"):
            MedicoLegalReport(
                examination_id=uuid4(),
                examiner_id="dr_k",
                examined_at=WHEN,
                status=ExaminationStatus.FINALISED,
                signature="dr_k:sig",
            )


class TestConsistencyFraming:
    def test_findings_are_framed_as_consistent_with(self) -> None:
        """Never a conclusion about what happened."""
        examination_id = uuid4()
        report = MedicoLegalReport(
            examination_id=examination_id,
            examiner_id="dr_k",
            examined_at=WHEN,
            injuries=(injury(str(examination_id)),),
            consistent_with=("blunt force trauma",),
            not_consistent_with=("firearm discharge",),
        )
        assert report.consistent_with == ("blunt force trauma",)
        assert report.not_consistent_with == ("firearm discharge",)

    def test_what_the_findings_argue_against_is_recorded(self) -> None:
        """Often the more useful half in court."""
        examination_id = uuid4()
        report = MedicoLegalReport(
            examination_id=examination_id,
            examiner_id="dr_k",
            examined_at=WHEN,
            injuries=(injury(str(examination_id)),),
            not_consistent_with=("self-inflicted",),
        )
        assert report.not_consistent_with


class TestEvidentialIsolation:
    def test_the_report_holds_no_reference_to_other_services(self) -> None:
        """Contamination from other sources is an attack surface in court."""
        fields = set(MedicoLegalReport.model_fields)
        assert not {
            "consult_session_id",
            "encounter_id",
            "prescription_id",
            "report_id",
        } & fields


class TestCustodyChain:
    def test_a_chain_of_accesses_verifies(self) -> None:
        examination_id = uuid4()
        first = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        second = record(
            first,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="registrar_p",
            occurred_at=LATER,
        )
        verify_chain((first, second))

    def test_reads_are_logged_not_only_writes(self) -> None:
        """A record read by someone with no role in the case is a custody problem."""
        examination_id = uuid4()
        viewed = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="registrar_p",
            occurred_at=WHEN,
        )
        assert viewed.payload["action"] == "viewed"

    def test_an_amendment_must_state_a_reason(self) -> None:
        with pytest.raises(CustodyChainError, match="distinguished from tampering"):
            record(
                None,
                examination_id=uuid4(),
                action=CustodyAction.AMENDED,
                actor="dr_k",
                occurred_at=WHEN,
            )

    def test_an_amendment_with_a_reason_is_recorded(self) -> None:
        amended = record(
            None,
            examination_id=uuid4(),
            action=CustodyAction.AMENDED,
            actor="dr_k",
            occurred_at=WHEN,
            reason="site corrected from right to left forearm",
        )
        assert "corrected" in str(amended.payload["reason"])

    def test_tampering_breaks_the_chain(self) -> None:
        examination_id = uuid4()
        first = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        second = record(
            first,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="registrar_p",
            occurred_at=LATER,
        )
        forged = second.model_copy(update={"actor": "nobody"})
        with pytest.raises(CustodyChainError, match="should not be produced as evidence"):
            verify_chain((first, forged))

    def test_the_violation_names_where_the_break_is(self) -> None:
        examination_id = uuid4()
        first = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        second = record(
            first,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="registrar_p",
            occurred_at=LATER,
        )
        with pytest.raises(CustodyChainError, match="entry 1"):
            verify_chain((first, second.model_copy(update={"actor": "nobody"})))

    def test_every_actor_is_listed_in_order_of_first_access(self) -> None:
        examination_id = uuid4()
        first = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        second = record(
            first,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="registrar_p",
            occurred_at=LATER,
        )
        third = record(
            second,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="dr_k",
            occurred_at=LATER,
        )
        assert actors((first, second, third)) == ("dr_k", "registrar_p")

    def test_accesses_can_be_filtered_by_actor(self) -> None:
        examination_id = uuid4()
        first = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        second = record(
            first,
            examination_id=examination_id,
            action=CustodyAction.VIEWED,
            actor="registrar_p",
            occurred_at=LATER,
        )
        assert len(accesses_by((first, second), "registrar_p")) == 1

    def test_an_amendment_after_finalisation_is_computed_not_left_to_be_noticed(
        self,
    ) -> None:
        examination_id = uuid4()
        created = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        finalised = record(
            created,
            examination_id=examination_id,
            action=CustodyAction.FINALISED,
            actor="dr_k",
            occurred_at=LATER,
        )
        amended = record(
            finalised,
            examination_id=examination_id,
            action=CustodyAction.AMENDED,
            actor="dr_k",
            occurred_at=LATER,
            reason="typo in site",
        )
        chain = (created, finalised, amended)
        assert was_amended_after_finalisation(chain)
        assert len(amendments(chain)) == 1

    def test_an_amendment_before_finalisation_is_not_flagged(self) -> None:
        examination_id = uuid4()
        created = record(
            None,
            examination_id=examination_id,
            action=CustodyAction.CREATED,
            actor="dr_k",
            occurred_at=WHEN,
        )
        amended = record(
            created,
            examination_id=examination_id,
            action=CustodyAction.AMENDED,
            actor="dr_k",
            occurred_at=LATER,
            reason="typo",
        )
        finalised = record(
            amended,
            examination_id=examination_id,
            action=CustodyAction.FINALISED,
            actor="dr_k",
            occurred_at=LATER,
        )
        assert not was_amended_after_finalisation((created, amended, finalised))

    def test_an_empty_chain_verifies(self) -> None:
        verify_chain(())
