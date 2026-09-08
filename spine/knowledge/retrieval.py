"""Asking the knowledge index a question.

The boundary between "the corpus contains this" and "this is clinically true"
runs through here, and it is the reason this module is small and opinionated.

Retrieval returns passages with citations. It never returns an answer. A caller
that wants prose asks a model to write it *from* these passages, and that model
is told to cite or say nothing — the same grounding discipline the extraction
agents use, applied to reference material instead of a patient's words.

What this must never become: a path by which a model's recollection of a
guideline reaches a clinical decision. A retrieved passage is evidence. A
generated summary of a retrieved passage is a claim, and it carries the
passage's citation only if the words are actually in it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final

from spine.knowledge.index import (
    EMBEDDING_MODEL,
    KnowledgeIndex,
    KnowledgeIndexError,
    Passage,
)
from spine.knowledge.sources import Tier

RELEVANCE_FLOOR: Final[float] = 0.55
"""Below this a passage is not returned.

Cosine similarity always ranks something first. For a question the corpus does
not cover, that something is noise wearing the same confident format as a real
hit, and a clinician reading a cited passage reasonably assumes the citation
means something. Set high enough that "no answer" is a normal outcome.
"""

EMBED_ENDPOINT: Final[str] = "http://localhost:11434/api/embeddings"


class RetrievalUnavailableError(RuntimeError):
    """Raised when a query cannot be embedded.

    Distinct from finding nothing. A caller must be able to tell "the corpus
    does not cover this" from "the embedding model is not running", because the
    first is an answer and the second is an outage.
    """


@dataclass(frozen=True)
class Answer:
    """What the corpus had to say, if anything.

    `passages` may be empty, and an empty answer is a real answer. The caller
    is expected to say "the corpus does not cover this" rather than falling
    back to what a model remembers.
    """

    question: str
    passages: tuple[Passage, ...]

    @property
    def found(self) -> bool:
        return bool(self.passages)

    @property
    def best_tier(self) -> Tier | None:
        """The most authoritative tier among the hits.

        A caller weighing a statutory passage against a reference one should
        prefer the statutory, and this saves them re-deriving the ordering.
        """
        if not self.passages:
            return None
        order = list(Tier)
        return min((p.source.tier for p in self.passages), key=order.index)

    def as_context(self) -> str:
        """The passages, formatted for a model prompt.

        Each carries its citation inline, so a model instructed to cite has
        something to cite and a reader can check the citation against the
        passage it sits beside.
        """
        if not self.passages:
            return "No passage in the corpus covers this question."
        blocks = [
            f"[{index}] {passage.text}\n    — {passage.citation}"
            for index, passage in enumerate(self.passages, start=1)
        ]
        return "\n\n".join(blocks)


def embed_query(text: str, model: str = EMBEDDING_MODEL) -> tuple[float, ...]:
    """Embed a question with the local model.

    The only network call in the retrieval path, and it is to localhost. If
    that distinction ever stops being true, this function is where it broke.
    """
    body = json.dumps({"model": model, "prompt": text}).encode()
    request = urllib.request.Request(
        EMBED_ENDPOINT, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return tuple(json.loads(response.read())["embedding"])
    except (urllib.error.URLError, TimeoutError, KeyError) as error:
        raise RetrievalUnavailableError(
            f"could not embed the query with {model}: {error}. The knowledge index "
            f"needs Ollama running locally; start it with 'ollama serve'"
        ) from error


def ask(
    index: KnowledgeIndex,
    question: str,
    *,
    limit: int = 4,
    floor: float = RELEVANCE_FLOOR,
    tiers: tuple[Tier, ...] | None = None,
) -> Answer:
    """Retrieve the passages that bear on a question.

    Returns an empty answer rather than a weak one. A caller deciding what a
    district hospital stocks would rather be told the corpus is silent than be
    handed the least-irrelevant paragraph in it.
    """
    if not question.strip():
        raise ValueError("question is empty; retrieval needs something to embed")
    if index.model != EMBEDDING_MODEL:
        raise KnowledgeIndexError(
            f"index was built with {index.model!r} but this code embeds queries with "
            f"{EMBEDDING_MODEL!r}; vectors from different models are not comparable. "
            f"Rebuild with scripts/build_knowledge_index.py"
        )
    vector = embed_query(question)
    passages = index.search(vector, limit=limit, floor=floor, tiers=tiers)
    return Answer(question=question, passages=passages)
