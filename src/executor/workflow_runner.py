"""Top-level workflow execution: reads a plan, runs phases in dependency order.

The workflow runner is the entry point for executing a WorkflowExecutionPlan.
It:

1. Loads the plan from file storage
2. Resolves the workflow definition (phase templates)
3. Builds a dependency DAG from depends_on_phases
4. Runs phases respecting dependencies, with parallelism where possible
   (e.g., Phase 1.0 and 1.5 can run in parallel)
5. Updates job progress after each phase
6. Handles errors, cancellation, and partial results

This runs in a background thread — spawned by the API route.
"""

import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from src.executor.job_manager import (
    clear_cancellation,
    get_job,
    is_cancelled,
    save_phase_result,
    update_job_progress,
    update_job_status,
)
from src.executor.phase_runner import run_phase
from src.executor.schemas import PhaseResult, PhaseStatus
from src.orchestrator.planner import load_plan
from src.orchestrator.schemas import PhaseExecutionSpec, WorkflowExecutionPlan
from src.workflows.registry import get_workflow_registry
from src.workflows.schemas import WorkflowPhase

logger = logging.getLogger(__name__)

# Max concurrent phases (for parallel execution of independent phases)
MAX_PHASE_CONCURRENCY = 2

# Regex for parsing engine/pass info from progress detail strings
import re
_ENGINE_RE = re.compile(r'Engine\s+(?:\d+/\d+:\s*)?(\S+)', re.IGNORECASE)
_PASS_RE = re.compile(r'pass\s+(\d+)', re.IGNORECASE)
_STANCE_RE = re.compile(r'stance[:\s]+(\S+)', re.IGNORECASE)


def _parse_structured_detail(detail: str) -> dict | None:
    """Extract engine_key, pass_number, stance_key from progress detail string."""
    if not detail:
        return None
    info: dict = {}
    m = _ENGINE_RE.search(detail)
    if m:
        info["engine_key"] = m.group(1)
    m = _PASS_RE.search(detail)
    if m:
        info["pass_number"] = int(m.group(1))
    m = _STANCE_RE.search(detail)
    if m:
        info["stance_key"] = m.group(1)
    return info if info else None

# Thread-safe guard against double-execution of the same job.
# If execute_plan() is somehow called twice for the same job_id
# (observed in production — cause TBD), the second call exits immediately.
_active_jobs: set[str] = set()
_active_jobs_lock = threading.Lock()


