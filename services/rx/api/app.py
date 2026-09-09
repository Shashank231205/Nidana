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
from pydantic import BaseModel, Field

from services.rx.agents.reading_agent import PrescriptionTooLongError, read
from services.rx.agents.resolver import BrandIndex, BrandIndexError, load_brand_index
from services.rx.clinical.checks import Finding, blocks_dispensing, run_all
from services.rx.clinical.interactions import (
    InteractionIndex,
    InteractionIndexError,
    check_interactions,
    findings_from,
    load_interaction_index,
)
from spine.inference.adapter import InferenceProvider
from spine.inference.config import InferenceConfig, build_provider, model_spec
from spine.inference.prompts import (
    Prompt,
    assert_clinical_prompts_are_deterministic,
    load_all,
)
from spine.schemas.medication import MedicationList
from spine.schemas.record import Record

INTERACTION_INDEX_PATH: Final[str] = "NIDANA_INTERACTION_INDEX"
"""Where the drug interaction dataset lives, if the deployment has one.

Unset by default. The best free dataset is CC BY-NC-SA, which fits a
non-commercial deployment and not a commercial one, so the choice belongs to
whoever deploys this rather than to this repository. See
services/rx/rules/interactions/CANDIDATES.md.
"""

INTERACTION_COVERAGE_PATH: Final[str] = "NIDANA_INTERACTION_COVERAGE"
"""Every molecule the dataset knows, including those it cleared.

Optional but strongly wanted: without it, a molecule the dataset examined and
found nothing for cannot be told from one it never saw, and the second must be
reported as unchecked.
"""

INTERACTION_ATTRIBUTION: Final[str] = "NIDANA_INTERACTION_ATTRIBUTION"
"""Who to credit for the interaction data, carried into every finding.

Required whenever an index is configured. CC BY-NC-SA and most other open data
licences require attribution, and a line in a README is not attribution at the
counter where the finding is read.
"""

BRAND_INDEX_PATH: Final[str] = "NIDANA_BRAND_INDEX"
"""Where the brand-to-molecule index lives.

Built by scripts/build_brand_index.py from the open dataset that script names.
Rx starts without it and reports every line unresolved rather than guessing a
molecule, because a wrong molecule silently invalidates every other check on
the list.
"""

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load the brand index before the first request.

    A missing index is not fatal here: the deterministic checks still run, and
    an unresolved line is already a CONTRAINDICATED finding.
    """
    # Module-level state is how startup publishes what it loaded. Request
    # handlers read it; nothing else writes it.
    global _brand_index, _provider, _prompts, _started, _model  # noqa: PLW0603
    global _interaction_index  # noqa: PLW0603
    _brand_index = build_dependencies()
    _interaction_index = build_interaction_index()
    _prompts = load_all("rx")
    assert_clinical_prompts_are_deterministic(_prompts, CONVERSATIONAL_AGENTS)
    config = InferenceConfig.from_environment()
    _provider = build_provider(config)
    _model = config.primary_model
    model_spec(config)
    _started = True
    yield


app = FastAPI(
    title="Nidana Rx",
    description="Prescription reading and dispensing safety checks.",
    version="0.1.0",
    lifespan=lifespan,
)

_brand_index: BrandIndex | None = None
_provider: InferenceProvider | None = None
_model: str = ""
_interaction_index: InteractionIndex | None = None
_prompts: dict[str, Prompt] = {}
_started = False

CONVERSATIONAL_AGENTS: Final[frozenset[str]] = frozenset()
"""Rx has no conversational agent.

