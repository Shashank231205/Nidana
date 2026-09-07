"""Patient identity resolution.

The same person arrives as a Consult session, a photographed prescription, and
a lab PDF, with three different spellings of their name. Linking those is what
makes the timeline and the cross-source medication list possible, and getting
it wrong merges two people's clinical records.

The asymmetry that shapes this module: a missed link costs a fragmented record,
and a wrong link puts one patient's allergies on another patient's chart. So
the default is to refuse rather than merge, and every automatic link needs
corroboration beyond a name.

ABHA is used where available and settles the question outright. Everything
below is what happens when it is not.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final
from uuid import UUID

from spine.schemas.primitives import Sex


class Confidence(str, Enum):
    """How sure a candidate link is.

    CERTAIN comes only from a verified identifier. Nothing derived from a name
    reaches it, however well it matches.
    """

    CERTAIN = "certain"
    PROBABLE = "probable"
    POSSIBLE = "possible"
    REJECTED = "rejected"


class IdentifierType(str, Enum):
    """Identifiers a patient may present.

    ABHA is the national health identifier and is the only one here that
    settles identity on its own. The others narrow a search and corroborate a
    match; none of them is unique to a person in practice.
    """

    ABHA = "abha"
    ABHA_ADDRESS = "abha_address"
    MOBILE = "mobile"
    AADHAAR_LAST_FOUR = "aadhaar_last_four"
    HOSPITAL_MRN = "hospital_mrn"
    LOCAL = "local"


@dataclass(frozen=True)
class Identifier:
    """One identifier a patient presented.

    `verified` records whether it was checked against its issuing authority. An
    unverified ABHA number is a claim, not an identity, and treating the two
    the same is how a wrong merge happens.
    """

    type: IdentifierType
    value: str
    verified: bool = False

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError(f"{self.type.value} identifier is empty")

    @property
    def is_authoritative(self) -> bool:
        return self.type is IdentifierType.ABHA and self.verified


@dataclass(frozen=True)
class PatientTraits:
    """What is known about a person at one point of contact.

    Deliberately thin. These are the fields reliably captured across a triage
    session, a prescription photograph, and a lab report, and asking for more
    would mean most records could not be compared at all.
    """

    name: str
    date_of_birth: date | None = None
    year_of_birth: int | None = None
    sex: Sex = Sex.UNKNOWN
    identifiers: tuple[Identifier, ...] = ()

    @property
    def authoritative_identifiers(self) -> tuple[Identifier, ...]:
        return tuple(i for i in self.identifiers if i.is_authoritative)

    def identifier_of(self, kind: IdentifierType) -> Identifier | None:
        for identifier in self.identifiers:
            if identifier.type is kind:
                return identifier
        return None


@dataclass(frozen=True)
class Candidate:
    """A possible match, with why it is possible."""

    patient_id: UUID
    confidence: Confidence
    reasons: tuple[str, ...]
    blockers: tuple[str, ...] = ()

    @property
    def is_automatic(self) -> bool:
        """Whether this link may be made without a human.

        Only a verified authoritative identifier qualifies. Everything else is
        proposed to a human, because the cost of a wrong merge is one patient's
        allergies appearing on another patient's chart.
        """
        return self.confidence is Confidence.CERTAIN and not self.blockers


NAME_NOISE: Final[frozenset[str]] = frozenset(
    {
        "mr",
        "mrs",
        "ms",
        "miss",
        "dr",
        "shri",
        "smt",
        "sri",
        "kumari",
        "baby",
        "master",
        "so",
        "do",
        "wo",
        "co",
        "s",
        "o",
        "d",
        "w",
        "c",
    }
)
"""Honorifics and relationship prefixes that carry no identity.

'S/O Ramesh' appears in the name field constantly on Indian records and is a
statement about someone else.
"""


def normalise_name(name: str) -> tuple[str, ...]:
    """Reduce a name to comparable tokens.

    Unicode-normalised, lowercased, punctuation-split, honorifics dropped.
    Tokens are returned unordered rather than joined, because the same person is
    written 'Kumar Rajesh' and 'Rajesh Kumar' on different records and neither
    ordering is wrong.

    Splitting on punctuation turns 'S/O' into two single letters, so the noise
    list carries those fragments as well as the joined forms. A single-letter
    token is an initial or the debris of a relationship prefix; neither
    identifies anyone, so dropping both is correct.
    """
    decomposed = unicodedata.normalize("NFKC", name).lower()
    cleaned = "".join(character if character.isalnum() else " " for character in decomposed)
    return tuple(
        token for token in cleaned.split() if token and token not in NAME_NOISE
    )


def name_overlap(left: str, right: str) -> float:
    """Proportion of tokens shared, over the shorter name.

    Over the shorter rather than the union, because one record often carries a
    middle name the other omits and that should not be read as disagreement.
    """
    first, second = set(normalise_name(left)), set(normalise_name(right))
    if not first or not second:
        return 0.0
    return len(first & second) / min(len(first), len(second))


NAME_MATCH_FLOOR: Final[float] = 0.5
"""Below this, two names are not the same name.

