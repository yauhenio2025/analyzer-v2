"""Extension points schemas for workflow analysis.

Defines the data structures for analyzing WHERE in a workflow additional
engines could be plugged in, and scoring candidates by composability fit.
"""

from pydantic import BaseModel, Field


class DimensionCoverage(BaseModel):
    """Tracks what analytical dimensions a phase currently covers vs could cover."""

    dimension_key: str
    dimension_description: str = ""
    covered_by: list[str] = Field(
        default_factory=list,
        description="Engine keys currently covering this dimension",
    )
    gap_engines: list[str] = Field(
        default_factory=list,
        description="Engine keys that could add coverage for this dimension",
    )
    coverage_ratio: float = Field(
        default=0.0,
        description="0.0 - 1.0 coverage ratio",
    )


class CapabilityGap(BaseModel):
    """A capability that no current engine in this phase provides."""

    capability_key: str
    capability_description: str = ""
    available_in: list[str] = Field(
        default_factory=list,
        description="Engine keys that have this capability",
    )
    relevance_score: float = Field(
        default=0.0,
        description="How relevant this capability is to the phase's purpose (0.0 - 1.0)",
    )


class CandidateEngine(BaseModel):
    """An engine that could be added to a phase."""

    engine_key: str
    engine_name: str
    category: str
    kind: str

    # Scoring breakdown (all 0.0 - 1.0)
    synergy_score: float = Field(
        default=0.0,
        description="Tier 1: explicit synergy_engines match",
    )
    dimension_production_score: float = Field(
        default=0.0,
        description="Tier 2: produces dimensions consumed by phase engines",
    )
    dimension_novelty_score: float = Field(
        default=0.0,
        description="Tier 3: covers dimensions no current engine covers",
    )
    category_affinity_score: float = Field(
        default=0.0,
        description="Tier 4: same category/kind as phase engines",
    )
    capability_gap_score: float = Field(
        default=0.0,
        description="Tier 5: fills a capability gap in the phase",
    )

    # Composite
    composite_score: float = Field(
        default=0.0,
        description="Weighted combination of all tier scores",
    )
    recommendation_tier: str = Field(
        default="exploratory",
        description="'strong' (>=0.65), 'moderate' (>=0.40), 'exploratory' (>=0.20)",
    )

    # Whether this engine has full v2 composability data
    has_full_composability: bool = Field(
        default=False,
        description="True if this engine has v2 capability definitions with rich composability data",
    )

    # Justification
    rationale: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons for recommendation",
    )
    synergy_with: list[str] = Field(
        default_factory=list,
        description="Which current engines it synergizes with",
    )
    dimensions_added: list[str] = Field(
        default_factory=list,
        description="New dimensions it would bring",
    )
    capabilities_added: list[str] = Field(
        default_factory=list,
        description="New capabilities it would bring",
    )
    potential_issues: list[str] = Field(
        default_factory=list,
        description="Any concerns (redundancy, scope creep)",
    )


class PhaseExtensionPoint(BaseModel):
    """Extension analysis for a single workflow phase."""

    phase_number: float
    phase_name: str
    current_engines: list[str] = Field(default_factory=list)
    current_chain_key: str | None = None

    # Analysis
    dimension_coverage: list[DimensionCoverage] = Field(default_factory=list)
    capability_gaps: list[CapabilityGap] = Field(default_factory=list)
    candidate_engines: list[CandidateEngine] = Field(
        default_factory=list,
        description="Sorted by composite_score descending",
    )

    # Summary
    extension_potential: str = Field(
        default="low",
        description="'high', 'moderate', or 'low'",
    )
    summary: str = ""


class WorkflowExtensionAnalysis(BaseModel):
    """Complete extension analysis for a workflow."""

    workflow_key: str
    workflow_name: str
    depth: str
    analysis_timestamp: str
    phase_extensions: list[PhaseExtensionPoint] = Field(default_factory=list)

    # Workflow-level insights
    total_candidate_engines: int = 0
    strong_recommendations: int = 0
    underserved_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimensions with low coverage across the workflow",
    )
    workflow_summary: str = ""
