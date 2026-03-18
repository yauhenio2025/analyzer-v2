"""Presentation Bridge — automated transformation pipeline.

Connects executor outputs (prose in phase_outputs) to consumer rendering
by running transformation templates (or dynamic extraction) and populating
the presentation_cache with structured data.

For each recommended view:
1. Resolve data_source → find matching phase_outputs row(s)
2. Check presentation_cache for existing entry
3. If cache miss: find curated transformation template
4. If no template: compose dynamic extraction prompt from engine metadata
   + renderer shape + presentation stance
5. Run transformation via TransformationExecutor
6. Persist result in presentation_cache

Dynamic extraction means every engine is renderable in any renderer without
hand-authoring a transformation template. Curated templates are optional
quality overrides that produce better results when available.
"""

import asyncio
import logging
import threading
from typing import Awaitable, Callable, Optional, TypeVar

from src.executor.job_manager import get_job
from src.executor.output_store import (
    load_phase_outputs,
    load_presentation_cache,
    save_presentation_cache,
)
from src.orchestrator.planner import load_plan
from src.transformations.executor import get_transformation_executor
from src.transformations.registry import get_transformation_registry
from src.views.registry import get_view_registry

from .composition_resolver import find_applicable_template, resolve_effective_render_contract
from .dynamic_prompt import compose_dynamic_extraction_prompt
from .recommendation_defaults import get_default_recommendations_for_workflow
from .view_hierarchy import (
    is_chain_container_view as _is_chain_container_view,
    iter_active_child_views as _iter_active_child_views,
    match_container_sections_to_children as _match_container_sections_to_children,
)
from .work_key_utils import (
    resolve_work_metadata as _resolve_work_metadata,
    try_split_collapsed_outputs,
)

from .schemas import (
    PresentationBridgeResult,
    RefinedViewRecommendation,
    TransformationTask,
    TransformationTaskResult,
)
from .store import load_view_refinement

logger = logging.getLogger(__name__)

_AwaitableResultT = TypeVar("_AwaitableResultT")


