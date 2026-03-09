"""Feedback API routes for Tier 3a capture and aggregation."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.feedback.schemas import (
    FeedbackIngestRequest,
    FeedbackIngestResponse,
    FeedbackListResponse,
    FeedbackSummaryResponse,
)
from src.feedback.store import list_events, save_events, summarize_events

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/events", response_model=FeedbackIngestResponse)
async def ingest_feedback_events(request: FeedbackIngestRequest) -> FeedbackIngestResponse:
    """Batch ingest feedback events with idempotent dedup by event_id."""
    accepted, duplicates = save_events(request.events)
    return FeedbackIngestResponse(accepted=accepted, duplicates=duplicates)


@router.get("/events", response_model=FeedbackListResponse)
async def get_feedback_events(
    job_id: Optional[str] = None,
    project_id: Optional[str] = None,
    event_type: Optional[str] = None,
    view_key: Optional[str] = None,
    from_ts: Optional[str] = Query(default=None, alias="from"),
    to_ts: Optional[str] = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> FeedbackListResponse:
    """List feedback events with filtering and pagination."""
    event_types = None
    if event_type:
        event_types = [part.strip() for part in event_type.split(",") if part.strip()]

    try:
        events, total = list_events(
            job_id=job_id,
            project_id=project_id,
            event_types=event_types,
            view_key=view_key,
            from_ts=from_ts,
            to_ts=to_ts,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FeedbackListResponse(
        events=events,
        count=len(events),
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=FeedbackSummaryResponse)
async def get_feedback_summary(
    job_id: Optional[str] = None,
    project_id: Optional[str] = None,
    from_ts: Optional[str] = Query(default=None, alias="from"),
    to_ts: Optional[str] = Query(default=None, alias="to"),
    group_by: str = "event_type",
) -> FeedbackSummaryResponse:
    """Aggregate feedback events by whitelisted group keys."""
    group_fields = [part.strip() for part in group_by.split(",") if part.strip()]

    try:
        groups, total_events = summarize_events(
            job_id=job_id,
            project_id=project_id,
            from_ts=from_ts,
            to_ts=to_ts,
            group_by=group_fields,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return FeedbackSummaryResponse(
        job_id=job_id,
        project_id=project_id,
        from_ts=from_ts,
        to_ts=to_ts,
        groups=groups,
        total_events=total_events,
    )
