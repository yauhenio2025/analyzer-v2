"""Pydantic schemas for audience definitions.

Audiences are first-class entities that define how analysis is targeted
for different reader types. Each audience has:
- Identity (who they are, what they care about)
- Engine affinities (which engines serve them best)
- Visual style (how Gemini renders for them)
- Textual style (how text output is written)
- Curation guidance (how content is selected/prioritized)
- Strategist guidance (how reports are structured)
- Pattern discovery guidance (what patterns matter)
- Vocabulary translations (jargon → plain language mappings)
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AudienceStatus(str, Enum):
    """Status of an audience definition."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class AudienceIdentity(BaseModel):
    """Tab 1: Who is this audience? Core identity and priorities."""

    core_questions: list[str] = Field(
        default_factory=list,
        description="What this audience fundamentally wants to understand",
    )
    priorities: list[str] = Field(
        default_factory=list,
        description="What aspects of analysis they prioritize",
    )
    deprioritize: list[str] = Field(
        default_factory=list,
        description="What they DON'T care about (can be de-emphasized)",
    )
    detail_level: str = Field(
        default="balanced",
        description="How detailed vs focused: comprehensive, balanced, or focused",
    )


class EngineAffinities(BaseModel):
    """Tab 2: How this audience relates to engines."""

    preferred_categories: list[str] = Field(
        default_factory=list,
        description="Engine categories that naturally serve this audience",
    )
    high_affinity_engines: list[str] = Field(
        default_factory=list,
        description="Specific engines particularly valuable for this audience",
    )
    low_affinity_engines: list[str] = Field(
        default_factory=list,
        description="Engines less relevant (weighted lower, not excluded)",
    )
    category_weights: dict[str, float] = Field(
        default_factory=dict,
        description="0.3-1.6 multiplier per engine category",
    )


class VisualStyleConfig(BaseModel):
    """Tab 3: Visual rendering guidance for Gemini."""

    style_preference: str = Field(
        default="",
        description="Primary dataviz school (e.g., tufte, ft_style, agitprop)",
    )
    aesthetic: str = Field(default="", description="Overall visual aesthetic")
    color_palette: str = Field(default="", description="Color palette guidance")
    typography: str = Field(default="", description="Typography guidance")
    layout: str = Field(default="", description="Layout approach")
    visual_elements: str = Field(default="", description="Key visual elements")
    information_density: str = Field(
        default="MEDIUM",
        description="Information density: HIGH, MEDIUM, LOW, MINIMAL",
    )
    emotional_tone: str = Field(default="", description="Emotional tone of visuals")
    key_principle: str = Field(
        default="",
        description="The ONE key principle for visual rendering",
    )
    style_affinities: list[str] = Field(
        default_factory=list,
        description="Ordered list of preferred dataviz school keys",
    )


class TextualStyleConfig(BaseModel):
    """Tab 4: Textual rendering guidance."""

    voice: str = Field(default="", description="Voice and tone")
    structure: str = Field(default="", description="Content structure approach")
    evidence_handling: str = Field(default="", description="How to handle evidence")
    sentence_style: str = Field(default="", description="Sentence style guidance")
    what_to_emphasize: str = Field(default="", description="What to emphasize")
    what_to_avoid: str = Field(default="", description="What to avoid")
    word_count_guidance: str = Field(default="", description="Target length guidance")
    opening_style: str = Field(default="", description="How to open the text")
    key_principle: str = Field(
        default="",
        description="The ONE key principle for textual rendering",
    )


class CurationGuidance(BaseModel):
    """Tab 5: How to curate/select content for this audience."""

    curation_emphasis: str = Field(
        default="",
        description="Multi-line prompt guidance for content curation",
    )
    fidelity_constraint: str = Field(
        default="The audience framing adjusts HOW you present findings, NOT WHAT the findings are.",
        description="What must NOT change regardless of audience",
    )


class StrategistGuidance(BaseModel):
    """Tab 6: Report strategist decisions."""

    num_visualizations: str = Field(
        default="",
        description="How many visualizations to produce",
    )
    visualization_complexity: str = Field(
        default="",
        description="How complex visualizations should be",
    )
    table_purposes: list[str] = Field(
        default_factory=list,
        description="What each table should accomplish",
    )
    table_differentiation: str = Field(
        default="",
        description="How tables should differ from each other",
    )
    narrative_focus: str = Field(
        default="",
        description="What the narrative should focus on",
    )
    what_matters_most: str = Field(
        default="",
        description="The single most important thing for this audience",
    )
    what_to_avoid_in_strategy: str = Field(
        default="",
        description="Strategic mistakes to avoid for this audience",
    )


class PatternDiscoveryConfig(BaseModel):
    """Tab 7: Pattern discovery across document collections."""

    pattern_types_priority: list[str] = Field(
        default_factory=list,
        description="Pattern types in order of importance for this audience",
    )
    meta_insight_focus: str = Field(
        default="",
        description="What meta-insights matter for this audience",
    )
    what_counts_as_significant: str = Field(
        default="",
        description="What patterns count as significant",
    )
    surprise_definition: str = Field(
        default="",
        description="What would surprise this audience",
    )


class VocabularyConfig(BaseModel):
    """Tab 8: Vocabulary translations for this audience.

    Maps technical/philosophical terms to audience-appropriate language.
    Each audience stores only ITS OWN translations (not all audiences).
    """

    translations: dict[str, str] = Field(
        default_factory=dict,
        description="technical_term → audience_translation mapping",
    )
    guidance_intro: str = Field(
        default="",
        description="Intro text for vocabulary guidance section",
    )
    guidance_outro: str = Field(
        default="",
        description="Closing text for vocabulary guidance section",
    )


class AudienceDefinition(BaseModel):
    """Complete audience definition — first-class entity."""

    audience_key: str = Field(
        ...,
        description="Unique key (snake_case, e.g., 'social_movements')",
    )
    audience_name: str = Field(
        ...,
        description="Human-readable name (e.g., 'Social Movements')",
    )
    description: str = Field(
        default="",
        description="What this audience type represents",
    )
    version: int = Field(default=1, description="Schema version")
    status: AudienceStatus = Field(
        default=AudienceStatus.ACTIVE,
        description="active, deprecated, or experimental",
    )

    # Tab sections
    identity: AudienceIdentity = Field(
        default_factory=AudienceIdentity,
        description="Core identity and priorities",
    )
    engine_affinities: EngineAffinities = Field(
        default_factory=EngineAffinities,
        description="Engine affinity configuration",
    )
    visual_style: VisualStyleConfig = Field(
        default_factory=VisualStyleConfig,
        description="Visual rendering guidance",
    )
    textual_style: TextualStyleConfig = Field(
        default_factory=TextualStyleConfig,
        description="Textual rendering guidance",
    )
    curation: CurationGuidance = Field(
        default_factory=CurationGuidance,
        description="Content curation guidance",
    )
    strategist: StrategistGuidance = Field(
        default_factory=StrategistGuidance,
        description="Report strategist guidance",
    )
    pattern_discovery: PatternDiscoveryConfig = Field(
        default_factory=PatternDiscoveryConfig,
        description="Pattern discovery guidance",
    )
    vocabulary: VocabularyConfig = Field(
        default_factory=VocabularyConfig,
        description="Vocabulary translations",
    )


class AudienceSummary(BaseModel):
    """Lightweight audience info for listing endpoints."""

    audience_key: str
    audience_name: str
    description: str
    detail_level: str = ""
    style_preference: str = ""
    engine_affinity_count: int = 0
    vocabulary_term_count: int = 0
    status: str = "active"
