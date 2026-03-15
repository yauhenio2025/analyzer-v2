"""Registry for classification taxonomies."""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import TaxonomyDefinition

logger = logging.getLogger(__name__)


class TaxonomyRegistry:
    """Loads taxonomy definitions from JSON files."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        if definitions_dir is None:
            definitions_dir = Path(__file__).parent / "definitions"
        self.definitions_dir = definitions_dir
        self._taxonomies: dict[str, TaxonomyDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        if not self.definitions_dir.exists():
            logger.warning("Taxonomy definitions directory not found: %s", self.definitions_dir)
            self._loaded = True
            return

        for json_file in sorted(self.definitions_dir.glob("*.json")):
            try:
                with open(json_file, "r") as handle:
                    data = json.load(handle)
                taxonomy = TaxonomyDefinition.model_validate(data)
                self._taxonomies[taxonomy.taxonomy_key] = taxonomy
                logger.debug("Loaded taxonomy: %s", taxonomy.taxonomy_key)
            except Exception as exc:
                logger.error("Failed to load taxonomy from %s: %s", json_file, exc)

        self._loaded = True
        logger.info("Loaded %d taxonomies", len(self._taxonomies))

    def get(self, taxonomy_key: str) -> Optional[TaxonomyDefinition]:
        self.load()
        return self._taxonomies.get(taxonomy_key)

    def list_all(self) -> list[TaxonomyDefinition]:
        self.load()
        return list(self._taxonomies.values())

    def count(self) -> int:
        self.load()
        return len(self._taxonomies)


_registry: Optional[TaxonomyRegistry] = None


def get_taxonomy_registry() -> TaxonomyRegistry:
    global _registry
    if _registry is None:
        _registry = TaxonomyRegistry()
        _registry.load()
    return _registry
