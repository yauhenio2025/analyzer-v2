"""Schemas for the context-driven orchestrator.

The central data structure is WorkflowExecutionPlan — a concrete,
contextualized plan for executing a genealogy workflow. It is NOT
a WorkflowDefinition (which is a template). It is a specific plan
adapted to a specific thinker and corpus.
"""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TargetWork(BaseModel):
    """The primary work being analyzed."""

    title: str
    author: Optional[str] = None
    year: Optional[int] = None
    description: str = Field(
        ...,
        description="Brief description of the work's argument/contribution (2-5 sentences)",
    )


class PriorWork(BaseModel):
    """A prior work to scan for genealogical traces."""

    title: str
    author: Optional[str] = None
    year: Optional[int] = None
    description: str = Field(
        default="",
        description="Brief description of the work",
    )
    relationship_hint: str = Field(
        default="",
        description="User's hint about relationship to target (e.g., 'First mention of core thesis')",
    )


class EngineExecutionSpec(BaseModel):
    """How a specific engine should run in this plan.

    The orchestrator sets these based on the thinker's intellectual profile.
    """

    engine_key: str
    depth: str = Field(
        default="standard",
        description="Depth level: surface, standard, or deep",
    )
    focus_dimensions: Optional[list[str]] = Field(
        default=None,
        description="Subset of engine's dimensions to prioritize (None = all)",
    )
    focus_capabilities: Optional[list[str]] = Field(
        default=None,
        description="Subset of engine's capabilities to exercise (None = all)",
    )
    rationale: str = Field(
        default="",
        description="WHY these choices for this engine in this context",
    )


class PhaseExecutionSpec(BaseModel):
    """How a workflow phase should run in this plan."""

    phase_number: float
    phase_name: str
    skip: bool = Field(
        default=False,
        description="Whether to skip this phase entirely",
    )
    skip_reason: Optional[str] = None
    depth: str = Field(
        default="standard",
        description="Overall depth for this phase",
    )
    engine_overrides: Optional[dict[str, EngineExecutionSpec]] = Field(
        default=None,
        description="Per-engine overrides within this phase (keyed by engine_key). "
        "If None, all engines use the phase depth.",
    )
    context_emphasis: Optional[str] = Field(
        default=None,
        description="What to emphasize when threading context from upstream phases. "
        "Injected into the context broker's assembly.",
    )
    rationale: str = Field(
        default="",
        description="WHY this configuration for this phase given the thinker/context",
    )

    # Milestone 2 additions: executor-relevant fields
    model_hint: Optional[str] = Field(
        default=None,
        description="Suggested model: 'opus', 'sonnet', or None (auto). "
        "Executor may override based on cost/latency constraints.",
    )
    requires_full_documents: bool = Field(
        default=False,
        description="Whether this phase needs full document texts (triggers 1M context).",
    )
    per_work_overrides: Optional[dict[str, dict]] = Field(
        default=None,
        description="Per-prior-work depth/focus overrides. "
        "Keys are work titles, values are {depth, focus_dimensions} dicts.",
    )

    # Milestone 5 additions: expanded target analysis & distilled context
    supplementary_chains: Optional[list[str]] = Field(
        default=None,
        description="Additional chain keys to run AFTER the phase's primary chain/engine. "
        "The orchestrator selects these based on the thinker's profile. "
        "All supplementary chain outputs are concatenated with the primary output.",
    )
    max_context_chars_override: Optional[int] = Field(
        default=None,
        description="Override the default 50K per-block context cap for this phase's output "
        "when consumed by downstream phases. Set higher for phases that produce "
        "rich analysis intended to replace raw document text.",
    )

    # Adaptive planner fields
    chain_key: Optional[str] = Field(
        default=None,
        description="Chain to execute (adaptive planner override). "
        "Takes precedence over the workflow template's chain_key.",
    )
    engine_key: Optional[str] = Field(
        default=None,
        description="Engine to execute (adaptive planner override). "
        "Takes precedence over the workflow template's engine_key.",
    )
    iteration_mode: Optional[str] = Field(
        default=None,
        description="How this phase iterates: 'single' (run once), "
        "'per_work' (run once per prior work), 'per_work_filtered' (subset of works). "
        "Overrides legacy hardcoded per-work detection.",
    )
    per_work_chain_map: Optional[dict[str, str]] = Field(
        default=None,
        description="Per-work chain differentiation. Maps work_title -> chain_key. "
        "Allows the adaptive planner to use different chains for different works.",
    )
    depends_on: Optional[list[float]] = Field(
        default=None,
        description="Dependency declaration for adaptive phases not in the workflow template. "
        "Phase numbers this phase depends on.",
    )
    estimated_tokens: int = Field(
        default=0,
        description="Estimated token usage for this phase.",
    )
    estimated_cost_usd: float = Field(
        default=0.0,
        description="Estimated cost in USD for this phase.",
    )


