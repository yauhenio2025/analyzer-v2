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
    renderer_type_override: Optional[str] = Field(
        default=None,
        description="Override the view's default container renderer",
    )
    rationale: str = Field(
        default="",
        description="Updated rationale based on actual results",
    )
    renderer_config_overrides: Optional[dict[str, Any]] = Field(
        default=None,
        description="Renderer config adjustments based on output characteristics",
    )
    display_label_override: Optional[str] = Field(
        default=None,
        description="Override the display label used in the consumer tab tree",
    )
    top_level_group: Optional[str] = Field(
        default=None,
        description="Bounded grouping hint for hybrid-dynamic top-level layouts",
    )
    promote_to_top_level: bool = Field(
        default=False,
        description="Promote a child view to top-level navigation for this run",
    )
    collapse_into_parent: bool = Field(
        default=False,
        description="Keep the view available for synthesis but hide it from normal child-tab navigation",
    )
    top_level_position_override: Optional[float] = Field(
        default=None,
        description="Override the top-level tab order for promoted/relabelled views",
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
    renderer_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Effective renderer config used for validation and dynamic extraction hints.",
    )
    section: str = Field(
        default="",
        description="Section label for presentation_cache",
    )
    content_override: Optional[Any] = Field(
        default=None,
        description="When set, use this content for transformation instead of loading "
        "from the single output_id row. Used for multi-pass concatenated content "
        "or persisted structured payloads.",
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


class ScaffoldArtifactDetail(BaseModel):
    """Per-view result for reading scaffold generation."""

    view_key: str
    scaffold_type: str
    status: str
    prompt_version: str = ""
    input_hash: str = ""
    model_used: str = ""
    error: Optional[str] = None


class ScaffoldGenerationResult(BaseModel):
    """Result of reading scaffold generation."""

    job_id: str
    artifacts_planned: int = 0
    artifacts_generated: int = 0
    artifacts_cached: int = 0
    artifacts_failed: int = 0
    details: list[ScaffoldArtifactDetail] = Field(default_factory=list)


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
    top_level_group: Optional[str] = None
    source_parent_view_key: Optional[str] = None
    promoted_to_top_level: bool = False
    selection_priority: Optional[str] = None
    navigation_state: Optional[str] = None
    structuring_policy: Optional[str] = None
    semantic_scaffold_type: Optional[str] = None
    scaffold_hosting_mode: Optional[str] = None
    derivation_kind: Optional[str] = None

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
    reading_scaffold: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional derived reading scaffold layered on top of canonical structured data",
    )
    raw_prose: Optional[str] = Field(
        default=None,
        description="Raw prose output from phase_outputs (for prose views or fallback)",
    )
    prose_ref_view_key: Optional[str] = Field(
        default=None,
        description="When raw_prose is omitted, references another view in the same page payload that owns the shared prose",
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
    consumer_key: str = ""
    presentation_version: int = 2
    presentation_contract_version: int = 1
    presentation_hash: str = ""
    presentation_content_hash: str = ""
    prepared_at: str = ""
    artifacts_ready: bool = False
    manifest_schema_version: int = 1
    trace_schema_version: int = 1
    resolver_version: str = ""
    thinker_name: str = ""
    strategy_summary: str = ""
    style_school: str = ""
    polish_state: str = "raw"

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


class EffectiveManifestView(BaseModel):
    """Data-light semantic contract for a single effective view."""

    view_key: str
    view_name: str
    description: str = ""
    renderer_type: str
    renderer_config: dict[str, Any] = Field(default_factory=dict)
    presentation_stance: Optional[str] = None
    selection_priority: str = "secondary"
    navigation_state: str = "normal"
    promoted_to_top_level: bool = False
    source_parent_view_key: Optional[str] = None
    display_parent_view_key: Optional[str] = None
    child_view_keys: list[str] = Field(default_factory=list)
    top_level_group: Optional[str] = None
    position: float = 0
    semantic_scaffold_type: str = "none"
    scaffold_hosting_mode: str = "none"
    structuring_policy: Optional[str] = None
    derivation_kind: Optional[str] = None
    legacy_visibility: Optional[str] = None


class EffectivePresentationManifest(BaseModel):
    """Effective capability-adapted semantic manifest for a job + consumer."""

    job_id: str
    plan_id: str
    consumer_key: str
    presentation_contract_version: int = 1
    presentation_hash: str = ""
    presentation_content_hash: str = ""
    prepared_at: str = ""
    artifacts_ready: bool = False
    manifest_schema_version: int = 1
    trace_schema_version: int = 1
    resolver_version: str = ""
    thinker_name: str = ""
    strategy_summary: str = ""
    style_school: str = ""
    polish_state: str = "raw"
    views: list[EffectiveManifestView] = Field(default_factory=list)
    view_count: int = 0


class DecisionTraceChange(BaseModel):
    """A single semantic change recorded in the reconstructed decision trace."""

    view_key: str
    field: str
    before: Any = None
    after: Any = None
    reason: str = ""


class IgnoredOverride(BaseModel):
    """Runtime override dropped during bounded-value validation."""

    view_key: str
    field: str
    value: Any = None
    reason: str = ""


class DecisionTraceEntry(BaseModel):
    """A coarse semantic trace stage reconstructed from presenter inputs."""

    stage: str
    reason: str = ""
    applied_changes: list[DecisionTraceChange] = Field(default_factory=list)
    ignored_changes: list[IgnoredOverride] = Field(default_factory=list)
    snapshot: list[EffectiveManifestView] = Field(default_factory=list)


class PresentationDecisionTrace(BaseModel):
    """Versioned, on-demand reconstruction of presentation decision making."""

    job_id: str
    plan_id: str
    consumer_key: str
    manifest_schema_version: int = 1
    trace_schema_version: int = 1
    resolver_version: str = ""
    style_school: str = ""
    polish_state: str = "raw"
    entries: list[DecisionTraceEntry] = Field(default_factory=list)
    final_manifest: EffectivePresentationManifest


# --- 3D: View Polishing ---


class PolishRequest(BaseModel):
    """Input for POST /v1/presenter/polish."""

    job_id: str
    view_key: str
    consumer_key: str = "the-critic"
    style_school: Optional[str] = Field(
        default=None,
        description="Style school to use. Auto-resolved from engine affinities if not set.",
    )
    force: bool = Field(
        default=False,
        description="Force re-generation, ignoring polish_cache.",
    )
    cache_only: bool = Field(
        default=False,
        description="Only return cached polish. Returns 204 if not cached "
        "(avoids triggering an LLM call).",
    )


class StyleOverrides(BaseModel):
    """CSS-like style overrides applied at defined injection points in renderers."""

    # === Existing injection points ===
    section_header: Optional[dict[str, str]] = None
    section_content: Optional[dict[str, str]] = None
    card: Optional[dict[str, str]] = None
    chip: Optional[dict[str, str]] = None
    badge: Optional[dict[str, str]] = None
    timeline_node: Optional[dict[str, str]] = None
    prose: Optional[dict[str, str]] = None
    accent_color: Optional[str] = None
    view_wrapper: Optional[dict[str, str]] = None
    items_container: Optional[dict[str, str]] = None

    # === New finer-grained injection points ===
    section_title: Optional[dict[str, str]] = None
    section_description: Optional[dict[str, str]] = None
    card_header: Optional[dict[str, str]] = None
    card_body: Optional[dict[str, str]] = None
    chip_label: Optional[dict[str, str]] = None
    chip_expanded: Optional[dict[str, str]] = None
    prose_lede: Optional[dict[str, str]] = None
    prose_body: Optional[dict[str, str]] = None
    prose_quote: Optional[dict[str, str]] = None
    timeline_connector: Optional[dict[str, str]] = None
    stat_number: Optional[dict[str, str]] = None
    stat_label: Optional[dict[str, str]] = None
    hero_card: Optional[dict[str, str]] = None
    view_header: Optional[dict[str, str]] = None


class PolishedViewPayload(BaseModel):
    """Polished renderer config + style overrides for a view."""

    original_view_key: str
    polished_renderer_config: dict[str, Any]
    style_overrides: StyleOverrides = Field(default_factory=StyleOverrides)
    section_descriptions: dict[str, str] = Field(
        default_factory=dict,
        description="Enhanced section descriptions keyed by section key.",
    )
    token_format_version: Optional[int] = Field(
        default=None,
        description="2=token-aware (var(--dt-*) for colors), None=legacy raw CSS",
    )


class PolishResult(BaseModel):
    """Result of polishing a view."""

    polished_payload: PolishedViewPayload
    model_used: str = ""
    tokens_used: int = 0
    execution_time_ms: int = 0
    style_school: str = ""
    changes_summary: str = ""


# --- 3E: Per-Section Polish ---


class SectionPolishRequest(BaseModel):
    """Input for POST /v1/presenter/polish-section."""

    job_id: str
    view_key: str
    section_key: str
    consumer_key: str = "the-critic"
    user_feedback: Optional[str] = Field(
        default=None,
        description="User's natural-language instructions for improving this section.",
    )
    style_school: Optional[str] = None
    force: bool = False


class SectionPolishResult(BaseModel):
    """Result of polishing a single section."""

    section_key: str
    style_overrides: StyleOverrides = Field(default_factory=StyleOverrides)
    renderer_config_patch: dict[str, Any] = Field(
        default_factory=dict,
        description="Partial config to merge into this section's renderer config.",
    )
    section_description: str = ""
    changes_summary: str = ""
    model_used: str = ""
    tokens_used: int = 0
    execution_time_ms: int = 0
    style_school: str = ""
    user_feedback_applied: Optional[str] = None
    token_format_version: Optional[int] = Field(
        default=None,
        description="2=token-aware (var(--dt-*) for colors), None=legacy raw CSS",
    )


# --- Request schemas ---


class RefineViewsRequest(BaseModel):
    """Input for POST /v1/presenter/refine-views."""

    job_id: str
    plan_id: str
    consumer_key: str = "the-critic"


class PrepareRequest(BaseModel):
    """Input for POST /v1/presenter/prepare."""

    job_id: str
    consumer_key: str = "the-critic"
    view_keys: Optional[list[str]] = Field(
        default=None,
        description="Specific views to prepare. None = all recommended views.",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction, ignoring presentation_cache.",
    )


class EnsurePresentationRequest(BaseModel):
    """Input for POST /v1/presenter/ensure."""

    job_id: str
    plan_id: str
    consumer_key: str = "the-critic"
    skip_refinement: bool = Field(
        default=False,
        description="Skip LLM view refinement when starting background prep.",
    )
    clear_refinement: bool = Field(
        default=False,
        description="Delete cached refinement before starting background prep.",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction, ignoring presentation_cache.",
    )


class ComposeRequest(BaseModel):
    """Input for POST /v1/presenter/compose (all-in-one)."""

    job_id: str
    plan_id: str
    consumer_key: str = "the-critic"
    skip_refinement: bool = Field(
        default=False,
        description="Skip LLM view refinement (use plan recommendations as-is)",
    )
    clear_refinement: bool = Field(
        default=False,
        description="Delete any existing cached refinement before running. "
        "Use this to recover from a bad refinement that hid all views.",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction, ignoring presentation_cache.",
    )
    auto_polish: bool = Field(
        default=False,
        description="Automatically polish all views after assembly. "
        "Results are cached — subsequent loads are instant.",
    )
    style_school: Optional[str] = Field(
        default=None,
        description="Force a single style school for ALL views in this presentation. "
        "When set, every auto-polished view uses this school instead of "
        "per-engine auto-resolution, ensuring visual coherence across tabs. "
        "Valid values: minimalist_precision, explanatory_narrative, "
        "restrained_elegance, humanist_craft, emergent_systems, mobilization.",
    )


# Resolve forward reference
ViewPayload.model_rebuild()
