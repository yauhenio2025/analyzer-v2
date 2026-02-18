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
        default="claude-sonnet-4-5-20250929",
        description="Fallback model if primary fails",
    )
    max_tokens: int = Field(
        default=8000, description="Max tokens for LLM response"
    )

    # Provenance
    source: Optional[str] = Field(
        default=None,
        description="Where this template was extracted from",
    )


class TransformationTemplateSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    template_key: str
    template_name: str
    description: str = ""
    transformation_type: str
    applicable_renderer_types: list[str] = []
    tags: list[str] = []
    status: str = "active"
