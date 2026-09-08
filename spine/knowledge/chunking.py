"""Splitting a source document into retrievable passages.

The failure this module exists to prevent: a chunk boundary falling between a
clinical statement and the qualification that makes it safe. "Give adrenaline
0.5mg IM" retrieved without the next sentence — the one naming the
contraindication — is worse than retrieving nothing, because it reads complete.

So chunks overlap, and they prefer to break at a blank line or a sentence end
rather than at a character count. A passage that ends mid-sentence is a passage
a reader cannot trust.

Chunks are not summarised, paraphrased or cleaned. What is indexed is what the
document says, character for character, so a retrieved passage can be found in
the original and checked. This is the same discipline the provenance layer
applies to patient utterances, for the same reason.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Final

TARGET_CHARACTERS: Final[int] = 1200
"""Roughly 250 words: long enough to hold a statement with its qualification,
short enough that a retrieved passage is read rather than skimmed."""

OVERLAP_CHARACTERS: Final[int] = 200
"""Carried from the end of one chunk into the next.

Cheap insurance against the boundary problem above. A statement split across
two chunks appears whole in at least one of them.
"""

MINIMUM_CHARACTERS: Final[int] = 120
"""Below this a chunk is dropped.

Page headers, footers and stray table fragments. They embed to nothing useful
and dilute a search for real content.
"""

MAX_NUMERIC_RATIO: Final[float] = 0.18
"""Above this proportion of digits, a chunk is dropped as navigation.

A contents page is mostly page numbers and a real clinical passage is mostly
words. Dosages and thresholds push the ratio up, so the bar sits well above
what prose containing numbers reaches — the intent is to drop "7.3. Medicines
57 7.4. Diagnostics 58", not "adrenaline 0.5mg IM repeated after 5 minutes".
"""

_BREAK = re.compile(r"\n\s*\n|(?<=[.;:])\s+(?=[A-Z(])")
"""Where a chunk prefers to end: a blank line, or a sentence boundary followed
by something that looks like the start of a new one."""

_WHITESPACE = re.compile(r"[ \t]+")
_PAGE_NOISE = re.compile(
    r"^\s*(?:page\s+)?\d{1,4}\s*$|^\s*IPHS\s*$|^\s*\|\s*$", re.IGNORECASE | re.MULTILINE
)


@dataclass(frozen=True)
class Chunk:
    """One retrievable passage, and where in the document it came from.

    `char_start` and `char_end` index into the extracted text of the source, so
    a retrieved chunk can be located in the original rather than merely
    believed. `chunk_id` is content-addressed: re-indexing an unchanged
    document produces the same ids, so an index rebuild does not invalidate a
    citation someone wrote down.
    """

    chunk_id: str
    source_id: str
    text: str
    char_start: int
    char_end: int
    page: int | None = None

    def __post_init__(self) -> None:
        if self.char_end <= self.char_start:
            raise ValueError(
                f"chunk {self.chunk_id} spans no text ({self.char_start}:{self.char_end})"
            )


def _content_id(source_id: str, text: str) -> str:
    digest = hashlib.sha256(f"{source_id}\x00{text}".encode()).hexdigest()
    return digest[:16]


def tidy(raw: str) -> str:
    """Normalise whitespace without changing what the document says.

    Runs of spaces collapse and page-number lines go, because a PDF extractor
    produces both and neither is content. Line structure is otherwise kept:
    it is what tells a table row from a paragraph.
    """
    text = _PAGE_NOISE.sub("", raw)
    text = _WHITESPACE.sub(" ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def is_navigation(text: str) -> bool:
    """Whether a passage is a contents listing rather than content.

    Judged by digit density. A retrieved contents entry answers no clinical
    question and displaces a passage that would have.
    """
    if not text:
        return True
    digits = sum(1 for character in text if character.isdigit())
    return digits / len(text) > MAX_NUMERIC_RATIO


def _split_points(text: str, start: int, ceiling: int) -> int:
    """The best place to end a chunk that begins at `start`.

    Prefers the last natural break before the ceiling, but only one that lands
    in the back half of the window. A break near the start would produce a
    chunk far shorter than the target, and a document dense in short lines —
    a contents page, a table — would otherwise fragment into hundreds of
    passages too small to hold a statement with its qualification.

    Falls back to the ceiling when the window holds no late break, which is the
    right answer inside a long table.
    """
    window = text[start:ceiling]
    floor = len(window) // 2
    breaks = [match.end() for match in _BREAK.finditer(window) if match.end() >= floor]
    if not breaks:
        return ceiling
    return start + breaks[-1]


def chunk_document(
    text: str,
    source_id: str,
    *,
    target: int = TARGET_CHARACTERS,
    overlap: int = OVERLAP_CHARACTERS,
) -> tuple[Chunk, ...]:
    """Split a document into overlapping passages.

    Pure. Text in, chunks out, no I/O and no model call, so the boundary
    behaviour is exhaustively testable.
    """
    if overlap >= target:
        raise ValueError(
            f"overlap ({overlap}) must be smaller than target ({target}); an overlap "
            f"at or above the target would never advance and would loop"
        )
    cleaned = tidy(text)
    chunks: list[Chunk] = []
    position = 0
    length = len(cleaned)

    while position < length:
        ceiling = min(position + target, length)
        end = ceiling if ceiling >= length else _split_points(cleaned, position, ceiling)
        body = cleaned[position:end].strip()
        if len(body) >= MINIMUM_CHARACTERS and not is_navigation(body):
            chunks.append(
                Chunk(
                    chunk_id=_content_id(source_id, body),
                    source_id=source_id,
                    text=body,
                    char_start=position,
                    char_end=end,
                )
            )
        if end >= length:
            break
        position = max(end - overlap, position + 1)

    return tuple(chunks)
