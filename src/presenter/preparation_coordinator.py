"""Coordinate background presentation preparation and dedupe concurrent runs."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from .preparation_store import load_presentation_run, save_presentation_run

logger = logging.getLogger(__name__)

_active_jobs: set[str] = set()
_conditions: dict[str, threading.Condition] = {}
_lock = threading.Lock()


def _get_condition(job_id: str) -> threading.Condition:
    with _lock:
        cond = _conditions.get(job_id)
        if cond is None:
            cond = threading.Condition()
            _conditions[job_id] = cond
        return cond


def _try_claim(job_id: str) -> bool:
    with _lock:
        if job_id in _active_jobs:
            return False
        _active_jobs.add(job_id)
        _conditions.setdefault(job_id, threading.Condition())
        return True


def _release(job_id: str) -> None:
    cond = _get_condition(job_id)
    with _lock:
        _active_jobs.discard(job_id)
    with cond:
        cond.notify_all()


def is_presentation_active(job_id: str) -> bool:
    with _lock:
        return job_id in _active_jobs


def get_preparation_state(job_id: str) -> dict:
    state = load_presentation_run(job_id) or {
        "job_id": job_id,
        "status": "not_started",
        "detail": "",
        "stats": {},
        "error": None,
        "started_at": None,
        "updated_at": None,
        "completed_at": None,
    }
    state["active"] = is_presentation_active(job_id)
    return state


def wait_for_preparation(job_id: str, timeout_s: Optional[float] = None) -> dict:
    """Wait for an active preparation run to finish, then return final state."""
    cond = _get_condition(job_id)
    deadline = None if timeout_s is None else (time.monotonic() + timeout_s)

    while True:
        state = get_preparation_state(job_id)
        if not state.get("active") and state.get("status") in {"completed", "failed", "not_started"}:
            return state

        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        if remaining == 0.0:
            return state

        with cond:
            cond.wait(timeout=1.0 if remaining is None else min(1.0, remaining))


def run_presentation_pipeline_sync(
    job_id: str,
    plan_id: str,
    *,
    consumer_key: str,
    skip_refinement: bool = False,
    clear_refinement: bool = False,
    force: bool = False,
    wait_if_active: bool = False,
) -> dict:
    """Run refinement + presentation prep once for a job.

    If another preparation is already running:
    - when wait_if_active=True, wait for that run to finish
    - otherwise, return current state immediately
    """
    current = get_preparation_state(job_id)
    if current.get("status") == "completed" and not force and not clear_refinement:
        return current

    if not _try_claim(job_id):
        return wait_for_preparation(job_id) if wait_if_active else get_preparation_state(job_id)

    try:
        from src.presenter.presentation_bridge import prepare_presentation
        from src.presenter.scaffold_generator import generate_reading_scaffolds
        from src.presenter.store import delete_view_refinement
        from src.presenter.view_refiner import deterministic_refine_views, refine_views

        save_presentation_run(job_id, "running", detail="Preparing presentation", stats={})

        if clear_refinement:
            delete_view_refinement(job_id)
            save_presentation_run(job_id, "running", detail="Cleared cached refinement", stats={})

        if not skip_refinement:
            save_presentation_run(job_id, "running", detail="Refining views", stats={})
            refinement = refine_views(
                job_id=job_id,
                plan_id=plan_id,
                consumer_key=consumer_key,
            )
            save_presentation_run(
                job_id,
                "running",
                detail="Refined views",
                stats={
                    "refined_views": len(refinement.refined_views),
                    "refinement_tokens": refinement.tokens_used,
                },
            )
        else:
            save_presentation_run(job_id, "running", detail="Applying deterministic refinement", stats={})
            refinement = deterministic_refine_views(
                job_id=job_id,
                plan_id=plan_id,
                consumer_key=consumer_key,
            )
            save_presentation_run(
                job_id,
                "running",
                detail="Applied deterministic refinement",
                stats={
                    "refined_views": len(refinement.refined_views),
                    "refinement_tokens": 0,
                },
            )

        save_presentation_run(job_id, "running", detail="Preparing structured view data", stats={})
        bridge_result = prepare_presentation(
            job_id=job_id,
            consumer_key=consumer_key,
            force=force,
        )
        save_presentation_run(job_id, "running", detail="Generating reading scaffolds", stats={})
        scaffold_result = generate_reading_scaffolds(
            job_id=job_id,
            consumer_key=consumer_key,
            force=force,
        )
        final_stats = {
            "tasks_planned": bridge_result.tasks_planned,
            "tasks_completed": bridge_result.tasks_completed,
            "tasks_failed": bridge_result.tasks_failed,
            "tasks_skipped": bridge_result.tasks_skipped,
            "cached_results": bridge_result.cached_results,
            "dynamic_extractions": bridge_result.dynamic_extractions,
            "scaffolds_planned": scaffold_result.artifacts_planned,
            "scaffolds_generated": scaffold_result.artifacts_generated,
            "scaffolds_cached": scaffold_result.artifacts_cached,
            "scaffolds_failed": scaffold_result.artifacts_failed,
        }
        save_presentation_run(
            job_id,
            "completed",
            detail="Presentation ready",
            stats=final_stats,
        )
        return get_preparation_state(job_id)
    except Exception as e:
        logger.warning("Presentation preparation failed for %s: %s", job_id, e, exc_info=True)
        save_presentation_run(
            job_id,
            "failed",
            detail="Presentation preparation failed",
            stats={},
            error=str(e),
        )
        raise
    finally:
        _release(job_id)


def start_background_preparation(
    job_id: str,
    plan_id: str,
    *,
    consumer_key: str,
    skip_refinement: bool = False,
    clear_refinement: bool = False,
    force: bool = False,
) -> dict:
    """Start background preparation if needed and return current state."""
    current = get_preparation_state(job_id)
    if current.get("status") == "completed" and not force and not clear_refinement:
        return current

    if not _try_claim(job_id):
        return get_preparation_state(job_id)

    def _worker() -> None:
        try:
            from src.presenter.presentation_bridge import prepare_presentation
            from src.presenter.scaffold_generator import generate_reading_scaffolds
            from src.presenter.store import delete_view_refinement
            from src.presenter.view_refiner import deterministic_refine_views, refine_views

            save_presentation_run(job_id, "running", detail="Preparing presentation", stats={})

            if clear_refinement:
                delete_view_refinement(job_id)
                save_presentation_run(job_id, "running", detail="Cleared cached refinement", stats={})

            if not skip_refinement:
                save_presentation_run(job_id, "running", detail="Refining views", stats={})
                refinement = refine_views(
                    job_id=job_id,
                    plan_id=plan_id,
                    consumer_key=consumer_key,
                )
                save_presentation_run(
                    job_id,
                    "running",
                    detail="Refined views",
                    stats={
                        "refined_views": len(refinement.refined_views),
                        "refinement_tokens": refinement.tokens_used,
                    },
                )
            else:
                save_presentation_run(job_id, "running", detail="Applying deterministic refinement", stats={})
                refinement = deterministic_refine_views(
                    job_id=job_id,
                    plan_id=plan_id,
                    consumer_key=consumer_key,
                )
                save_presentation_run(
                    job_id,
                    "running",
                    detail="Applied deterministic refinement",
                    stats={
                        "refined_views": len(refinement.refined_views),
                        "refinement_tokens": 0,
                    },
                )

            save_presentation_run(job_id, "running", detail="Preparing structured view data", stats={})
            bridge_result = prepare_presentation(
                job_id=job_id,
                consumer_key=consumer_key,
                force=force,
            )
            save_presentation_run(job_id, "running", detail="Generating reading scaffolds", stats={})
            scaffold_result = generate_reading_scaffolds(
                job_id=job_id,
                consumer_key=consumer_key,
                force=force,
            )
            save_presentation_run(
                job_id,
                "completed",
                detail="Presentation ready",
                stats={
                    "tasks_planned": bridge_result.tasks_planned,
                    "tasks_completed": bridge_result.tasks_completed,
                    "tasks_failed": bridge_result.tasks_failed,
                    "tasks_skipped": bridge_result.tasks_skipped,
                    "cached_results": bridge_result.cached_results,
                    "dynamic_extractions": bridge_result.dynamic_extractions,
                    "scaffolds_planned": scaffold_result.artifacts_planned,
                    "scaffolds_generated": scaffold_result.artifacts_generated,
                    "scaffolds_cached": scaffold_result.artifacts_cached,
                    "scaffolds_failed": scaffold_result.artifacts_failed,
                },
            )
        except Exception as e:
            logger.warning("Background presentation preparation failed for %s: %s", job_id, e, exc_info=True)
            save_presentation_run(
                job_id,
                "failed",
                detail="Presentation preparation failed",
                stats={},
                error=str(e),
            )
        finally:
            _release(job_id)

    thread = threading.Thread(
        target=_worker,
        name=f"presenter-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info("Started background presentation preparation for %s", job_id)
    return get_preparation_state(job_id)
