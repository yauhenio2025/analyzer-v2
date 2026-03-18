"""Consumer-facing live-run routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from src.analysis_products.result_contract import DEFAULT_CONSUMER_KEY
from src.analysis_products.run_contract import build_run_detail, build_run_discovery
from src.analysis_products.schemas import RunDetail, RunSummary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/by-job/{job_id}", response_model=RunDetail)
async def get_run_by_job(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    try:
        return build_run_detail(job_id, consumer_key=consumer_key)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        logger.error("Run detail failed for %s: %s", job_id, error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/discovery", response_model=list[RunSummary])
async def discover_runs(
    project_id: str,
    workflow_key: Optional[str] = None,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
    scope: str = "active",
    limit: int = 20,
    selected_source_thinker_id: Optional[str] = None,
):
    try:
        return build_run_discovery(
            project_id=project_id,
            workflow_key=workflow_key,
            consumer_key=consumer_key,
            scope=scope,
            limit=limit,
            selected_source_thinker_id=selected_source_thinker_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        logger.error("Run discovery failed: %s", error, exc_info=True)
        raise HTTPException(status_code=500, detail=str(error))
