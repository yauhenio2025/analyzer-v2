"""Engine definition schemas for Analyzer v2.

Pure analytical capability definitions - NO execution logic.
These schemas define what engines ARE, not how they RUN.

MIGRATION NOTES (2026-01-29):
- BREAKING CHANGE: extraction_prompt, curation_prompt, concretization_prompt removed
- NEW: stage_context field with StageContext for template composition
- Prompts are now composed at runtime from generic templates + engine context
- See src/stages/ for template system
- Migration script: scripts/migrate_engines_to_stages.py
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from ..stages.schemas import StageContext


class EngineKind(str, Enum):
    """Type of analysis engine."""

    PRIMITIVE = "primitive"
    RELATIONAL = "relational"
    SYNTHESIS = "synthesis"
    EXTRACTION = "extraction"
    COMPARISON = "comparison"


class EngineCategory(str, Enum):
    """Semantic category for engine organization.

    14-Category Architecture:
    - ANALYTICAL FOUNDATIONS: ARGUMENT, EPISTEMOLOGY, METHODOLOGY, SYSTEMS
    - SUBJECT DOMAINS: CONCEPTS, EVIDENCE, TEMPORAL
    - ACTOR & STRUCTURE: POWER, INSTITUTIONAL, MARKET
    - DISCOURSE ANALYSIS: RHETORIC, SCHOLARLY
    - CRITICAL ANALYSIS: VULNERABILITY (self-analysis of weaknesses)
    - SYNTHESIS: OUTLINE (essay construction operations)
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

    # Critical Analysis (self-examination)
    VULNERABILITY = "vulnerability"  # Counter-response self-analysis, exposed flanks

    # Synthesis (construction operations)
    OUTLINE = "outline"  # Essay construction, talking points, outline management


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

    # Stage context (replaces old prompt fields - 2026-01-29 migration)
    # Prompts are now composed at runtime from templates + this context
    stage_context: StageContext = Field(
        ...,
        description="Context for composing stage prompts from generic templates",
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

    # Rich profile/about section (optional)
    engine_profile: Optional["EngineProfile"] = Field(
        default=None,
        description="Rich 'About' section with theoretical foundations, methodology, use cases",
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
                "stage_context": {
                    "framework_key": "toulmin",
                    "additional_frameworks": ["dennett"],
                    "extraction": {
                        "analysis_type": "argument structure",
                        "analysis_type_plural": "argument structures",
                        "core_question": "How is this argument structured?",
                        "id_field": "arg_id",
                        "key_relationships": ["supports", "opposes", "chains_to"],
                    },
                    "curation": {
                        "item_type": "argument",
                        "item_type_plural": "arguments",
                    },
                    "concretization": {},
                },
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
    has_profile: bool = Field(default=False, description="Whether this engine has a rich profile")


class EnginePromptResponse(BaseModel):
    """Response for prompt retrieval endpoints.

    MIGRATION NOTE (2026-01-29): Prompts are now COMPOSED at runtime
    from generic templates + engine stage_context. The prompt field
    contains the fully rendered prompt ready for use.
    """

    engine_key: str
    prompt_type: str  # "extraction", "curation", or "concretization"
    prompt: str
    audience: str = "analyst"  # Target audience used for composition
    framework_used: Optional[str] = None  # Framework primer injected (if any)


class EngineSchemaResponse(BaseModel):
    """Response for schema retrieval endpoints."""

    engine_key: str
    canonical_schema: dict[str, Any]


# ============================================================================
# Engine Profile - Rich "About" Section for Engines
# ============================================================================


class TheoreticalFoundation(BaseModel):
    """A theoretical foundation that underlies the engine's approach."""

    name: str = Field(..., description="Name of the theoretical foundation")
    description: str = Field(..., description="Brief explanation of this foundation")
    source_thinker: Optional[str] = Field(
        default=None, description="Key thinker associated with this foundation"
    )


class KeyThinker(BaseModel):
    """A key thinker whose work informs the engine."""

    name: str = Field(..., description="Name of the thinker")
    contribution: str = Field(..., description="What they contributed to this approach")
    works: list[str] = Field(
        default_factory=list, description="Key works by this thinker"
    )


class Methodology(BaseModel):
    """The methodological approach of the engine."""

    approach: str = Field(
        ..., description="Plain-language description of the methodology (2-3 sentences)"
    )
    key_moves: list[str] = Field(
        default_factory=list, description="Analytical steps the engine performs"
    )
    conceptual_tools: list[str] = Field(
        default_factory=list, description="Tools/concepts the engine uses"
    )


class EngineExtracts(BaseModel):
    """What the engine extracts from texts."""

    primary_outputs: list[str] = Field(
        default_factory=list, description="Main things the engine extracts"
    )
    secondary_outputs: list[str] = Field(
        default_factory=list, description="Secondary/supporting extractions"
    )
    relationships: list[str] = Field(
        default_factory=list, description="Types of relationships identified"
    )


class UseCase(BaseModel):
    """A use case for the engine."""

    domain: str = Field(..., description="Domain where this is useful")
    description: str = Field(..., description="How the engine helps in this domain")
    example: Optional[str] = Field(
        default=None, description="Concrete example of use"
    )


class RelatedEngine(BaseModel):
    """A related engine and how it relates."""

    engine_key: str = Field(..., description="Key of the related engine")
    relationship: str = Field(
        ...,
        description="How this engine relates: complementary, alternative, prerequisite, or extends",
    )


class EngineProfile(BaseModel):
    """Rich 'About' section for an engine.

    Contains theoretical foundations, methodology, use cases, and other
    rich metadata that helps users understand what the engine does and
    how to use it effectively.
    """

    # Theoretical foundations
    theoretical_foundations: list[TheoreticalFoundation] = Field(
        default_factory=list,
        description="Theoretical foundations underlying the engine's approach",
    )

    # Key thinkers
    key_thinkers: list[KeyThinker] = Field(
        default_factory=list,
        description="Key thinkers whose work informs the engine",
    )

    # Methodology
    methodology: Optional[Methodology] = Field(
        default=None, description="The methodological approach of the engine"
    )

    # What it extracts
    extracts: Optional[EngineExtracts] = Field(
        default=None, description="What the engine extracts from texts"
    )

    # Use cases
    use_cases: list[UseCase] = Field(
        default_factory=list, description="Use cases for the engine"
    )

    # Strengths & limitations
    strengths: list[str] = Field(
        default_factory=list, description="Strengths of this engine"
    )
    limitations: list[str] = Field(
        default_factory=list, description="Known limitations"
    )

    # Related engines
    related_engines: list[RelatedEngine] = Field(
        default_factory=list, description="Related engines and their relationships"
    )

    # Preamble for prompt injection
    preamble: str = Field(
        default="",
        description="Preamble text that can be injected into prompts for context",
    )


class EngineProfileResponse(BaseModel):
    """Response for profile retrieval endpoints."""

    engine_key: str
    engine_name: str
    has_profile: bool
    profile: Optional[EngineProfile] = None


# Rebuild EngineDefinition to resolve forward reference to EngineProfile
EngineDefinition.model_rebuild()
