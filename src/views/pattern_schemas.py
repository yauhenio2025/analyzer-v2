"""View pattern schemas — reusable templates for common view configurations.

ViewPatterns are abstractions over concrete view definitions. They capture
the renderer + config + sub-renderer combination that works well for a
class of analytical output. An LLM orchestrator building a new app
instantiates patterns rather than copying specific views.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ViewPattern(BaseModel):
    """A reusable view configuration template.

    Patterns capture the structural recipe for a type of view —
    which renderer, what config shape, which sub-renderers work well.
    They are domain-independent templates that can be instantiated
    for any analytical domain.
    """

    # Identity
    pattern_key: str = Field(
        ...,
        description="Unique identifier (snake_case, e.g. 'accordion_sections')",
    )
    pattern_name: str = Field(
        ...,
        description="Human-readable name (e.g. 'Accordion with Typed Sections')",
    )
    description: str = Field(
        default="",
        description="What this pattern does and when to use it",
    )

    # Renderer specification
    renderer_type: str = Field(
        ...,
        description="Which renderer this pattern uses: 'accordion', 'card_grid', "
        "'tab', 'prose', 'timeline', 'table'",
    )
    default_renderer_config: dict[str, Any] = Field(
        default_factory=dict,
        description="Template config with placeholders. Consumers fill in "
        "domain-specific field names.",
    )

    # Sub-renderer recommendations
    recommended_sub_renderers: list[str] = Field(
        default_factory=list,
        description="Sub-renderer keys that work well with this pattern",
    )

    # Usage guidance
    ideal_for: list[str] = Field(
        default_factory=list,
        description="Use cases this pattern suits: 'multi-category output', "
        "'nested analysis', 'chronological data', 'narrative synthesis'",
    )
    data_shape_in: str = Field(
        default="",
        description="What data shape this pattern expects: 'nested_sections', "
        "'object_array', 'prose_text', 'timeline_data'",
    )
    instantiation_hints: str = Field(
        default="",
        description="Guidance for an LLM on how to fill in the template — "
        "which fields to customize, what config keys matter",
    )

    # Provenance
    example_views: list[str] = Field(
        default_factory=list,
        description="Existing view_keys that use this pattern (for reference)",
    )

    # Metadata
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags",
    )
    status: str = Field(
        default="active",
        description="'active', 'draft', 'deprecated'",
    )


class ViewPatternSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    pattern_key: str
    pattern_name: str
    description: str = ""
    renderer_type: str = ""
    ideal_for: list[str] = Field(default_factory=list)
    data_shape_in: str = ""
    example_views: list[str] = Field(default_factory=list)
    status: str = "active"
