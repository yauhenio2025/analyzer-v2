"""Helpers for loading effective plan context from file or job state.

Stage 2 needs presenter/read paths to work even when the file-backed plan
is missing, as long as executor_jobs.plan_data still contains a usable plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.executor.job_manager import get_job
from src.orchestrator.planner import load_plan
from src.orchestrator.schemas import WorkflowExecutionPlan


@dataclass(frozen=True)
class EffectivePlanContext:
    plan: Optional[WorkflowExecutionPlan]
    source: str


def load_effective_plan_context(
    job_id: str,
    plan_id: Optional[str] = None,
) -> EffectivePlanContext:
    """Load the best available plan context for a job.

    Source precedence:
    1. full serialized plan in executor_jobs.plan_data
    2. file-backed plan via plan_id
    3. missing

    Request snapshots are not sufficient for presenter/refinement work and
    therefore count as missing plan context for Stage 2.
    """

    job = get_job(job_id)
    resolved_plan_id = plan_id or (job or {}).get("plan_id", "")

    if job and isinstance(job.get("plan_data"), dict):
        plan_data = job["plan_data"]
        if plan_data.get("_type") != "request_snapshot":
            try:
                return EffectivePlanContext(
                    plan=WorkflowExecutionPlan(**plan_data),
                    source="job_plan_data",
                )
            except Exception:
                pass

    if resolved_plan_id:
        plan = load_plan(resolved_plan_id)
        if plan is not None:
            return EffectivePlanContext(plan=plan, source="plan_file")

    return EffectivePlanContext(plan=None, source="missing")


def load_effective_plan(
    job_id: str,
    plan_id: Optional[str] = None,
) -> Optional[WorkflowExecutionPlan]:
    """Convenience wrapper returning only the plan object."""

    return load_effective_plan_context(job_id, plan_id).plan
