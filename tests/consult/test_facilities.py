"""Choosing where to send a patient.

Routing says what a facility must be able to do; this says which ones can. The
tests that matter are the refusals, because every one of them is a case where
answering would be worse than not answering:

A facility meeting three of four requirements is not a 75% match. Sent there,
the patient arrives somewhere that cannot treat them, having travelled past
nothing better but believing they were routed.

An empty result is a real answer. It means no known facility can do this, which
a clinician must act on — transfer further, or treat in place — and it must not
be papered over with the nearest hospital.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from services.consult.clinical.facilities import (
    STALE_AFTER,
    Facility,
    FacilityIndex,
    FacilityIndexError,
    haversine_km,
    load_facility_index,
)
from spine.schemas.triage import Capability

TODAY = date(2026, 9, 9)
HEADER = "id,name,district,latitude,longitude,capabilities,verified_on,phone\n"

# Nagpur, roughly. Distances between these are real enough to order by.
NAGPUR = (21.1458, 79.0882)


def facility(
    identifier: str = "F1",
    *,
    capabilities: tuple[Capability, ...] = (Capability.EMERGENCY_24X7,),
    latitude: float = 21.1458,
    longitude: float = 79.0882,
    verified_on: date = TODAY,
) -> Facility:
    return Facility(
        id=identifier,
        name=f"Hospital {identifier}",
        district="Nagpur",
        latitude=latitude,
        longitude=longitude,
        capabilities=frozenset(capabilities),
        verified_on=verified_on,
    )


def refer(index: FacilityIndex, *required: Capability, today: date = TODAY):  # type: ignore[no-untyped-def]
    return index.refer(
        frozenset(required), latitude=NAGPUR[0], longitude=NAGPUR[1], today=today
    )


class TestMatching:
    def test_a_capable_facility_is_offered(self) -> None:
        index = FacilityIndex((facility(capabilities=(Capability.EMERGENCY_24X7,)),))
        assert refer(index, Capability.EMERGENCY_24X7).found

    def test_every_capability_must_be_present(self) -> None:
        """Three of four is not a partial match. It is the wrong hospital."""
        index = FacilityIndex((facility(capabilities=(Capability.EMERGENCY_24X7,)),))
        found = refer(index, Capability.EMERGENCY_24X7, Capability.ANTIVENOM)
        assert not found.found

    def test_a_facility_with_extra_capabilities_still_matches(self) -> None:
        index = FacilityIndex(
            (
                facility(
                    capabilities=(
                        Capability.EMERGENCY_24X7,
                        Capability.ANTIVENOM,
                        Capability.VENTILATOR,
                    )
                ),
            )
        )
        assert refer(index, Capability.ANTIVENOM).found

    def test_no_capable_facility_returns_empty_not_the_nearest(self) -> None:
        """The failure this module exists to prevent.

        A snakebite sent to the nearest hospital without antivenom has been
        sent to the wrong place, with more confidence than if nothing had been
        suggested.
        """
        index = FacilityIndex((facility(capabilities=(Capability.EMERGENCY_24X7,)),))
        found = refer(index, Capability.ANTIVENOM)
        assert found.matches == ()
        assert found.best is None

    def test_an_empty_index_finds_nothing(self) -> None:
        assert not refer(FacilityIndex(), Capability.EMERGENCY_24X7).found

    def test_requiring_nothing_matches_everything(self) -> None:
        """An empty requirement set is satisfied by any facility."""
        index = FacilityIndex((facility(),))
        assert refer(index).found


class TestDistance:
    def test_the_nearest_capable_facility_comes_first(self) -> None:
        near = facility("NEAR", capabilities=(Capability.ANTIVENOM,), latitude=21.15)
        far = facility("FAR", capabilities=(Capability.ANTIVENOM,), latitude=22.50)
        index = FacilityIndex((far, near))
        best = refer(index, Capability.ANTIVENOM).best
        assert best is not None
        assert best.facility.id == "NEAR"

    def test_distance_never_substitutes_for_capability(self) -> None:
        """The nearest capable facility is the answer; the nearest is not."""
        near = facility("NEAR", capabilities=(Capability.EMERGENCY_24X7,), latitude=21.15)
        far = facility("FAR", capabilities=(Capability.ANTIVENOM,), latitude=22.50)
        index = FacilityIndex((near, far))
        best = refer(index, Capability.ANTIVENOM).best
        assert best is not None
        assert best.facility.id == "FAR"

    def test_a_known_distance_is_about_right(self) -> None:
        """Nagpur to Mumbai is roughly 690km great-circle."""
        assert 650 < haversine_km(21.1458, 79.0882, 19.0760, 72.8777) < 730

    def test_zero_distance_to_itself(self) -> None:
        assert haversine_km(21.1, 79.0, 21.1, 79.0) == pytest.approx(0.0)

    def test_the_result_is_capped(self) -> None:
        index = FacilityIndex(
            tuple(
                facility(f"F{n}", capabilities=(Capability.ANTIVENOM,), latitude=21.1 + n / 100)
                for n in range(10)
            )
        )
        assert len(refer(index, Capability.ANTIVENOM).matches) == 3


class TestExplainingWhatWasSkipped:
    def test_a_closer_unsuitable_facility_is_reported(self) -> None:
        """A patient told to travel past their district hospital needs a reason."""
        near = facility("NEAR", capabilities=(Capability.EMERGENCY_24X7,), latitude=21.15)
        far = facility("FAR", capabilities=(Capability.ANTIVENOM,), latitude=22.50)
        found = refer(FacilityIndex((near, far)), Capability.ANTIVENOM)
        assert [f.id for f, _ in found.nearest_unsuitable] == ["NEAR"]

    def test_what_the_skipped_facility_lacked_is_named(self) -> None:
        near = facility("NEAR", capabilities=(Capability.EMERGENCY_24X7,), latitude=21.15)
        far = facility("FAR", capabilities=(Capability.ANTIVENOM,), latitude=22.50)
        found = refer(FacilityIndex((near, far)), Capability.ANTIVENOM)
        assert found.nearest_unsuitable[0][1] == frozenset({Capability.ANTIVENOM})

    def test_facilities_further_than_the_match_are_not_reported(self) -> None:
        """Only what was passed over is worth explaining."""
        near = facility("NEAR", capabilities=(Capability.ANTIVENOM,), latitude=21.15)
        far = facility("FAR", capabilities=(Capability.EMERGENCY_24X7,), latitude=22.50)
        found = refer(FacilityIndex((near, far)), Capability.ANTIVENOM)
        assert found.nearest_unsuitable == ()


class TestStaleness:
    def test_a_recently_verified_facility_is_not_stale(self) -> None:
        index = FacilityIndex((facility(capabilities=(Capability.ANTIVENOM,)),))
        assert not refer(index, Capability.ANTIVENOM).any_stale

    def test_an_old_entry_is_reported_stale(self) -> None:
        """A ventilator out for service makes an old claim a false one."""
        old = facility(
            capabilities=(Capability.ANTIVENOM,),
            verified_on=TODAY - STALE_AFTER - timedelta(days=1),
        )
        assert refer(FacilityIndex((old,)), Capability.ANTIVENOM).any_stale

    def test_a_stale_facility_is_still_offered(self) -> None:
        """Stale is better than nothing, and much better than silent staleness."""
        old = facility(
            capabilities=(Capability.ANTIVENOM,),
            verified_on=TODAY - STALE_AFTER - timedelta(days=1),
        )
        found = refer(FacilityIndex((old,)), Capability.ANTIVENOM)
        assert found.found
        assert found.matches[0].stale

    def test_the_boundary_day_is_not_yet_stale(self) -> None:
        edge = facility(capabilities=(Capability.ANTIVENOM,), verified_on=TODAY - STALE_AFTER)
        assert not refer(FacilityIndex((edge,)), Capability.ANTIVENOM).any_stale


class TestLoading:
    def test_a_csv_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "facilities.csv"
        path.write_text(
            HEADER + "F1,District Hospital,Nagpur,21.1,79.0,emergency_24x7,2026-09-01,\n",
            encoding="utf-8",
        )
        assert len(load_facility_index(path)) == 1

    def test_capabilities_are_pipe_separated(self, tmp_path: Path) -> None:
        path = tmp_path / "facilities.csv"
        path.write_text(
            HEADER
            + "F1,DH,Nagpur,21.1,79.0,emergency_24x7|antivenom,2026-09-01,\n",
            encoding="utf-8",
        )
        index = load_facility_index(path)
        assert refer(index, Capability.ANTIVENOM).found

    def test_an_unknown_capability_is_an_error_not_a_skipped_field(
        self, tmp_path: Path
    ) -> None:
        """A misspelled antivenom line would silently stop matching snakebite.

        The failure would look like an absence of facilities rather than a
        typo, which is the worst possible way for it to present.
        """
        path = tmp_path / "facilities.csv"
        path.write_text(
            HEADER + "F1,DH,Nagpur,21.1,79.0,snake_antivenom,2026-09-01,\n",
            encoding="utf-8",
        )
        with pytest.raises(FacilityIndexError, match="Known capabilities are"):
            load_facility_index(path)

    def test_a_missing_file_says_what_it_is_for(self, tmp_path: Path) -> None:
        with pytest.raises(FacilityIndexError, match="names a specialty and no destination"):
            load_facility_index(tmp_path / "absent.csv")

    def test_a_missing_column_is_named(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text("id,name\nF1,DH\n", encoding="utf-8")
        with pytest.raises(FacilityIndexError, match="missing column"):
            load_facility_index(path)

    def test_an_empty_index_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.csv"
        path.write_text(HEADER, encoding="utf-8")
        with pytest.raises(FacilityIndexError, match="lists no facilities"):
            load_facility_index(path)

    def test_a_bad_coordinate_names_the_line(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(
            HEADER + "F1,DH,Nagpur,north,79.0,emergency_24x7,2026-09-01,\n",
            encoding="utf-8",
        )
        with pytest.raises(FacilityIndexError, match="line 2"):
            load_facility_index(path)

    def test_a_duplicate_id_is_refused(self) -> None:
        with pytest.raises(FacilityIndexError, match="listed twice"):
            FacilityIndex((facility("F1"), facility("F1")))

    def test_a_phone_number_is_optional(self, tmp_path: Path) -> None:
        path = tmp_path / "facilities.csv"
        path.write_text(
            HEADER + "F1,DH,Nagpur,21.1,79.0,emergency_24x7,2026-09-01,0712-2760000\n",
            encoding="utf-8",
        )
        index = load_facility_index(path)
        best = refer(index, Capability.EMERGENCY_24X7).best
        assert best is not None
        assert best.facility.phone == "0712-2760000"