def execute_plan(
    job_id: str,
    plan_id: str,
    document_ids: Optional[dict[str, str]] = None,
    plan_object: Optional[WorkflowExecutionPlan] = None,
) -> None:
    """Execute a workflow plan. Called from background thread.

    This is the main entry point. It:
    1. Loads the plan (from file, DB, or passed object)
    2. Resolves workflow phases
    3. Runs phases in dependency order (skipping already-completed ones on resume)
    4. Updates job status on completion/failure

    Args:
        plan_object: Pre-loaded plan (used for resume when file-based plan is gone).
    """
    # Guard against double-execution
    with _active_jobs_lock:
        if job_id in _active_jobs:
            logger.warning(
                f"DUPLICATE EXECUTION BLOCKED: job {job_id} is already running. "
                f"Exiting this thread."
            )
            return
        _active_jobs.add(job_id)

    try:
        update_job_status(job_id, "running")

        # Load the plan: prefer passed object, then file, then DB
        plan = plan_object
        if plan is None:
            plan = load_plan(plan_id)
        if plan is None:
            # Try loading from job's plan_data column
            job_record = get_job(job_id)
            if job_record and job_record.get("plan_data"):
                try:
                    plan = WorkflowExecutionPlan(**job_record["plan_data"])
                    logger.info(f"Loaded plan from DB plan_data for job {job_id}")
                except Exception as e:
                    logger.error(f"Failed to parse plan_data from DB: {e}")
        if plan is None:
            raise ValueError(f"Plan not found: {plan_id} (file, object, and DB all empty)")

        logger.info(
            f"Starting execution of plan {plan_id} for job {job_id}\n"
            f"  Thinker: {plan.thinker_name}\n"
            f"  Target: {plan.target_work.title}\n"
            f"  Prior works: {len(plan.prior_works)}\n"
            f"  Phases: {len(plan.phases)}\n"
            f"  Estimated LLM calls: {plan.estimated_llm_calls}"
        )

        # Load workflow definition for phase templates
        workflow_reg = get_workflow_registry()
        workflow = workflow_reg.get(plan.workflow_key)
        if workflow is None:
            raise ValueError(f"Workflow not found: {plan.workflow_key}")

        # Build the phase lookup: phase_number -> WorkflowPhase
        workflow_phases = {p.phase_number: p for p in workflow.phases}

        # Apply execution_model to ALL phases. When the user explicitly
        # selects an execution model, it should override the planner's
        # per-phase model_hint suggestions (e.g. "opus"/"sonnet"). The user's
        # explicit choice takes priority over the planner's defaults.
        if plan.execution_model:
            applied_count = 0
            for pp in plan.phases:
                old_hint = pp.model_hint
                pp.model_hint = plan.execution_model
                applied_count += 1
                if old_hint and old_hint != plan.execution_model:
                    logger.debug(
                        f"Phase {pp.phase_number}: overriding model_hint "
                        f"{old_hint} → {plan.execution_model}"
                    )
            logger.info(
                f"Applied execution_model={plan.execution_model} to "
                f"all {applied_count} phases (user override)"
            )

        # Build plan phases lookup
        plan_phases = {p.phase_number: p for p in plan.phases}

        # Extract prior work titles
        prior_work_titles = [pw.title for pw in plan.prior_works]

        # Precompute context char overrides from plan (Milestone 5)
        # Phases with max_context_chars_override get higher char limits
        # when their output is consumed by downstream phases
        context_char_overrides: dict[float, int] = {}
        for pp in plan.phases:
            if pp.max_context_chars_override:
                context_char_overrides[pp.phase_number] = pp.max_context_chars_override

        if context_char_overrides:
            logger.info(f"Context char overrides: {context_char_overrides}")

        # Build dependency groups for parallel execution
        phase_groups = _build_execution_order(plan.phases, workflow_phases)

        total_phases = sum(
            1 for p in plan.phases if not p.skip
        )
        completed_phases: list[str] = []
        phase_statuses: dict[str, str] = {}
        all_results: dict[float, PhaseResult] = {}

        # RESUME: Check which phases already completed (from prior execution)
        job_record = get_job(job_id)
        prior_phase_results = {}
        if job_record:
            prior_phase_results = job_record.get("phase_results", {})
            if isinstance(prior_phase_results, str):
                import json
                prior_phase_results = json.loads(prior_phase_results)

        already_completed = set()
        for pn_str, pr in prior_phase_results.items():
            if isinstance(pr, dict) and pr.get("status") == "completed":
                already_completed.add(float(pn_str))
                completed_phases.append(f"{pn_str}: {pr.get('phase_name', '')}")
                phase_statuses[pn_str] = "completed"

        if already_completed:
            logger.info(
                f"RESUME: {len(already_completed)} phases already completed: {already_completed}"
            )

        # Track whether mid-course revision has been attempted
        # (loaded from plan if resuming)
        mid_course_attempted = plan.current_revision >= 1
        skip_revision = getattr(plan, '_skip_plan_revision', False)

        # Execute phase groups
        for group_idx, group in enumerate(phase_groups):
            if is_cancelled(job_id):
                logger.info(f"Job {job_id} cancelled before group {group_idx}")
                break

            # ── Mid-course plan revision checkpoint ──
            # After phases {1.0, 1.5} complete and before any phase >= 2.0,
            # run an Opus-based plan revision to adjust remaining phases
            # based on what was actually learned from profiling.
            if (
                not mid_course_attempted
                and not skip_revision
                and not is_cancelled(job_id)
            ):
                completed_phase_numbers = {
                    float(pn_str)
                    for pn_str, status in phase_statuses.items()
                    if status == "completed"
                } | already_completed
                upcoming_min = min(
                    (p.phase_number for p in group), default=0
                )

                if (
                    1.0 in completed_phase_numbers
                    and 1.5 in completed_phase_numbers
                    and upcoming_min >= 2.0
                ):
                    mid_course_attempted = True
                    try:
                        plan, phase_groups, group_idx = _try_mid_course_revision(
                            plan=plan,
                            all_results=all_results,
                            workflow_phases=workflow_phases,
                            completed_phase_numbers=completed_phase_numbers,
                            job_id=job_id,
                            phase_groups=phase_groups,
                            current_group_idx=group_idx,
                        )
                        plan_phases = {p.phase_number: p for p in plan.phases}
                    except Exception as e:
                        logger.warning(
                            f"Mid-course revision failed (continuing): {e}"
                        )

            logger.info(
                f"Executing phase group {group_idx + 1}/{len(phase_groups)}: "
                f"{[p.phase_number for p in group]}"
            )

            # RESUME: Filter out already-completed phases from this group
            remaining_group = [
                p for p in group if p.phase_number not in already_completed
            ]
            if not remaining_group:
                logger.info(
                    f"RESUME: Skipping group {group_idx + 1} — all phases already completed: "
                    f"{[p.phase_number for p in group]}"
                )
                continue

            # Run phases in this group — parallel if >1
            if len(remaining_group) == 1:
                # Single phase — run directly
                plan_phase = remaining_group[0]
                wf_phase = workflow_phases.get(plan_phase.phase_number)
                if wf_phase is None:
                    # Adaptive phase: construct synthetic WorkflowPhase from plan
                    if plan_phase.chain_key or plan_phase.engine_key:
                        wf_phase = WorkflowPhase(
                            phase_number=plan_phase.phase_number,
                            phase_name=plan_phase.phase_name,
                            chain_key=plan_phase.chain_key,
                            engine_key=plan_phase.engine_key,
                            depends_on_phases=plan_phase.depends_on or [],
                            caches_result=True,
                            iteration_mode=plan_phase.iteration_mode or "single",
                        )
                        logger.info(
                            f"Constructed synthetic WorkflowPhase for adaptive phase "
                            f"{plan_phase.phase_number}: chain={plan_phase.chain_key}, "
                            f"engine={plan_phase.engine_key}"
                        )
                    else:
                        logger.error(
                            f"Phase {plan_phase.phase_number} not in template and "
                            f"no chain/engine override in plan, skipping"
                        )
                        continue

                # Update progress
                for p in remaining_group:
                    phase_statuses[str(p.phase_number)] = "running"
                update_job_progress(
                    job_id,
                    current_phase=plan_phase.phase_number,
                    phase_name=plan_phase.phase_name,
                    detail=f"Running phase {plan_phase.phase_number}",
                    completed_phases=completed_phases,
                    phase_statuses=phase_statuses,
                    total_phases=total_phases,
                )

                result = run_phase(
                    workflow_phase=wf_phase,
                    plan_phase=plan_phase,
                    job_id=job_id,
                    document_ids=document_ids,
                    prior_work_titles=prior_work_titles,
                    cancellation_check=lambda: is_cancelled(job_id),
                    progress_callback=lambda detail: update_job_progress(
                        job_id,
                        current_phase=plan_phase.phase_number,
                        phase_name=plan_phase.phase_name,
                        detail=detail,
                        completed_phases=completed_phases,
                        phase_statuses=phase_statuses,
                        total_phases=total_phases,
                        structured_detail=_parse_structured_detail(detail),
                    ),
                    context_char_overrides=context_char_overrides or None,
                )

                _record_phase_result(
                    job_id, plan_phase, result,
                    completed_phases, phase_statuses, all_results,
                )
            else:
                # Multiple phases — run in parallel
                _run_parallel_phases(
                    group=remaining_group,
                    workflow_phases=workflow_phases,
                    job_id=job_id,
                    document_ids=document_ids,
                    prior_work_titles=prior_work_titles,
                    completed_phases=completed_phases,
                    phase_statuses=phase_statuses,
                    all_results=all_results,
                    total_phases=total_phases,
                    context_char_overrides=context_char_overrides or None,
                )

        # Final status
        if is_cancelled(job_id):
            update_job_status(job_id, "cancelled")
        else:
            # Check if any phase failed
            failed_phases = [
                pn for pn, r in all_results.items()
                if r.status == PhaseStatus.FAILED
            ]
            if failed_phases:
                update_job_status(
                    job_id, "failed",
                    error=f"Phases {failed_phases} failed",
                )
            else:
                update_job_status(job_id, "completed")

                # Auto-presentation: run view refinement + transformation bridge
                # so PagePresentation is ready by the time the client polls
                _run_auto_presentation(job_id, plan_id)

        logger.info(
            f"Job {job_id} finished: "
            f"{len(completed_phases)} phases completed, "
            f"status={phase_statuses}"
        )

    except InterruptedError:
        update_job_status(job_id, "cancelled")
        logger.info(f"Job {job_id} cancelled via InterruptedError")

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        update_job_status(job_id, "failed", error=str(e))

    finally:
        clear_cancellation(job_id)
        with _active_jobs_lock:
            _active_jobs.discard(job_id)


