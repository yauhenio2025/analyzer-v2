"""Presenter API routes — consumer-facing presentation layer.

Endpoints:
    POST /v1/presenter/refine-views     Refine view recommendations post-execution
    POST /v1/presenter/prepare          Run transformations for recommended views
    GET  /v1/presenter/page/{job_id}    Get complete page presentation
    GET  /v1/presenter/view/{job_id}/{view_key}  Get single view data
    GET  /v1/presenter/status/{job_id}  Check presentation readiness
    POST /v1/presenter/compose          All-in-one: refine + prepare + assemble
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from src.presenter.schemas import (
    ComposeRequest,
    EffectivePresentationManifest,
    EnsurePresentationRequest,
    PagePresentation,
    PolishRequest,
    PresentationDecisionTrace,
    PrepareRequest,
    RefineViewsRequest,
    SectionPolishRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/presenter", tags=["presenter"])
DEFAULT_CONSUMER_KEY = "the-critic"


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
            consumer_key=request.consumer_key,
        )
        # Touch project activity (user is actively working with results)
        from src.executor.project_manager import touch_project_activity_for_job
        touch_project_activity_for_job(request.job_id)

        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"View refinement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/refine-views/{job_id}")
async def delete_view_refinement(job_id: str):
    """Delete view refinement for a job, falling back to registry defaults."""
    from src.executor.db import execute

    try:
        execute("DELETE FROM view_refinements WHERE job_id = %s", (job_id,))
        return {"deleted": True, "job_id": job_id}
    except Exception as e:
        logger.error(f"Delete refinement failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare")
async def prepare_presentation(request: PrepareRequest):
    """Run transformations and reading-scaffold generation for recommended views.

    For each recommended view with an applicable transformation template,
    extracts structured data from the stored prose, caches it, then generates
    any scaffold artifacts needed by v2 reading surfaces.
    """
    from src.presenter.presentation_bridge import async_prepare_presentation
    from src.presenter.scaffold_generator import generate_reading_scaffolds

    try:
        result = await async_prepare_presentation(
            job_id=request.job_id,
            consumer_key=request.consumer_key,
            view_keys=request.view_keys,
            force=request.force,
        )
        scaffold_result = await asyncio.to_thread(
            generate_reading_scaffolds,
            request.job_id,
            consumer_key=request.consumer_key,
            force=request.force,
        )
        payload = result.model_dump()
        payload["scaffolds"] = scaffold_result.model_dump()
        return payload
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Presentation preparation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ensure")
async def ensure_presentation(request: EnsurePresentationRequest):
    """Ensure background presentation preparation is running for a job."""
    from src.presenter.preparation_coordinator import start_background_preparation

    try:
        state = start_background_preparation(
            job_id=request.job_id,
            plan_id=request.plan_id,
            consumer_key=request.consumer_key,
            skip_refinement=request.skip_refinement,
            clear_refinement=request.clear_refinement,
            force=request.force,
        )
        return state
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Ensure presentation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/page/{job_id}")
async def get_page_presentation(
    job_id: str,
    slim: bool = False,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Get complete page presentation for a job.

    Returns a render-ready PagePresentation with nested view tree,
    structured data, and raw prose. The consumer (The Critic) can
    render this directly without additional API calls.

    Query params:
        slim: If true, omits raw_prose from each view to reduce response
              size from ~1MB to ~10KB. Use /view/{job_id}/{view_key}
              to lazy-load prose for individual views.
    """
    from src.presenter.presentation_api import assemble_page

    try:
        result = assemble_page(job_id, consumer_key=consumer_key, slim=slim)
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Page assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/view/{job_id}/{view_key}")
async def get_single_view(
    job_id: str,
    view_key: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Get a single view's data (for lazy loading on-demand views)."""
    from src.presenter.presentation_api import assemble_single_view

    try:
        result = assemble_single_view(job_id, view_key, consumer_key=consumer_key)
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
async def get_presentation_status(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Check which views have data ready, need transformation, or are empty.

    Useful for the consumer to know what's available before requesting
    the full page presentation.
    """
    from src.presenter.presentation_api import get_presentation_status as do_status

    try:
        return do_status(job_id, consumer_key=consumer_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/manifest/{job_id}", response_model=EffectivePresentationManifest)
async def get_presentation_manifest(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
    slim: bool = True,
):
    """Get the data-light effective presentation manifest for a job + consumer."""
    from src.presenter.presentation_api import build_presentation_manifest

    try:
        return build_presentation_manifest(
            job_id,
            consumer_key=consumer_key,
            slim=slim,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Manifest assembly failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trace/{job_id}", response_model=PresentationDecisionTrace)
async def get_presentation_trace(
    job_id: str,
    consumer_key: str = DEFAULT_CONSUMER_KEY,
):
    """Get the reconstructed decision trace for a job + consumer."""
    from src.presenter.decision_trace import build_presentation_trace

    try:
        return build_presentation_trace(job_id, consumer_key=consumer_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Decision trace failed: {e}", exc_info=True)
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
    from src.presenter.preparation_coordinator import run_presentation_pipeline_sync
    from src.presenter.presentation_api import assemble_page

    try:
        state = await asyncio.to_thread(
            run_presentation_pipeline_sync,
            request.job_id,
            request.plan_id,
            consumer_key=request.consumer_key,
            skip_refinement=request.skip_refinement,
            clear_refinement=request.clear_refinement,
            force=request.force,
            wait_if_active=True,
        )
        if state.get("status") == "failed":
            raise HTTPException(
                status_code=500,
                detail=state.get("error") or "Presentation preparation failed",
            )
        logger.info(
            "Presentation prep ready for %s: %s",
            request.job_id,
            state.get("stats", {}),
        )

        # Step 3: Assemble page
        page = assemble_page(request.job_id, consumer_key=request.consumer_key)

        # Step 4: Auto-polish views (if requested)
        if request.auto_polish:
            from src.presenter.delivery_style import collect_view_keys, seed_polish_cache_for_views

            auto_polish = seed_polish_cache_for_views(
                job_id=request.job_id,
                consumer_key=request.consumer_key,
                view_keys=collect_view_keys(page.views),
                style_school=request.style_school,
                force=request.force,
            )
            logger.info(
                "[auto-polish] Complete: %s polished, %s cached, %s failed (of %s views, style=%s)",
                auto_polish.get("polished", 0),
                auto_polish.get("cached", 0),
                auto_polish.get("failed", 0),
                auto_polish.get("total_views", 0),
                auto_polish.get("style_school", request.style_school or ""),
            )

        # Touch project activity (user is actively composing presentations)
        from src.executor.project_manager import touch_project_activity_for_job
        touch_project_activity_for_job(request.job_id)

        return page.model_dump()

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Compose failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/polish")
async def polish_view_endpoint(request: PolishRequest):
    """Polish a view's visual presentation using an LLM.

    Calls Sonnet 4.6 to enhance the view's renderer_config and produce
    style_overrides using the resolved style school's palette and typography.
    Results are cached per (job_id, view_key, consumer_key, style_school).
    """
    from src.presenter.polish_store import load_polish_cache, save_polish_cache
    from src.presenter.polisher import compute_config_hash, polish_view
    from src.presenter.presentation_api import assemble_single_view

    try:
        # Load the current view payload
        payload = assemble_single_view(
            request.job_id,
            request.view_key,
            consumer_key=request.consumer_key,
        )
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"View not found: {request.view_key}",
            )

        # Check cache (unless force=True)
        style_school = request.style_school  # may be None → auto-resolved
        if not request.force:
            cached = load_polish_cache(
                job_id=request.job_id,
                view_key=request.view_key,
                consumer_key=request.consumer_key,
                style_school=style_school,
                expected_config_hash=compute_config_hash(payload.renderer_config),
            )
            if cached is not None:
                logger.info(
                    f"[polish] Cache hit for job={request.job_id} "
                    f"view={request.view_key}"
                )
                return {
                    "polished_payload": cached["polished_data"],
                    "model_used": cached["model_used"],
                    "tokens_used": cached["tokens_used"],
                    "style_school": cached["style_school"],
                    "changes_summary": "Loaded from cache",
                    "execution_time_ms": 0,
                    "cached": True,
                }

        # cache_only mode: return 204 if no cache hit (avoids LLM call)
        if request.cache_only:
            from starlette.responses import Response
            return Response(status_code=204)

        # Run polish
        result = polish_view(
            payload=payload,
            engine_key=payload.engine_key,
            style_school=style_school,
        )

        # Cache the result
        config_hash = compute_config_hash(payload.renderer_config)
        save_polish_cache(
            job_id=request.job_id,
            view_key=request.view_key,
            consumer_key=request.consumer_key,
            style_school=result.style_school,
            polished_data=result.polished_payload.model_dump(),
            config_hash=config_hash,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
        )

        # Touch project activity (user is actively polishing)
        from src.executor.project_manager import touch_project_activity_for_job
        touch_project_activity_for_job(request.job_id)

        resp = result.model_dump()
        resp["cached"] = False
        return resp

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Polish failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/polish-section")
async def polish_section_endpoint(request: SectionPolishRequest):
    """Polish a single accordion section with optional user feedback.

    Calls Sonnet 4.6 to enhance just one section's styling, incorporating
    user's natural-language instructions. Results are cached per
    (job_id, view_key, consumer_key, section_key, style_school).
    """
    from src.presenter.polish_store import load_polish_cache, save_polish_cache
    from src.presenter.polisher import compute_config_hash, polish_section
    from src.presenter.presentation_api import assemble_single_view

    try:
        # Load the current view payload
        payload = assemble_single_view(
            request.job_id,
            request.view_key,
            consumer_key=request.consumer_key,
        )
        if payload is None:
            raise HTTPException(
                status_code=404,
                detail=f"View not found: {request.view_key}",
            )

        # Verify section exists in structured data
        if (
            payload.structured_data
            and isinstance(payload.structured_data, dict)
            and request.section_key not in payload.structured_data
        ):
            available = list(payload.structured_data.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Section '{request.section_key}' not found. "
                f"Available: {available}",
            )

        # Check cache (unless force=True or user_feedback is provided)
        style_school = request.style_school
        if not request.force and not request.user_feedback:
            cached = load_polish_cache(
                job_id=request.job_id,
                view_key=request.view_key,
                consumer_key=request.consumer_key,
                style_school=style_school,
                section_key=request.section_key,
                expected_config_hash=compute_config_hash(payload.renderer_config),
            )
            if cached is not None:
                logger.info(
                    f"[polish-section] Cache hit for job={request.job_id} "
                    f"view={request.view_key} section={request.section_key}"
                )
                return {
                    **cached["polished_data"],
                    "model_used": cached["model_used"],
                    "tokens_used": cached["tokens_used"],
                    "style_school": cached["style_school"],
                    "changes_summary": "Loaded from cache",
                    "execution_time_ms": 0,
                    "cached": True,
                }

        # Run section polish
        result = polish_section(
            payload=payload,
            section_key=request.section_key,
            user_feedback=request.user_feedback,
            engine_key=payload.engine_key,
            style_school=style_school,
        )

        # Cache the result
        config_hash = compute_config_hash(payload.renderer_config)
        save_polish_cache(
            job_id=request.job_id,
            view_key=request.view_key,
            consumer_key=request.consumer_key,
            style_school=result.style_school,
            polished_data=result.model_dump(),
            config_hash=config_hash,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
            section_key=request.section_key,
        )

        # Touch project activity (user is actively polishing sections)
        from src.executor.project_manager import touch_project_activity_for_job
        touch_project_activity_for_job(request.job_id)

        resp = result.model_dump()
        resp["cached"] = False
        return resp

    except HTTPException:
        raise
    except ValueError as e:
        # Pydantic ValidationError is a subclass of ValueError in v2
        logger.error(f"Section polish validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Section polish failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/polish-cache/{job_id}")
async def clear_polish_cache(job_id: str):
    """Delete all cached polish results for a job.

    Use this to force re-polishing with updated prompts/injection points.
    """
    from src.presenter.polish_store import delete_polish_cache

    count = delete_polish_cache(job_id)
    return {"job_id": job_id, "deleted": count}