class ViewRecommendation(BaseModel):
    """A recommended view for presenting analysis results."""

    view_key: str
    priority: str = Field(
        default="primary",
        description="primary (always show), secondary (show if data exists), optional (on-demand)",
    )
    presentation_stance_override: Optional[str] = Field(
        default=None,
        description="Override the view's default presentation stance",
    )
    rationale: str = Field(
        default="",
        description="WHY this view is recommended for this analysis",
    )


class OrchestratorPlanRequest(BaseModel):
    """Input for generating a new plan."""

    thinker_name: str = Field(
        ...,
        description="Name of the thinker being analyzed",
    )
    target_work: TargetWork
    prior_works: list[PriorWork] = Field(
        default_factory=list,
        description="Prior works to scan for genealogical traces",
    )
    research_question: Optional[str] = Field(
        default=None,
        description="Optional research question guiding the analysis",
    )
    depth_preference: Optional[str] = Field(
        default=None,
        description="User's depth preference: surface, standard, deep, or None (let orchestrator decide)",
    )
    focus_hint: Optional[str] = Field(
        default=None,
        description="Optional hint about what to focus on (e.g., 'vocabulary evolution', 'Marxist origins')",
    )


class PlanRefinementRequest(BaseModel):
    """Input for refining an existing plan."""

    feedback: str = Field(
        ...,
        description="User feedback on what to change",
    )
    specific_changes: Optional[dict[str, Any]] = Field(
        default=None,
        description="Specific field changes to apply before LLM refinement",
    )


class WorkflowExecutionPlan(BaseModel):
    """A concrete, contextualized plan for executing a workflow.

    This is the orchestrator's primary output. It configures the existing
    5-phase genealogy pipeline with context-appropriate settings.
    """

    # Identity
    plan_id: str = Field(
        default_factory=lambda: f"plan-{uuid.uuid4().hex[:12]}",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
    )
    workflow_key: str = Field(
        default="intellectual_genealogy",
    )

    # Context that drove this plan
    thinker_name: str
    target_work: TargetWork
    prior_works: list[PriorWork] = Field(default_factory=list)
    research_question: Optional[str] = None

    # The strategy
    strategy_summary: str = Field(
        default="",
        description="2-3 paragraphs explaining the overall analytical approach",
    )
    phases: list[PhaseExecutionSpec] = Field(
        default_factory=list,
        description="Per-phase execution configuration",
    )
    recommended_views: list[ViewRecommendation] = Field(
        default_factory=list,
        description="Recommended views for presenting results",
    )

    # Estimates
    estimated_llm_calls: int = Field(
        default=0,
        description="Estimated number of LLM calls across all phases",
    )
    estimated_depth_profile: str = Field(
        default="",
        description="Human-readable summary (e.g., 'deep profiling, standard scanning, deep synthesis')",
    )

    # Metadata
    status: str = Field(
        default="draft",
        description="draft, approved, executing, completed",
    )
    model_used: str = Field(
        default="",
        description="Model that generated this plan",
    )
    generation_tokens: int = Field(
        default=0,
        description="Tokens used to generate this plan",
    )

    # Adaptive orchestrator fields
    objective_key: Optional[str] = Field(
        default=None,
        description="Analysis objective that drove this plan (e.g., 'genealogical', 'logical'). "
        "None for legacy fixed-pipeline plans.",
    )
    book_samples: list[dict] = Field(
        default_factory=list,
        description="Serialized BookSamples that informed adaptive planning decisions.",
    )
    estimated_total_cost_usd: float = Field(
        default=0.0,
        description="Estimated total cost for executing this plan.",
    )
