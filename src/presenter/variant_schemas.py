"""Schemas for Tier 3b A/B View Composition — variant generation and selection."""

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class VariantGenerateRequest(BaseModel):
    """Request to generate presentation variants for a view."""

    job_id: str = Field(..., min_length=1)
    view_key: str = Field(..., min_length=1)
    dimension: Literal["renderer_type", "sub_renderer_strategy"]
    max_variants: int = Field(default=3, ge=2, le=3)
    style_school: Optional[str] = None
    force: bool = Field(
        default=False,
        description="Regenerate even if cached (deletes existing variants + selections for this set)",
    )


class VariantResponse(BaseModel):
    """A single variant within a variant set."""

    variant_id: str
    variant_index: int
    is_control: bool
    renderer_type: str
    renderer_config: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    compatibility_score: float = 0.0


class VariantSetResponse(BaseModel):
    """A complete variant set with all its variants."""

    variant_set_id: str
    job_id: str
    view_key: str
    dimension: str
    base_renderer: str
    variants: list[VariantResponse] = Field(default_factory=list)
    variant_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class VariantSelectRequest(BaseModel):
    """Request to select a variant from a variant set."""

    variant_set_id: str = Field(..., min_length=1)
    variant_id: str = Field(..., min_length=1)
    job_id: str = Field(..., min_length=1)
    project_id: Optional[str] = None


class VariantSelectionResponse(BaseModel):
    """Response after selecting a variant."""

    variant_set_id: str
    variant_id: str
    view_key: str
    selected_at: str
    feedback_event_emitted: bool = False


class VariantSelectionSummary(BaseModel):
    """Aggregate selection data for analytics."""

    project_id: str
    dimension: str
    view_key: str
    base_renderer: str
    selected_renderer: str
    selection_count: int