Reading a prescription is a transcription task, so every prompt here runs at
temperature 0. Named explicitly so adding one forces the decision.
"""


def build_interaction_index() -> InteractionIndex | None:
    """Load the interaction dataset if one is configured.

    Returns None when unset, and the service then reports
    interaction_checking_available false rather than an empty findings list. A
    deployment that has not licensed a dataset must not appear to have checked.
    """
    configured = os.environ.get(INTERACTION_INDEX_PATH, "").strip()
    if not configured:
        return None
    attribution = os.environ.get(INTERACTION_ATTRIBUTION, "").strip()
    if not attribution:
        raise RuntimeError(
            f"{INTERACTION_INDEX_PATH} is set but {INTERACTION_ATTRIBUTION} is not. "
            f"Name the dataset and its licence, for example "
            f"'DDInter (CC BY-NC-SA 4.0)'; it is shown with every interaction finding"
        )
    coverage = os.environ.get(INTERACTION_COVERAGE_PATH, "").strip()
    try:
        return load_interaction_index(
            Path(configured),
            attribution=attribution,
            covered_path=Path(coverage) if coverage else None,
        )
    except InteractionIndexError as error:
        raise RuntimeError(
            f"{INTERACTION_INDEX_PATH} is set to {configured} but the index did not "
            f"load: {error}. Unset it to run without interaction checking, or fix "
            f"the file"
        ) from error


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
    interaction_checking_available: bool
    molecules_not_interaction_checked: tuple[str, ...]


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
        "interaction_checking_available": _interaction_index is not None,
    }


@app.post("/v1/checks", status_code=status.HTTP_201_CREATED)
def check_prescription(request: CheckRequest) -> CheckResponse:
    """Run every safety check over a medication list.

    Interaction checking runs only when a dataset is configured, and the
    response says which. An empty findings list from a deployment with no
    dataset would read as "no interactions found", which is a different
    statement from "interactions were not checked" and the more dangerous one.

    `molecules_not_interaction_checked` carries the same distinction one level
    down: even with a dataset, the molecules it does not cover were skipped
    rather than cleared.
    """
    if not _started:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; the brand index is not loaded yet",
        )

    interactions: tuple[Finding, ...] = ()
    uncovered: tuple[str, ...] = ()
    if _interaction_index is not None:
        report = check_interactions(request.medications, _interaction_index)
        interactions = findings_from(report, request.medications)
        uncovered = report.uncovered

    findings = run_all(request.medications, request.record, interactions)
    return CheckResponse(
        check_id=uuid4(),
        findings=tuple(_to_response(finding) for finding in findings),
        blocks_dispensing=blocks_dispensing(findings),
        brand_resolution_available=_brand_index is not None,
        interaction_checking_available=_interaction_index is not None,
        molecules_not_interaction_checked=uncovered,
    )


class ReadRequest(BaseModel):
    """The OCR text of a prescription, and where it came from."""

    ocr_text: str = Field(min_length=1)
    source_id: str = Field(min_length=1)


class ReadResponse(BaseModel):
    """What the reading agent read, and what the gate refused.

    `unresolved_count` is separate from `fabrication_count` deliberately. A
    line the pharmacist must confirm is the resolver working as designed; a
    line the model invented is not.
    """

    medications: MedicationList
    fabrication_count: int
    unresolved_count: int
    dropped: tuple[str, ...]


@app.post("/v1/prescriptions/read", status_code=status.HTTP_201_CREATED)
def read_prescription(request: ReadRequest) -> ReadResponse:
    """Read the medication lines from a prescription.

    Brand resolution needs the index, so this refuses without one rather than
    returning every line unresolved: a caller who asked to read a prescription
    and got nothing readable back would reasonably blame the image.
    """
    if not _started or _provider is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; the brand index is not loaded yet",
        )
    if _brand_index is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"brand resolution is unavailable: {BRAND_INDEX_PATH} is not set, so "
                f"every line would come back unresolved. Set it to a brand index, or "
                f"post an already-resolved list to /v1/checks"
            ),
        )
    prompt = _prompts.get("reading_agent")
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="reading_agent prompt is not loaded; check services/rx/prompts/",
        )
    try:
        built = read(
            _provider,
            prompt,
            _model,
            request.ocr_text,
            source_id=request.source_id,
            index=_brand_index,
        )
    except PrescriptionTooLongError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error
    return ReadResponse(
        medications=built.medications,
        fabrication_count=built.fabrication_count,
        unresolved_count=built.unresolved_count,
        dropped=tuple(dropped.reason for dropped in built.dropped),
    )