def _run_parallel_phases(
    group: list[PhaseExecutionSpec],
    workflow_phases: dict[float, WorkflowPhase],
    job_id: str,
    document_ids: Optional[dict[str, str]],
    prior_work_titles: list[str],
    completed_phases: list[str],
    phase_statuses: dict[str, str],
    all_results: dict[float, PhaseResult],
    total_phases: int,
    context_char_overrides: Optional[dict[float, int]] = None,
) -> None:
    """Run multiple phases in parallel."""
    # Mark all as running
    for p in group:
        phase_statuses[str(p.phase_number)] = "running"
    update_job_progress(
        job_id,
        current_phase=group[0].phase_number,
        phase_name=f"Parallel: {', '.join(p.phase_name for p in group)}",
        detail="Running phases in parallel",
        completed_phases=completed_phases,
        phase_statuses=phase_statuses,
        total_phases=total_phases,
    )

    with ThreadPoolExecutor(max_workers=MAX_PHASE_CONCURRENCY) as executor:
        futures = {}
        for plan_phase in group:
            wf_phase = workflow_phases.get(plan_phase.phase_number)
            if wf_phase is None:
                # Adaptive phase: construct synthetic WorkflowPhase from plan
                if plan_phase.chain_key or plan_phase.engine_key:
                    wf_phase = WorkflowPhase(
                        phase_number=plan_phase.phase_number,
                        phase_name=plan_phase.phase_name,
                        chain_key=plan_phase.chain_key,
                        engine_key=plan_phase.engine_key,
                        depends_on_phases=plan_phase.depends_on or [],
                        caches_result=True,
                        iteration_mode=plan_phase.iteration_mode or "single",
                    )
                    logger.info(
                        f"Constructed synthetic WorkflowPhase for adaptive phase "
                        f"{plan_phase.phase_number}: chain={plan_phase.chain_key}, "
                        f"engine={plan_phase.engine_key}"
                    )
                else:
                    logger.error(
                        f"Phase {plan_phase.phase_number} not in template and "
                        f"no chain/engine override in plan, skipping"
                    )
                    continue

            future = executor.submit(
                run_phase,
                workflow_phase=wf_phase,
                plan_phase=plan_phase,
                job_id=job_id,
                document_ids=document_ids,
                prior_work_titles=prior_work_titles,
                cancellation_check=lambda: is_cancelled(job_id),
                progress_callback=None,  # Skip per-phase progress in parallel mode
                context_char_overrides=context_char_overrides,
            )
            futures[future] = plan_phase

        for future in as_completed(futures):
            plan_phase = futures[future]
            try:
                result = future.result()
                _record_phase_result(
                    job_id, plan_phase, result,
                    completed_phases, phase_statuses, all_results,
                )
            except InterruptedError:
                raise
            except Exception as e:
                logger.error(
                    f"Phase {plan_phase.phase_number} failed in parallel execution: {e}"
                )
                failed_result = PhaseResult(
                    phase_number=plan_phase.phase_number,
                    phase_name=plan_phase.phase_name,
                    status=PhaseStatus.FAILED,
                    error=str(e),
                )
                _record_phase_result(
                    job_id, plan_phase, failed_result,
                    completed_phases, phase_statuses, all_results,
                )


