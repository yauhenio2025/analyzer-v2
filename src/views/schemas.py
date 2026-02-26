"""View definition schemas — declarative UI rendering specifications.

ViewDefinitions declare what data renders where and how. They reference
data sources (workflows, phases, engines, chains) and specify renderer
types and presentation stances for transformation.

Consumer apps fetch these definitions and dispatch to their own component
registries. No execution logic lives here — just declarations.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class DataSourceRef(BaseModel):
    """Reference to analytical output data.

    Points to a specific piece of output from a workflow execution.
    The consumer app resolves this reference against its own data store.
    """

    workflow_key: Optional[str] = Field(
        default=None,
        description="Workflow that produces this data (e.g. 'intellectual_genealogy')",
    )
    phase_number: Optional[float] = Field(
        default=None,
        description="Phase within the workflow (e.g. 1.0, 1.5, 2.0, 3.0, 4.0)",
    )
    engine_key: Optional[str] = Field(
        default=None,
        description="Specific engine that produced the output",
    )
    chain_key: Optional[str] = Field(
        default=None,
        description="Chain that produced the output",
    )
    result_path: str = Field(
        default="",
        description="JSONPath-like expression into the result data "
        "(e.g. 'tactics_detected', 'ideas[*].vocabulary')",
    )
    scope: str = Field(
        default="aggregated",
        description="'aggregated' (single result) or 'per_item' (one result per prior work/input item)",
    )


class TransformationSpec(BaseModel):
    """How to transform raw analytical output for display.

    When data needs reshaping before rendering — especially when LLM
    extraction is needed to convert prose into structured formats —
    this spec guides the transformation.
    """

    type: str = Field(
        default="none",
        description="Transformation type: 'none', 'schema_map', 'llm_extract', "
        "'llm_summarize', 'aggregate'",
    )
    field_mapping: Optional[dict[str, str]] = Field(
        default=None,
        description="Source field -> display field mapping for schema_map type",
    )
    llm_extraction_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON schema for LLM extraction output (llm_extract type)",
    )
    llm_prompt_template: Optional[str] = Field(
        default=None,
        description="Prompt template for LLM transformation. "
        "Supports {data}, {stance}, {format} placeholders.",
    )
    stance_key: Optional[str] = Field(
        default=None,
        description="Overrides parent view's presentation_stance for this transform",
    )


class ViewDefinition(BaseModel):
    """Declarative specification for how analytical output becomes UI.

    A ViewDefinition says: this data source -> this renderer type ->
    this position in this app. Consumer apps interpret the definition
    and dispatch to their own component libraries.
    """

    # Identity
    view_key: str = Field(
        ...,
        description="Unique identifier (snake_case, e.g. 'genealogy_relationship_landscape')",
    )
    view_name: str = Field(
        ...,
        description="Human-readable display name",
    )
    description: str = Field(
        default="",
        description="What this view shows and why it's useful",
    )
    version: int = Field(default=1)

    # WHERE — target location in consumer app
    target_app: str = Field(
        default="generic",
        description="Consumer app: 'the-critic', 'visualizer', 'generic'",
    )
    target_page: str = Field(
        ...,
        description="Page/context within the app (e.g. 'genealogy', 'concept_analysis')",
    )
    target_section: str = Field(
        default="results",
        description="Section of the page: 'results', 'sidebar', 'config', 'debug'",
    )

    # WHAT component — renderer specification
    renderer_type: str = Field(
        ...,
        description="Component type: 'tab', 'card_grid', 'timeline', 'prose', "
        "'matrix', 'accordion', 'card', 'stat_summary', 'table', 'raw_json'",
    )
    renderer_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Renderer-specific config (title_field, columns, expand_first, etc.)",
    )

    # WHAT data — sources
    data_source: DataSourceRef = Field(
        ...,
        description="Primary data reference",
    )
    secondary_sources: list[DataSourceRef] = Field(
        default_factory=list,
        description="Additional data sources to merge/overlay",
    )

    # HOW to transform
    transformation: TransformationSpec = Field(
        default_factory=TransformationSpec,
        description="How to transform raw data for display",
    )
    presentation_stance: Optional[str] = Field(
        default=None,
        description="Presentation stance key: 'summary', 'evidence', 'comparison', "
        "'narrative', 'interactive', 'diagnostic'",
    )

    # LAYOUT — position and nesting
    position: float = Field(
        default=0,
        description="Sort order within section (lower = earlier)",
    )
    parent_view_key: Optional[str] = Field(
        default=None,
        description="Key of parent view for nesting (e.g. subtabs within tabs)",
    )
    tab_count_field: Optional[str] = Field(
        default=None,
        description="JSONPath expression for count badge on tab",
    )

    # VISIBILITY
    visibility: str = Field(
        default="if_data_exists",
        description="'always', 'if_data_exists', 'on_demand'",
    )

    # AUDIENCE
    audience_overrides: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-audience config overrides keyed by audience_key",
    )

    # PLANNER
    planner_hint: str = Field(
        default="",
        description="Free-text guidance for the LLM planner about when/how to recommend this view",
    )
    planner_eligible: bool = Field(
        default=True,
        description="Whether the planner should consider this view for recommendations",
    )

    # METADATA
    status: str = Field(
        default="active",
        description="'active', 'draft', 'deprecated'",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags",
    )
    source_project: Optional[str] = Field(
        default=None,
        description="Which project this view was designed for",
    )
    generation_mode: str = Field(
        default="curated",
        description="How this view was created: 'curated' (hand-authored), "
        "'generated' (LLM-generated), 'hybrid' (generated then manually refined)",
    )


class ViewSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    view_key: str
    view_name: str
    description: str = ""
    target_app: str = "generic"
    target_page: str = ""
    renderer_type: str = ""
    presentation_stance: Optional[str] = None
    position: float = 0
    parent_view_key: Optional[str] = None
    visibility: str = "if_data_exists"
    status: str = "active"
    generation_mode: str = "curated"
    # Structural hints computed from renderer_config
    sections_count: int = 0
    has_sub_renderers: bool = False
    config_hints: list[str] = Field(default_factory=list)


class ChainViewInfo(BaseModel):
    """Enriched view summary showing how a chain's output reaches the UI.

    Returned by the /for-chain/{chain_key} endpoint to show the
    chain → view → renderer → sub-renderer presentation pipeline.
    """

    view_key: str
    view_name: str
    description: str = ""
    target_app: str = "generic"
    target_page: str = ""
    renderer_type: str = ""
    presentation_stance: Optional[str] = None
    position: float = 0
    parent_view_key: Optional[str] = None
    sections_count: int = 0
    has_sub_renderers: bool = False
    config_hints: list[str] = Field(default_factory=list)
    # Data source details — the key addition over ViewSummary
    source_chain_key: Optional[str] = Field(
        default=None, description="Chain key in data_source (if view references chain directly)"
    )
    source_engine_key: Optional[str] = Field(
        default=None, description="Engine key in data_source (if view references a specific engine)"
    )
    source_scope: str = Field(
        default="aggregated", description="Data scope: aggregated or per_item"
    )
    source_type: str = Field(
        default="primary",
        description="'primary' if chain/engine is in data_source, 'secondary' if in secondary_sources",
    )
    # Sub-renderer breakdown
    sub_renderers_used: list[str] = Field(
        default_factory=list,
        description="List of sub-renderer types used (e.g., ['mini_card_list', 'prose_block'])",
    )
    children: list["ChainViewInfo"] = Field(
        default_factory=list,
        description="Child views nested under this view",
    )


class ComposedView(BaseModel):
    """A view with its children resolved for tree composition."""

    view_key: str
    view_name: str
    description: str = ""
    renderer_type: str
    renderer_config: dict[str, Any] = {}
    data_source: DataSourceRef
    secondary_sources: list[DataSourceRef] = []
    transformation: TransformationSpec = TransformationSpec()
    presentation_stance: Optional[str] = None
    position: float = 0
    visibility: str = "if_data_exists"
    tab_count_field: Optional[str] = None
    audience_overrides: dict[str, dict[str, Any]] = {}
    children: list["ComposedView"] = Field(default_factory=list)


class ComposedPageResponse(BaseModel):
    """Response for the compose endpoint — full tree of views for a page."""

    app: str
    page: str
    view_count: int
    views: list[ComposedView]

    # Page-level metadata derived from workflow definition
    page_title: Optional[str] = None
    page_subtitle: Optional[str] = None
    workflow_key: Optional[str] = None
    workflow_category: Optional[str] = None


# Resolve forward reference
ComposedView.model_rebuild()
