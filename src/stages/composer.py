"""Stage prompt composer using Jinja2 templates.

MIGRATION NOTES (2026-01-29):
- Composes generic templates with engine-specific context
- Injects shared framework primers when referenced
- Handles audience-specific vocabulary transformations
"""

from datetime import datetime, timezone
from typing import Any, Optional

from jinja2 import Environment, BaseLoader, TemplateError

from .schemas import (
    StageContext,
    Framework,
    ComposedPrompt,
    AudienceVocabulary,
)
from .registry import StageRegistry, get_stage_registry


class StageComposer:
    """Composes stage prompts from templates and engine context.

    Usage:
        composer = StageComposer()
        prompt = composer.compose(
            stage="extraction",
            engine_key="inferential_commitment_mapper_advanced",
            stage_context=engine.stage_context,
            audience="analyst"
        )
    """

    def __init__(self, registry: Optional[StageRegistry] = None):
        """Initialize the composer.

        Args:
            registry: StageRegistry instance (default: global singleton)
        """
        self.registry = registry or get_stage_registry()

        # Configure Jinja2 environment
        self.env = Environment(
            loader=BaseLoader(),
            autoescape=False,  # We're generating markdown, not HTML
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["join_lines"] = lambda items: "\n".join(f"- {item}" for item in items)
        self.env.filters["numbered"] = lambda items: "\n".join(f"{i+1}. {item}" for i, item in items)

    def compose(
        self,
        stage: str,
        engine_key: str,
        stage_context: StageContext,
        audience: str = "analyst",
        canonical_schema: Optional[dict[str, Any]] = None,
    ) -> ComposedPrompt:
        """Compose a stage prompt from template and context.

        Args:
            stage: Stage name ("extraction", "curation", "concretization")
            engine_key: Engine key for metadata
            stage_context: Engine's stage context
            audience: Target audience for vocabulary
            canonical_schema: Engine's schema (for schema guidance injection)

        Returns:
            ComposedPrompt with fully rendered prompt text

        Raises:
            ValueError: If template or required context is missing
        """
        # Check for skip
        if stage == "concretization" and stage_context.skip_concretization:
            return ComposedPrompt(
                engine_key=engine_key,
                stage=stage,
                prompt="",
                audience=audience,
                template_version="1.0",
                composed_at=datetime.now(timezone.utc).isoformat(),
            )

        # Get template
        template_str = self.registry.get_template(stage)
        if not template_str:
            raise ValueError(f"Template not found for stage: {stage}")

        # Build context dict for Jinja2
        context = self._build_context(
            stage=stage,
            engine_key=engine_key,
            stage_context=stage_context,
            audience=audience,
            canonical_schema=canonical_schema,
        )

        # Render template
        try:
            template = self.env.from_string(template_str)
            rendered = template.render(**context)
        except TemplateError as e:
            raise ValueError(f"Template rendering error for {stage}: {e}")

        return ComposedPrompt(
            engine_key=engine_key,
            stage=stage,
            prompt=rendered.strip(),
            audience=audience,
            framework_used=stage_context.framework_key,
            template_version="1.0",
            composed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _build_context(
        self,
        stage: str,
        engine_key: str,
        stage_context: StageContext,
        audience: str,
        canonical_schema: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build the context dictionary for Jinja2 rendering.

        Args:
            stage: Stage name
            engine_key: Engine key
            stage_context: Engine's stage context
            audience: Target audience
            canonical_schema: Engine's schema

        Returns:
            Dictionary of context values for template
        """
        context: dict[str, Any] = {
            "engine_key": engine_key,
            "audience": audience,
        }

        # Add stage-specific context
        if stage == "extraction":
            context["extraction"] = stage_context.extraction.model_dump()
        elif stage == "curation":
            context["curation"] = stage_context.curation.model_dump()
        elif stage == "concretization":
            context["concretization"] = stage_context.concretization.model_dump()

        # Add schema if provided
        if canonical_schema:
            context["schema"] = canonical_schema
            context["schema_json"] = self._format_schema_for_prompt(canonical_schema)

        # Load and inject framework primer(s)
        framework_primers = []

        if stage_context.framework_key:
            primer = self.registry.get_framework_primer(stage_context.framework_key)
            if primer:
                framework_primers.append(primer)
                context["framework_key"] = stage_context.framework_key

        for additional_key in stage_context.additional_frameworks:
            primer = self.registry.get_framework_primer(additional_key)
            if primer:
                framework_primers.append(primer)

        context["framework_primer"] = "\n\n---\n\n".join(framework_primers) if framework_primers else ""
        context["has_framework"] = bool(framework_primers)

        # Add audience vocabulary
        context["vocabulary"] = self._get_audience_vocabulary(
            stage_context.audience_vocabulary,
            audience,
        )

        # Load framework vocabulary if available
        if stage_context.framework_key:
            framework = self.registry.get_framework(stage_context.framework_key)
            if framework and framework.vocabulary:
                framework_vocab = self._get_audience_vocabulary(framework.vocabulary, audience)
                # Merge framework vocab (framework takes precedence)
                context["vocabulary"] = {**context["vocabulary"], **framework_vocab}

        # Add audience guidance block
        context["audience_guidance"] = self._generate_audience_guidance(
            stage_context.audience_vocabulary,
            audience,
        )

        return context

    def _get_audience_vocabulary(
        self,
        vocab: AudienceVocabulary,
        audience: str,
    ) -> dict[str, str]:
        """Get vocabulary dict for specific audience.

        Args:
            vocab: AudienceVocabulary object
            audience: Target audience name

        Returns:
            Dictionary of term -> translation for this audience
        """
        audience_map = {
            "researcher": vocab.researcher,
            "analyst": vocab.analyst,
            "executive": vocab.executive,
            "activist": vocab.activist,
        }
        return audience_map.get(audience, vocab.analyst)

    def _generate_audience_guidance(
        self,
        vocab: AudienceVocabulary,
        audience: str,
    ) -> str:
        """Generate audience-specific language guidance block.

        Args:
            vocab: AudienceVocabulary object
            audience: Target audience name

        Returns:
            Markdown block with audience guidance
        """
        if audience == "researcher":
            return """
## AUDIENCE: RESEARCHER

Use full technical vocabulary. Researchers want precision and rigor.
Include proper terms with brief parenthetical definitions where helpful.
"""
        elif audience == "analyst":
            return """
## AUDIENCE: ANALYST

Use balanced language - technical terms are OK if defined on first use.
Lean toward clarity over precision when they conflict.
The goal is to be understood by smart generalists.
"""
        elif audience == "executive":
            return """
## AUDIENCE: EXECUTIVE

Use plain language with zero jargon. Focus on:
- Strategic implications and decision points
- What this means for the business/organization
- Concrete action items and risks

Every concept must be immediately understandable without specialized knowledge.
"""
        elif audience == "activist":
            return """
## AUDIENCE: ACTIVIST / SOCIAL MOVEMENTS

Use action-oriented, punchy language with zero academic jargon. Focus on:
- Power dynamics and who benefits
- What can be challenged and where to push
- Concrete contradictions to expose

Frame as revelation and strategic intel, not academic analysis.
"""
        else:
            return f"## AUDIENCE: {audience.upper()}\n\nAdapt language appropriately for this audience."

    def _format_schema_for_prompt(self, schema: dict[str, Any]) -> str:
        """Format canonical schema as readable text for prompt injection.

        Args:
            schema: Canonical schema dictionary

        Returns:
            Human-readable schema description
        """
        lines = ["## OUTPUT SCHEMA", ""]

        for field, spec in schema.items():
            if isinstance(spec, list) and spec:
                # Array field
                lines.append(f"### {field}")
                if isinstance(spec[0], dict):
                    for key, desc in spec[0].items():
                        lines.append(f"- **{key}**: {desc}")
                lines.append("")
            elif isinstance(spec, dict):
                # Object field
                lines.append(f"### {field}")
                for key, desc in spec.items():
                    if isinstance(desc, dict):
                        lines.append(f"- **{key}**:")
                        for k, v in desc.items():
                            lines.append(f"  - {k}: {v}")
                    else:
                        lines.append(f"- **{key}**: {desc}")
                lines.append("")

        return "\n".join(lines)

    def compose_all_stages(
        self,
        engine_key: str,
        stage_context: StageContext,
        audience: str = "analyst",
        canonical_schema: Optional[dict[str, Any]] = None,
    ) -> dict[str, ComposedPrompt]:
        """Compose all stage prompts for an engine.

        Args:
            engine_key: Engine key
            stage_context: Engine's stage context
            audience: Target audience
            canonical_schema: Engine's schema

        Returns:
            Dictionary mapping stage name to ComposedPrompt
        """
        stages = ["extraction", "curation", "concretization"]
        return {
            stage: self.compose(
                stage=stage,
                engine_key=engine_key,
                stage_context=stage_context,
                audience=audience,
                canonical_schema=canonical_schema if stage == "extraction" else None,
            )
            for stage in stages
        }


# Convenience function
def compose_prompt(
    stage: str,
    engine_key: str,
    stage_context: StageContext,
    audience: str = "analyst",
    canonical_schema: Optional[dict[str, Any]] = None,
) -> ComposedPrompt:
    """Compose a stage prompt (convenience function).

    Args:
        stage: Stage name ("extraction", "curation", "concretization")
        engine_key: Engine key
        stage_context: Engine's stage context
        audience: Target audience
        canonical_schema: Engine's schema (for extraction stage)

    Returns:
        ComposedPrompt with fully rendered prompt
    """
    composer = StageComposer()
    return composer.compose(
        stage=stage,
        engine_key=engine_key,
        stage_context=stage_context,
        audience=audience,
        canonical_schema=canonical_schema,
    )
