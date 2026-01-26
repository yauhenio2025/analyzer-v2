"""Engine definition schemas for Analyzer v2.

Pure analytical capability definitions - NO execution logic.
These schemas define what engines ARE, not how they RUN.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EngineKind(str, Enum):
    """Type of analysis engine."""

    PRIMITIVE = "primitive"
    RELATIONAL = "relational"
    SYNTHESIS = "synthesis"
    EXTRACTION = "extraction"
    COMPARISON = "comparison"


class EngineCategory(str, Enum):
    """Semantic category for engine organization.

    12-Category Architecture:
    - ANALYTICAL FOUNDATIONS: ARGUMENT, EPISTEMOLOGY, METHODOLOGY, SYSTEMS
    - SUBJECT DOMAINS: CONCEPTS, EVIDENCE, TEMPORAL
    - ACTOR & STRUCTURE: POWER, INSTITUTIONAL, MARKET
    - DISCOURSE ANALYSIS: RHETORIC, SCHOLARLY
    """

    # Analytical Foundations (how to reason)
    ARGUMENT = "argument"
    EPISTEMOLOGY = "epistemology"
    METHODOLOGY = "methodology"
    SYSTEMS = "systems"

    # Subject Domains (what to extract)
    CONCEPTS = "concepts"
    EVIDENCE = "evidence"
    TEMPORAL = "temporal"

    # Actor & Structure Analysis (who and how)
    POWER = "power"
    INSTITUTIONAL = "institutional"
    MARKET = "market"

    # Discourse Analysis (how it's said)
    RHETORIC = "rhetoric"
    SCHOLARLY = "scholarly"


class EngineDefinition(BaseModel):
    """Pure analytical capability definition - NO execution logic.

    This schema captures everything needed to UNDERSTAND and USE an engine,
    but contains no code for actually running it.
    """

    # Identity
    engine_key: str = Field(
        ...,
        description="Unique identifier for this engine (snake_case)",
        examples=["inferential_commitment_mapper_advanced", "argument_architecture"],
    )
    engine_name: str = Field(
        ...,
        description="Human-readable name",
        examples=["Inferential Commitment Mapper (Advanced)", "Argument Architecture"],
    )
    description: str = Field(
        ..., description="What this engine does and why it's useful"
    )
    version: int = Field(default=1, description="Schema/definition version")

    # Classification
    category: EngineCategory = Field(
        ..., description="Semantic category for UI grouping"
    )
    kind: EngineKind = Field(
        default=EngineKind.PRIMITIVE, description="Type of analysis this engine performs"
    )
    reasoning_domain: str = Field(
        default="",
        description="The domain of reasoning this engine operates in",
        examples=["brandomian_inferentialism_advanced", "argument_structure"],
    )
    researcher_question: str = Field(
        default="",
        description="The question a researcher would ask that this engine answers",
        examples=["What are you really signing up for when you accept these ideas?"],
    )

    # Prompts (the theory - this is what we're extracting)
    extraction_prompt: str = Field(
        ...,
        description="Prompt that guides Stage 1 extraction from documents",
    )
    curation_prompt: str = Field(
        ...,
        description="Prompt that guides Stage 2 curation/synthesis",
    )
    concretization_prompt: Optional[str] = Field(
        default=None,
        description="Prompt for Stage 2.5 label transformation (optional)",
    )

    # Schema (the structure)
    canonical_schema: dict[str, Any] = Field(
        ...,
        description="JSON Schema defining the engine's canonical output structure",
    )
    extraction_focus: list[str] = Field(
        default_factory=list,
        description="What aspects to focus on during extraction",
        examples=[["claims", "entities", "relationships"]],
    )

    # Output compatibility
    primary_output_modes: list[str] = Field(
        default_factory=list,
        description="Compatible output/renderer modes",
        examples=[["gemini_network_graph", "integrated_report", "smart_table"]],
    )

    # Paradigm associations
    paradigm_keys: list[str] = Field(
        default_factory=list,
        description="Associated paradigm keys for paradigm-aware analysis",
        examples=[["marxist", "brandomian"]],
    )

    # Metadata
    added_date: Optional[str] = Field(
        default=None, description="When this engine was added (ISO date)"
    )
    source_file: Optional[str] = Field(
        default=None,
        description="Original source file path in current Analyzer (for extraction tracking)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "engine_key": "argument_architecture",
                "engine_name": "Argument Architecture",
                "description": "Maps the logical structure of arguments",
                "version": 1,
                "category": "argument",
                "kind": "synthesis",
                "reasoning_domain": "argument_structure",
                "researcher_question": "How is this argument structured?",
                "extraction_prompt": "Analyze the document for argument structure...",
                "curation_prompt": "Synthesize the extracted argument structures...",
                "canonical_schema": {"claims": [{"id": "string", "text": "string"}]},
                "extraction_focus": ["claims", "relationships", "evidence"],
                "primary_output_modes": ["gemini_network_graph", "smart_table"],
                "paradigm_keys": [],
            }
        }


class EngineSummary(BaseModel):
    """Lightweight engine info for listing endpoints."""

    engine_key: str
    engine_name: str
    description: str
    category: EngineCategory
    kind: EngineKind
    version: int
    paradigm_keys: list[str] = Field(default_factory=list)


class EnginePromptResponse(BaseModel):
    """Response for prompt retrieval endpoints."""

    engine_key: str
    prompt_type: str  # "extraction", "curation", or "concretization"
    prompt: str


class EngineSchemaResponse(BaseModel):
    """Response for schema retrieval endpoints."""

    engine_key: str
    canonical_schema: dict[str, Any]
