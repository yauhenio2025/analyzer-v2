"""Renderer definition schemas — data models for the renderer catalog.

RendererDefinitions declare rendering strategies with their capabilities,
stance affinities, and configuration schemas. Consumer apps use these
to select and configure appropriate renderers for analytical output.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SectionRendererHint(BaseModel):
    """Per-section renderer recommendation within an accordion/container."""

    section_key: str
    renderer_type: str = Field(
        ...,
        description="Sub-renderer type: 'chip_grid', 'mini_card_list', "
        "'key_value_table', 'prose_block', 'timeline_strip', "
        "'comparison_panel', 'stat_row'",
    )
    config: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""


class RendererDefinition(BaseModel):
    """A rendering strategy with capabilities and affinities.

    Renderers describe HOW to present analytical output. They are
    cataloged with metadata so the view refiner and consumer apps
    can make informed rendering choices.
    """

    # Identity
    renderer_key: str = Field(
        ...,
        description="Unique identifier (snake_case, e.g. 'accordion', 'card_grid')",
    )
    renderer_name: str = Field(
        ...,
        description="Human-readable name (e.g. 'Accordion with Expandable Sections')",
    )
    description: str = Field(
        default="",
        description="What this renderer does and when to use it",
    )
    category: str = Field(
        ...,
        description="Renderer category: 'container', 'list', 'narrative', "
        "'comparative', 'diagnostic'",
    )

    # What data shapes this renderer handles well
    ideal_data_shapes: list[str] = Field(
        default_factory=list,
        description="Data shapes this renderer handles well: "
        "'object_array', 'nested_sections', 'key_value_pairs', "
        "'flat_list', 'prose_text', 'timeline_data', 'comparison_pairs'",
    )

    # Formal JSON Schema for the data this renderer expects as input
    input_data_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema describing the structured data shape "
        "this renderer consumes. Used by the planner to match "
        "transformation outputs to renderer inputs.",
    )

    # Which analytical primitives this renderer is suited for
    primitive_affinities: list[str] = Field(
        default_factory=list,
        description="Analytical primitive keys this renderer can visualize "
        "(e.g. 'temporal_evolution', 'dialectical_tension'). "
        "Enables planner discovery: primitive -> renderer -> transformation.",
    )

    # Named configuration presets for common use-cases
    variants: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        description="Named config presets keyed by variant name. "
        "Each value has 'description', optional 'config' overrides, "
        "and 'example_use'.",
    )

    # Stance affinities — which presentation stances this renderer suits
    stance_affinities: dict[str, float] = Field(
        default_factory=dict,
        description="Stance key -> affinity score (0.0-1.0). "
        "Higher = better fit for that stance.",
    )

    # Section-level sub-renderers (for containers like accordion)
    available_section_renderers: list[str] = Field(
        default_factory=list,
        description="Sub-renderer types this container can host: "
        "'chip_grid', 'mini_card_list', 'key_value_table', etc.",
    )

    # Configuration schema — what config keys this renderer accepts
    config_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing the renderer_config keys "
        "this renderer accepts",
    )

    # Consumer support
    supported_apps: list[str] = Field(
        default_factory=lambda: ["the-critic"],
        description="Which consumer apps implement this renderer",
    )

    # Metadata
    status: str = Field(
        default="active",
        description="'active', 'draft', 'deprecated'",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags",
    )


class RendererSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    renderer_key: str
    renderer_name: str
    description: str = ""
    category: str = ""
    stance_affinities: dict[str, float] = Field(default_factory=dict)
    supported_apps: list[str] = Field(default_factory=list)
    status: str = "active"


# -- Renderer Recommendation Schemas --


class RendererRecommendRequest(BaseModel):
    """Context for LLM-powered renderer recommendation."""

    view_key: str = ""
    view_name: str = ""
    description: str = ""
    presentation_stance: Optional[str] = None
    renderer_type: Optional[str] = None  # current selection
    renderer_config: dict[str, Any] = Field(default_factory=dict)
    data_source: dict[str, Any] = Field(default_factory=dict)
    has_children: bool = False
    child_count: int = 0
    parent_view_key: Optional[str] = None
    target_app: str = "generic"
    include_config_migration: bool = False
    migrate_from: Optional[str] = None


class RendererRecommendation(BaseModel):
    """A single scored renderer recommendation."""

    renderer_key: str
    renderer_name: str
    category: str
    score: float
    rank: int
    reasoning: str
    stance_fit: str
    data_shape_fit: str
    config_suggestions: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)


class ConfigMigrationHint(BaseModel):
    """Guidance for migrating config between renderers."""

    from_renderer: str
    to_renderer: str
    fields_to_add: list[str] = Field(default_factory=list)
    fields_to_remove: list[str] = Field(default_factory=list)
    fields_to_transform: dict[str, str] = Field(default_factory=dict)
    explanation: str


class RendererRecommendResponse(BaseModel):
    """Full recommendation response with ranked options."""

    recommendations: list[RendererRecommendation]
    best_match: str
    config_migration: Optional[ConfigMigrationHint] = None
    analysis_summary: str
