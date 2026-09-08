"""Build the local knowledge index from the corpus registry.

Run once, at build or deployment time, with a network connection and Ollama
running. Everything after that is local: the index it writes is searched with
no network access at all.

    python scripts/build_knowledge_index.py

This is the only part of Nidana that reaches the internet, and it is
deliberately a separate script rather than something a service does lazily. A
clinic's deployment fetches the corpus once, reviews what it got, and ships the
index. A service that fetched on demand would be a service that phones home.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spine.knowledge.chunking import Chunk, chunk_document
from spine.knowledge.index import EMBEDDING_MODEL, Entry, KnowledgeIndex
from spine.knowledge.sources import REGISTRY, Source

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
CACHE: Final[Path] = REPO_ROOT / "data" / "corpus"
INDEX_PATH: Final[Path] = REPO_ROOT / "data" / "knowledge_index.json"
OLLAMA: Final[str] = "http://localhost:11434/api/embeddings"

USER_AGENT: Final[str] = "nidana-corpus-builder"
"""Named rather than disguised. A publisher whose logs show what fetched their
document can ask us to stop, which is the correct relationship to have with a
source we intend to cite."""


def fetch(source: Source, *, refresh: bool = False) -> Path:
    """Download a source, caching it so a rebuild does not refetch.

    The cache is by source id and version, so bumping a version in the registry
    fetches the new edition rather than silently reusing the old one.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    target = CACHE / f"{source.id}-{source.version}.pdf"
    if target.is_file() and not refresh:
        return target
    request = urllib.request.Request(source.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response:
        target.write_bytes(response.read())
    return target


def extract(path: Path) -> str:
    """Pull the text out of a PDF.

    pypdf is a build-time dependency only. The clinic's runtime never parses a
    PDF; it reads the index this script produced.
    """
    try:
        from pypdf import PdfReader  # noqa: PLC0415
    except ImportError as error:
        raise SystemExit(
            "pypdf is needed to build the index: pip install pypdf. It is a "
            "build-time dependency and is not required to run Nidana"
        ) from error
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def embed(text: str, model: str = EMBEDDING_MODEL) -> tuple[float, ...]:
    """Embed one passage with the local model."""
    body = json.dumps({"model": model, "prompt": text}).encode()
    request = urllib.request.Request(
        OLLAMA, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return tuple(json.loads(response.read())["embedding"])


def build(
    *, refresh: bool = False, limit: int | None = None, workers: int = 8
) -> KnowledgeIndex:
    entries: list[Entry] = []
    for source in REGISTRY:
        print(f"[{source.id}] {source.tier.value}")
        try:
            path = fetch(source, refresh=refresh)
        except OSError as error:
            print(f"  fetch failed: {error}. Skipped.")
            continue
        chunks: tuple[Chunk, ...] = chunk_document(extract(path), source.id)
        if limit is not None:
            chunks = chunks[:limit]
        print(f"  {len(chunks)} chunks, embedding with {workers} workers")
        entries.extend(_embed_all(chunks, workers))
    return KnowledgeIndex(tuple(entries))


def _embed_all(chunks: tuple[Chunk, ...], workers: int) -> list[Entry]:
    """Embed a document's chunks concurrently.

    Serially this runs at roughly two seconds a chunk, which is twenty minutes
    for one volume and long enough that a deployment skips the step. Ollama
    handles concurrent embedding requests, and the work is IO-bound from here,
    so a thread pool is the whole fix.

    Results are reordered to match the input: the index stores char offsets and
    a citation that pointed at the wrong passage would be worse than no
    citation at all.
    """
    done = 0
    ordered: list[Entry | None] = [None] * len(chunks)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(embed, chunk.text): position
            for position, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            position = futures[future]
            ordered[position] = Entry(chunk=chunks[position], vector=future.result())
            done += 1
            if done % 100 == 0:
                print(f"    {done}/{len(chunks)}")
    return [entry for entry in ordered if entry is not None]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="refetch cached sources")
    parser.add_argument(
        "--limit", type=int, default=None, help="chunks per source, for a smoke build"
    )
    parser.add_argument(
        "--workers", type=int, default=8, help="concurrent embedding requests"
    )
    arguments = parser.parse_args()

    index = build(
        refresh=arguments.refresh, limit=arguments.limit, workers=arguments.workers
    )
    if not len(index):
        print("No chunks indexed. Nothing written.")
        return 1
    index.save(INDEX_PATH)
    size_mb = INDEX_PATH.stat().st_size / 1_000_000
    print(
        f"\nOK: {len(index)} chunks from {len(index.sources)} source(s) "
        f"-> {INDEX_PATH} ({size_mb:.1f} MB)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
