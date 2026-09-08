"""The routing vocabulary, and the patient-facing translation of it.

Two things this file protects.

**The enums are grounded, not guessed.** Specialty and Capability were
originally my assumptions about what an Indian hospital provides. They are now
scoped to IPHS 2022, and a specialty the referral network does not staff is not
a useful routing decision. These tests name the ones whose absence was a real
gap, so removing one is a deliberate act rather than a tidy-up.

**The UI can say every value out loud.** A patient shown `obstetrics_gynaecology`
has been shown a database column. The frontend carries a plain-language map, and
a value added to the enum without a translation reaches a patient as a raw
identifier. That drift is silent, so it is tested rather than remembered.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

from spine.schemas.triage import Capability, Specialty

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
API_CLIENT: Final[Path] = REPO_ROOT / "web" / "shared" / "api.js"


def _mapped_keys(marker: str, until: str | None) -> set[str]:
    """The keys of one translation map in the frontend client.

    Parsed rather than imported: it is JavaScript, and a test that shelled out
    to node to read it would fail on a machine without node for a reason that
    has nothing to do with the vocabulary.
    """
    source = API_CLIENT.read_text(encoding="utf-8")
    start = source.index(marker)
    end = source.index(until) if until else len(source)
    return set(re.findall(r"^\s{2}(\w+):", source[start:end], re.MULTILINE))


class TestSpecialty:
    def test_the_gaps_that_prompted_the_expansion_are_closed(self) -> None:
        """Each of these was a real presentation with nowhere to route it."""
        for value in (
            "nephrology",
            "endocrinology",
            "rheumatology",
            "haematology",
            "oncology",
            "neonatology",
            "geriatrics",
            "infectious_disease",
        ):
            assert value in {specialty.value for specialty in Specialty}

    def test_human_review_survives_the_expansion(self) -> None:
        """A wrong specialty sends someone to the wrong queue.

        A stated refusal sends them to a person, which is why the escape hatch
        matters more as the vocabulary grows, not less.
        """
        assert Specialty.HUMAN_REVIEW in set(Specialty)

    def test_every_specialty_has_patient_facing_words(self) -> None:
        """A patient shown a raw enum value has been shown a database column."""
        mapped = _mapped_keys("SPECIALTY_TEXT", "CAPABILITY_TEXT")
        missing = sorted({s.value for s in Specialty} - mapped)
        assert not missing, f"no patient-facing text for: {missing}"

    def test_no_translation_names_a_specialty_that_no_longer_exists(self) -> None:
        mapped = _mapped_keys("SPECIALTY_TEXT", "CAPABILITY_TEXT")
        stale = sorted(mapped - {s.value for s in Specialty})
        assert not stale, f"translation for unknown specialty: {stale}"


class TestCapability:
    def test_antivenom_is_expressible(self) -> None:
        """India records the highest snakebite mortality in the world.

        A snakebite routed to a hospital with no antivenom has been sent to the
        wrong place however well staffed it is, and before this the system
        could not say so.
        """
        assert Capability.ANTIVENOM in set(Capability)

    def test_the_other_gaps_are_closed(self) -> None:
        for value in ("dialysis", "burn_unit", "rabies_immunoglobulin", "ventilator"):
            assert value in {capability.value for capability in Capability}

    def test_every_capability_has_patient_facing_words(self) -> None:
        """The facility requirement is read by a frightened person choosing a hospital."""
        mapped = _mapped_keys("CAPABILITY_TEXT", None)
        missing = sorted({c.value for c in Capability} - mapped)
        assert not missing, f"no patient-facing text for: {missing}"

    def test_no_translation_names_a_capability_that_no_longer_exists(self) -> None:
        mapped = _mapped_keys("CAPABILITY_TEXT", None)
        stale = sorted(mapped - {c.value for c in Capability})
        assert not stale, f"translation for unknown capability: {stale}"


class TestVocabularyHygiene:
    def test_values_are_lowercase_identifiers(self) -> None:
        """They appear in YAML rules and in URLs; casing drift breaks both."""
        for member in (*Specialty, *Capability):
            assert re.fullmatch(r"[a-z0-9_]+", member.value), member.value

    def test_no_value_is_duplicated_across_the_two(self) -> None:
        """A specialty and a capability are different questions.

        'Can this hospital dialyse' and 'is there a nephrologist' are not the
        same, and a shared value would let one answer stand in for the other.
        """
        overlap = {s.value for s in Specialty} & {c.value for c in Capability}
        assert not overlap, f"value used as both specialty and capability: {overlap}"
