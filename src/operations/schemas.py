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

from typing import Optional

from pydantic import BaseModel, Field


class RendererAffinity(BaseModel):
    """A renderer preference for a presentation stance."""

    renderer_key: str
    affinity: float = Field(
        default=0.5,
        description="Affinity score 0.0-1.0. Higher = better fit.",
    )


class AnalyticalStance(BaseModel):
    """A cognitive posture for an analytical or presentation pass.

    Analytical stances describe HOW the LLM should think — discovery mode
    vs. confrontation mode vs. integration mode. The output is always
    connected analytical prose.

    Presentation stances describe HOW to render output for display —
    summary mode vs. evidence mode vs. comparison mode. They guide
    LLM transformations from prose to structured formats.
    """

    key: str = Field(
        ...,
        description="Unique identifier (snake_case)",
        examples=["discovery", "confrontation", "integration", "summary", "evidence"],
    )
    name: str = Field(
        ...,
        description="Human-readable name",
    )
    stance: str = Field(
        ...,
        description="The prose description of the cognitive posture. "
        "This is injected into the prompt to set the LLM's mode.",
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
    stance_type: str = Field(
        default="analytical",
        description="'analytical' (guides HOW to analyze) or 'presentation' (guides HOW to render)",
    )
    ui_pattern: Optional[str] = Field(
        default=None,
        description="For presentation stances: the typical UI pattern "
        "(e.g. 'stat cards, bullet lists', 'split panels, diff views')",
    )
    preferred_renderers: list[RendererAffinity] = Field(
        default_factory=list,
        description="For presentation stances: preferred renderers with affinity scores",
    )


class StanceSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    key: str
    name: str
    cognitive_mode: str
    typical_position: str
    stance_type: str = "analytical"
