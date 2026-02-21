"""Renderer definition schemas — data models for the renderer catalog.

RendererDefinitions declare rendering strategies with their capabilities,
stance affinities, and configuration schemas. Consumer apps use these
to select and configure appropriate renderers for analytical output.
"""

from typing import Any

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
