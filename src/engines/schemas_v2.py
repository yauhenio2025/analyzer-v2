"""Capability-based engine definition schemas for Analyzer v2.

This is the NEW engine definition format that describes WHAT an engine
investigates (the problematique, analytical dimensions, capabilities)
rather than HOW it formats output (canonical schemas, extraction steps).

The core insight: define the analytical WHAT richly, let LLMs determine
the HOW (output structure, number of passes, depth) at runtime.

These schemas coexist with the original EngineDefinition in schemas.py.
Engines can have both formats during the migration period.

See docs/refactoring_engines.md and docs/plain_text_architecture.md
for the architectural rationale.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from .schemas import EngineCategory, EngineKind


class AnalyticalDimension(BaseModel):
    """A dimension of analysis the engine can explore.

    NOT a schema field — a direction of inquiry. The LLM decides
    how deeply to explore each dimension based on the document
    and requested depth level.
    """

    key: str = Field(
        ...,
        description="Unique identifier for this dimension (snake_case)",
        examples=["epistemic_conditions", "power_knowledge_nexus"],
    )
    description: str = Field(
        ...,
        description="What this dimension investigates (1-2 sentences)",
    )
    probing_questions: list[str] = Field(
        default_factory=list,
        description="Questions the LLM should explore within this dimension",
    )
    depth_guidance: dict[str, str] = Field(
        default_factory=dict,
        description="Per-depth guidance: {'surface': '...', 'standard': '...', 'deep': '...'}",
    )


class CapabilityGrounding(BaseModel):
    """The intellectual tradition grounding a specific capability.

    Links a capability to the thinker, concept, and method that
    makes it analytically legitimate — not just what it does, but
    WHY it's a valid analytical move and where it comes from.
    """

    thinker: str = Field(
        ...,
        description="Primary thinker whose work grounds this capability (e.g., 'Brandom', 'Foucault')",
    )
    concept: str = Field(
        ...,
        description="Key concept from that thinker (e.g., 'incompatibility', 'episteme')",
    )
    method: str = Field(
        ...,
        description="How the thinker's approach informs this capability (1-2 sentences)",
    )


class EngineCapability(BaseModel):
    """Something this engine CAN DO.

    Capabilities are the unit of composability — the orchestrator
    selects engines based on which capabilities are needed.

    Each capability has both a one-line description (for lists and
    quick reference) and optionally a rich extended description that
    grounds it in the engine's intellectual tradition, explains its
    analytical method, and shows how it scales across depths.
    """

    key: str = Field(
        ...,
        description="Unique identifier for this capability (snake_case)",
        examples=["map_enabling_conditions", "detect_ruptures"],
    )
    description: str = Field(
        ...,
        description="What this capability does (1 sentence)",
    )
    extended_description: Optional[str] = Field(
        default=None,
        description="Rich 2-3 paragraph description grounding this capability in the "
        "engine's intellectual tradition, explaining its analytical method, "
        "and connecting it to the problematique.",
    )
    intellectual_grounding: Optional[CapabilityGrounding] = Field(
        default=None,
        description="The thinker, concept, and method that ground this capability",
    )
    indicators: list[str] = Field(
        default_factory=list,
        description="Textual signals that indicate this capability is needed "
        "(e.g., 'Contradictory premises in the same argument')",
    )
    depth_scaling: dict[str, str] = Field(
        default_factory=dict,
        description="How this capability's output scales across depths: "
        "{'surface': '...', 'standard': '...', 'deep': '...'}",
    )
    requires_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimension keys from OTHER engines this capability needs as input",
    )
    produces_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimension keys this capability contributes to",
    )


class ComposabilitySpec(BaseModel):
    """How this engine composes with others.

    Defines the context flow: what this engine shares with others,
    and what it benefits from receiving. The orchestrator uses this
    to plan shared context and avoid redundant extraction.
    """

    shares_with: dict[str, str] = Field(
        default_factory=dict,
        description="Dimensions this engine can share: {dimension_key: description}",
    )
    consumes_from: dict[str, str] = Field(
        default_factory=dict,
        description="Dimensions this engine benefits from receiving: {dimension_key: 'from engine X'}",
    )
    synergy_engines: list[str] = Field(
        default_factory=list,
        description="Engine keys that produce particularly good results when combined with this one",
    )


class PassDefinition(BaseModel):
    """An explicit pass within a depth level.

    Describes what analytical work happens in this pass, what cognitive
    stance the LLM adopts, and how data flows between passes. The output
    is always prose — the stance guides HOW to think, not what shape
    the output takes.
    """

    pass_number: int = Field(
        ...,
        description="1-indexed pass number within this depth level",
    )
    label: str = Field(
        ...,
        description="Human-readable name for this pass (e.g., 'Commitment Discovery')",
    )
    stance: str = Field(
        ...,
        description="Key of the analytical stance (e.g., 'discovery', 'confrontation'). "
        "References a stance from the operations/stances library.",
    )
    focus_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimension keys this pass focuses on (subset of engine's dimensions)",
    )
    focus_capabilities: list[str] = Field(
        default_factory=list,
        description="Capability keys this pass exercises (subset of engine's capabilities)",
    )
    consumes_from: list[int] = Field(
        default_factory=list,
        description="Pass numbers whose prose output feeds into this pass as context",
    )
    description: str = Field(
        ...,
        description="Engine-specific description of what this pass does and why. "
        "Written in prose — this is injected into the prompt alongside the stance.",
    )


class DepthLevel(BaseModel):
    """A depth level for analysis.

    The orchestrator selects depth based on document complexity,
    user preferences, and available budget.

    Depth levels can optionally include explicit pass definitions
    that break down the multi-pass structure: what stance each pass
    adopts, which dimensions it focuses on, and how data flows
    between passes. When passes are defined, the prompt composer
    can generate per-pass prompts.
    """

    key: str = Field(
        ...,
        description="Depth identifier: 'surface', 'standard', or 'deep'",
    )
    description: str = Field(
        ...,
        description="What this depth level involves",
    )
    typical_passes: int = Field(
        default=1,
        description="How many LLM passes this depth typically requires",
    )
    suitable_for: str = Field(
        default="",
        description="When to use this depth (document types, analysis goals)",
    )
    passes: list[PassDefinition] = Field(
        default_factory=list,
        description="Explicit pass breakdown. When present, makes the multi-pass "
        "structure legible: what stance each pass adopts, which dimensions it "
        "focuses on, and how prose flows between passes.",
    )


class IntellectualLineage(BaseModel):
    """The intellectual tradition this engine draws from."""

    primary: str = Field(
        ...,
        description="Primary thinker or tradition (e.g., 'foucault', 'brandom')",
    )
    secondary: list[str] = Field(
        default_factory=list,
        description="Secondary influences",
    )
    traditions: list[str] = Field(
        default_factory=list,
        description="Intellectual traditions (e.g., 'archaeology', 'genealogy', 'inferentialism')",
    )
    key_concepts: list[str] = Field(
        default_factory=list,
        description="Core concepts from the tradition that inform the engine",
    )


class CapabilityEngineDefinition(BaseModel):
    """Capability-driven engine definition.

    Describes WHAT an engine investigates, not HOW it formats output.
    The LLM orchestrator uses this to plan analysis, compose prompts,
    and determine output structure at runtime.
    """

    # Identity
    engine_key: str = Field(
        ...,
        description="Unique identifier matching the engine in the old system",
    )
    engine_name: str = Field(
        ...,
        description="Human-readable name",
    )
    version: int = Field(default=1, description="Capability definition version")
    category: EngineCategory = Field(
        ..., description="Semantic category"
    )
    kind: EngineKind = Field(
        default=EngineKind.PRIMITIVE, description="Type of analysis"
    )

    # THE WHAT — richly specified
    problematique: str = Field(
        ...,
        description="The core intellectual question this engine investigates (3-5 sentences). "
        "This is the engine's reason for existing — the analytical puzzle it addresses.",
    )
    researcher_question: str = Field(
        default="",
        description="The one-line question a researcher would ask",
    )
    intellectual_lineage: IntellectualLineage = Field(
        default_factory=lambda: IntellectualLineage(primary="general"),
        description="The intellectual tradition this engine draws from",
    )

    # Analytical dimensions — directions of inquiry
    analytical_dimensions: list[AnalyticalDimension] = Field(
        default_factory=list,
        description="Dimensions of analysis to explore (NOT schema fields)",
    )

    # Capabilities — what the engine can do
    capabilities: list[EngineCapability] = Field(
        default_factory=list,
        description="Discrete analytical capabilities this engine offers",
    )

    # Composability — how it plays with others
    composability: ComposabilitySpec = Field(
        default_factory=ComposabilitySpec,
        description="How this engine composes with other engines",
    )

    # Depth guidance
    depth_levels: list[DepthLevel] = Field(
        default_factory=list,
        description="Available depth levels for this engine",
    )

    # Legacy bridge
    legacy_engine_key: Optional[str] = Field(
        default=None,
        description="Engine key in old EngineDefinition format (for fallback)",
    )

    # Metadata
    apps: list[str] = Field(
        default_factory=list,
        description="Apps that use this engine (e.g., 'critic', 'visualizer')",
    )
    paradigm_keys: list[str] = Field(
        default_factory=list,
        description="Associated paradigm keys",
    )


class CapabilityEngineSummary(BaseModel):
    """Lightweight summary for listing/catalog endpoints."""

    engine_key: str
    engine_name: str
    category: EngineCategory
    kind: EngineKind
    problematique: str
    capability_count: int = 0
    dimension_count: int = 0
    depth_levels: list[str] = Field(default_factory=list)
    synergy_engines: list[str] = Field(default_factory=list)
    apps: list[str] = Field(default_factory=list)
