"""Audience registry for loading and managing audience definitions."""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import AudienceDefinition, AudienceSummary

logger = logging.getLogger(__name__)


class AudienceRegistry:
    """Registry for audience definitions.

    Loads audience definitions from JSON files in the definitions directory.
    Provides CRUD operations and audience-specific utility methods.
    """

    def __init__(self, definitions_dir: Optional[Path] = None):
        self.definitions_dir = definitions_dir or (
            Path(__file__).parent / "definitions"
        )
        self._audiences: dict[str, AudienceDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all audience definitions from JSON files."""
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            self._loaded = True
            return

        for json_file in self.definitions_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                audience = AudienceDefinition.model_validate(data)
                self._audiences[audience.audience_key] = audience
            except Exception as e:
                logger.error(f"Failed to load audience {json_file}: {e}")

        self._loaded = True

    def get(self, audience_key: str) -> Optional[AudienceDefinition]:
        """Get an audience definition by key."""
        self.load()
        return self._audiences.get(audience_key)

    def list_all(self) -> list[AudienceDefinition]:
        """List all audience definitions."""
        self.load()
        return list(self._audiences.values())

    def list_summaries(self) -> list[AudienceSummary]:
        """List all audience summaries (lightweight)."""
        self.load()
        return [
            AudienceSummary(
                audience_key=a.audience_key,
                audience_name=a.audience_name,
                description=a.description,
                detail_level=a.identity.detail_level,
                style_preference=a.visual_style.style_preference,
                engine_affinity_count=len(a.engine_affinities.high_affinity_engines),
                vocabulary_term_count=len(a.vocabulary.translations),
                status=a.status.value,
            )
            for a in self._audiences.values()
        ]

    def get_keys(self) -> list[str]:
        """Get all audience keys."""
        self.load()
        return list(self._audiences.keys())

    def count(self) -> int:
        """Get total number of audiences."""
        self.load()
        return len(self._audiences)

    def save(self, audience_key: str, definition: AudienceDefinition) -> bool:
        """Save an audience definition to JSON file.

        Creates or updates the file and in-memory cache.
        """
        self.load()

        json_file = self.definitions_dir / f"{audience_key}.json"

        try:
            self.definitions_dir.mkdir(parents=True, exist_ok=True)

            with open(json_file, "w") as f:
                json.dump(
                    definition.model_dump(mode="json"),
                    f,
                    indent=2,
                    ensure_ascii=False,
                )

            self._audiences[audience_key] = definition
            logger.info(f"Saved audience: {audience_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to save audience {audience_key}: {e}")
            return False

    def delete(self, audience_key: str) -> bool:
        """Delete an audience definition."""
        self.load()

        if audience_key not in self._audiences:
            logger.warning(f"Audience not found for deletion: {audience_key}")
            return False

        json_file = self.definitions_dir / f"{audience_key}.json"

        try:
            if json_file.exists():
                json_file.unlink()

            del self._audiences[audience_key]
            logger.info(f"Deleted audience: {audience_key}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete audience {audience_key}: {e}")
            return False

    def reload(self) -> None:
        """Force reload all definitions from disk."""
        self._loaded = False
        self._audiences.clear()
        self.load()

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def generate_guidance(self, audience_key: str) -> Optional[str]:
        """Generate a composed audience guidance block for prompt injection.

        This replaces the hardcoded _generate_audience_guidance() in StageComposer.
        """
        audience = self.get(audience_key)
        if audience is None:
            return None

        identity = audience.identity
        priorities = "\n".join(f"- {p}" for p in identity.priorities)
        deprioritize = "\n".join(f"- {d}" for d in identity.deprioritize)
        core_questions = "\n".join(f"- {q}" for q in identity.core_questions)

        return f"""## AUDIENCE: {audience.audience_name.upper()}

{audience.description}

### Priorities:
{priorities}

### De-emphasize:
{deprioritize}

### Core Questions:
{core_questions}

### Detail Level: {identity.detail_level}

### Curation Emphasis:
{audience.curation.curation_emphasis}

### Fidelity Constraint:
{audience.curation.fidelity_constraint}
"""

    def get_engine_weight(
        self,
        engine_key: str,
        engine_category: str,
        audience_key: str,
    ) -> float:
        """Calculate audience-specific weight multiplier for an engine.

        Returns a 0.4-1.6 multiplier based on category weights and
        engine-specific affinities.
        """
        audience = self.get(audience_key)
        if audience is None:
            return 1.0

        affinities = audience.engine_affinities

        # Start with category weight
        base_weight = affinities.category_weights.get(engine_category.lower(), 1.0)

        # Boost for high-affinity engines
        if engine_key in affinities.high_affinity_engines:
            base_weight *= 1.2

        # Penalty for low-affinity engines
        if engine_key in affinities.low_affinity_engines:
            base_weight *= 0.7

        # Clamp
        return max(0.4, min(1.6, base_weight))

    def translate_term(self, term: str, audience_key: str) -> str:
        """Translate a technical term for a specific audience.

        Returns the audience-specific translation, or the original term
        if no translation exists.
        """
        audience = self.get(audience_key)
        if audience is None:
            return term

        return audience.vocabulary.translations.get(term, term)

    def get_vocabulary_guidance(self, audience_key: str) -> Optional[str]:
        """Generate vocabulary guidance block for prompt injection."""
        audience = self.get(audience_key)
        if audience is None:
            return None

        vocab = audience.vocabulary
        if not vocab.translations:
            return None

        # Build translation table
        lines = []
        for term, translation in sorted(vocab.translations.items()):
            if term != translation:
                lines.append(f"- \"{term}\" → \"{translation}\"")

        if not lines:
            return vocab.guidance_intro if vocab.guidance_intro else None

        translations_block = "\n".join(lines[:50])  # Cap at 50 for prompt size
        if len(lines) > 50:
            translations_block += f"\n... and {len(lines) - 50} more translations"

        parts = []
        if vocab.guidance_intro:
            parts.append(vocab.guidance_intro)
        parts.append(f"### Key Vocabulary Translations:\n{translations_block}")
        if vocab.guidance_outro:
            parts.append(vocab.guidance_outro)

        return "\n\n".join(parts)


# Global registry instance
_registry: Optional[AudienceRegistry] = None


def get_audience_registry() -> AudienceRegistry:
    """Get the global audience registry instance."""
    global _registry
    if _registry is None:
        _registry = AudienceRegistry()
    return _registry