def _record_phase_result(
    job_id: str,
    plan_phase: PhaseExecutionSpec,
    result: PhaseResult,
    completed_phases: list[str],
    phase_statuses: dict[str, str],
    all_results: dict[float, PhaseResult],
) -> None:
    """Record a phase result: update tracking dicts and persist to DB."""
    pn = plan_phase.phase_number
    all_results[pn] = result
    phase_statuses[str(pn)] = result.status.value

    if result.status == PhaseStatus.COMPLETED:
        completed_phases.append(f"{pn}: {plan_phase.phase_name}")

    # Save to job record
    save_phase_result(
        job_id, pn,
        {
            "phase_number": pn,
            "phase_name": plan_phase.phase_name,
            "status": result.status.value,
            "duration_ms": result.duration_ms,
            "total_tokens": result.total_tokens,
            "error": result.error,
            "final_output_preview": result.final_output[:500] if result.final_output else "",
        },
    )

    # Token counts are now updated INCREMENTALLY in chain_runner after each
    # LLM call (update_job_tokens per pass). No phase-level update needed —
    # doing so would double-count.

    logger.info(
        f"Phase {pn} ({plan_phase.phase_name}): {result.status.value}, "
        f"{result.total_tokens:,} tokens, {result.duration_ms:,}ms"
        + (f" — error: {result.error}" if result.error else "")
    )


