"""Workflow schemas for multi-pass analysis pipelines.

Workflows are complex, multi-pass analysis pipelines that differ from chains:
- Chains: Combine engines, run once, produce single output
- Workflows: Multi-pass pipelines with intermediate state, caching, resumability
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class WorkflowCategory(str, Enum):
    """Categories for workflow organization."""

    SYNTHESIS = "synthesis"       # Essay and argument construction
    INFLUENCE = "influence"       # Intellectual debt analysis
    OUTLINE = "outline"           # Essay outline management
    ANALYSIS = "analysis"         # Multi-pass analytical workflows


class WorkflowPass(BaseModel):
    """A single pass within a workflow."""

    pass_number: int = Field(..., description="Order of this pass (1-indexed)")
    pass_name: str = Field(..., description="Human-readable name for this pass")
    pass_description: str = Field(
        default="", description="What this pass accomplishes"
    )
    engine_key: Optional[str] = Field(
        default=None,
        description="Engine to use for this pass (if engine-backed)",
    )
    prompt_template: Optional[str] = Field(
        default=None,
        description="Custom prompt template (if not engine-backed)",
    )
    requires_external_docs: bool = Field(
        default=False,
        description="Whether this pass needs documents beyond the corpus",
    )
    caches_result: bool = Field(
        default=True,
        description="Whether to cache pass results for resumability",
    )
    depends_on_passes: list[int] = Field(
        default_factory=list,
        description="Pass numbers this pass depends on",
    )
    output_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="Expected output schema for this pass",
    )


class WorkflowDefinition(BaseModel):
    """Definition for a multi-pass analysis workflow."""

    workflow_key: str = Field(
        ...,
        description="Unique identifier for this workflow (snake_case)",
    )
    workflow_name: str = Field(
        ...,
        description="Human-readable name",
    )
    description: str = Field(
        ...,
        description="What this workflow does and when to use it",
    )
    category: WorkflowCategory = Field(
        ...,
        description="Category for UI grouping",
    )
    version: int = Field(default=1, description="Workflow definition version")

    passes: list[WorkflowPass] = Field(
        ...,
        description="Ordered list of passes in this workflow",
    )

    # Input requirements
    required_inputs: list[str] = Field(
        default_factory=list,
        description="Required input types (e.g., 'corpus', 'external_texts', 'thinker_name')",
    )
    optional_inputs: list[str] = Field(
        default_factory=list,
        description="Optional input types",
    )

    # Output
    output_description: str = Field(
        default="",
        description="What the workflow produces",
    )
    final_output_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="Schema for the final workflow output",
    )

    # Metadata
    estimated_passes: Optional[int] = Field(
        default=None,
        description="Typical number of passes (may vary based on content)",
    )
    source_project: Optional[str] = Field(
        default=None,
        description="Project this workflow was extracted from",
    )


class WorkflowSummary(BaseModel):
    """Lightweight workflow info for listing endpoints."""

    workflow_key: str
    workflow_name: str
    description: str
    category: WorkflowCategory
    pass_count: int
    version: int