A cohort boundary for search, not a clinical threshold. It decides what is
proposed to a human, never what is merged automatically.
"""


def _birth_agreement(left: PatientTraits, right: PatientTraits) -> tuple[bool | None, str]:
    """Whether birth dates agree, disagree, or are unknown.

    Three-valued deliberately. Unknown is not agreement, and treating it as
    such is how two people with the same common name get merged.
    """
    if left.date_of_birth and right.date_of_birth:
        if left.date_of_birth == right.date_of_birth:
            return True, "date of birth matches"
        return False, (
            f"date of birth differs: {left.date_of_birth} against {right.date_of_birth}"
        )
    if left.year_of_birth and right.year_of_birth:
        if left.year_of_birth == right.year_of_birth:
            return True, "year of birth matches"
        return False, (
            f"year of birth differs: {left.year_of_birth} against {right.year_of_birth}"
        )
    return None, "no comparable birth date"


def _sex_disagrees(left: PatientTraits, right: PatientTraits) -> bool:
    """Whether recorded sex actively conflicts.

    Unknown never conflicts. Sex is recorded to gate clinical logic and is
    frequently absent on a lab report, so its absence must not block a link.
    """
    known = {Sex.FEMALE, Sex.MALE}
    return left.sex in known and right.sex in known and left.sex is not right.sex


def compare(
    incoming: PatientTraits,
    existing: PatientTraits,
    existing_id: UUID,
) -> Candidate:
    """Assess whether two sets of traits describe one person.

    Returns a candidate at the highest confidence the evidence supports, with
    the reasons that produced it and any blocker that caps it.
    """
    reasons: list[str] = []
    blockers: list[str] = []

    shared_authoritative = _shared_authoritative(incoming, existing)
    if shared_authoritative:
        reasons.append(f"verified {shared_authoritative} matches")

    overlap = name_overlap(incoming.name, existing.name)
    if overlap >= NAME_MATCH_FLOOR:
        reasons.append(f"name overlap {overlap:.0%}")

    agreed, birth_reason = _birth_agreement(incoming, existing)
    if agreed is True:
        reasons.append(birth_reason)
    elif agreed is False:
        blockers.append(birth_reason)

    if _sex_disagrees(incoming, existing):
        blockers.append(
            f"recorded sex differs: {incoming.sex.value} against {existing.sex.value}"
        )

    shared_contact = _shared_contact(incoming, existing)
    if shared_contact:
        reasons.append(f"{shared_contact} matches")

    return Candidate(
        patient_id=existing_id,
        confidence=_confidence(
            authoritative=bool(shared_authoritative),
            overlap=overlap,
            birth_agreed=agreed,
            corroborated=bool(shared_contact),
            blocked=bool(blockers),
        ),
        reasons=tuple(reasons),
        blockers=tuple(blockers),
    )


def _shared_authoritative(left: PatientTraits, right: PatientTraits) -> str | None:
    for identifier in left.authoritative_identifiers:
        for other in right.authoritative_identifiers:
            if identifier.type is other.type and identifier.value == other.value:
                return identifier.type.value
    return None


def _shared_contact(left: PatientTraits, right: PatientTraits) -> str | None:
    """A non-authoritative identifier both records carry.

    A shared mobile number corroborates; it does not establish identity. Family
    members share one constantly.
    """
    for identifier in left.identifiers:
        if identifier.is_authoritative:
            continue
        other = right.identifier_of(identifier.type)
        if other is not None and other.value == identifier.value:
            return identifier.type.value
    return None


def _confidence(
    *,
    authoritative: bool,
    overlap: float,
    birth_agreed: bool | None,
    corroborated: bool,
    blocked: bool,
) -> Confidence:
    if blocked:
        return Confidence.REJECTED
    if authoritative:
        return Confidence.CERTAIN
    if overlap < NAME_MATCH_FLOOR:
        return Confidence.REJECTED
    if birth_agreed is True and corroborated:
        return Confidence.PROBABLE
    if birth_agreed is True or corroborated:
        return Confidence.POSSIBLE
    return Confidence.POSSIBLE


def rank(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    """Candidates worth showing, best first, with rejections dropped."""
    order = {
        Confidence.CERTAIN: 0,
        Confidence.PROBABLE: 1,
        Confidence.POSSIBLE: 2,
        Confidence.REJECTED: 3,
    }
    viable = [c for c in candidates if c.confidence is not Confidence.REJECTED]
    return tuple(sorted(viable, key=lambda c: (order[c.confidence], -len(c.reasons))))


def automatic_link(candidates: tuple[Candidate, ...]) -> Candidate | None:
    """The one candidate that may be linked without a human, if there is one.

    Returns None when two candidates both qualify. Two records both carrying
    the same verified identifier is a data problem, and resolving it by picking
    one would bury it.
    """
    automatic = [c for c in candidates if c.is_automatic]
    return automatic[0] if len(automatic) == 1 else None
