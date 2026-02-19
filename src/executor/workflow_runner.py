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
    is_cancelled,
    save_phase_result,
    update_job_progress,
    update_job_status,
    update_job_tokens,
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


def execute_plan(
    job_id: str,
    plan_id: str,
    document_ids: Optional[dict[str, str]] = None,
) -> None:
    """Execute a workflow plan. Called from background thread.

    This is the main entry point. It:
    1. Loads the plan
    2. Resolves workflow phases
    3. Runs phases in dependency order
    4. Updates job status on completion/failure
    """
    try:
        update_job_status(job_id, "running")

        # Load the plan
        plan = load_plan(plan_id)
        if plan is None:
            raise ValueError(f"Plan not found: {plan_id}")

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

        # Build plan phases lookup
        plan_phases = {p.phase_number: p for p in plan.phases}

        # Extract prior work titles
        prior_work_titles = [pw.title for pw in plan.prior_works]

        # Build dependency groups for parallel execution
        phase_groups = _build_execution_order(plan.phases, workflow_phases)

        total_phases = sum(
            1 for p in plan.phases if not p.skip
        )
        completed_phases: list[str] = []
        phase_statuses: dict[str, str] = {}
        all_results: dict[float, PhaseResult] = {}

        # Execute phase groups
        for group_idx, group in enumerate(phase_groups):
            if is_cancelled(job_id):
                logger.info(f"Job {job_id} cancelled before group {group_idx}")
                break

            logger.info(
                f"Executing phase group {group_idx + 1}/{len(phase_groups)}: "
                f"{[p.phase_number for p in group]}"
            )

            # Run phases in this group — parallel if >1
            if len(group) == 1:
                # Single phase — run directly
                plan_phase = group[0]
                wf_phase = workflow_phases.get(plan_phase.phase_number)
                if wf_phase is None:
                    logger.error(
                        f"Workflow phase {plan_phase.phase_number} not found, skipping"
                    )
                    continue

                # Update progress
                for p in group:
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
                    ),
                )

                _record_phase_result(
                    job_id, plan_phase, result,
                    completed_phases, phase_statuses, all_results,
                )
            else:
                # Multiple phases — run in parallel
                _run_parallel_phases(
                    group=group,
                    workflow_phases=workflow_phases,
                    job_id=job_id,
                    document_ids=document_ids,
                    prior_work_titles=prior_work_titles,
                    completed_phases=completed_phases,
                    phase_statuses=phase_statuses,
                    all_results=all_results,
                    total_phases=total_phases,
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
                logger.error(
                    f"Workflow phase {plan_phase.phase_number} not found, skipping"
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

    # Update token counts
    if result.total_tokens > 0:
        # Count LLM calls from engine results
        llm_calls = 0
        if result.engine_results:
            llm_calls = sum(len(passes) for passes in result.engine_results.values())
        if result.work_results:
            for work_engines in result.work_results.values():
                llm_calls += sum(len(passes) for passes in work_engines.values())

        input_tokens = 0
        output_tokens = 0
        if result.engine_results:
            for passes in result.engine_results.values():
                for p in passes:
                    input_tokens += p.input_tokens
                    output_tokens += p.output_tokens
        if result.work_results:
            for work_engines in result.work_results.values():
                for passes in work_engines.values():
                    for p in passes:
                        input_tokens += p.input_tokens
                        output_tokens += p.output_tokens

        update_job_tokens(job_id, llm_calls, input_tokens, output_tokens)

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

    # Build dependency map from workflow definition
    deps: dict[float, set[float]] = {}
    for pp in active_phases:
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