def _build_execution_order(
    plan_phases: list[PhaseExecutionSpec],
    workflow_phases: dict[float, WorkflowPhase],
) -> list[list[PhaseExecutionSpec]]:
    """Build execution groups from dependency DAG.

    Returns a list of groups. Phases within a group have all dependencies
    satisfied and can run in parallel. Groups must execute sequentially.

    Example for intellectual_genealogy:
    - Group 1: [Phase 1.0, Phase 1.5] (no dependencies, run in parallel)
    - Group 2: [Phase 2.0] (depends on 1.0 and 1.5)
    - Group 3: [Phase 3.0] (depends on 1.0 and 2.0)
    - Group 4: [Phase 4.0] (depends on all prior)
    """
    # Filter out skipped phases
    active_phases = [p for p in plan_phases if not p.skip]

    if not active_phases:
        return []

    # Build dependency map: prefer plan-level depends_on (adaptive phases),
    # fall back to workflow template
    deps: dict[float, set[float]] = {}
    for pp in active_phases:
        if pp.depends_on is not None:
            deps[pp.phase_number] = set(pp.depends_on)
        else:
            wf = workflow_phases.get(pp.phase_number)
            if wf:
                deps[pp.phase_number] = set(wf.depends_on_phases)
            else:
                deps[pp.phase_number] = set()

    # Topological sort into groups (Kahn's algorithm)
    phase_lookup = {p.phase_number: p for p in active_phases}
    remaining = set(phase_lookup.keys())
    groups: list[list[PhaseExecutionSpec]] = []

    while remaining:
        # Find phases with all dependencies satisfied
        ready = []
        for pn in sorted(remaining):
            unmet = deps.get(pn, set()) & remaining
            if not unmet:
                ready.append(pn)

        if not ready:
            # Circular dependency or missing phases — just run remaining in order
            logger.warning(
                f"Could not resolve dependencies for phases: {remaining}. "
                f"Running sequentially."
            )
            for pn in sorted(remaining):
                groups.append([phase_lookup[pn]])
            break

        groups.append([phase_lookup[pn] for pn in ready])
        remaining -= set(ready)

    logger.info(
        f"Execution order: {[[p.phase_number for p in g] for g in groups]}"
    )
    return groups


def _try_mid_course_revision(
    plan: WorkflowExecutionPlan,
    all_results: dict,
    workflow_phases: dict,
    completed_phase_numbers: set[float],
    job_id: str,
    phase_groups: list[list[PhaseExecutionSpec]],
    current_group_idx: int,
) -> tuple[WorkflowExecutionPlan, list[list[PhaseExecutionSpec]], int]:
    """Attempt mid-course plan revision after profiling phases complete.

    Returns (possibly revised plan, rebuilt phase_groups, adjusted group_idx).
    If revision is not needed, returns the inputs unchanged.
    """
    from src.orchestrator.plan_revision import (
        apply_revision_to_plan,
        revise_plan_mid_course,
        should_trigger_mid_course_revision,
    )

    if not should_trigger_mid_course_revision(
        completed_phases=completed_phase_numbers,
        current_revision=plan.current_revision,
    ):
        return plan, phase_groups, current_group_idx

    logger.info(f"[Job {job_id}] Triggering mid-course plan revision...")

    from src.executor.job_manager import update_job_progress
    update_job_progress(
        job_id,
        current_phase=1.5,
        phase_name="Mid-Course Plan Revision",
        detail="Opus reviewing profiling results and adjusting remaining phases...",
    )

    # Collect phase outputs for the revision prompt
    phase_outputs: dict[float, str] = {}
    for pn, result in all_results.items():
        if hasattr(result, 'final_output') and result.final_output:
            phase_outputs[pn] = result.final_output

    plan_dict = plan.model_dump()
    result = revise_plan_mid_course(
        plan_dict=plan_dict,
        phase_outputs=phase_outputs,
        book_samples=plan_dict.get("book_samples", []),
        completed_phases=completed_phase_numbers,
    )

    if result is None:
        logger.info(f"[Job {job_id}] Mid-course revision: no changes needed")
        return plan, phase_groups, current_group_idx

    # Apply revision
    revised_dict = apply_revision_to_plan(
        plan_dict=plan_dict,
        revision_result=result,
        completed_phases=completed_phase_numbers,
    )

    revised_plan = WorkflowExecutionPlan(**revised_dict)

    # Rebuild execution order with the revised phases
    revised_groups = _build_execution_order(revised_plan.phases, workflow_phases)

    # Find the group index that contains the first unexecuted phase
    new_group_idx = 0
    for g_idx, group in enumerate(revised_groups):
        if any(p.phase_number not in completed_phase_numbers for p in group):
            new_group_idx = g_idx
            break

    logger.info(
        f"[Job {job_id}] Mid-course revision applied: "
        f"{result['revision']['changes_summary']}\n"
        f"  Resuming from group {new_group_idx + 1}/{len(revised_groups)}"
    )

    return revised_plan, revised_groups, new_group_idx


