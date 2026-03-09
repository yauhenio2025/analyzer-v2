"""API routes for Tier 3b A/B View Composition — variant generation and selection."""

import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Response

from src.feedback.schemas import FeedbackEventInput, FeedbackEventType
from src.feedback.store import save_events
from src.presenter.variant_generator import generate_variant_set
from src.presenter.variant_schemas import (
    VariantGenerateRequest,
    VariantSelectRequest,
    VariantSelectionResponse,
    VariantSelectionSummary,
    VariantSetResponse,
)
from src.presenter.variant_store import (
    list_variant_sets,
    load_selections,
    load_variant_set,
    save_selection,
    summarize_selections,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/variants", tags=["variants"])


@router.post("/generate", response_model=VariantSetResponse)
async def generate_variants(request: VariantGenerateRequest):
    """Generate 2-3 presentation variants for a view.

    Returns a variant set with control + alternative variants.
    If no compatible alternatives are found, returns control-only
    (variant_count=1) with metadata.reason explaining why.
    """
    try:
        result = generate_variant_set(
            job_id=request.job_id,
            view_key=request.view_key,
            dimension=request.dimension,
            max_variants=request.max_variants,
            style_school=request.style_school,
            force=request.force,
        )
        return VariantSetResponse(**result)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)


@router.get("/sets", response_model=list[VariantSetResponse])
async def list_sets(job_id: str, view_key: str):
    """List variant sets for a job+view combination."""
    if not job_id or not view_key:
        raise HTTPException(status_code=400, detail="job_id and view_key are required")
    sets = list_variant_sets(job_id, view_key)
    return [VariantSetResponse(**s) for s in sets]


@router.get("/sets/{variant_set_id}", response_model=VariantSetResponse)
async def get_set(variant_set_id: str):
    """Get a specific variant set by ID."""
    result = load_variant_set(variant_set_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Variant set not found: {variant_set_id}")
    return VariantSetResponse(**result)


@router.post("/select", response_model=VariantSelectionResponse)
async def select_variant(request: VariantSelectRequest):
    """Select a variant from a variant set.

    Upserts the selection (replaces previous choice for same set+job).
    Emits a variant_selected feedback event.
    """
    # Validate variant_id belongs to variant_set_id
    vs = load_variant_set(request.variant_set_id)
    if vs is None:
        raise HTTPException(
            status_code=404,
            detail=f"Variant set not found: {request.variant_set_id}",
        )

    matching_variant = None
    for v in vs["variants"]:
        if v["variant_id"] == request.variant_id:
            matching_variant = v
            break

    if matching_variant is None:
        raise HTTPException(
            status_code=400,
            detail=f"Variant {request.variant_id} not in set {request.variant_set_id}",
        )

    view_key = vs["view_key"]

    # Persist selection
    selected_at = save_selection(
        variant_set_id=request.variant_set_id,
        variant_id=request.variant_id,
        job_id=request.job_id,
        view_key=view_key,
        project_id=request.project_id,
    )

    # Emit feedback event
    feedback_emitted = False
    try:
        event_hash_input = f"{request.job_id}|{request.variant_set_id}|{request.variant_id}"
        event_id = f"vsel-{hashlib.sha256(event_hash_input.encode()).hexdigest()[:24]}"

        event = FeedbackEventInput(
            event_id=event_id,
            event_type=FeedbackEventType.VARIANT_SELECTED,
            job_id=request.job_id,
            project_id=request.project_id,
            view_key=view_key,
            renderer_type=matching_variant["renderer_type"],
            payload={
                "variant_set_id": request.variant_set_id,
                "variant_id": request.variant_id,
                "dimension": vs["dimension"],
                "selected_renderer": matching_variant["renderer_type"],
                "base_renderer": vs["base_renderer"],
                "compatibility_score": matching_variant.get("compatibility_score", 0.0),
                "variant_index": matching_variant["variant_index"],
            },
        )
        accepted, _ = save_events([event])
        feedback_emitted = accepted > 0
        logger.info(
            f"Variant selected: {request.variant_id} from set {request.variant_set_id} "
            f"(feedback_emitted={feedback_emitted})"
        )
    except Exception as e:
        logger.error(f"Failed to emit variant_selected feedback event: {e}")

    return VariantSelectionResponse(
        variant_set_id=request.variant_set_id,
        variant_id=request.variant_id,
        view_key=view_key,
        selected_at=selected_at,
        feedback_event_emitted=feedback_emitted,
    )


@router.get("/selection")
async def get_selection(job_id: str, view_key: str, response: Response):
    """Get current selections for a job+view.

    Returns 204 if no selections exist.
    """
    if not job_id or not view_key:
        raise HTTPException(status_code=400, detail="job_id and view_key are required")

    selections = load_selections(job_id, view_key)
    if not selections:
        response.status_code = 204
        return None

    return selections


@router.get("/selections/summary", response_model=list[VariantSelectionSummary])
async def selections_summary(project_id: str):
    """Aggregate selection data grouped by dimension and view_key."""
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    rows = summarize_selections(project_id)
    return [
        VariantSelectionSummary(
            project_id=project_id,
            dimension=r["dimension"],
            view_key=r["view_key"],
            base_renderer=r["base_renderer"],
            selected_renderer=r["selected_renderer"],
            selection_count=r["selection_count"],
        )
        for r in rows
    ]
