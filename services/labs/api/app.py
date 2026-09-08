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
from typing import Final
from uuid import UUID, uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from services.labs.clinical.critical_values import (
    CriticalFinding,
    CriticalThreshold,
    check,
    load_thresholds,
    require_verified,
    unit_mismatches,
)
from spine.schemas.lab import LabReport


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Load and validate everything before the first request, or refuse to serve.

    A deployment that cannot detect a critical value should not accept reports:
    returning "no critical findings" because the thresholds failed to load is
    indistinguishable, to the reader, from a normal result.
    """
    # Module-level state is how startup publishes what it loaded. Request
    # handlers read it; nothing else writes it.
    global _thresholds  # noqa: PLW0603
    _thresholds = build_dependencies()
    yield


app = FastAPI(
    title="Nidana Labs",
    description="Lab report interpretation and critical value detection.",
    version="0.1.0",
    lifespan=lifespan,
)

_thresholds: dict[str, CriticalThreshold] | None = None

ALLOW_UNVERIFIED: Final[str] = "NIDANA_ALLOW_UNVERIFIED_RULES"


def _allow_unverified() -> bool:
    return os.environ.get(ALLOW_UNVERIFIED, "true").strip().lower() == "true"


def build_dependencies() -> dict[str, CriticalThreshold]:
    """Load and validate the thresholds, or refuse to start.

    A deployment that cannot detect a critical value should not accept reports:
    returning "no critical findings" because the thresholds failed to load is
    indistinguishable, to the reader, from a normal result.
    """
    thresholds = load_thresholds()
    require_verified(thresholds, allow_unverified=_allow_unverified())
    return thresholds




def _deps() -> dict[str, CriticalThreshold]:
    if _thresholds is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="service is still starting; critical value thresholds are not loaded yet",
        )
    return _thresholds


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
    ready = _thresholds is not None
    return {
        "status": "healthy" if ready else "degraded",
        "thresholds_loaded": len(_thresholds) if _thresholds else 0,
    }


@app.post("/v1/reports", status_code=status.HTTP_201_CREATED)
def interpret(report: LabReport) -> InterpretResponse:
    """Check a report against every critical threshold.

    Trend tracking is deliberately absent: it needs the patient's prior results,
    which arrive through the record rather than the report, and a trend computed
    from one point is not a trend.
    """
    thresholds = _deps()
    findings = check(report, thresholds)
    return InterpretResponse(
        report_id=uuid4(),
        critical_findings=tuple(_to_response(finding) for finding in findings),
        unit_mismatches=unit_mismatches(report, thresholds),
        has_critical_value=bool(findings),
    )


@app.get("/v1/thresholds")
def read_thresholds() -> dict[str, object]:
    """The loaded thresholds and their verification state.

    Exposed so an operator can see which numbers are awaiting clinician
    sign-off without reading the rules directory on the server.
    """
    thresholds = _deps()
    return {
        "count": len(thresholds),
        "unverified": [
            analyte
            for analyte, threshold in sorted(thresholds.items())
            if threshold.verify_before_ship
        ],
    }
