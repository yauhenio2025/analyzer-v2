"""Operationalization schemas — the bridge between stances and engines.

Stances are abstract cognitive postures (discovery, confrontation, etc.).
Engines define analytical dimensions and capabilities.
Operationalizations specify HOW each stance applies to each engine:
what label it gets, what prose description guides the LLM, and which
dimensions/capabilities it focuses on.

This is the third layer in the three-layer architecture:
  Stances (HOW to think) × Engines (WHAT to think about) → Operationalizations (the bridge)
"""

from pydantic import BaseModel, Field


class StanceOperationalization(BaseModel):
    """How a specific analytical stance applies to a specific engine.

    This is the core unit of the operationalization layer. It captures
    the engine-specific meaning of an abstract stance — the prose that
    tells the LLM exactly what 'discovery' or 'confrontation' means
    when applied to THIS engine's dimensions and capabilities.
    """

    stance_key: str = Field(
        ...,
        description="Key of the analytical stance (references stances.yaml)",
        examples=["discovery", "confrontation", "dialectical"],
    )
    label: str = Field(
        ...,
        description="Engine-specific label for this stance application "
        "(e.g., 'Commitment Discovery' for discovery + inferential_commitment_mapper)",
    )
    description: str = Field(
        ...,
        description="Engine-specific prose describing what this stance does for this engine. "
        "This is the operationalization — injected into the prompt alongside the stance.",
    )
    focus_dimensions: list[str] = Field(
        default_factory=list,
        description="Dimension keys this stance focuses on (subset of engine's dimensions)",
    )
    focus_capabilities: list[str] = Field(
        default_factory=list,
        description="Capability keys this stance exercises (subset of engine's capabilities)",
    )


class DepthPassEntry(BaseModel):
    """A single pass in a depth-level sequence.

    References a stance operationalization by key and defines data flow
    between passes via consumes_from.
    """

    pass_number: int = Field(
        ...,
        description="1-indexed pass number within this depth level",
    )
    stance_key: str = Field(
        ...,
        description="Key of the analytical stance for this pass "
        "(must have a matching StanceOperationalization)",
    )
    consumes_from: list[int] = Field(
        default_factory=list,
        description="Pass numbers whose prose output feeds into this pass as context",
    )


class DepthSequence(BaseModel):
    """The pass ordering for a specific depth level of an engine.

    Defines which stances appear in what order at surface/standard/deep.
    """

    depth_key: str = Field(
        ...,
        description="Depth level key",
        examples=["surface", "standard", "deep"],
    )
    passes: list[DepthPassEntry] = Field(
        default_factory=list,
        description="Ordered list of passes for this depth level",
    )


class EngineOperationalization(BaseModel):
    """Complete operationalization for one engine.

    One file per engine in src/operationalizations/definitions/.
    Contains all stance operationalizations and depth sequences.
    """

    engine_key: str = Field(
        ...,
        description="Engine key (must match a capability engine definition)",
    )
    engine_name: str = Field(
        ...,
        description="Human-readable engine name",
    )
    stance_operationalizations: list[StanceOperationalization] = Field(
        default_factory=list,
        description="How each stance applies to this engine",
    )
    depth_sequences: list[DepthSequence] = Field(
        default_factory=list,
        description="Pass orderings for each depth level",
    )

    def get_stance_op(self, stance_key: str) -> StanceOperationalization | None:
        """Look up a stance operationalization by key."""
        for op in self.stance_operationalizations:
            if op.stance_key == stance_key:
                return op
        return None

    def get_depth_sequence(self, depth_key: str) -> DepthSequence | None:
        """Look up a depth sequence by key."""
        for seq in self.depth_sequences:
            if seq.depth_key == depth_key:
                return seq
        return None

    @property
    def stance_keys(self) -> list[str]:
        """All stance keys that have operationalizations."""
        return [op.stance_key for op in self.stance_operationalizations]

    @property
    def depth_keys(self) -> list[str]:
        """All depth levels that have sequences."""
        return [seq.depth_key for seq in self.depth_sequences]


class OperationalizationSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    engine_key: str
    engine_name: str
    stance_count: int
    depth_count: int
    stance_keys: list[str]
    depth_keys: list[str]


class CoverageEntry(BaseModel):
    """One cell in the coverage matrix."""

    engine_key: str
    engine_name: str
    has_operationalization: bool
    stance_keys: list[str]


class CoverageMatrix(BaseModel):
    """Engine x Stance coverage grid."""

    all_stance_keys: list[str] = Field(
        description="All known stance keys (columns)",
    )
    engines: list[CoverageEntry] = Field(
        description="One entry per engine with operationalization status",
    )
