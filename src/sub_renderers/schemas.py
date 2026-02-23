"""Sub-renderer definition schemas — data models for atomic UI components.

SubRendererDefinitions declare rendering strategies for individual sections
within container renderers (accordion, tab). They are browsable, editable
first-class catalog entries that the orchestrator can select from.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class SubRendererDefinition(BaseModel):
    """An atomic UI component within a container renderer.

    Sub-renderers handle the rendering of individual sections
    inside containers like accordion or tab renderers.
    """

    # Identity
    sub_renderer_key: str = Field(
        ...,
        description="Unique identifier (snake_case, e.g. 'chip_grid')",
    )
    sub_renderer_name: str = Field(
        ...,
        description="Human-readable name (e.g. 'Chip Grid')",
    )
    description: str = Field(
        default="",
        description="What this sub-renderer does and when to use it",
    )
    category: str = Field(
        ...,
        description="Sub-renderer category: 'atomic', 'composite', 'specialized', 'meta'",
    )

    # What data shapes this sub-renderer handles well
    ideal_data_shapes: list[str] = Field(
        default_factory=list,
        description="Data shapes this sub-renderer handles well: "
        "'flat_list', 'object_array', 'key_value_pairs', "
        "'prose_text', 'timeline_data', 'comparison_pairs', 'nested_sections'",
    )

    # Configuration schema
    config_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema describing the config keys this sub-renderer accepts",
    )

    # Stance affinities
    stance_affinities: dict[str, float] = Field(
        default_factory=dict,
        description="Stance key -> affinity score (0.0-1.0). "
        "Higher = better fit for that stance.",
    )

    # Parent compatibility
    parent_renderer_types: list[str] = Field(
        default_factory=list,
        description="Container renderer types this sub-renderer works within: "
        "'accordion', 'tab'",
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


class SubRendererSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    sub_renderer_key: str
    sub_renderer_name: str
    description: str = ""
    category: str = ""
    ideal_data_shapes: list[str] = Field(default_factory=list)
    stance_affinities: dict[str, float] = Field(default_factory=dict)
    parent_renderer_types: list[str] = Field(default_factory=list)
    status: str = "active"
