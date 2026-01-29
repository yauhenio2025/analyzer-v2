"""Pydantic schemas for stage prompt composition.

MIGRATION NOTES (2026-01-29):
- This replaces the old extraction_prompt, curation_prompt, concretization_prompt
  fields in EngineDefinition
- Engines now provide stage_context with injection data for generic templates
- Shared frameworks (Brandomian, Dennett) are loaded separately and injected

BREAKING CHANGES:
- EngineDefinition no longer has extraction_prompt, curation_prompt, concretization_prompt
- API endpoints /v1/engines/{key}/*-prompt now compose prompts at runtime
- Old engine JSON files need migration via scripts/migrate_engines_to_stages.py
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AudienceVocabulary(BaseModel):
    """Vocabulary translations for different audiences.

    Each audience type maps Jargon -> Plain language.
    """
    researcher: dict[str, str] = Field(
        default_factory=dict,
        description="Technical terms for researchers (can use full jargon)",
    )
    analyst: dict[str, str] = Field(
        default_factory=dict,
        description="Balanced terms for analysts (some jargon, explained)",
    )
    executive: dict[str, str] = Field(
        default_factory=dict,
        description="Plain language for executives (no jargon)",
    )
    activist: dict[str, str] = Field(
        default_factory=dict,
        description="Action-oriented language for activists (no jargon, punchy)",
    )


class ExtractionContext(BaseModel):
    """Engine-specific context for extraction stage template.

    This replaces the old extraction_prompt field. The template will
    compose the framework primer + these engine-specific details.
    """
    # What this engine analyzes
    analysis_type: str = Field(
        ...,
        description="What this engine analyzes (e.g., 'inferential commitments', 'argument structure')",
    )
    analysis_type_plural: str = Field(
        ...,
        description="Plural form (e.g., 'inferential commitments', 'argument structures')",
    )

    # The core analytical question
    core_question: str = Field(
        ...,
        description="The question this analysis answers (e.g., 'What are you really signing up for?')",
    )

    # Extraction steps - the numbered task list
    extraction_steps: list[str] = Field(
        default_factory=list,
        description="Numbered steps for the extraction task (engine-specific)",
    )

    # Schema field descriptions
    key_fields: dict[str, str] = Field(
        default_factory=dict,
        description="Key output fields and their descriptions (for schema guidance)",
    )

    # ID field naming convention
    id_field: str = Field(
        default="item_id",
        description="The ID field name used in this engine (e.g., 'commitment_id', 'arg_id')",
    )

    # What relationships to look for
    key_relationships: list[str] = Field(
        default_factory=list,
        description="Relationship types to identify (e.g., ['entails', 'conflicts_with', 'supports'])",
    )

    # Additional engine-specific notes
    special_instructions: Optional[str] = Field(
        default=None,
        description="Any additional engine-specific extraction instructions",
    )


class CurationContext(BaseModel):
    """Engine-specific context for curation stage template.

    This replaces the old curation_prompt field.
    """
    # What's being consolidated
    item_type: str = Field(
        ...,
        description="What items are being curated (e.g., 'inferential commitments')",
    )
    item_type_plural: str = Field(
        ...,
        description="Plural form",
    )

    # Consolidation rules - how to merge/dedupe
    consolidation_rules: list[str] = Field(
        default_factory=list,
        description="Rules for merging/deduplicating items across documents",
    )

    # What cross-document patterns to look for
    cross_doc_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns to identify across documents (e.g., 'shared commitments', 'contested claims')",
    )

    # Synthesis outputs - what collections to build
    synthesis_outputs: list[str] = Field(
        default_factory=list,
        description="Named outputs to produce (e.g., 'author_commitment_map', 'fault_line_map')",
    )

    # Additional instructions
    special_instructions: Optional[str] = Field(
        default=None,
        description="Any additional engine-specific curation instructions",
    )


class ConcretizationContext(BaseModel):
    """Engine-specific context for concretization stage template.

    This replaces the old concretization_prompt field.
    """
    # ID transformation examples
    id_examples: list[dict[str, str]] = Field(
        default_factory=list,
        description="Examples of ID -> concrete name transformations",
        json_schema_extra={
            "example": [
                {"from": "C1", "to": "The 'Humans Stay in Charge' commitment"},
                {"from": "X1", "to": "The 'Can't Have Both' choice: automation vs. accountability"},
            ]
        },
    )

    # What makes good concrete names for this engine
    naming_guidance: str = Field(
        default="",
        description="Guidance for creating vivid, concrete names",
    )

    # Table types this engine commonly uses
    recommended_table_types: list[str] = Field(
        default_factory=list,
        description="Table types recommended for this engine's output",
    )

    # Visual patterns for graphs
    recommended_visual_patterns: list[str] = Field(
        default_factory=list,
        description="Visual patterns for network/diagram output",
    )


class StageContext(BaseModel):
    """Complete stage context for an engine.

    This is the NEW field that replaces extraction_prompt, curation_prompt,
    and concretization_prompt in EngineDefinition.
    """
    # Framework reference (optional) - loads shared primer
    framework_key: Optional[str] = Field(
        default=None,
        description="Key of shared framework to inject (e.g., 'brandomian', 'dennett', 'toulmin')",
    )

    # Additional framework keys for layered primers
    additional_frameworks: list[str] = Field(
        default_factory=list,
        description="Additional framework primers to layer on top",
    )

    # Stage-specific contexts
    extraction: ExtractionContext = Field(
        ...,
        description="Context for extraction stage template",
    )
    curation: CurationContext = Field(
        ...,
        description="Context for curation stage template",
    )
    concretization: ConcretizationContext = Field(
        ...,
        description="Context for concretization stage template",
    )

    # Audience vocabulary for all stages
    audience_vocabulary: AudienceVocabulary = Field(
        default_factory=AudienceVocabulary,
        description="Vocabulary translations for different audience types",
    )

    # Skip concretization for simple engines
    skip_concretization: bool = Field(
        default=False,
        description="Whether to skip concretization stage for this engine",
    )


class Framework(BaseModel):
    """A shared methodological framework that can be injected into prompts.

    Examples: Brandomian inferentialism, Dennett's critical tools, Toulmin model.
    These are loaded from frameworks/ directory and composed into prompts.
    """
    key: str = Field(
        ...,
        description="Unique identifier for this framework (e.g., 'brandomian')",
    )
    name: str = Field(
        ...,
        description="Human-readable name (e.g., 'Brandomian Inferentialism')",
    )
    description: str = Field(
        ...,
        description="Brief description of the framework",
    )

    # The primer content - the big methodological text
    primer: str = Field(
        ...,
        description="The full framework primer text (can be very long)",
    )

    # Audience-specific vocabulary for this framework
    vocabulary: AudienceVocabulary = Field(
        default_factory=AudienceVocabulary,
        description="Framework-specific vocabulary translations",
    )

    # Compatible paradigms
    paradigm_keys: list[str] = Field(
        default_factory=list,
        description="Paradigm keys this framework is associated with",
    )


class ComposedPrompt(BaseModel):
    """A fully composed prompt ready for use.

    This is what the API returns after composing template + context + framework.
    """
    engine_key: str
    stage: str  # "extraction", "curation", "concretization"
    prompt: str
    audience: str = "analyst"  # default audience

    # Metadata about composition
    framework_used: Optional[str] = None
    template_version: str = "1.0"
    composed_at: str = Field(default="", description="ISO timestamp of composition")
