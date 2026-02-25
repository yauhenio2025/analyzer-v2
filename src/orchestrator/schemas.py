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


class ChapterTarget(BaseModel):
    """A chapter to target for chapter-level analysis."""

    chapter_id: str = Field(
        ...,
        description="Chapter identifier (e.g., 'ch7', 'appendix_a')",
    )
    chapter_title: str = Field(
        default="",
        description="Human-readable chapter title",
    )
    start_marker: Optional[str] = Field(
        default=None,
        description="Text or regex marker for chapter start",
    )
    end_marker: Optional[str] = Field(
        default=None,
        description="Text or regex marker for chapter end",
    )
    start_char: Optional[int] = Field(
        default=None,
        description="Character offset for chapter start",
    )
    end_char: Optional[int] = Field(
        default=None,
        description="Character offset for chapter end",
    )
    rationale: str = Field(
        default="",
        description="Why this chapter was selected for targeted analysis",
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

    # Chapter-level targeting
    chapter_targets: Optional[list[ChapterTarget]] = Field(
        default=None,
        description="Chapters to analyze individually in this phase. "
        "When set with document_scope='chapter', the phase runs once per chapter.",
    )
    document_scope: str = Field(
        default="whole",
        description="'whole' = analyze entire document, 'chapter' = per-chapter analysis. "
        "Requires chapter_targets to be set.",
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


class SamplingInsight(BaseModel):
    """What the adaptive planner observed from sampling a specific work."""

    work_title: str
    role: str  # "target" or "prior_work"
    key_observations: list[str]
    implications: list[str]
    affinity_rationale: str = ""


class ObjectiveAlignmentEntry(BaseModel):
    """Maps a specific goal to the engines/chains serving it."""

    goal: str
    serving_engines: list[str] = Field(default_factory=list)
    serving_chains: list[str] = Field(default_factory=list)
    coverage_assessment: str = ""


class PhaseDecision(BaseModel):
    """Structured rationale for a single phase's configuration."""

    phase_number: float
    phase_name: str
    chain_or_engine: str
    selection_rationale: str
    depth_rationale: str
    iteration_mode_rationale: str = ""
    alternatives_considered: list[str] = Field(default_factory=list)
    dependency_rationale: str = ""


class PerWorkDecision(BaseModel):
    """Why a specific chain was chosen for a specific work."""

    phase_number: float
    work_title: str
    chain_key: str
    rationale: str


class CatalogCoverageEntry(BaseModel):
    """Status of a single engine in the catalog relative to this plan."""

    engine_key: str
    status: str  # "selected" | "rejected" | "available_unused"
    reason: str = ""
    used_in_phases: list[float] = Field(default_factory=list)


class PlannerDecisionTrace(BaseModel):
    """Complete decision trace from adaptive planner.

    Externalizes the reasoning that drives pipeline composition:
    what was observed, how goals map to engines, why each phase
    was configured the way it was, and what was considered but rejected.
    """

    sampling_insights: list[SamplingInsight] = Field(default_factory=list)
    objective_alignment: list[ObjectiveAlignmentEntry] = Field(default_factory=list)
    phase_decisions: list[PhaseDecision] = Field(default_factory=list)
    per_work_decisions: list[PerWorkDecision] = Field(default_factory=list)
    catalog_coverage: list[CatalogCoverageEntry] = Field(default_factory=list)
    overall_strategy_rationale: str = ""


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

    # Model selection
    planning_model: Optional[str] = Field(
        default=None,
        description="Model for plan generation: 'claude-opus-4-6', 'gemini-3.1-pro-preview', etc. "
        "None = default (claude-opus-4-6).",
    )
    execution_model: Optional[str] = Field(
        default=None,
        description="Default model for phase execution: 'claude-sonnet-4-6', 'gemini-3.1-pro-preview', etc. "
        "None = use plan's per-phase model_hint. Can be overridden per-phase.",
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

    # Model selection
    execution_model: Optional[str] = Field(
        default=None,
        description="Default execution model for all phases. "
        "Per-phase model_hint takes priority if set. "
        "E.g., 'claude-sonnet-4-6', 'gemini-3.1-pro-preview'.",
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
    decision_trace: Optional['PlannerDecisionTrace'] = Field(
        default=None,
        description="Complete decision trace from adaptive planner. None for legacy plans.",
    )

    # Plan revision tracking
    revision_history: list[dict] = Field(
        default_factory=list,
        description="History of plan revisions (pre-execution, mid-course). "
        "Each entry is a serialized PlanRevisionEntry.",
    )
    current_revision: int = Field(
        default=0,
        description="Current revision number. 0 = original plan, 1+ = revised.",
    )
