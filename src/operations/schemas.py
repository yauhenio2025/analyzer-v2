"""Analytical Stances — shared cognitive postures for multi-pass analysis.

Stances describe HOW the LLM should think in a given pass, not what
shape the output takes. The output is always prose. The stance guides
the analytical posture: discovery mode vs. confrontation mode vs.
integration mode.

These are the reusable "verbs" of analytical progression that appear
across all engines. The engine-specific part is WHAT dimensions to
explore. The stance is the cognitive approach.

See docs/refactoring_engines.md and docs/plain_text_architecture.md
for the architectural rationale. Stances preserve the prose-first,
schema-on-read architecture while making multi-pass structure legible.
"""

from pydantic import BaseModel, Field


class AnalyticalStance(BaseModel):
    """A cognitive posture for an analytical pass.

    NOT an output template — a description of what kind of thinking
    the LLM should be doing. The output is always connected analytical
    prose. The stance just says "think like a discoverer" vs "think
    like a critic" vs "think like a synthesizer."
    """

    key: str = Field(
        ...,
        description="Unique identifier (snake_case)",
        examples=["discovery", "confrontation", "integration"],
    )
    name: str = Field(
        ...,
        description="Human-readable name",
    )
    stance: str = Field(
        ...,
        description="The prose description of the cognitive posture. "
        "This is injected into the prompt to set the LLM's analytical mode.",
    )
    cognitive_mode: str = Field(
        ...,
        description="One-line characterization of the thinking mode",
        examples=["divergent — maximize coverage", "adversarial — maximize tension detection"],
    )
    typical_position: str = Field(
        default="any",
        description="Where in a multi-pass sequence this stance typically appears: "
        "'early', 'middle', 'late', or 'any'",
    )
    pairs_well_with: list[str] = Field(
        default_factory=list,
        description="Stance keys that naturally follow or precede this one",
    )


class StanceSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    key: str
    name: str
    cognitive_mode: str
    typical_position: str
