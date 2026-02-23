"""Presenter schemas — data models for the presentation layer.

These models bridge execution outputs and consumer rendering:
- RefinedViewRecommendation: Post-execution view adjustment
- ViewPayload: Render-ready data for a single view
- PagePresentation: Complete page payload for the consumer
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# --- 3A: View Refinement ---


class RefinedViewRecommendation(BaseModel):
    """Enhanced view recommendation with post-execution insights."""

    view_key: str
    priority: str = Field(
        default="primary",
        description="primary (always show), secondary (show if data exists), "
        "optional (on-demand), hidden (suppress)",
    )
    presentation_stance_override: Optional[str] = Field(
        default=None,
        description="Override the view's default presentation stance",
    )
    rationale: str = Field(
        default="",
        description="Updated rationale based on actual results",
    )
    renderer_config_overrides: Optional[dict[str, Any]] = Field(
        default=None,
        description="Renderer config adjustments based on output characteristics",
    )
    data_quality_assessment: str = Field(
        default="standard",
        description="Assessment of data quality: rich, standard, thin, empty",
    )


class ViewRefinementResult(BaseModel):
    """Output of the view refinement process."""

    job_id: str
    plan_id: str
    original_views: list[dict] = Field(
        default_factory=list,
        description="Original recommended_views from the plan",
    )
    refined_views: list[RefinedViewRecommendation] = Field(
        default_factory=list,
    )
    changes_summary: str = Field(
        default="",
        description="Human-readable summary of what changed and why",
    )
    refinement_model: str = ""
    tokens_used: int = 0


# --- 3B: Presentation Bridge ---


class TransformationTask(BaseModel):
    """A single transformation to run."""

    view_key: str
    output_id: str
    template_key: Optional[str] = Field(
        default=None,
        description="Curated template key. None when using dynamic extraction.",
    )
    engine_key: str
    renderer_type: str
    section: str = Field(
        default="",
        description="Section label for presentation_cache",
    )
    content_override: Optional[str] = Field(
        default=None,
        description="When set, use this content for transformation instead of loading "
        "from the single output_id row. Used for multi-pass concatenated content.",
    )
    dynamic_config: Optional[dict[str, Any]] = Field(
        default=None,
        description="Dynamic extraction config (system_prompt, model, etc.) "
        "when no curated template exists. Composed at runtime from engine "
        "metadata + renderer shape + stance.",
    )


class TransformationTaskResult(BaseModel):
    """Result of a single transformation task."""

    view_key: str
    output_id: str
    template_key: Optional[str] = None
    section: str
    success: bool
    cached: bool = False
    error: Optional[str] = None
    model_used: Optional[str] = None
    execution_time_ms: int = 0
    extraction_source: str = Field(
        default="curated",
        description="'curated' (from template) or 'dynamic' (from engine+renderer metadata)",
    )


class PresentationBridgeResult(BaseModel):
    """Result of running the presentation bridge."""

    job_id: str
    tasks_planned: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    tasks_skipped: int = Field(
        default=0,
        description="Views with no applicable transformation (passthrough)",
    )
    cached_results: int = Field(
        default=0,
        description="Already in presentation_cache (skipped re-extraction)",
    )
    dynamic_extractions: int = Field(
        default=0,
        description="Tasks that used dynamic extraction (no curated template)",
    )
    details: list[TransformationTaskResult] = Field(default_factory=list)


# --- 3C: Presentation API ---


class ViewPayload(BaseModel):
    """Complete render-ready payload for a single view."""

    view_key: str
    view_name: str
    description: str = ""
    renderer_type: str
    renderer_config: dict[str, Any] = Field(default_factory=dict)
    presentation_stance: Optional[str] = None

    # Recommendation metadata
    priority: str = "secondary"
    rationale: str = ""
    data_quality: str = "standard"

    # Data source info
    phase_number: Optional[float] = None
    engine_key: Optional[str] = None
    chain_key: Optional[str] = None
    scope: str = "aggregated"

    # The data
    has_structured_data: bool = False
    structured_data: Optional[Any] = Field(
        default=None,
        description="Pre-extracted structured data from presentation_cache",
    )
    raw_prose: Optional[str] = Field(
        default=None,
        description="Raw prose output from phase_outputs (for prose views or fallback)",
    )

    # For per_item views
    items: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="List of {work_key, structured_data/raw_prose} for per_item views",
    )

    # Tab count (from tab_count_field)
    tab_count: Optional[int] = None

    # Visibility
    visibility: str = "if_data_exists"
    position: float = 0

    # Nested children
    children: list["ViewPayload"] = Field(default_factory=list)


class PagePresentation(BaseModel):
    """Complete page presentation for the consumer.

    This is the primary output of the presenter module. The consumer app
    (The Critic) receives this and renders it directly — no additional
    API calls needed.
    """

    job_id: str
    plan_id: str
    thinker_name: str = ""
    strategy_summary: str = ""

    # The view tree (render-ready)
    views: list[ViewPayload] = Field(default_factory=list)
    view_count: int = 0

    # Execution metadata
    execution_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Phase statuses, timing, token usage from the job",
    )

    # Refinement metadata
    refinement_applied: bool = False
    refinement_summary: str = ""


# --- Request schemas ---


class RefineViewsRequest(BaseModel):
    """Input for POST /v1/presenter/refine-views."""

    job_id: str
    plan_id: str


class PrepareRequest(BaseModel):
    """Input for POST /v1/presenter/prepare."""

    job_id: str
    view_keys: Optional[list[str]] = Field(
        default=None,
        description="Specific views to prepare. None = all recommended views.",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction, ignoring presentation_cache.",
    )


class ComposeRequest(BaseModel):
    """Input for POST /v1/presenter/compose (all-in-one)."""

    job_id: str
    plan_id: str
    skip_refinement: bool = Field(
        default=False,
        description="Skip LLM view refinement (use plan recommendations as-is)",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction, ignoring presentation_cache.",
    )


# Resolve forward reference
ViewPayload.model_rebuild()
