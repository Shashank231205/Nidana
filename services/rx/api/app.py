"""The Rx HTTP boundary. No clinical reasoning happens here.

Every endpoint delegates to the deterministic check layer and serialises what
comes back. The one thing this layer decides is whether a response reports a
dispensing block, and it does that by reading `blocks_dispensing` rather than
inspecting severities itself.

Rx never computes a dose. It range-checks a stated dose and flags implausibility
for a human, which stays the right side of the regulatory boundary.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from services.rx.agents.resolver import BrandIndex, BrandIndexError, load_brand_index
from services.rx.clinical.checks import Finding, blocks_dispensing, run_all
from spine.schemas.medication import MedicationList
from spine.schemas.record import Record

BRAND_INDEX_PATH: Final[str] = "NIDANA_BRAND_INDEX"
"""Where the brand-to-molecule index lives.

BUILD_SPEC lists this dataset as an unresolved dependency. Rx starts without
it and reports every line unresolved rather than guessing a molecule, because
a wrong molecule silently invalidates every other check on the list.
"""

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load the brand index before the first request.

    A missing index is not fatal here: the deterministic checks still run, and
    an unresolved line is already a CONTRAINDICATED finding.
    """
    # Module-level state is how startup publishes what it loaded. Request
    # handlers read it; nothing else writes it.
    global _brand_index, _started  # noqa: PLW0603
    _brand_index = build_dependencies()
    _started = True
    yield


app = FastAPI(
    title="Nidana Rx",
    description="Prescription reading and dispensing safety checks.",
    version="0.1.0",
    lifespan=lifespan,
)

_brand_index: BrandIndex | None = None
_started = False


def build_dependencies() -> BrandIndex | None:
    """Load the brand index if one is configured.

    Returns None rather than raising when the path is unset: an unresolved line
    is a reported finding with CONTRAINDICATED severity, not a crash, and a
    pharmacy with no index still gets duplicate-therapy and allergy checking.
    """
    configured = os.environ.get(BRAND_INDEX_PATH, "").strip()
    if not configured:
        return None
    try:
        return load_brand_index(Path(configured))
    except BrandIndexError as error:
        raise RuntimeError(
            f"{BRAND_INDEX_PATH} is set to {configured} but the index did not load: "
            f"{error}. Unset it to run without brand resolution, or fix the file"
        ) from error


class FindingResponse(BaseModel):
    """One thing a pharmacist or prescriber should look at."""

    kind: str
    severity: str
    molecules: tuple[str, ...]
    written_as: tuple[str, ...]
    message: str
    source: str
    blocks_dispensing: bool


class CheckRequest(BaseModel):
    medications: MedicationList
    record: Record


class CheckResponse(BaseModel):
    """The result of every check that could run.

    `blocks_dispensing` is derived from the findings rather than stored beside
    them, so the two cannot disagree.
    """

    check_id: UUID
    findings: tuple[FindingResponse, ...]
    blocks_dispensing: bool
    brand_resolution_available: bool


def _to_response(finding: Finding) -> FindingResponse:
    return FindingResponse(
        kind=finding.kind.value,
        severity=finding.severity.value,
        molecules=finding.molecules,
        written_as=finding.written_as,
        message=finding.message,
        source=finding.source,
        blocks_dispensing=finding.blocks_dispensing,
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Whether this instance can serve.

    Brand resolution being unavailable is reported rather than treated as
    unhealthy: the deterministic checks still run without it.
    """
    return {
        "status": "healthy" if _started else "degraded",
        "brand_resolution_available": _brand_index is not None,
    }


@app.post("/v1/checks", status_code=status.HTTP_201_CREATED)
def check_prescription(request: CheckRequest) -> CheckResponse:
    """Run every safety check over a medication list.

    Interaction checking is deliberately absent from the result. It needs a
    licensed interaction dataset, and approximating it from general knowledge
    would produce a check that looks like it works.
    """
    if not _started:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; the brand index is not loaded yet",
        )
    findings = run_all(request.medications, request.record)
    return CheckResponse(
        check_id=uuid4(),
        findings=tuple(_to_response(finding) for finding in findings),
        blocks_dispensing=blocks_dispensing(findings),
        brand_resolution_available=_brand_index is not None,
    )
