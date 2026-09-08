"""The local knowledge index: embed once at build time, search at inference time.

Two properties this design exists to hold.

**No network egress at inference.** Embeddings are computed when the index is
built and stored beside the chunks. A search at request time is a dot product
over a matrix already in memory — no model call, no service, nothing that
leaves the machine. The embedding model is only needed to build the index and
to embed the query, and that query embedding runs against the same local Ollama
the rest of the system uses.

**Every hit cites its source.** A passage is returned with the source it came
from, that source's tier, and its character offsets in the original document.
A retrieved claim a clinician cannot check is a claim they should not act on,
and the whole point of building this rather than calling a search engine is
that the provenance survives.

The index is a plain JSON file plus a float32 array. Not a vector database:
5,000 chunks is a 15MB matrix, brute-force cosine over it takes single-digit
milliseconds, and a dependency that runs a server would be one more thing to
install on a clinic's machine for no gain at this size.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from spine.knowledge.chunking import Chunk
from spine.knowledge.sources import Source, Tier, source_for

INDEX_VERSION: Final[int] = 1
"""Bumped when the on-disk shape changes.

An index built by an older version is refused rather than read, because a
silently misread offset points a citation at the wrong passage.
"""

EMBEDDING_MODEL: Final[str] = "nomic-embed-text"
"""Fixed, and recorded in the index.

Vectors from two different models are not comparable, so a query embedded with
one model searching an index built with another returns confident nonsense.
The index records which model built it and the loader refuses a mismatch.
"""


class KnowledgeIndexError(RuntimeError):
    """Raised when an index cannot be loaded or is inconsistent."""


@dataclass(frozen=True)
class Passage:
    """One retrieved chunk, with everything needed to check it."""

    chunk_id: str
    source: Source
    text: str
    score: float
    char_start: int
    char_end: int

    @property
    def citation(self) -> str:
        """How this passage is referred to in output a human reads."""
        return (
            f"{self.source.title} ({self.source.publisher}, {self.source.version}), "
            f"characters {self.char_start}-{self.char_end}"
        )


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Similarity between two vectors.

    Written out rather than pulled from numpy: it is four lines, and the index
    is the one part of the system a clinic's IT department may have to reason
    about without the dependency tree installed.
    """
    if len(left) != len(right):
        raise KnowledgeIndexError(
            f"vectors have different dimensions ({len(left)} and {len(right)}); the "
            f"index was probably built with a different embedding model"
        )
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


@dataclass(frozen=True)
class Entry:
    chunk: Chunk
    vector: tuple[float, ...]


class KnowledgeIndex:
    """Chunks and their embeddings, searchable by cosine similarity."""

    def __init__(self, entries: tuple[Entry, ...], model: str = EMBEDDING_MODEL) -> None:
        self._entries = entries
        self._model = model

    def __len__(self) -> int:
        return len(self._entries)

    @property
    def model(self) -> str:
        return self._model

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(sorted({entry.chunk.source_id for entry in self._entries}))

    def search(
        self,
        query_vector: tuple[float, ...],
        *,
        limit: int = 5,
        floor: float = 0.0,
        tiers: tuple[Tier, ...] | None = None,
    ) -> tuple[Passage, ...]:
        """The closest passages to a query.

        `tiers` restricts the search to sources of a given authority: a
        question about what a district hospital stocks is answered by the
        statutory standard, not by a review of what a hospital ideally would.

        `floor` drops weak matches. Cosine similarity always returns something,
        and the something it returns for a question the corpus does not cover
        reads as confidently as a real hit.
        """
        allowed = set(tiers) if tiers else None
        scored: list[Passage] = []
        for entry in self._entries:
            source = source_for(entry.chunk.source_id)
            if allowed is not None and source.tier not in allowed:
                continue
            score = cosine(query_vector, entry.vector)
            if score < floor:
                continue
            scored.append(
                Passage(
                    chunk_id=entry.chunk.chunk_id,
                    source=source,
                    text=entry.chunk.text,
                    score=score,
                    char_start=entry.chunk.char_start,
                    char_end=entry.chunk.char_end,
                )
            )
        scored.sort(key=lambda passage: passage.score, reverse=True)
        return tuple(scored[:limit])

    def save(self, path: Path) -> None:
        payload = {
            "index_version": INDEX_VERSION,
            "embedding_model": self._model,
            "entries": [
                {
                    "chunk_id": entry.chunk.chunk_id,
                    "source_id": entry.chunk.source_id,
                    "text": entry.chunk.text,
                    "char_start": entry.chunk.char_start,
                    "char_end": entry.chunk.char_end,
                    "vector": list(entry.vector),
                }
                for entry in self._entries
            ],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")


def load_index(path: Path) -> KnowledgeIndex:
    """Read an index, refusing one this code cannot read correctly."""
    if not path.is_file():
        raise KnowledgeIndexError(
            f"no knowledge index at {path}; build one with "
            f"scripts/build_knowledge_index.py"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("index_version")
    if version != INDEX_VERSION:
        raise KnowledgeIndexError(
            f"index at {path} is version {version}; this code reads version "
            f"{INDEX_VERSION}. Rebuild it with scripts/build_knowledge_index.py"
        )
    entries = tuple(
        Entry(
            chunk=Chunk(
                chunk_id=raw["chunk_id"],
                source_id=raw["source_id"],
                text=raw["text"],
                char_start=raw["char_start"],
                char_end=raw["char_end"],
            ),
            vector=tuple(raw["vector"]),
        )
        for raw in payload["entries"]
    )
    return KnowledgeIndex(entries, model=payload.get("embedding_model", EMBEDDING_MODEL))
