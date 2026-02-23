"""Transformation template schemas.

TransformationTemplates are named, reusable transformation specifications.
They extend the TransformationSpec embedded in view definitions with
metadata, execution config, and applicability declarations.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class AggregateConfig(BaseModel):
    """Configuration for aggregate-type transformations."""

    group_by: Optional[str] = Field(
        default=None, description="Field to group by"
    )
    count_field: Optional[str] = Field(
        default=None, description="Field to count occurrences of"
    )
    sum_fields: list[str] = Field(
        default_factory=list, description="Fields to sum"
    )
    sort_by: Optional[str] = Field(
        default=None, description="Field to sort results by"
    )
    sort_order: str = Field(
        default="desc", description="Sort order: 'asc' or 'desc'"
    )
    limit: Optional[int] = Field(
        default=None, description="Max items to return"
    )


class TransformationTemplate(BaseModel):
    """A named, reusable transformation specification with metadata.

    Templates are the library of extraction recipes. Views can apply
    a template to copy its spec into their transformation field.
    """

    # Identity
    template_key: str = Field(
        ..., description="Unique snake_case identifier"
    )
    template_name: str = Field(
        ..., description="Human-readable display name"
    )
    description: str = Field(
        default="", description="What this transformation does"
    )
    version: int = Field(default=1)

    # Core transformation spec (mirrors views.TransformationSpec)
    transformation_type: str = Field(
        ...,
        description="Type: 'none', 'schema_map', 'llm_extract', "
        "'llm_summarize', 'aggregate'",
    )
    field_mapping: Optional[dict[str, str]] = Field(
        default=None,
        description="Source -> display field mapping (schema_map type)",
    )
    llm_extraction_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON schema for LLM extraction output (llm_extract type)",
    )
    llm_prompt_template: Optional[str] = Field(
        default=None,
        description="System prompt for LLM transformation. "
        "The data is passed as user message.",
    )
    stance_key: Optional[str] = Field(
        default=None,
        description="Presentation stance key for context",
    )
    aggregate_config: Optional[AggregateConfig] = Field(
        default=None,
        description="Aggregation configuration (aggregate type)",
    )

    # Applicability metadata
    applicable_renderer_types: list[str] = Field(
        default_factory=list,
        description="Renderer types this template works with",
    )
    applicable_engines: list[str] = Field(
        default_factory=list,
        description="Engines whose output this template can transform",
    )

    # Primitive cross-references (for planner discovery)
    primitive_affinities: list[str] = Field(
        default_factory=list,
        description="Analytical primitive keys this transformation serves "
        "(e.g. 'temporal_evolution'). Enables planner discovery: "
        "primitive -> renderer -> transformation.",
    )
    renderer_config_presets: Optional[dict[str, dict[str, Any]]] = Field(
        default=None,
        description="Per-renderer-type config presets. Keyed by renderer_key, "
        "value is the renderer_config to use when pairing this "
        "transformation with that renderer.",
    )

    tags: list[str] = Field(
        default_factory=list, description="Categorization tags"
    )
    status: str = Field(
        default="active", description="active, draft, deprecated"
    )

    # LLM execution config
    model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Primary model for LLM transformations",
    )
    model_fallback: str = Field(
        default="claude-sonnet-4-6",
        description="Fallback model if primary fails",
    )
    max_tokens: int = Field(
        default=8000, description="Max tokens for LLM response"
    )

    # Domain classification (for multi-domain independence)
    domain: str = Field(
        default="generic",
        description="Domain this template belongs to: 'generic', 'genealogy', "
        "'rhetoric', 'policy', 'economics'. Enables cross-domain template discovery.",
    )
    pattern_type: Optional[str] = Field(
        default=None,
        description="Structural pattern: 'section_extraction', 'timeline_extraction', "
        "'card_extraction', 'table_extraction', 'narrative_extraction'. "
        "Used to find templates by output structure regardless of domain.",
    )
    data_shape_out: Optional[str] = Field(
        default=None,
        description="Output data shape: 'object_array', 'nested_sections', "
        "'timeline_data', 'key_value_pairs', 'prose_text'. "
        "Enables matching template output to renderer input.",
    )
    compatible_sub_renderers: list[str] = Field(
        default_factory=list,
        description="Sub-renderer keys that can consume this template's output. "
        "Enables orchestrator to chain: engine -> template -> sub-renderer.",
    )

    # Provenance
    source: Optional[str] = Field(
        default=None,
        description="Where this template was extracted from",
    )
    generation_mode: str = Field(
        default="curated",
        description="How this template was created: 'curated' (hand-authored), "
        "'generated' (LLM-generated), 'hybrid' (generated then manually refined)",
    )


class TransformationTemplateSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    template_key: str
    template_name: str
    description: str = ""
    transformation_type: str
    applicable_renderer_types: list[str] = []
    domain: str = "generic"
    pattern_type: Optional[str] = None
    data_shape_out: Optional[str] = None
    tags: list[str] = []
    status: str = "active"
    generation_mode: str = "curated"
