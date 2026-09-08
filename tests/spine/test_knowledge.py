"""The knowledge index.

The failure this whole subsystem must not have: a retrieved passage that reads
complete while missing the qualification that made it safe. Chunk boundaries
are where that happens, so they carry most of these tests.

The second failure: a confident answer to a question the corpus does not cover.
Cosine similarity always ranks something first, and that something is formatted
exactly like a real hit.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from spine.knowledge.chunking import (
    Chunk,
    chunk_document,
    is_navigation,
    tidy,
)
from spine.knowledge.index import (
    Entry,
    KnowledgeIndex,
    KnowledgeIndexError,
    cosine,
    load_index,
)
from spine.knowledge.sources import BY_ID, REGISTRY, Source, Tier, source_for

PROSE = (
    "Adrenaline 0.5mg intramuscular is given for anaphylaxis in an adult. "
    "It is repeated after five minutes if there is no response. "
    "The intravenous route is not used outside a monitored setting because of "
    "the risk of arrhythmia. "
) * 6


class TestSources:
    def test_every_source_carries_a_version(self) -> None:
        """A statement that cannot be traced to an edition cannot be rechecked."""
        for source in REGISTRY:
            assert source.version.strip()

    def test_a_source_without_a_version_is_refused(self) -> None:
        with pytest.raises(ValueError, match="cannot be rechecked"):
            Source(
                id="x",
                title="t",
                publisher="p",
                tier=Tier.REFERENCE,
                version="  ",
                url="https://example.org",
                covers=(),
                licence="l",
            )

    def test_source_ids_are_unique(self) -> None:
        assert len(BY_ID) == len(REGISTRY)

    def test_an_unknown_source_names_the_remedy(self) -> None:
        with pytest.raises(KeyError, match=r"spine/knowledge/sources\.py"):
            source_for("not_a_source")

    def test_statutory_outranks_reference(self) -> None:
        """Tier order is what a caller uses to weigh conflicting passages."""
        order = list(Tier)
        assert order.index(Tier.STATUTORY) < order.index(Tier.REFERENCE)


class TestTidy:
    def test_runs_of_spaces_collapse(self) -> None:
        assert tidy("a     b") == "a b"

    def test_paragraph_breaks_survive(self) -> None:
        """Line structure is what tells a table row from a paragraph."""
        assert "\n\n" in tidy("first line\n\nsecond line")

    def test_page_numbers_are_dropped(self) -> None:
        assert "137" not in tidy("some text\n137\nmore text")


class TestChunking:
    def test_a_short_document_is_one_chunk(self) -> None:
        chunks = chunk_document(PROSE[:400], "iphs_2022_dh")
        assert len(chunks) == 1

    def test_a_long_document_splits(self) -> None:
        chunks = chunk_document(PROSE, "iphs_2022_dh")
        assert len(chunks) > 1

    def test_chunks_overlap_so_a_split_statement_survives_whole(self) -> None:
        """The boundary failure: a threshold split from its contraindication."""
        chunks = chunk_document(PROSE, "iphs_2022_dh")
        assert len(chunks) >= 2
        for earlier, later in pairwise(chunks):
            assert later.char_start < earlier.char_end

    def test_offsets_locate_the_chunk_in_the_source(self) -> None:
        """A retrieved passage must be findable in the original."""
        text = tidy(PROSE)
        for chunk in chunk_document(PROSE, "iphs_2022_dh"):
            assert chunk.text in text[chunk.char_start : chunk.char_end]

    def test_ids_are_content_addressed(self) -> None:
        """Re-indexing an unchanged document must not invalidate a citation."""
        first = chunk_document(PROSE, "iphs_2022_dh")
        second = chunk_document(PROSE, "iphs_2022_dh")
        assert [c.chunk_id for c in first] == [c.chunk_id for c in second]

    def test_the_same_text_from_another_source_gets_another_id(self) -> None:
        here = chunk_document(PROSE, "iphs_2022_dh")[0]
        there = chunk_document(PROSE, "iphs_2022_chc")[0]
        assert here.chunk_id != there.chunk_id

    def test_tiny_fragments_are_dropped(self) -> None:
        assert chunk_document("short", "iphs_2022_dh") == ()

    def test_an_overlap_at_or_above_the_target_is_refused(self) -> None:
        """It would never advance, and would loop."""
        with pytest.raises(ValueError, match="would loop"):
            chunk_document(PROSE, "iphs_2022_dh", target=100, overlap=100)

    def test_an_empty_document_produces_nothing(self) -> None:
        assert chunk_document("", "iphs_2022_dh") == ()

    def test_a_chunk_spanning_no_text_is_refused(self) -> None:
        with pytest.raises(ValueError, match="spans no text"):
            Chunk(
                chunk_id="x", source_id="iphs_2022_dh", text="t", char_start=5, char_end=5
            )


class TestNavigationFiltering:
    def test_a_contents_line_is_navigation(self) -> None:
        assert is_navigation("7.3. Medicines 57 7.4. Diagnostics 58 7.5. Equipment 59")

    def test_a_dosage_sentence_is_not_navigation(self) -> None:
        """The filter must not eat the passages the corpus exists for."""
        assert not is_navigation(
            "Adrenaline 0.5mg intramuscular, repeated after 5 minutes if there is "
            "no response in an adult with anaphylaxis."
        )

    def test_empty_text_is_navigation(self) -> None:
        assert is_navigation("")

    def test_a_contents_page_produces_no_chunks(self) -> None:
        contents = " ".join(f"{n}.1 Section {n} {n * 3}" for n in range(1, 60))
        assert chunk_document(contents, "iphs_2022_dh") == ()


class TestCosine:
    def test_an_identical_vector_scores_one(self) -> None:
        assert cosine((1.0, 2.0, 3.0), (1.0, 2.0, 3.0)) == pytest.approx(1.0)

    def test_an_orthogonal_vector_scores_zero(self) -> None:
        assert cosine((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)

    def test_a_zero_vector_scores_zero_rather_than_dividing(self) -> None:
        assert cosine((0.0, 0.0), (1.0, 1.0)) == 0.0

    def test_mismatched_dimensions_name_the_likely_cause(self) -> None:
        with pytest.raises(KnowledgeIndexError, match="different embedding model"):
            cosine((1.0, 2.0), (1.0, 2.0, 3.0))


def entry(source_id: str, text: str, vector: tuple[float, ...]) -> Entry:
    return Entry(
        chunk=Chunk(
            chunk_id=f"id-{text[:8]}",
            source_id=source_id,
            text=text,
            char_start=0,
            char_end=len(text),
        ),
        vector=vector,
    )


class TestSearch:
    INDEX = KnowledgeIndex(
        (
            entry("iphs_2022_dh", "district hospital dialysis services", (1.0, 0.0, 0.0)),
            entry("iphs_2022_chc", "community health centre staffing", (0.0, 1.0, 0.0)),
            entry("iphs_2022_phc", "primary health centre referral", (0.0, 0.0, 1.0)),
        )
    )

    def test_the_closest_passage_ranks_first(self) -> None:
        hits = self.INDEX.search((1.0, 0.0, 0.0), limit=3)
        assert hits[0].source.id == "iphs_2022_dh"

    def test_the_limit_is_respected(self) -> None:
        assert len(self.INDEX.search((1.0, 1.0, 1.0), limit=2)) == 2

    def test_a_floor_drops_weak_matches(self) -> None:
        """A question the corpus does not cover must return nothing.

        The query sits between all three entries, so its best cosine is well
        under the floor. Returning the least-irrelevant paragraph, formatted
        exactly like a real hit, is the failure being prevented.
        """
        assert self.INDEX.search((1.0, 1.0, 1.0), floor=0.9, limit=3) == ()

    def test_every_hit_carries_its_source(self) -> None:
        """A retrieved claim a clinician cannot check is one they cannot act on."""
        for hit in self.INDEX.search((1.0, 1.0, 1.0), limit=3):
            assert hit.source.publisher
            assert hit.source.version in hit.citation

    def test_the_index_reports_its_sources(self) -> None:
        assert len(self.INDEX.sources) == 3


class TestPersistence:
    def test_a_saved_index_round_trips(self, tmp_path: object) -> None:
        path = tmp_path / "index.json"  # type: ignore[operator]
        original = KnowledgeIndex((entry("iphs_2022_dh", "text here", (1.0, 0.0)),))
        original.save(path)
        assert len(load_index(path)) == 1

    def test_a_missing_index_names_the_build_script(self, tmp_path: object) -> None:
        with pytest.raises(KnowledgeIndexError, match="build_knowledge_index"):
            load_index(tmp_path / "absent.json")  # type: ignore[operator]

    def test_an_index_of_the_wrong_version_is_refused(self, tmp_path: object) -> None:
        """A silently misread offset points a citation at the wrong passage."""
        path = tmp_path / "old.json"  # type: ignore[operator]
        path.write_text('{"index_version": 0, "entries": []}', encoding="utf-8")
        with pytest.raises(KnowledgeIndexError, match="Rebuild it"):
            load_index(path)
