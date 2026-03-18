"""Result manifest, discovery, and presentation-refresh routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.analysis_products.result_contract import (
    ConflictError,
    DEFAULT_CONSUMER_KEY,
    attach_project_to_job,
    build_discovery_summaries,
    build_result_manifest,
    get_result_presentation,
    refresh_presentation_result,
)
from src.analysis_products.schemas import (
    AnalysisResultManifest,
    AnalysisResultPresentationResponse,
    AttachProjectRequest,
    AttachProjectResponse,
    DiscoverySummary,
    RefreshPresentationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/results", tags=["results"])


@router.get("/by-job/{job_id}", response_model=AnalysisResultManifest)
async def get_result_manifest(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Get the consumer-facing result manifest for a job."""

    try:
        return build_result_manifest(job_id, consumer_key=consumer_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.error("Result manifest failed for %s: %s", job_id, error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/by-job/{job_id}/presentation", response_model=AnalysisResultPresentationResponse)
async def get_result_presentation_route(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Get the current authoritative result presentation state without mutating preparation."""

    try:
        return get_result_presentation(job_id, consumer_key=consumer_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.error("Result presentation read failed for %s: %s", job_id, error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/by-job/{job_id}/refresh-presentation", response_model=RefreshPresentationResponse)
async def refresh_result_presentation(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Refresh presenter-owned delivery artifacts for a job without re-executing analysis."""

    try:
        return refresh_presentation_result(job_id, consumer_key=consumer_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.error("Result refresh failed for %s: %s", job_id, error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/discovery", response_model=list[DiscoverySummary])
async def discover_results(
    project_id: str,
    workflow_key: Optional[str] = None,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
    selected_source_thinker_id: Optional[str] = None,
    limit: int = 50,
):
    """Discover completed analysis results as lightweight summaries.

    Returns completed jobs matching the filters, sorted by completed_at DESC.
    Does not assemble pages — only manifest-level metadata.
    """

    try:
        return build_discovery_summaries(
            project_id=project_id,
            workflow_key=workflow_key,
            consumer_key=consumer_key,
            selected_source_thinker_id=selected_source_thinker_id,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.error("Discovery failed: %s", error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/by-job/{job_id}/attach-project", response_model=AttachProjectResponse)
async def attach_project(
    job_id: str,
    request: AttachProjectRequest,
):
    """Attach a project_id to an existing job for upstream discoverability.

    - If project_id is null on the job, sets it.
    - If it already matches, returns success (idempotent).
    - If it points to a different project, returns 409 Conflict.
    """

    try:
        return attach_project_to_job(job_id, request.project_id)
    except ValueError as error:
        detail = str(error)
        status_code = 400 if detail == "project_id is required" else 404
        raise HTTPException(status_code=status_code, detail=detail)
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error))
    except Exception as error:
        logger.error("Attach project failed for %s: %s", job_id, error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))
