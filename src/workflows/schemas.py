"""Workflow schemas for multi-phase analysis pipelines.

Workflows are complex, multi-phase analysis pipelines that differ from chains:
- Chains: Combine engines, run once, produce single output
- Workflows: Multi-phase pipelines with intermediate state, caching, resumability

Terminology: workflow-level steps are "phases" (not "passes").
Engine-level stance iterations within depth levels remain "passes".
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class WorkflowCategory(str, Enum):
    """Categories for workflow organization."""

    SYNTHESIS = "synthesis"       # Essay and argument construction
    INFLUENCE = "influence"       # Intellectual debt analysis
    OUTLINE = "outline"           # Essay outline management
    ANALYSIS = "analysis"               # Multi-phase analytical workflows
    GENEALOGY = "genealogy"             # Intellectual genealogy / self-influence analysis
    DECISION_SUPPORT = "decision_support"  # Decision support system workflows


class WorkflowPhase(BaseModel):
    """A single phase within a workflow.

    Note: workflow-level steps are called "phases" to distinguish from
    engine-level "passes" (stance iterations within depth levels).
    """

    phase_number: float = Field(..., description="Order of this phase (1-indexed, supports .5 for intermediate phases)")
    phase_name: str = Field(..., description="Human-readable name for this phase")
    phase_description: str = Field(
        default="", description="What this phase accomplishes"
    )
    base_phase_description: Optional[str] = Field(
        default=None,
        description="Human-written invariant phase summary. When present, 'phase_description' "
        "is auto-computed from this + the engine/chain info on save. "
        "When absent, 'phase_description' is used as-is (backwards compatible).",
    )
    engine_key: Optional[str] = Field(
        default=None,
        description="Engine to use for this phase (if engine-backed)",
    )
    function_key: Optional[str] = Field(
        default=None,
        description="Function to use for this phase (if function-backed)",
    )
    chain_key: Optional[str] = Field(
        default=None,
        description="Chain to execute for this phase (if chain-backed). "
        "Mutually exclusive with engine_key and function_key.",
    )
    context_parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description="Runtime context passed to chain or engine. "
        "Free-form dict injected into prompts at execution time. "
        "Example: {'relationship_type': 'direct_precursor', 'focus_dimensions': ['vocabulary']}",
    )
    prompt_template: Optional[str] = Field(
        default=None,
        description="Custom prompt template (if not engine-backed)",
    )
    requires_external_docs: bool = Field(
        default=False,
        description="Whether this phase needs documents beyond the corpus",
    )
    caches_result: bool = Field(
        default=True,
        description="Whether to cache phase results for resumability",
    )
    depends_on_phases: list[float] = Field(
        default_factory=list,
        description="Phase numbers this phase depends on (supports .5 for intermediate phases)",
    )
    output_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="Expected output schema for this phase",
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_pass_fields(cls, data: Any) -> Any:
        """Backwards compatibility: accept old 'pass_*' field names."""
        if isinstance(data, dict):
            renames = {
                "pass_number": "phase_number",
                "pass_name": "phase_name",
                "pass_description": "phase_description",
                "depends_on_passes": "depends_on_phases",
            }
            for old_key, new_key in renames.items():
                if old_key in data and new_key not in data:
                    data[new_key] = data.pop(old_key)
        return data

    @model_validator(mode="after")
    def validate_execution_target(self) -> "WorkflowPhase":
        """Ensure at most one execution target is set."""
        targets = [
            ("engine_key", self.engine_key),
            ("function_key", self.function_key),
            ("chain_key", self.chain_key),
        ]
        set_targets = [name for name, val in targets if val is not None]
        if len(set_targets) > 1:
            raise ValueError(
                f"At most one of engine_key, function_key, chain_key may be set. "
                f"Got: {', '.join(set_targets)}"
            )
        return self


# Backwards compatibility alias
WorkflowPass = WorkflowPhase


class WorkflowDefinition(BaseModel):
    """Definition for a multi-phase analysis workflow."""

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

    phases: list[WorkflowPhase] = Field(
        ...,
        description="Ordered list of phases in this workflow",
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

    # Planner configuration
    planner_strategy: Optional[str] = Field(
        default=None,
        description="Domain-specific planning rules injected into the LLM planner's system prompt. "
        "Contains decision guidelines, engine focus heuristics, depth selection rules, "
        "and view recommendation logic specific to this workflow's domain.",
    )

    # Metadata
    estimated_phases: Optional[int] = Field(
        default=None,
        description="Typical number of phases (may vary based on content)",
    )
    source_project: Optional[str] = Field(
        default=None,
        description="Project this workflow was extracted from",
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_pass_fields(cls, data: Any) -> Any:
        """Backwards compatibility: accept old 'passes'/'estimated_passes' field names."""
        if isinstance(data, dict):
            if "passes" in data and "phases" not in data:
                data["phases"] = data.pop("passes")
            if "estimated_passes" in data and "estimated_phases" not in data:
                data["estimated_phases"] = data.pop("estimated_passes")
        return data


class WorkflowSummary(BaseModel):
    """Lightweight workflow info for listing endpoints."""

    workflow_key: str
    workflow_name: str
    description: str
    category: WorkflowCategory
    phase_count: int
    version: int
