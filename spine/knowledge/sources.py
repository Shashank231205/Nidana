"""The corpus registry: what Nidana is allowed to reason from, and how far.

Every chunk in the knowledge index traces to one of these sources. A retrieved
passage carries its source's tier, and the tier is what a reader uses to decide
how much weight it deserves.

**Tier is not a quality score.** A Cochrane review is not "better" than the
Indian Public Health Standards; they answer different questions. Tier records
what kind of authority a document carries, so a routing decision cites IPHS and
a clinical threshold cites a guideline body, rather than either standing in for
the other.

Why the corpus is a fixed registry rather than an open crawl: this product runs
on-premise with no network egress at inference time. Everything retrievable is
fetched once, at build time, from a named source with a recorded version. A
passage whose origin cannot be stated is worse than no passage, because a
clinician cannot check it.

Nothing here is a clinical threshold and nothing here is verified content. The
registry says where to look. What a rule asserts still carries
`verify_before_ship` until a clinician signs it off.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final


class Tier(str, Enum):
    """What kind of authority a source carries.

    Ordered by how directly a statement in it binds an Indian clinician.
    """

    STATUTORY = "statutory"
    """Indian government standards and law. Binding, not advisory.

    IPHS, CDSCO, the Clinical Establishments Act. When one of these says a
    district hospital provides dialysis, that is what the system should expect
    to find, whatever a textbook says is ideal.
    """

    NATIONAL_GUIDELINE = "national_guideline"
    """Indian national clinical programmes and councils.

    ICMR, NCDC, the National Health Mission programme guidelines. These reflect
    Indian epidemiology, which is the reason they outrank international
    guidance here: snakebite, tuberculosis and rheumatic heart disease are
    common presentations locally and rare in the sources that dominate the
    literature.
    """

    INTERNATIONAL_GUIDELINE = "international_guideline"
    """WHO, and international specialty bodies.

    Authoritative and often more current, but written for a different case mix
    and a different set of available facilities.
    """

    SYSTEMATIC_REVIEW = "systematic_review"
    """Cochrane and comparable evidence syntheses.

    The strongest evidence about whether something works, and the weakest
    guidance about what to do in a clinic on a Tuesday.
    """

    REFERENCE = "reference"
    """Standard clinical reference works and triage handbooks.

    AHRQ's ESI handbook sits here: widely used, methodologically sound, and not
    binding on anyone in India.
    """


@dataclass(frozen=True)
class Source:
    """One document in the corpus.

    `version` is mandatory and is usually a year or an edition. A clinical
    statement without the version of the document it came from cannot be
    rechecked when the document is revised, and revision is the normal case:
    IPHS was rewritten in 2022 and the IPC became the BNS in 2024.
    """

    id: str
    title: str
    publisher: str
    tier: Tier
    version: str
    url: str
    covers: tuple[str, ...]
    licence: str

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError(
                f"source {self.id!r} has no version; a clinical statement that cannot "
                f"be traced to an edition cannot be rechecked when that edition changes"
            )


REGISTRY: Final[tuple[Source, ...]] = (
    Source(
        id="iphs_2022_dh",
        title="Indian Public Health Standards 2022, Volume I: Sub-District and District Hospital",
        publisher="Ministry of Health and Family Welfare, Government of India",
        tier=Tier.STATUTORY,
        version="2022",
        url=(
            "https://nhm.gov.in/images/pdf/guidelines/iphs/"
            "iphs-revised-guidlines-2022/01-SDH_DH_IPHS_Guidelines-2022.pdf"
        ),
        covers=("facility_capability", "specialty_availability", "referral"),
        licence="Government of India, open publication",
    ),
    Source(
        id="iphs_2022_chc",
        title="Indian Public Health Standards 2022, Volume II: Community Health Centre",
        publisher="Ministry of Health and Family Welfare, Government of India",
        tier=Tier.STATUTORY,
        version="2022",
        url="https://nhsrcindia.org/sites/default/files/CHC%20IPHS%202022%20Guidelines%20pdf.pdf",
        covers=("facility_capability", "specialty_availability", "referral"),
        licence="Government of India, open publication",
    ),
    Source(
        id="iphs_2022_phc",
        title="Indian Public Health Standards 2022, Volume III: Primary Health Centre",
        publisher="Ministry of Health and Family Welfare, Government of India",
        tier=Tier.STATUTORY,
        version="2022",
        url=(
            "https://nhm.gov.in/images/pdf/guidelines/iphs/"
            "iphs-revised-guidlines-2022/03_PHC_IPHS_Guidelines-2022.pdf"
        ),
        covers=("facility_capability", "referral"),
        licence="Government of India, open publication",
    ),
)
"""The corpus, as fetched.

Deliberately small and deliberately explicit. A source is added here only when
someone has read enough of it to state what it covers, and `covers` is what the
retriever uses to decide whether a passage is relevant to the question being
asked rather than merely similar to it.
"""

BY_ID: Final[dict[str, Source]] = {source.id: source for source in REGISTRY}


def source_for(source_id: str) -> Source:
    known = ", ".join(sorted(BY_ID))
    if source_id not in BY_ID:
        raise KeyError(
            f"no source {source_id!r} in the corpus registry; known sources are "
            f"{known}. Add it to spine/knowledge/sources.py before indexing it"
        )
    return BY_ID[source_id]
