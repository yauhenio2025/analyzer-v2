"""Paradigm definition schemas for Analyzer v2.

Based on the IE (Inferential Explorer) 4-layer ontology structure.
Paradigms provide philosophical frameworks for analysis.
"""

from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# 4-Layer Ontology Components
# =============================================================================


class FoundationalLayer(BaseModel):
    """The bedrock assumptions and tensions of a paradigm.

    This layer defines what the paradigm takes as given and where
    it sees fundamental conflicts.
    """

    assumptions: list[str] = Field(
        ...,
        description="Core claims the paradigm takes as foundational",
        examples=[
            [
                "Material conditions of production determine social consciousness",
                "History progresses through class struggle and modes of production",
            ]
        ],
    )
    core_tensions: list[str] = Field(
        ...,
        description="Fundamental conflicts or dialectical oppositions",
        examples=[
            [
                "Forces vs Relations of Production - technological capacity versus social organization",
                "Use Value vs Exchange Value - concrete utility versus abstract market value",
            ]
        ],
    )
    scope_conditions: list[str] = Field(
        default_factory=list,
        description="Where and when the paradigm applies (and doesn't)",
        examples=[
            [
                "Applies to societies with developed division of labor and private property",
                "Cannot explain pre-class societies fully",
            ]
        ],
    )


class StructuralLayer(BaseModel):
    """The ontological furniture of the paradigm.

    What entities exist according to this paradigm? How are they related?
    At what levels do we analyze?
    """

    primary_entities: list[str] = Field(
        ...,
        description="The basic objects/actors the paradigm recognizes",
        examples=[
            [
                "Classes - groups defined by relationship to means of production",
                "Mode of Production - unity of forces and relations defining an epoch",
                "Commodity - product with both use and exchange value for market",
            ]
        ],
    )
    relations: list[str] = Field(
        ...,
        description="How entities connect and interact",
        examples=[
            [
                "Exploitation - extraction of surplus value from labor",
                "Class antagonism - structural opposition of class interests",
            ]
        ],
    )
    levels_of_analysis: list[str] = Field(
        default_factory=list,
        description="Analytical strata or scales of analysis",
        examples=[
            [
                "Economic base - forces and relations of production",
                "Political superstructure - state, law, and institutions",
                "Ideological superstructure - culture, consciousness, ideas",
            ]
        ],
    )


class DynamicLayer(BaseModel):
    """How systems transform according to this paradigm.

    What drives change? What patterns does history follow?
    How do transformations unfold?
    """

    change_mechanisms: list[str] = Field(
        ...,
        description="What drives systemic change",
        examples=[
            [
                "Contradiction-driven crisis - internal contradictions generate systemic crises",
                "Class struggle - conflict between classes drives historical change",
            ]
        ],
    )
    temporal_patterns: list[str] = Field(
        default_factory=list,
        description="Historical progressions and rhythms",
        examples=[
            [
                "Historical materialism - modes of production succeed through revolution",
                "Crisis cycles - periodic crises of overproduction and profitability",
            ]
        ],
    )
    transformation_processes: list[str] = Field(
        default_factory=list,
        description="How specific transformations unfold",
        examples=[
            [
                "Revolution - fundamental restructuring of class relations",
                "Proletarianization - expansion of wage labor relations",
            ]
        ],
    )


class ExplanatoryLayer(BaseModel):
    """The conceptual and methodological toolkit.

    What concepts does the paradigm deploy? How does it explain?
    What does it diagnose as wrong? What does it envision as ideal?
    """

    key_concepts: list[str] = Field(
        ...,
        description="Theoretical vocabulary and conceptual tools",
        examples=[
            [
                "Surplus value - value created by workers beyond their wages",
                "Alienation - separation from product, process, species-being, and others",
                "Commodity fetishism - social relations appear as relations between things",
            ]
        ],
    )
    analytical_methods: list[str] = Field(
        default_factory=list,
        description="Epistemological tools and approaches",
        examples=[
            [
                "Dialectical materialism - analyzing contradictions in material conditions",
                "Historical materialism - tracing modes of production through history",
            ]
        ],
    )
    problem_diagnosis: list[str] = Field(
        default_factory=list,
        description="What the paradigm sees as wrong with current conditions",
        examples=[
            [
                "Exploitation of labor by capital",
                "Alienation from human creative essence",
            ]
        ],
    )
    ideal_state: list[str] = Field(
        default_factory=list,
        description="What the paradigm envisions as the goal or better state",
        examples=[
            [
                "Classless society with collective ownership",
                "From each according to ability, to each according to need",
            ]
        ],
    )


# =============================================================================
# Traits and Critique Patterns
# =============================================================================


class TraitDefinition(BaseModel):
    """A distinguishing characteristic of a paradigm.

    Traits are analytical lenses or emphases that can be activated
    to guide analysis in particular directions.
    """

    trait_name: str = Field(
        ...,
        description="Unique identifier for the trait",
        examples=["dialectical_trait", "materialist_trait"],
    )
    trait_description: str = Field(
        ..., description="What this trait emphasizes in analysis"
    )
    trait_items: list[str] = Field(
        ...,
        description="Specific elements or aspects this trait focuses on",
        examples=[
            [
                "Forces-relations contradiction",
                "Capital-labor contradiction",
                "Thesis-antithesis-synthesis",
            ]
        ],
    )