def _run_awaitable_sync(awaitable_factory: Callable[[], Awaitable[_AwaitableResultT]]) -> _AwaitableResultT:
    """Run an awaitable from sync code, even if the current thread already has a running loop."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable_factory())

    result: dict[str, _AwaitableResultT] = {}
    error: dict[str, BaseException] = {}

    def _worker() -> None:
        try:
            result["value"] = asyncio.run(awaitable_factory())
        except BaseException as exc:  # pragma: no cover - re-raised in caller thread
            error["value"] = exc

    thread = threading.Thread(
        target=_worker,
        name="presentation-bridge-awaitable",
        daemon=True,
    )
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]
    return result["value"]


async def async_prepare_presentation(
    job_id: str,
    *,
    consumer_key: str,
    view_keys: Optional[list[str]] = None,
    force: bool = False,
) -> PresentationBridgeResult:
    """Async version — safe to call from FastAPI async routes.

    Awaits the async TransformationExecutor.execute() directly.
    When force=True, ignores presentation_cache and re-runs all transformations.
    """
    tasks, skipped, recommended = _build_transformation_tasks(
        job_id,
        view_keys,
        consumer_key=consumer_key,
    )
    results, cached_count, completed_count, failed_count = await _execute_tasks_async(job_id, tasks, force=force)
    dynamic_count = sum(1 for r in results if r.extraction_source == "dynamic" and r.success)

    return PresentationBridgeResult(
        job_id=job_id,
        tasks_planned=len(tasks),
        tasks_completed=completed_count,
        tasks_failed=failed_count,
        tasks_skipped=skipped,
        cached_results=cached_count,
        dynamic_extractions=dynamic_count,
        details=results,
    )


def prepare_presentation(
    job_id: str,
    *,
    consumer_key: str,
    view_keys: Optional[list[str]] = None,
    force: bool = False,
) -> PresentationBridgeResult:
    """Sync version — safe to call from background threads (workflow_runner).

    Creates its own event loop to run the async executor.
    Do NOT call from async context (use async_prepare_presentation instead).
    When force=True, ignores presentation_cache and re-runs all transformations.
    """
    tasks, skipped, recommended = _build_transformation_tasks(
        job_id,
        view_keys,
        consumer_key=consumer_key,
    )
    results, cached_count, completed_count, failed_count = _execute_tasks_sync(job_id, tasks, force=force)
    dynamic_count = sum(1 for r in results if r.extraction_source == "dynamic" and r.success)

    return PresentationBridgeResult(
        job_id=job_id,
        tasks_planned=len(tasks),
        tasks_completed=completed_count,
        tasks_failed=failed_count,
        tasks_skipped=skipped,
        cached_results=cached_count,
        dynamic_extractions=dynamic_count,
        details=results,
    )


def _build_transformation_tasks(
    job_id: str,
    view_keys: Optional[list[str]] = None,
    *,
    consumer_key: str,
) -> tuple[list[TransformationTask], int, list[dict]]:
    """Build the list of transformation tasks for a job.

    Returns:
        (tasks, skipped_count, recommended_views)
    """
    job = get_job(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    workflow_key = job.get("workflow_key") or "intellectual_genealogy"
    recommended = _get_recommended_views(
        job_id,
        job["plan_id"],
        workflow_key=workflow_key,
        consumer_key=consumer_key,
    )

    if view_keys:
        recommended = [v for v in recommended if v["view_key"] in view_keys]

    view_registry = get_view_registry()
    transform_registry_obj = get_transformation_registry()
    recommended = _ensure_required_section_children(recommended, view_registry)
    recommended = [v for v in recommended if v.get("priority") != "hidden"]

    tasks = []
    skipped = 0

    for rec in recommended:
        view_def = view_registry.get(rec["view_key"])
        if view_def is None:
            logger.warning(f"View definition not found: {rec['view_key']}")
            continue

        if _is_chain_container_view(view_def, view_registry):
            logger.debug(
                f"View {rec['view_key']} is a chain-backed container with active children, "
                "skipping direct transformation task"
            )
            skipped += 1
            continue

        engine_key = view_def.data_source.engine_key
        chain_key = view_def.data_source.chain_key
        phase_number = view_def.data_source.phase_number
        composition = resolve_effective_render_contract(
            view_def=view_def,
            rec=rec,
            consumer_key=consumer_key,
            job_id=job_id,
            view_registry=view_registry,
        )
        renderer_type = composition.renderer_type

        if not engine_key and not chain_key:
            logger.debug(f"View {rec['view_key']} has no engine/chain ref, skipping")
            skipped += 1
            continue

        # Resolve engine keys to search for templates
        # For chain-backed views, search templates for ALL engines in the chain
        search_engine_keys = []
        if engine_key:
            search_engine_keys = [engine_key]
        elif chain_key:
            from src.chains.registry import get_chain_registry
            chain_registry = get_chain_registry()
            chain = chain_registry.get(chain_key)
            if chain:
                search_engine_keys = list(chain.engine_keys)
            else:
                logger.warning(f"Chain not found for view {rec['view_key']}: {chain_key}")

        template_key = getattr(composition, "template_key", None)
        template = (
            transform_registry_obj.get(template_key)
            if template_key
            else find_applicable_template(view_def=view_def, renderer_type=renderer_type)
        )

        # Determine extraction strategy: curated template or dynamic prompt
        dynamic_config = None
        if template is None and view_def.transformation.type == "none":
            # View explicitly says "no transformation" AND no curated template → skip
            logger.debug(
                f"View {rec['view_key']}: no transformation needed (type=none, no template)"
            )
            skipped += 1
            continue

        if template is None:
            # No curated template → compose dynamic extraction prompt
            effective_engine_key = engine_key or (search_engine_keys[0] if search_engine_keys else "")
            stance_key = composition.presentation_stance or "interactive"
            dynamic_config = compose_dynamic_extraction_prompt(
                engine_key=effective_engine_key,
                renderer_type=renderer_type,
                stance_key=stance_key,
            )
            logger.info(
                f"[dynamic-fallback] View {rec['view_key']}: no curated template for "
                f"{effective_engine_key}+{renderer_type}, using dynamic extraction"
            )

        # Determine section key and template_key for task
        task_template_key = template.template_key if template else None
        task_section_base = (
            template.template_key if template
            else f"dyn:{engine_key or (search_engine_keys[0] if search_engine_keys else 'unknown')}:{renderer_type}"
        )

        # Find matching phase_outputs
        scope = view_def.data_source.scope

        if scope == "per_item":
            outputs = load_phase_outputs(
                job_id=job_id,
                phase_number=phase_number,
                engine_key=engine_key,
            )
            # For chain-backed per_item views, get all outputs for the phase
            if not outputs and chain_key and not engine_key:
                outputs = load_phase_outputs(
                    job_id=job_id,
                    phase_number=phase_number,
                )

            # Try splitting collapsed work_keys (imported jobs where all
            # outputs share work_key='target' but represent multiple works)
            effective_chain_key = chain_key or engine_key or ""
            split_result = try_split_collapsed_outputs(outputs, job_id, effective_chain_key)
            if split_result is not None:
                # Split succeeded: one task per real work_key, using latest output per group
                work_outputs = {
                    wk: max(outs, key=lambda o: o.get("pass_number", 0))
                    for wk, outs in split_result.items()
                }
            else:
                work_outputs = _group_latest_by_work_key(outputs)

            for work_key, output in work_outputs.items():
                section = f"{task_section_base}:{work_key}" if work_key else task_section_base
                tasks.append(TransformationTask(
                    view_key=rec["view_key"],
                    output_id=output["id"],
                    template_key=task_template_key,
                    engine_key=engine_key or chain_key or "",
                    renderer_type=renderer_type,
                    renderer_config=composition.renderer_config,
                    section=section,
                    dynamic_config=dynamic_config,
                ))
        else:
            outputs = load_phase_outputs(
                job_id=job_id,
                phase_number=phase_number,
                engine_key=engine_key,
            )
            if not outputs and chain_key:
                outputs = load_phase_outputs(
                    job_id=job_id,
                    phase_number=phase_number,
                )
            if not outputs:
                logger.warning(
                    f"No outputs found for view {rec['view_key']} "
                    f"(phase={phase_number}, engine={engine_key})"
                )
                continue
            latest = max(outputs, key=lambda o: o.get("pass_number", 0))

            # For single-engine views with multiple passes, concatenate all
            # passes into content_override so the LLM sees all the prose
            content_override = None
            metadata = latest.get("metadata") or {}
            structured_payloads = metadata.get("structured_payloads") or {}
            if rec["view_key"] in structured_payloads:
                content_override = structured_payloads[rec["view_key"]]
            if engine_key and not chain_key:
                sorted_outputs = sorted(outputs, key=lambda o: o.get("pass_number", 0))
                if content_override is None and len(sorted_outputs) > 1:
                    prose_parts = []
                    for o in sorted_outputs:
                        content = o.get("content", "")
                        if content:
                            prose_parts.append(f"## [Pass {o.get('pass_number', 0)}]\n\n{content}")
                    if prose_parts:
                        content_override = "\n\n---\n\n".join(prose_parts)
                        logger.info(
                            f"View {rec['view_key']}: concatenated {len(sorted_outputs)} passes "
                            f"({len(content_override)} chars) for {engine_key}"
                        )

            tasks.append(TransformationTask(
                view_key=rec["view_key"],
                output_id=latest["id"],
                template_key=task_template_key,
                engine_key=engine_key or chain_key or "",
                renderer_type=renderer_type,
                renderer_config=composition.renderer_config,
                section=task_section_base,
                content_override=content_override,
                dynamic_config=dynamic_config,
            ))

    return tasks, skipped, recommended


def _ensure_required_section_children(recommended: list[dict], view_registry) -> list[dict]:
    """Keep section-backed analytical children available when a parent container is shown.

    LLM refinement may hide dense child views to reduce clutter, but if a visible
    container's renderer sections depend on those children we still need to run
    their extractions and keep them available for parent synthesis.
    """
    by_key = {rec.get("view_key"): dict(rec) for rec in recommended if rec.get("view_key")}
    ordered_keys = [rec.get("view_key") for rec in recommended if rec.get("view_key")]

    for rec in list(recommended):
        view_key = rec.get("view_key")
        if not view_key or rec.get("priority") == "hidden":
            continue

        parent_view = view_registry.get(view_key)
        if parent_view is None:
            continue

        child_views = _iter_active_child_views(view_registry, view_key)
        if not child_views:
            continue

        section_matches = _match_container_sections_to_children(parent_view, child_views)
        for child_view in section_matches.values():
            child_rec = by_key.get(child_view.view_key)
            reason = "Auto-included because the visible parent container depends on this child section."
            if child_rec is None:
                by_key[child_view.view_key] = {
                    "view_key": child_view.view_key,
                    "priority": "secondary",
                    "rationale": reason,
                }
                ordered_keys.append(child_view.view_key)
                continue

            if child_rec.get("priority") == "hidden":
                child_rec["priority"] = "secondary"
                child_rec["rationale"] = f"{child_rec.get('rationale', '')} {reason}".strip()

    return [by_key[key] for key in ordered_keys if key in by_key]


def _run_single_task(
    job_id: str,
    task: TransformationTask,
    transform_executor,
    transform_registry_obj,
) -> tuple[TransformationTaskResult, str]:
    """Execute a single transformation task synchronously.

    Returns:
        (result, status) where status is 'completed', 'cached', or 'failed'
    """
    output_row = _load_output_by_id(job_id, task.output_id)
    if output_row is None:
        return TransformationTaskResult(
            view_key=task.view_key,
            output_id=task.output_id,
            template_key=task.template_key,
            section=task.section,
            success=False,
            error="Output not found",
        ), "failed"

    content = output_row["content"]

    # Check cache
    cached = load_presentation_cache(
        output_id=task.output_id,
        section=task.section,
        source_content=content,
    )
    if cached is not None:
        return TransformationTaskResult(
            view_key=task.view_key,
            output_id=task.output_id,
            template_key=task.template_key,
            section=task.section,
            success=True,
            cached=True,
        ), "cached"

    template = transform_registry_obj.get(task.template_key)
    if template is None:
        return TransformationTaskResult(
            view_key=task.view_key,
            output_id=task.output_id,
            template_key=task.template_key,
            section=task.section,
            success=False,
            error=f"Template not found: {task.template_key}",
        ), "failed"

    return None, template  # Signal that we need to run the actual transformation


def _validate_transform_output(
    task: TransformationTask,
    transform_result,
    extraction_source: str = "curated",
) -> None:
    """Validate transformation output against renderer's input_data_schema.

    Always runs in WARN mode — logs but never blocks the pipeline.
    Wrapped in try/except so validation errors never crash processing.
    """
    try:
        from src.renderers.validator import ValidationMode, validate_renderer_data

        result = validate_renderer_data(
            renderer_key=task.renderer_type,
            data=transform_result.data,
            renderer_config=task.renderer_config,
            mode=ValidationMode.WARN,
        )
        if not result.valid:
            first_error = result.errors[0]["message"] if result.errors else "unknown"
            logger.warning(
                f"[renderer-validation] {task.view_key}/{task.section} "
                f"renderer={task.renderer_type} source={extraction_source}: "
                f"data invalid — {first_error} "
                f"({len(result.errors)} error(s) total)"
            )
    except Exception:
        # Validation must never crash the pipeline
        logger.debug(
            f"[renderer-validation] Could not validate {task.view_key}/{task.section}",
            exc_info=True,
        )


def _save_and_report(
    task: TransformationTask,
    transform_result,
    content: str,
    extraction_source: str = "curated",
) -> tuple[TransformationTaskResult, str]:
    """Save transformation result and return task result."""
    if transform_result.success:
        _validate_transform_output(task, transform_result, extraction_source)
        save_presentation_cache(
            output_id=task.output_id,
            section=task.section,
            structured_data=transform_result.data if isinstance(transform_result.data, dict) else {"data": transform_result.data},
            source_content=content,
            model_used=transform_result.model_used or "",
        )
        source_tag = f" [{extraction_source}]" if extraction_source == "dynamic" else ""
        logger.info(
            f"Transformed{source_tag} {task.view_key}/{task.section}: "
            f"{transform_result.execution_time_ms}ms, "
            f"model={transform_result.model_used}"
        )
        return TransformationTaskResult(
            view_key=task.view_key,
            output_id=task.output_id,
            template_key=task.template_key,
            section=task.section,
            success=True,
            model_used=transform_result.model_used,
            execution_time_ms=transform_result.execution_time_ms,
            extraction_source=extraction_source,
        ), "completed"
    else:
        logger.warning(
            f"Transformation failed for {task.view_key}/{task.section}: "
            f"{transform_result.error}"
        )
        return TransformationTaskResult(
            view_key=task.view_key,
            output_id=task.output_id,
            template_key=task.template_key,
            section=task.section,
            success=False,
            error=transform_result.error,
            execution_time_ms=transform_result.execution_time_ms,
            extraction_source=extraction_source,
        ), "failed"


def _prepare_task_content(
    job_id: str,
    task: TransformationTask,
    output_row: dict,
) -> tuple[object, Optional[str]]:
    """Build LLM input content while keeping cache freshness tied to source prose.

    Per-item tasks prepend a source-document label to help the extraction model
    identify the correct work title. That prefix should not affect cache
    freshness, which must remain anchored to the original executor prose.

    Returns:
        (llm_content, cache_source_content)
    """
    base_content = task.content_override if task.content_override is not None else output_row["content"]
    cache_source_content = output_row["content"]
    llm_content = base_content

    if isinstance(task.content_override, str):
        cache_source_content = None

    if isinstance(llm_content, str) and ":" in task.section:
        work_identifier = task.section.split(":", 1)[1]
        work_meta = _resolve_work_metadata(job_id, work_identifier)
        source_label = work_meta.get("display_title") or work_identifier
        source_year = work_meta.get("year")
        if source_year:
            source_label = f"{source_label} ({source_year})"
        llm_content = f"[SOURCE DOCUMENT: {source_label}]\n\n{base_content}"

    return llm_content, cache_source_content


async def _execute_tasks_async(
    job_id: str,
    tasks: list[TransformationTask],
    force: bool = False,
) -> tuple[list[TransformationTaskResult], int, int, int]:
    """Execute transformation tasks using async await (for FastAPI context).

    When force=True, skips presentation_cache and re-runs all transformations.
    """
    results = []
    cached_count = 0
    completed_count = 0
    failed_count = 0

    transform_executor = get_transformation_executor()
    transform_registry_obj = get_transformation_registry()

    for task in tasks:
        # Check output + cache
        output_row = _load_output_by_id(job_id, task.output_id)
        if output_row is None:
            results.append(TransformationTaskResult(
                view_key=task.view_key,
                output_id=task.output_id,
                template_key=task.template_key,
                section=task.section,
                success=False,
                error="Output not found",
            ))
            failed_count += 1
            continue

        llm_content, cache_source_content = _prepare_task_content(job_id, task, output_row)

        # Check cache (skip when force=True)
        if not force:
            cached = load_presentation_cache(
                output_id=task.output_id,
                section=task.section,
                source_content=cache_source_content,
            )
            if cached is not None:
                results.append(TransformationTaskResult(
                    view_key=task.view_key,
                    output_id=task.output_id,
                    template_key=task.template_key,
                    section=task.section,
                    success=True,
                    cached=True,
                ))
                cached_count += 1
                completed_count += 1
                continue
        else:
            logger.info(f"Force mode: skipping cache for {task.view_key}/{task.section}")

        # Resolve extraction parameters: curated template or dynamic config
        if task.template_key:
            template = transform_registry_obj.get(task.template_key)
            if template is None:
                results.append(TransformationTaskResult(
                    view_key=task.view_key,
                    output_id=task.output_id,
                    template_key=task.template_key,
                    section=task.section,
                    success=False,
                    error=f"Template not found: {task.template_key}",
                ))
                failed_count += 1
                continue

            # Curated template path
            transform_result = await transform_executor.execute(
                data=llm_content,
                transformation_type=template.transformation_type,
                field_mapping=template.field_mapping,
                llm_extraction_schema=template.llm_extraction_schema,
                llm_prompt_template=template.llm_prompt_template,
                stance_key=template.stance_key,
                model=template.model or "claude-haiku-4-5-20251001",
                model_fallback=template.model_fallback or "claude-sonnet-4-6",
                max_tokens=template.max_tokens or 8000,
            )
            extraction_source = "curated"
        elif task.dynamic_config:
            # Dynamic extraction path — no curated template
            dc = task.dynamic_config
            transform_result = await transform_executor.execute(
                data=llm_content,
                transformation_type=dc["transformation_type"],
                llm_prompt_template=dc["system_prompt"],
                stance_key=dc.get("stance_key"),
                model=dc.get("model", "claude-haiku-4-5-20251001"),
                model_fallback=dc.get("model_fallback", "claude-sonnet-4-6"),
                max_tokens=dc.get("max_tokens", 8000),
            )
            extraction_source = "dynamic"
        else:
            results.append(TransformationTaskResult(
                view_key=task.view_key,
                output_id=task.output_id,
                template_key=task.template_key,
                section=task.section,
                success=False,
                error="No template_key or dynamic_config on task",
            ))
            failed_count += 1
            continue

        task_result, status = _save_and_report(
            task,
            transform_result,
            cache_source_content or llm_content,
            extraction_source,
        )
        results.append(task_result)
        if status == "completed":
            completed_count += 1
        else:
            failed_count += 1

    return results, cached_count, completed_count, failed_count


def _execute_tasks_sync(
    job_id: str,
    tasks: list[TransformationTask],
    force: bool = False,
) -> tuple[list[TransformationTaskResult], int, int, int]:
    """Execute transformation tasks synchronously (for background threads).

    When force=True, skips presentation_cache and re-runs all transformations.
    """
    results = []
    cached_count = 0
    completed_count = 0
    failed_count = 0

    transform_executor = get_transformation_executor()
    transform_registry_obj = get_transformation_registry()

    for task in tasks:
        output_row = _load_output_by_id(job_id, task.output_id)
        if output_row is None:
            results.append(TransformationTaskResult(
                view_key=task.view_key,
                output_id=task.output_id,
                template_key=task.template_key,
                section=task.section,
                success=False,
                error="Output not found",
            ))
            failed_count += 1
            continue

        llm_content, cache_source_content = _prepare_task_content(job_id, task, output_row)

        # Check cache (skip when force=True)
        if not force:
            cached = load_presentation_cache(
                output_id=task.output_id,
                section=task.section,
                source_content=cache_source_content,
            )
            if cached is not None:
                results.append(TransformationTaskResult(
                    view_key=task.view_key,
                    output_id=task.output_id,
                    template_key=task.template_key,
                    section=task.section,
                    success=True,
                    cached=True,
                ))
                cached_count += 1
                completed_count += 1
                continue
        else:
            logger.info(f"Force mode: skipping cache for {task.view_key}/{task.section}")

        # Resolve extraction parameters: curated template or dynamic config
        if task.template_key:
            template = transform_registry_obj.get(task.template_key)
            if template is None:
                results.append(TransformationTaskResult(
                    view_key=task.view_key,
                    output_id=task.output_id,
                    template_key=task.template_key,
                    section=task.section,
                    success=False,
                    error=f"Template not found: {task.template_key}",
                ))
                failed_count += 1
                continue

            # Curated template path
            transform_result = _run_awaitable_sync(
                lambda: transform_executor.execute(
                    data=llm_content,
                    transformation_type=template.transformation_type,
                    field_mapping=template.field_mapping,
                    llm_extraction_schema=template.llm_extraction_schema,
                    llm_prompt_template=template.llm_prompt_template,
                    stance_key=template.stance_key,
                    model=template.model or "claude-haiku-4-5-20251001",
                    model_fallback=template.model_fallback or "claude-sonnet-4-6",
                    max_tokens=template.max_tokens or 8000,
                )
            )
            extraction_source = "curated"

        elif task.dynamic_config:
            # Dynamic extraction path — no curated template
            dc = task.dynamic_config
            transform_result = _run_awaitable_sync(
                lambda: transform_executor.execute(
                    data=llm_content,
                    transformation_type=dc["transformation_type"],
                    llm_prompt_template=dc["system_prompt"],
                    stance_key=dc.get("stance_key"),
                    model=dc.get("model", "claude-haiku-4-5-20251001"),
                    model_fallback=dc.get("model_fallback", "claude-sonnet-4-6"),
                    max_tokens=dc.get("max_tokens", 8000),
                )
            )
            extraction_source = "dynamic"

        else:
            results.append(TransformationTaskResult(
                view_key=task.view_key,
                output_id=task.output_id,
                template_key=task.template_key,
                section=task.section,
                success=False,
                error="No template_key or dynamic_config on task",
            ))
            failed_count += 1
            continue

        task_result, status = _save_and_report(
            task,
            transform_result,
            cache_source_content or llm_content,
            extraction_source,
        )
        results.append(task_result)
        if status == "completed":
            completed_count += 1
        else:
            failed_count += 1

    return results, cached_count, completed_count, failed_count


def _get_recommended_views(
    job_id: str,
    plan_id: str,
    workflow_key: str = "intellectual_genealogy",
    *,
    consumer_key: str,
) -> list[dict]:
    """Get recommended views — refined if available, else from plan."""
    # Check for refinement first
    refinement = load_view_refinement(job_id)
    if refinement and refinement.get("refined_views"):
        return refinement["refined_views"]

    # Fall back to plan
    plan = load_plan(plan_id)
    if plan and plan.recommended_views:
        return [v.model_dump() for v in plan.recommended_views]

    return get_default_recommendations_for_workflow(
        workflow_key,
        consumer_key=consumer_key,
    )


def _group_latest_by_work_key(outputs: list[dict]) -> dict[str, dict]:
    """Group outputs by work_key, keeping only the latest pass for each."""
    by_work: dict[str, dict] = {}
    for o in outputs:
        work_key = o.get("work_key", "")
        if not work_key:
            continue
        existing = by_work.get(work_key)
        if existing is None or o.get("pass_number", 0) > existing.get("pass_number", 0):
            by_work[work_key] = o
    return by_work


def _load_output_by_id(job_id: str, output_id: str) -> Optional[dict]:
    """Load a specific output by ID.

    Uses a direct query rather than load_phase_outputs filter.
    """
    from src.executor.db import execute

    row = execute(
        "SELECT * FROM phase_outputs WHERE id = %s AND job_id = %s",
        (output_id, job_id),
        fetch="one",
    )
    if row and isinstance(row.get("metadata"), str):
        from src.executor.db import _json_loads

        row["metadata"] = _json_loads(row["metadata"])
    return row
