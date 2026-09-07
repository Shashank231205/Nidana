"""Terminology lookup and patient identity resolution.

Both are deterministic and both are built around a refusal. Terminology returns
nothing rather than a plausible neighbour; identity refuses to merge rather
than guess, because a wrong merge puts one patient's allergies on another
patient's chart.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from spine.identity.resolution import (
    NAME_MATCH_FLOOR,
    Candidate,
    Confidence,
    Identifier,
    IdentifierType,
    PatientTraits,
    automatic_link,
    compare,
    name_overlap,
    normalise_name,
    rank,
)
from spine.schemas.primitives import Sex
from spine.terminology.index import (
    CodeSystem,
    Concept,
    TerminologyIndex,
    TerminologyLoadError,
    load_csv,
    load_index,
    normalise,
)

CSV_HEADER = "system,code,display,synonyms\n"


def index_of(*concepts: Concept) -> TerminologyIndex:
    return TerminologyIndex(concepts)


def concept(code: str, display: str, *synonyms: str) -> Concept:
    return Concept(
        system=CodeSystem.ICD_10, code=code, display=display, synonyms=synonyms
    )


class TestNormalisation:
    def test_case_and_whitespace_are_flattened(self) -> None:
        assert normalise("  Chest   Pain  ") == "chest pain"

    def test_unicode_forms_that_render_alike_compare_alike(self) -> None:
        """Clinical text arrives with combining marks that look identical."""
        assert normalise("क़") == normalise("क़")

    def test_punctuation_inside_a_name_is_kept(self) -> None:
        """Punctuation inside a drug name is part of the drug name."""
        assert normalise("Co-trimoxazole") == "co-trimoxazole"


class TestLookup:
    def test_a_display_name_resolves(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction"))
        match = index.resolve("Acute myocardial infarction")
        assert match is not None
        assert match.concept.code == "I21"

    def test_a_synonym_resolves(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction", "heart attack"))
        match = index.resolve("heart attack")
        assert match is not None
        assert match.concept.code == "I21"

    def test_matching_is_case_insensitive(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction", "heart attack"))
        assert index.resolve("HEART ATTACK") is not None

    def test_a_code_switched_synonym_resolves(self) -> None:
        index = index_of(concept("R07.4", "Chest pain", "seene mein dard"))
        assert index.resolve("seene mein dard") is not None

    def test_an_unknown_term_resolves_to_nothing(self) -> None:
        """A lookup that invents a code is worse than one that finds none."""
        assert index_of(concept("I21", "Acute myocardial infarction")).resolve("banana") is None

    def test_a_near_miss_is_not_a_match(self) -> None:
        """paracetamol and paroxetine share a prefix and nothing else."""
        index = index_of(concept("N02BE01", "Paracetamol"))
        assert index.resolve("Paroxetine") is None

    def test_an_ambiguous_term_resolves_to_nothing(self) -> None:
        """Resolving ambiguity by picking the first is the failure to avoid."""
        index = index_of(
            Concept(CodeSystem.ICD_10, "A", "shared term"),
            Concept(CodeSystem.SNOMED_CT, "B", "shared term"),
        )
        assert index.resolve("shared term") is None
        assert len(index.lookup("shared term")) == 2

    def test_a_system_filter_can_disambiguate(self) -> None:
        index = index_of(
            Concept(CodeSystem.ICD_10, "A", "shared term"),
            Concept(CodeSystem.SNOMED_CT, "B", "shared term"),
        )
        match = index.resolve("shared term", CodeSystem.ICD_10)
        assert match is not None
        assert match.concept.code == "A"

    def test_an_exact_match_is_marked_as_such(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction"))
        matches = index.lookup("Acute myocardial infarction")
        assert matches[0].exact

    def test_a_normalised_match_is_not_marked_exact(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction"))
        assert not index.lookup("acute myocardial infarction")[0].exact

    def test_a_resolved_term_produces_a_coding(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction"))
        coding = index.code_for("Acute myocardial infarction")
        assert coding is not None
        assert coding.system == CodeSystem.ICD_10.value

    def test_a_concept_can_be_fetched_by_code(self) -> None:
        index = index_of(concept("I21", "Acute myocardial infarction"))
        assert index.by_code(CodeSystem.ICD_10, "I21") is not None
        assert index.by_code(CodeSystem.SNOMED_CT, "I21") is None

    def test_a_duplicate_code_is_rejected(self) -> None:
        with pytest.raises(TerminologyLoadError, match="silently ignored"):
            index_of(concept("I21", "First"), concept("I21", "Second"))


class TestLoading:
    def test_a_csv_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "icd10.csv"
        path.write_text(
            CSV_HEADER
            + "http://hl7.org/fhir/sid/icd-10,I21,Acute myocardial infarction,heart attack|MI\n",
            encoding="utf-8",
        )
        loaded = load_csv(path)
        assert loaded[0].synonyms == ("heart attack", "MI")

    def test_synonyms_are_pipe_separated_so_a_display_may_contain_a_comma(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "icd10.csv"
        path.write_text(
            CSV_HEADER + 'http://hl7.org/fhir/sid/icd-10,X,"Pain, unspecified",ache|soreness\n',
            encoding="utf-8",
        )
        loaded = load_csv(path)
        assert loaded[0].display == "Pain, unspecified"
        assert loaded[0].synonyms == ("ache", "soreness")

    def test_a_missing_file_names_the_path(self, tmp_path: Path) -> None:
        with pytest.raises(TerminologyLoadError, match="versioned"):
            load_csv(tmp_path / "absent.csv")

    def test_a_missing_column_is_reported(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text("system,code\nhttp://hl7.org/fhir/sid/icd-10,I21\n", encoding="utf-8")
        with pytest.raises(TerminologyLoadError, match="missing column"):
            load_csv(path)

    def test_an_unknown_code_system_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.csv"
        path.write_text(CSV_HEADER + "http://example.com/made-up,X,Something,\n", encoding="utf-8")
        with pytest.raises(TerminologyLoadError, match="unknown code system"):
            load_csv(path)

    def test_no_terminology_subset_ships(self) -> None:
        """SNOMED CT licensing for India is unresolved.

        An invented subset would produce codes that look real.
        """
        assert len(load_index()) == 0

    def test_a_missing_directory_produces_an_empty_index(self, tmp_path: Path) -> None:
        assert len(load_index(tmp_path / "absent")) == 0


def traits(
    name: str,
    *,
    year: int | None = None,
    born: date | None = None,
    sex: Sex = Sex.UNKNOWN,
    identifiers: tuple[Identifier, ...] = (),
) -> PatientTraits:
    return PatientTraits(
        name=name,
        year_of_birth=year,
        date_of_birth=born,
        sex=sex,
        identifiers=identifiers,
    )


class TestNameHandling:
    def test_honorifics_are_dropped(self) -> None:
        assert normalise_name("Mr Rajesh Kumar") == ("rajesh", "kumar")

    def test_relationship_prefixes_are_dropped(self) -> None:
        """'S/O Ramesh' is a statement about someone else."""
        assert "ramesh" in normalise_name("Rajesh Kumar S/O Ramesh")
        assert "s" not in normalise_name("Rajesh Kumar S/O Ramesh")

    def test_reordered_names_overlap_fully(self) -> None:
        """The same person is written both ways on different records."""
        assert name_overlap("Rajesh Kumar", "Kumar Rajesh") == 1.0

    def test_a_missing_middle_name_is_not_disagreement(self) -> None:
        assert name_overlap("Rajesh Kumar", "Rajesh Mohan Kumar") == 1.0

    def test_unrelated_names_do_not_overlap(self) -> None:
        assert name_overlap("Rajesh Kumar", "Priya Sharma") == 0.0

    def test_an_empty_name_overlaps_nothing(self) -> None:
        assert name_overlap("", "Rajesh Kumar") == 0.0


class TestIdentityComparison:
    def test_a_verified_abha_is_certain(self) -> None:
        abha = (Identifier(IdentifierType.ABHA, "12-3456-7890", verified=True),)
        candidate = compare(
            traits("Rajesh Kumar", identifiers=abha),
            traits("R Kumar", identifiers=abha),
            uuid4(),
        )
        assert candidate.confidence is Confidence.CERTAIN

    def test_an_unverified_abha_is_not_certain(self) -> None:
        """An unverified identifier is a claim, not an identity."""
        abha = (Identifier(IdentifierType.ABHA, "12-3456-7890", verified=False),)
        candidate = compare(
            traits("Rajesh Kumar", identifiers=abha),
            traits("Rajesh Kumar", identifiers=abha),
            uuid4(),
        )
        assert candidate.confidence is not Confidence.CERTAIN

    def test_name_and_birth_year_and_mobile_reach_probable(self) -> None:
        mobile = (Identifier(IdentifierType.MOBILE, "9876543210"),)
        candidate = compare(
            traits("Rajesh Kumar", year=1978, identifiers=mobile),
            traits("Kumar Rajesh", year=1978, identifiers=mobile),
            uuid4(),
        )
        assert candidate.confidence is Confidence.PROBABLE

    def test_probable_is_not_automatic(self) -> None:
        """Only a verified identifier links without a human."""
        mobile = (Identifier(IdentifierType.MOBILE, "9876543210"),)
        candidate = compare(
            traits("Rajesh Kumar", year=1978, identifiers=mobile),
            traits("Kumar Rajesh", year=1978, identifiers=mobile),
            uuid4(),
        )
        assert not candidate.is_automatic

    def test_a_differing_birth_year_rejects(self) -> None:
        candidate = compare(
            traits("Rajesh Kumar", year=1978),
            traits("Rajesh Kumar", year=1990),
            uuid4(),
        )
        assert candidate.confidence is Confidence.REJECTED
        assert candidate.blockers

    def test_a_differing_birth_date_rejects(self) -> None:
        candidate = compare(
            traits("Rajesh Kumar", born=date(1978, 3, 4)),
            traits("Rajesh Kumar", born=date(1978, 3, 5)),
            uuid4(),
        )
        assert candidate.confidence is Confidence.REJECTED

    def test_an_unknown_birth_date_is_not_agreement(self) -> None:
        """Treating unknown as agreement merges two people with one common name."""
        candidate = compare(traits("Rajesh Kumar"), traits("Rajesh Kumar"), uuid4())
        assert candidate.confidence is Confidence.POSSIBLE

    def test_a_differing_recorded_sex_rejects(self) -> None:
        candidate = compare(
            traits("Rajesh Kumar", year=1978, sex=Sex.MALE),
            traits("Rajesh Kumar", year=1978, sex=Sex.FEMALE),
            uuid4(),
        )
        assert candidate.confidence is Confidence.REJECTED

    def test_an_unknown_sex_never_blocks(self) -> None:
        """Sex is frequently absent on a lab report."""
        candidate = compare(
            traits("Rajesh Kumar", year=1978, sex=Sex.MALE),
            traits("Rajesh Kumar", year=1978, sex=Sex.UNKNOWN),
            uuid4(),
        )
        assert candidate.confidence is not Confidence.REJECTED

    def test_a_verified_identifier_is_certain_despite_a_different_name(self) -> None:
        abha = (Identifier(IdentifierType.ABHA, "12-3456", verified=True),)
        candidate = compare(
            traits("Rajesh Kumar", identifiers=abha),
            traits("Completely Different", identifiers=abha),
            uuid4(),
        )
        assert candidate.is_automatic

    def test_a_blocker_overrides_even_a_verified_identifier(self) -> None:
        """A shared identifier and a contradicting birth date is a data problem."""
        abha = (Identifier(IdentifierType.ABHA, "12-3456", verified=True),)
        candidate = compare(
            traits("Rajesh Kumar", year=1978, identifiers=abha),
            traits("Rajesh Kumar", year=1990, identifiers=abha),
            uuid4(),
        )
        assert candidate.confidence is Confidence.REJECTED

    def test_unrelated_names_reject(self) -> None:
        candidate = compare(traits("Rajesh Kumar"), traits("Priya Sharma"), uuid4())
        assert candidate.confidence is Confidence.REJECTED

    def test_the_reasons_are_recorded(self) -> None:
        mobile = (Identifier(IdentifierType.MOBILE, "9876543210"),)
        candidate = compare(
            traits("Rajesh Kumar", year=1978, identifiers=mobile),
            traits("Rajesh Kumar", year=1978, identifiers=mobile),
            uuid4(),
        )
        assert any("name overlap" in reason for reason in candidate.reasons)
        assert any("mobile" in reason for reason in candidate.reasons)

    def test_an_empty_identifier_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="is empty"):
            Identifier(IdentifierType.MOBILE, "   ")


class TestRanking:
    def test_rejections_are_dropped(self) -> None:
        candidates = (
            Candidate(uuid4(), Confidence.REJECTED, ()),
            Candidate(uuid4(), Confidence.POSSIBLE, ("name",)),
        )
        assert len(rank(candidates)) == 1

    def test_certain_outranks_probable(self) -> None:
        certain = Candidate(uuid4(), Confidence.CERTAIN, ("abha",))
        probable = Candidate(uuid4(), Confidence.PROBABLE, ("name", "dob"))
        assert rank((probable, certain))[0] is certain

    def test_a_single_certain_candidate_links_automatically(self) -> None:
        certain = Candidate(uuid4(), Confidence.CERTAIN, ("abha",))
        assert automatic_link((certain,)) is certain

    def test_two_certain_candidates_link_to_nothing(self) -> None:
        """Two records with the same verified identifier is a data problem."""
        first = Candidate(uuid4(), Confidence.CERTAIN, ("abha",))
        second = Candidate(uuid4(), Confidence.CERTAIN, ("abha",))
        assert automatic_link((first, second)) is None

    def test_a_probable_candidate_does_not_link_automatically(self) -> None:
        probable = Candidate(uuid4(), Confidence.PROBABLE, ("name", "dob"))
        assert automatic_link((probable,)) is None

    def test_a_certain_candidate_with_a_blocker_does_not_link(self) -> None:
        blocked = Candidate(uuid4(), Confidence.CERTAIN, ("abha",), ("dob differs",))
        assert automatic_link((blocked,)) is None

    def test_the_name_floor_is_where_it_is_claimed(self) -> None:
        assert 0.0 < NAME_MATCH_FLOOR < 1.0
