"""Which hospital can actually take this patient.

Routing decides what a facility must be able to do. This decides which
facilities can do it. The gap between those two has been open since routing was
written: `required_capabilities()` returns a set of capabilities and nothing
answered them, so a triage result named a specialty and sent the patient
nowhere in particular.

Three things this module refuses to do, each because the failure is worse than
having no answer.

**It does not fall back to the nearest facility.** A facility matching some of
the required capabilities is not a partial match, it is a wrong destination. A
snakebite sent to the nearest hospital without antivenom has been sent to the
wrong place with more confidence than if nothing had been suggested.

**It does not rank on distance alone.** The nearest capable facility is the
answer; the nearest facility is not. Distance breaks ties between facilities
that already match, and never substitutes for matching.

**It does not treat a stale index as current.** Capabilities change — a
ventilator goes out for service, antivenom stock runs out — and an index nobody
has refreshed is a set of claims about the past. Staleness is reported with
every answer rather than checked by the caller.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Final

from spine.schemas.triage import Capability

STALE_AFTER: Final[timedelta] = timedelta(days=90)
"""How long a facility's declared capabilities are trusted.

Ninety days is a judgement, not a measurement: it is short enough that a closed
ward is noticed within a quarter and long enough that a district with hundreds
of facilities is not re-surveying constantly. A deployment that can refresh
more often should.

Nothing is hidden when the index goes stale. The answer still comes back, with
`stale` set, because a stale index is better than no index and much better than
a caller silently believing it is current.
"""

EARTH_RADIUS_KM: Final[float] = 6371.0


class FacilityIndexError(RuntimeError):
    """Raised when the facility index is missing or malformed."""


@dataclass(frozen=True)
class Facility:
    """One hospital and what it can do.

    `capabilities` is what this facility can do *today*, as declared by whoever
    maintains the index. It is not what its category implies: a district
    hospital that should have a blood bank and does not is the case this
    module exists to catch.
    """

    id: str
    name: str
    district: str
    latitude: float
    longitude: float
    capabilities: frozenset[Capability]
    verified_on: date
    phone: str | None = None

    def satisfies(self, required: frozenset[Capability]) -> bool:
        """Whether this facility can do everything required.

        All, not some. A facility meeting three of four requirements is not a
        75% match; it is a place that cannot treat this patient.
        """
        return required <= self.capabilities

    def missing(self, required: frozenset[Capability]) -> frozenset[Capability]:
        """What this facility cannot do of what was asked.

        Returned so a caller can tell a clinician *why* the nearest hospital
        was not offered, which is the difference between a routing decision and
        an unexplained one.
        """
        return required - self.capabilities

    def is_stale(self, today: date) -> bool:
        return today - self.verified_on > STALE_AFTER


@dataclass(frozen=True)
class Match:
    """One facility that can take the patient, and how far away it is."""

    facility: Facility
    distance_km: float
    stale: bool


@dataclass(frozen=True)
class Referral:
    """Where to send the patient, and what could not be answered.

    `matches` empty is a real answer and the important one. It means no known
    facility can do what this patient needs, which is a fact a clinician must
    act on — by transferring further afield, or by treating in place — and not
    a lookup failure to be papered over with the nearest hospital.
    """

    required: frozenset[Capability]
    matches: tuple[Match, ...]
    nearest_unsuitable: tuple[tuple[Facility, frozenset[Capability]], ...]
    any_stale: bool

    @property
    def found(self) -> bool:
        return bool(self.matches)

    @property
    def best(self) -> Match | None:
        """The nearest facility that can do everything required."""
        return self.matches[0] if self.matches else None


def haversine_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two points.

    Straight-line, not road distance. It is honest about being an
    approximation: in hill districts the road distance can be several times
    this, so it orders candidates rather than promising a travel time.
    """
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


class FacilityIndex:
    """The facilities a deployment can route to."""

    def __init__(self, facilities: tuple[Facility, ...] = ()) -> None:
        self._facilities = facilities
        seen: set[str] = set()
        for facility in facilities:
            if facility.id in seen:
                raise FacilityIndexError(
                    f"facility {facility.id!r} is listed twice; one entry would be "
                    f"silently ignored and it is not knowable which"
                )
            seen.add(facility.id)

    def __len__(self) -> int:
        return len(self._facilities)

    def refer(
        self,
        required: frozenset[Capability],
        *,
        latitude: float,
        longitude: float,
        today: date,
        limit: int = 3,
        explain_limit: int = 3,
    ) -> Referral:
        """Find the nearest facilities that can do everything required.

        `nearest_unsuitable` carries the closer facilities that were skipped
        and what each lacked. A patient told to travel past their district
        hospital deserves a reason, and a clinician overriding this decision
        needs to see what was rejected.
        """
        scored = [
            (
                facility,
                haversine_km(latitude, longitude, facility.latitude, facility.longitude),
            )
            for facility in self._facilities
        ]
        scored.sort(key=lambda pair: pair[1])

        matches = tuple(
            Match(facility=facility, distance_km=distance, stale=facility.is_stale(today))
            for facility, distance in scored
            if facility.satisfies(required)
        )[:limit]

        best_distance = matches[0].distance_km if matches else float("inf")
        unsuitable = tuple(
            (facility, facility.missing(required))
            for facility, distance in scored
            if not facility.satisfies(required) and distance < best_distance
        )[:explain_limit]

        return Referral(
            required=required,
            matches=matches,
            nearest_unsuitable=unsuitable,
            any_stale=any(match.stale for match in matches),
        )


def load_facility_index(path: Path) -> FacilityIndex:
    """Read the facility index from CSV.

    Columns: id, name, district, latitude, longitude, capabilities,
    verified_on, phone. Capabilities are pipe-separated.

    An unrecognised capability is an error rather than a skipped field. A
    facility whose antivenom line was misspelled would silently stop matching
    snakebite, and the failure would look like an absence of facilities.
    """
    if not path.is_file():
        raise FacilityIndexError(
            f"no facility index at {path}. Routing decides what a facility must be "
            f"able to do and this file says which ones can; without it a triage "
            f"result names a specialty and no destination. See "
            f"services/consult/rules/facilities/README.md for the format"
        )
    facilities: list[Facility] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {
            "id", "name", "district", "latitude", "longitude",
            "capabilities", "verified_on",
        }
        missing = required_columns - set(reader.fieldnames or ())
        if missing:
            raise FacilityIndexError(
                f"{path} is missing column(s): {', '.join(sorted(missing))}"
            )
        for number, row in enumerate(reader, start=2):
            facilities.append(_facility_from(row, path, number))
    if not facilities:
        raise FacilityIndexError(f"{path} lists no facilities")
    return FacilityIndex(tuple(facilities))


def _facility_from(row: dict[str, str], path: Path, line: int) -> Facility:
    """One row, or a message naming the row that is wrong."""
    try:
        capabilities = frozenset(
            Capability(value.strip())
            for value in row["capabilities"].split("|")
            if value.strip()
        )
    except ValueError as error:
        known = ", ".join(sorted(c.value for c in Capability))
        raise FacilityIndexError(
            f"{path} line {line}: {error}. Known capabilities are: {known}"
        ) from error

    try:
        return Facility(
            id=row["id"].strip(),
            name=row["name"].strip(),
            district=row["district"].strip(),
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            capabilities=capabilities,
            verified_on=date.fromisoformat(row["verified_on"].strip()),
            phone=(row.get("phone") or "").strip() or None,
        )
    except ValueError as error:
        raise FacilityIndexError(f"{path} line {line}: {error}") from error
