"""Registry for prompt-context providers."""

import json
import logging
from pathlib import Path
from typing import Optional

from src.taxonomies.registry import get_taxonomy_registry

from .schemas import PromptContextProviderDefinition

logger = logging.getLogger(__name__)


class PromptContextRegistry:
    """Loads prompt-context providers from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._providers: dict[str, PromptContextProviderDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning("Prompt context definitions directory not found: %s", self.definitions_dir)
            self._loaded = True
            return

        for json_file in sorted(self.definitions_dir.glob("*.json")):
            try:
                with open(json_file, "r") as handle:
                    data = json.load(handle)
                provider = PromptContextProviderDefinition.model_validate(data)
                self._providers[provider.provider_key] = provider
                logger.debug("Loaded prompt context provider: %s", provider.provider_key)
            except Exception as exc:
                logger.error("Failed to load prompt context provider from %s: %s", json_file, exc)

        self._loaded = True
        logger.info("Loaded %d prompt context providers", len(self._providers))

    def get(self, provider_key: str) -> Optional[PromptContextProviderDefinition]:
        self.load()
        return self._providers.get(provider_key)

    def count(self) -> int:
        self.load()
        return len(self._providers)

    def render(self, provider_key: str) -> Optional[str]:
        self.load()
        provider = self._providers.get(provider_key)
        if provider is None or provider.status != "active":
            return None

        if provider.source_type == "static_text":
            return provider.static_value or ""

        if provider.source_type in {"taxonomy_enum", "taxonomy_guidance"}:
            if not provider.taxonomy_key:
                return None
            taxonomy = get_taxonomy_registry().get(provider.taxonomy_key)
            if taxonomy is None:
                return None
            if provider.source_type == "taxonomy_enum":
                return ", ".join(taxonomy.value_keys())
            return taxonomy.render_guidance()

        logger.warning("Unknown prompt context provider source_type=%s for %s", provider.source_type, provider_key)
        return None


_registry: Optional[PromptContextRegistry] = None


def get_prompt_context_registry() -> PromptContextRegistry:
    global _registry
    if _registry is None:
        _registry = PromptContextRegistry()
        _registry.load()
    return _registry