def _run_auto_presentation(job_id: str, plan_id: str) -> None:
    """Auto-run view refinement + transformation bridge after execution completes.

    This is non-fatal: if presentation fails, the job is still "completed"
    and the client can access raw prose outputs. The presentation layer
    is a convenience optimization, not a requirement.
    """
    try:
        logger.info(f"Auto-presentation starting for job {job_id}")

        # Step 1: Refine view recommendations based on actual results
        try:
            from src.presenter.view_refiner import refine_views
            refinement = refine_views(job_id=job_id, plan_id=plan_id)
            logger.info(
                f"Auto-presentation: view refinement complete — "
                f"{len(refinement.refined_views)} views, "
                f"{refinement.tokens_used} tokens"
            )
        except Exception as e:
            logger.warning(f"Auto-presentation: view refinement failed (continuing): {e}")

        # Step 2: Run transformations for recommended views
        try:
            from src.presenter.presentation_bridge import prepare_presentation
            bridge_result = prepare_presentation(job_id=job_id)
            logger.info(
                f"Auto-presentation: transformation bridge complete — "
                f"{bridge_result.tasks_completed} transformed, "
                f"{bridge_result.cached_results} cached, "
                f"{bridge_result.tasks_skipped} skipped"
            )
        except Exception as e:
            logger.warning(f"Auto-presentation: transformation bridge failed (continuing): {e}")

        logger.info(f"Auto-presentation complete for job {job_id}")

    except Exception as e:
        logger.warning(f"Auto-presentation failed for job {job_id} (non-fatal): {e}")


def start_execution_thread(
    job_id: str,
    plan_id: str,
    document_ids: Optional[dict[str, str]] = None,
) -> threading.Thread:
    """Spawn a background thread to execute the plan.

    Returns the thread (for testing). In production, the caller
    doesn't need to join — the thread updates the DB directly.
    """
    thread = threading.Thread(
        target=execute_plan,
        args=(job_id, plan_id, document_ids),
        name=f"executor-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info(f"Started execution thread for job {job_id}")
    return thread


def start_resume_thread(
    job_id: str,
    plan_data: dict,
    document_ids: Optional[dict[str, str]] = None,
) -> threading.Thread:
    """Spawn a background thread to RESUME a previously interrupted job.

    Called from recover_orphaned_jobs() when an instance recycles and
    an orphaned running job has plan_data stored in the DB.

    The plan is passed as a dict (from DB) and converted to a
    WorkflowExecutionPlan object. The execution will skip already-completed
    phases and engine passes (checked via phase_outputs table).
    """
    try:
        plan_object = WorkflowExecutionPlan(**plan_data)
    except Exception as e:
        logger.error(f"Failed to deserialize plan_data for resume of job {job_id}: {e}")
        from src.executor.job_manager import update_job_status
        update_job_status(job_id, "failed", error=f"Resume failed: bad plan_data: {e}")
        return None

    plan_id = plan_data.get("plan_id", "unknown")

    thread = threading.Thread(
        target=execute_plan,
        args=(job_id, plan_id, document_ids),
        kwargs={"plan_object": plan_object},
        name=f"executor-resume-{job_id}",
        daemon=True,
    )
    thread.start()
    logger.info(f"Started RESUME thread for job {job_id} (plan {plan_id})")
    return thread
