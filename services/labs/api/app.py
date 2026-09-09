"""The Labs HTTP boundary. No clinical reasoning happens here.

Every endpoint delegates to the deterministic threshold layer and serialises
what comes back.

Two things this layer refuses to hide. Unit mismatches are reported in the
response body rather than logged, because a threshold that could not be applied
is a missed critical value and that is the one failure this service exists to
prevent. And a critical finding carries the `unverified` flag of the threshold
that produced it, so a reader can see which numbers are still awaiting
clinician sign-off.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from services.labs.agents.extraction_agent import ReportTooLongError, extract
from services.labs.clinical.critical_values import (
    CriticalFinding,
    CriticalThreshold,
    check,
    load_thresholds,
    require_verified,
    unit_mismatches,
)
from spine.inference.adapter import InferenceProvider
from spine.inference.config import InferenceConfig, build_provider, model_spec
from spine.inference.prompts import (
    Prompt,
    assert_clinical_prompts_are_deterministic,
    load_all,
)
from spine.schemas.lab import LabReport

CONVERSATIONAL_AGENTS: Final[frozenset[str]] = frozenset()
"""Labs has no conversational agent.

Reading a report is a transcription task, so every prompt here runs at
temperature 0. Named explicitly so adding one forces the decision.
"""


@dataclass(frozen=True)
class Dependencies:
    thresholds: dict[str, CriticalThreshold]
    provider: InferenceProvider
    prompts: dict[str, Prompt]
    model: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load and validate everything before the first request, or refuse to serve.

    A deployment that cannot detect a critical value should not accept reports:
    returning "no critical findings" because the thresholds failed to load is
    indistinguishable, to the reader, from a normal result.
    """
    # Module-level state is how startup publishes what it loaded. Request
    # handlers read it; nothing else writes it.
    global _dependencies  # noqa: PLW0603
    _dependencies = build_dependencies()
    yield


app = FastAPI(
    title="Nidana Labs",
    description="Lab report interpretation and critical value detection.",
    version="0.1.0",
    lifespan=lifespan,
)

_dependencies: Dependencies | None = None

ALLOW_UNVERIFIED: Final[str] = "NIDANA_ALLOW_UNVERIFIED_RULES"


def _allow_unverified() -> bool:
    return os.environ.get(ALLOW_UNVERIFIED, "true").strip().lower() == "true"


def build_dependencies() -> Dependencies:
    """Load and validate everything, or refuse to start.

    Thresholds are checked before the model is reached: a deployment that
    cannot detect a critical value should not accept reports whether or not
    inference works.
    """
    thresholds = load_thresholds()
    require_verified(thresholds, allow_unverified=_allow_unverified())

    prompts = load_all("labs")
    assert_clinical_prompts_are_deterministic(prompts, CONVERSATIONAL_AGENTS)

    config = InferenceConfig.from_environment()
    provider = build_provider(config)
    model_spec(config)

    return Dependencies(
        thresholds=thresholds,
        provider=provider,
        prompts=prompts,
        model=config.primary_model,
    )




def _deps() -> Dependencies:
    if _dependencies is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; critical value thresholds are not loaded yet",
        )
    return _dependencies


class CriticalFindingResponse(BaseModel):
    analyte: str
    value: float
    unit: str
    flag: str
    threshold: float
    source: str
    unverified: bool
    message: str


class InterpretResponse(BaseModel):
    """What the deterministic layer concluded about one report.

    `unit_mismatches` names analytes whose threshold could not be applied. It is
    part of the response rather than a log line because an empty findings list
    means something different when this list is not empty.
    """

    report_id: UUID
    critical_findings: tuple[CriticalFindingResponse, ...]
    unit_mismatches: tuple[str, ...]
    has_critical_value: bool


def _to_response(finding: CriticalFinding) -> CriticalFindingResponse:
    return CriticalFindingResponse(
        analyte=finding.analyte,
        value=finding.value,
        unit=finding.unit,
        flag=finding.flag.value,
        threshold=finding.threshold,
        source=finding.source,
        unverified=finding.unverified,
        message=finding.message,
    )


@app.get("/health")
def health() -> dict[str, object]:
    """Whether this instance can serve."""
    ready = _dependencies is not None
    return {
        "status": "healthy" if ready else "degraded",
        "thresholds_loaded": len(_dependencies.thresholds) if _dependencies else 0,
    }


@app.post("/v1/reports", status_code=status.HTTP_201_CREATED)
def interpret(report: LabReport) -> InterpretResponse:
    """Check a report against every critical threshold.

    Trend tracking is deliberately absent: it needs the patient's prior results,
    which arrive through the record rather than the report, and a trend computed
    from one point is not a trend.
    """
    thresholds = _deps().thresholds
    findings = check(report, thresholds)
    return InterpretResponse(
        report_id=uuid4(),
        critical_findings=tuple(_to_response(finding) for finding in findings),
        unit_mismatches=unit_mismatches(report, thresholds),
        has_critical_value=bool(findings),
    )


class ExtractRequest(BaseModel):
    """The text of a report, and where it came from."""

    report_text: str = Field(min_length=1)
    source_id: str = Field(min_length=1)


class ExtractResponse(BaseModel):
    """What the extraction agent read, and what the gate refused.

    `dropped` is part of the response rather than a log line. A result the gate
    refused is one a human must enter by hand, and a caller who cannot see the
    refusals does not know the report is incomplete.
    """

    report: LabReport
    fabrication_count: int
    dropped: tuple[str, ...]
    critical_findings: tuple[CriticalFindingResponse, ...]
    unit_mismatches: tuple[str, ...]
    has_critical_value: bool


@app.post("/v1/reports/extract", status_code=status.HTTP_201_CREATED)
def extract_report(request: ExtractRequest) -> ExtractResponse:
    """Read a report, then check what was read against the thresholds.

    Extraction and checking are one call because a report read but not checked
    is the failure this service exists to prevent, and leaving the second step
    to the caller makes forgetting it possible.
    """
    dependencies = _deps()
    prompt = dependencies.prompts.get("extraction_agent")
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="extraction_agent prompt is not loaded; check services/labs/prompts/",
        )
    try:
        built = extract(
            dependencies.provider,
            prompt,
            dependencies.model,
            request.report_text,
            request.source_id,
        )
    except ReportTooLongError as error:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(error)
        ) from error

    report = LabReport(results=built.results)
    findings = check(report, dependencies.thresholds)
    return ExtractResponse(
        report=report,
        fabrication_count=built.fabrication_count,
        dropped=tuple(dropped.reason for dropped in built.dropped),
        critical_findings=tuple(_to_response(finding) for finding in findings),
        unit_mismatches=unit_mismatches(report, dependencies.thresholds),
        has_critical_value=bool(findings),
    )


@app.get("/v1/thresholds")
def read_thresholds() -> dict[str, object]:
    """The loaded thresholds and their verification state.

    Exposed so an operator can see which numbers are awaiting clinician
    sign-off without reading the rules directory on the server.
    """
    thresholds = _deps().thresholds
    return {
        "count": len(thresholds),
        "unverified": [
            analyte
            for analyte, threshold in sorted(thresholds.items())
            if threshold.verify_before_ship
        ],
    }
