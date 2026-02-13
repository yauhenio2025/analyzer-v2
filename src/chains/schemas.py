"""Engine chain definition schemas for Analyzer v2.

Chains define how multiple engines can be combined for complex analysis.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class BlendMode(str, Enum):
    """How engines in a chain combine their outputs."""

    LLM_SELECTION = "llm_selection"  # LLM picks best engines for the task
    MERGE = "merge"  # Combine all outputs into unified result
    SEQUENTIAL = "sequential"  # Run engines in order, each building on previous
    PARALLEL = "parallel"  # Run all engines, keep separate outputs


class EngineChainSpec(BaseModel):
    """Specification for a multi-engine analysis chain.

    Chains allow combining multiple engines for richer analysis.
    Different blend modes determine how outputs are combined.
    """

    # Identity
    chain_key: str = Field(
        ...,
        description="Unique identifier for this chain (snake_case)",
        examples=["concept_analysis_suite", "comprehensive_critique"],
    )
    chain_name: str = Field(
        ...,
        description="Human-readable name",
        examples=["Concept Analysis Suite", "Comprehensive Critique"],
    )
    description: str = Field(
        ..., description="What this chain does and when to use it"
    )
    version: int = Field(default=1, description="Chain specification version")

    # Engine composition
    engine_keys: list[str] = Field(
        ...,
        description="Engine keys in this chain (order matters for sequential)",
        examples=[
            [
                "concept_centrality_mapper",
                "concept_evolution",
                "conceptual_affordance_analyzer",
            ]
        ],
    )

    # Blend configuration
    blend_mode: BlendMode = Field(
        ..., description="How engine outputs are combined"
    )

    # For llm_selection mode
    selection_criteria: Optional[str] = Field(
        default=None,
        description="Criteria for LLM to select which engines to use",
        examples=[
            "Select the 2-3 engines most relevant to the user's research question"
        ],
    )
    max_engines: int = Field(
        default=3,
        description="Maximum engines to select (for llm_selection mode)",
    )

    # For merge mode
    merge_strategy: Optional[str] = Field(
        default=None,
        description="How to merge outputs from multiple engines",
        examples=["Synthesize findings into unified concept map"],
    )

    # For sequential mode
    pass_context: bool = Field(
        default=True,
        description="Whether each engine receives previous engine's output as context",
    )

    # Category for organization
    category: Optional[str] = Field(
        default=None,
        description="Category for grouping chains in UI",
        examples=["concepts", "critique", "comprehensive"],
    )

    # Runtime context schema
    context_parameter_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema describing what runtime context this chain expects. "
        "Informational — tells consumers what context_parameters to pass when invoking. "
        "Example: {'type': 'object', 'properties': {'relationship_type': {'type': 'string'}}}",
    )

    # Metadata
    recommended_for: list[str] = Field(
        default_factory=list,
        description="Use cases this chain is recommended for",
        examples=[["deep concept analysis", "philosophical texts"]],
    )

    class Config:
        json_schema_extra = {
            "example": {
                "chain_key": "concept_analysis_suite",
                "chain_name": "Concept Analysis Suite",
                "description": "Comprehensive concept analysis using multiple philosophical lenses",
                "version": 1,
                "engine_keys": [
                    "concept_centrality_mapper",
                    "concept_evolution",
                    "conceptual_affordance_analyzer",
                    "concept_demarcation_analyzer",
                ],
                "blend_mode": "llm_selection",
                "selection_criteria": "Select 2-3 engines most relevant to the concepts discussed",
                "max_engines": 3,
                "category": "concepts",
                "recommended_for": [
                    "philosophical texts",
                    "theoretical analysis",
                    "conceptual clarification",
                ],
            }
        }


class ChainSummary(BaseModel):
    """Lightweight chain info for listing endpoints."""

    chain_key: str
    chain_name: str
    description: str
    blend_mode: BlendMode
    engine_count: int
    category: Optional[str] = None
    has_context_parameters: bool = False


class ChainRecommendRequest(BaseModel):
    """Request for chain recommendation."""

    intent: str = Field(
        ...,
        description="User's analysis intent or question",
        examples=["I want to understand the key concepts and how they evolved"],
    )
    document_type: Optional[str] = Field(
        default=None,
        description="Type of document being analyzed",
        examples=["philosophical paper", "policy document", "news article"],
    )
    depth: str = Field(
        default="medium",
        description="Desired analysis depth: quick, medium, thorough",
    )


class ChainRecommendResponse(BaseModel):
    """Response for chain recommendation."""

    recommended_chain_key: str
    chain_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    alternative_chains: list[str] = Field(default_factory=list)
