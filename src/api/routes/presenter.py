"""Presenter API routes — consumer-facing presentation layer.

Endpoints:
    POST /v1/presenter/refine-views     Refine view recommendations post-execution
    POST /v1/presenter/prepare          Run transformations for recommended views
    GET  /v1/presenter/page/{job_id}    Get complete page presentation
    GET  /v1/presenter/view/{job_id}/{view_key}  Get single view data
    GET  /v1/presenter/status/{job_id}  Check presentation readiness
    POST /v1/presenter/compose          All-in-one: refine + prepare + assemble
"""

import logging

from fastapi import APIRouter, HTTPException

from src.presenter.schemas import (
    ComposeRequest,
    PagePresentation,
    PrepareRequest,
    RefineViewsRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presenter", tags=["presenter"])


@router.post("/refine-views")
async def refine_views(request: RefineViewsRequest):
    """Refine view recommendations based on actual execution results.

    Calls Sonnet to inspect phase results and adjust the planner's
    original recommended_views.
    """
    from src.presenter.view_refiner import refine_views as do_refine

    try:
        result = do_refine(
            job_id=request.job_id,
            plan_id=request.plan_id,
        )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"View refinement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare")
async def prepare_presentation(request: PrepareRequest):
    """Run transformations for recommended views and populate presentation_cache.

    For each recommended view with an applicable transformation template,
    extracts structured data from the stored prose and caches it.
    """
    from src.presenter.presentation_bridge import async_prepare_presentation

    try:
        result = await async_prepare_presentation(
            job_id=request.job_id,
            view_keys=request.view_keys,
        )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Presentation preparation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/page/{job_id}")
async def get_page_presentation(job_id: str):
    """Get complete page presentation for a job.

    Returns a render-ready PagePresentation with nested view tree,
    structured data, and raw prose. The consumer (The Critic) can
    render this directly without additional API calls.
    """
    from src.presenter.presentation_api import assemble_page

    try:
        result = assemble_page(job_id)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Page assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/view/{job_id}/{view_key}")
async def get_single_view(job_id: str, view_key: str):
    """Get a single view's data (for lazy loading on-demand views)."""
    from src.presenter.presentation_api import assemble_single_view

    try:
        result = assemble_single_view(job_id, view_key)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"View not found: {view_key}",
            )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single view assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{job_id}")
async def get_presentation_status(job_id: str):
    """Check which views have data ready, need transformation, or are empty.

    Useful for the consumer to know what's available before requesting
    the full page presentation.
    """
    from src.presenter.presentation_api import get_presentation_status as do_status

    try:
        return do_status(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compose")
async def compose_presentation(request: ComposeRequest):
    """All-in-one: refine views + prepare transformations + assemble page.

    This is the convenience endpoint that runs the full presentation
    pipeline in sequence:
    1. Refine view recommendations (unless skip_refinement=True)
    2. Run applicable transformations
    3. Assemble the page presentation

    Returns the complete PagePresentation.
    """
    from src.presenter.presentation_api import assemble_page
    from src.presenter.presentation_bridge import async_prepare_presentation
    from src.presenter.view_refiner import refine_views

    try:
        # Step 1: Refine views
        if not request.skip_refinement:
            try:
                refinement = refine_views(
                    job_id=request.job_id,
                    plan_id=request.plan_id,
                )
                logger.info(
                    f"View refinement complete: {len(refinement.refined_views)} views, "
                    f"{refinement.tokens_used} tokens"
                )
            except Exception as e:
                logger.warning(f"View refinement failed (continuing): {e}")

        # Step 2: Prepare transformations (async — safe in FastAPI context)
        try:
            bridge_result = await async_prepare_presentation(job_id=request.job_id)
            logger.info(
                f"Presentation prep complete: {bridge_result.tasks_completed} transformed, "
                f"{bridge_result.cached_results} cached, {bridge_result.tasks_skipped} skipped"
            )
        except Exception as e:
            logger.warning(f"Presentation preparation failed (continuing): {e}")

        # Step 3: Assemble page
        page = assemble_page(request.job_id)
        return page.model_dump()

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Compose failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