class CritiquePattern(BaseModel):
    """A reusable critique template for this paradigm.

    Critique patterns identify common analytical gaps and provide
    fix templates with placeholders for specific content.
    """

    pattern: str = Field(
        ...,
        description="Pattern identifier",
        examples=["missing_class_analysis", "idealist_causation"],
    )
    diagnostic: str = Field(
        ...,
        description="What the pattern identifies as problematic",
        examples=["Abstract categories without class content"],
    )
    fix: str = Field(
        ...,
        description="Template for fixing the issue, with {placeholders}",
        examples=["Specify class position of {actors} and interests in {process}"],
    )


# =============================================================================
# Main Paradigm Definition
# =============================================================================


class ParadigmDefinition(BaseModel):
    """Complete paradigm definition with 4-layer ontology.

    A paradigm is a philosophical framework that provides:
    - Foundational assumptions and tensions
    - Structural ontology (what exists, how related)
    - Dynamic understanding (how things change)
    - Explanatory concepts and methods

    Plus traits (analytical emphases) and critique patterns (reusable critiques).
    """

    # Identity
    paradigm_key: str = Field(
        ...,
        description="Unique identifier (snake_case)",
        examples=["marxist", "brandomian", "foucauldian"],
    )
    paradigm_name: str = Field(
        ..., description="Human-readable name", examples=["Marxist", "Brandomian"]
    )
    version: str = Field(default="1.0.0", description="Semantic version string")
    guiding_thinkers: str = Field(
        ...,
        description="Key thinkers associated with this paradigm",
        examples=["Karl Marx, Friedrich Engels, Antonio Gramsci, Rosa Luxemburg"],
    )
    description: str = Field(
        ..., description="What this paradigm is and what it emphasizes"
    )
    status: str = Field(
        default="active",
        description="Current status (active, deprecated, experimental)",
    )

    # 4-Layer Ontology
    foundational: FoundationalLayer = Field(
        ..., description="Bedrock assumptions and tensions"
    )
    structural: StructuralLayer = Field(
        ..., description="Ontological entities and relations"
    )
    dynamic: DynamicLayer = Field(
        ..., description="Change mechanisms and patterns"
    )
    explanatory: ExplanatoryLayer = Field(
        ..., description="Concepts and methods"
    )

    # Traits
    active_traits: list[str] = Field(
        default_factory=list,
        description="Which traits are active by default",
        examples=[["dialectical_trait", "materialist_trait", "critical_trait"]],
    )
    trait_definitions: list[TraitDefinition] = Field(
        default_factory=list, description="Available traits for this paradigm"
    )

    # Critique patterns
    critique_patterns: list[CritiquePattern] = Field(
        default_factory=list, description="Reusable critique templates"
    )

    # Metadata
    historical_context: str = Field(
        default="",
        description="Historical background and development of this paradigm",
    )
    related_paradigms: list[str] = Field(
        default_factory=list,
        description="Related or complementary paradigms",
        examples=[["Critical Theory", "World-Systems Theory"]],
    )

    # Engine associations
    primary_engines: list[str] = Field(
        default_factory=list,
        description="Engine keys that embody this paradigm's approach",
    )
    compatible_engines: list[str] = Field(
        default_factory=list,
        description="Engine keys that work well with this paradigm",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "paradigm_key": "marxist",
                "paradigm_name": "Marxist",
                "version": "2.1.0",
                "guiding_thinkers": "Karl Marx, Friedrich Engels, Antonio Gramsci",
                "description": "Analyzes society through class struggle and material conditions",
                "status": "active",
                "foundational": {
                    "assumptions": ["Material conditions determine consciousness"],
                    "core_tensions": ["Forces vs Relations of Production"],
                    "scope_conditions": ["Applies to class societies"],
                },
                "structural": {
                    "primary_entities": ["Classes", "Mode of Production"],
                    "relations": ["Exploitation", "Class antagonism"],
                    "levels_of_analysis": ["Economic base", "Superstructure"],
                },
                "dynamic": {
                    "change_mechanisms": ["Contradiction-driven crisis"],
                    "temporal_patterns": ["Crisis cycles"],
                    "transformation_processes": ["Revolution"],
                },
                "explanatory": {
                    "key_concepts": ["Surplus value", "Alienation"],
                    "analytical_methods": ["Dialectical materialism"],
                    "problem_diagnosis": ["Exploitation of labor"],
                    "ideal_state": ["Classless society"],
                },
                "active_traits": ["dialectical_trait", "materialist_trait"],
                "trait_definitions": [],
                "critique_patterns": [],
            }
        }


class ParadigmSummary(BaseModel):
    """Lightweight paradigm info for listing endpoints."""

    paradigm_key: str
    paradigm_name: str
    description: str
    version: str
    status: str
    guiding_thinkers: str
    active_traits: list[str] = Field(default_factory=list)


class ParadigmPrimerResponse(BaseModel):
    """Response for primer generation endpoint.

    A primer is an LLM-ready text that explains the paradigm
    for use in analysis prompts.
    """

    paradigm_key: str
    primer_text: str
    sections: dict[str, str] = Field(
        default_factory=dict,
        description="Individual sections of the primer",
    )


class ParadigmEnginesResponse(BaseModel):
    """Response for paradigm-engine association endpoint."""

    paradigm_key: str
    primary_engines: list[str]
    compatible_engines: list[str]


class ParadigmCritiquePatternsResponse(BaseModel):
    """Response for critique patterns endpoint."""

    paradigm_key: str
    critique_patterns: list[CritiquePattern]
