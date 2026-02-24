"""Schemas for analysis objectives — high-level goal definitions that drive adaptive planning."""

from typing import Optional
from pydantic import BaseModel, Field


class AnalysisObjective(BaseModel):
    """High-level definition of what an analysis type must achieve.

    This is NOT a workflow template. It's a goal specification that the
    adaptive planner uses to compose a bespoke pipeline. The planner
    reads these objectives + the engine catalog + book samples and
    decides what phases/engines/chains best serve these objectives.
    """
    objective_key: str = Field(
        ..., description="Unique key: 'genealogical', 'logical', 'rhetorical'"
    )
    objective_name: str = Field(
        ..., description="Human-readable name"
    )

    # Core goals (what the analysis must produce)
    primary_goals: list[str] = Field(
        ..., description="What the analysis must achieve"
    )

    # Quality criteria (how we judge success)
    quality_criteria: list[str] = Field(
        default_factory=list,
        description="How we judge whether analysis met its goals"
    )

    # Engine affinity hints (starting points, not constraints)
    preferred_engine_functions: list[str] = Field(
        default_factory=list,
        description="Engine function tags to prioritize (e.g., 'genealogy', 'logic')"
    )
    preferred_categories: list[str] = Field(
        default_factory=list,
        description="Engine categories to prioritize (e.g., 'concepts', 'argument')"
    )

    # Planner strategy (injected into LLM planner prompt)
    planner_strategy: str = Field(
        default="",
        description="Rich free-text guidance for the LLM planner. "
        "Replaces WorkflowDefinition.planner_strategy for adaptive mode."
    )

    # Output expectations
    expected_deliverables: list[str] = Field(
        default_factory=list,
        description="What the final deliverable should contain"
    )

    # Baseline workflow (optional skeleton the planner can modify)
    baseline_workflow_key: Optional[str] = Field(
        default=None,
        description="Workflow key providing a starting skeleton (e.g., 'intellectual_genealogy')"
    )

    # View/presentation hints
    preferred_views: list[str] = Field(
        default_factory=list,
        description="Default view keys to recommend"
    )
