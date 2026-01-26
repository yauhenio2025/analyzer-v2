"""Paradigm registry - loads and serves paradigm definitions from JSON files."""

import json
import logging
from pathlib import Path
from typing import Optional

from src.paradigms.schemas import (
    ParadigmDefinition,
    ParadigmSummary,
)

logger = logging.getLogger(__name__)


class ParadigmRegistry:
    """Registry of paradigm definitions loaded from JSON files.

    Paradigms are loaded from src/paradigms/instances/*.json at startup.
    Each JSON file should contain one ParadigmDefinition.
    """

    def __init__(self, instances_dir: Optional[Path] = None):
        """Initialize registry with optional custom instances directory."""
        if instances_dir is None:
            instances_dir = Path(__file__).parent / "instances"
        self.instances_dir = instances_dir
        self._paradigms: dict[str, ParadigmDefinition] = {}
        self._loaded = False

    def load(self) -> None:
        """Load all paradigm definitions from JSON files."""
        if self._loaded:
            return

        if not self.instances_dir.exists():
            logger.warning(f"Instances directory not found: {self.instances_dir}")
            self._loaded = True
            return

        for json_file in self.instances_dir.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)
                paradigm = ParadigmDefinition.model_validate(data)
                self._paradigms[paradigm.paradigm_key] = paradigm
                logger.debug(f"Loaded paradigm: {paradigm.paradigm_key}")
            except Exception as e:
                logger.error(f"Failed to load paradigm from {json_file}: {e}")

        self._loaded = True
        logger.info(f"Loaded {len(self._paradigms)} paradigms")

    def get(self, paradigm_key: str) -> Optional[ParadigmDefinition]:
        """Get paradigm definition by key."""
        self.load()
        return self._paradigms.get(paradigm_key)

    def get_validated(self, paradigm_key: str) -> ParadigmDefinition:
        """Get paradigm definition by key, raising if not found."""
        paradigm = self.get(paradigm_key)
        if paradigm is None:
            available = list(self._paradigms.keys())
            raise ValueError(
                f"Paradigm not found: {paradigm_key}. Available: {available}"
            )
        return paradigm

    def list_all(self) -> list[ParadigmDefinition]:
        """List all paradigm definitions."""
        self.load()
        return list(self._paradigms.values())

    def list_summaries(self) -> list[ParadigmSummary]:
        """List lightweight paradigm summaries."""
        self.load()
        return [
            ParadigmSummary(
                paradigm_key=p.paradigm_key,
                paradigm_name=p.paradigm_name,
                description=p.description,
                version=p.version,
                status=p.status,
                guiding_thinkers=p.guiding_thinkers,
                active_traits=p.active_traits,
            )
            for p in self._paradigms.values()
        ]

    def list_keys(self) -> list[str]:
        """List all paradigm keys."""
        self.load()
        return list(self._paradigms.keys())

    def list_active(self) -> list[ParadigmDefinition]:
        """List only active paradigms."""
        self.load()
        return [p for p in self._paradigms.values() if p.status == "active"]

    def count(self) -> int:
        """Get total number of paradigms."""
        self.load()
        return len(self._paradigms)

    def reload(self) -> None:
        """Force reload all definitions."""
        self._loaded = False
        self._paradigms.clear()
        self.load()

    def generate_primer(self, paradigm_key: str) -> str:
        """Generate an LLM-ready primer text for a paradigm.

        The primer synthesizes all layers into a coherent explanation
        that can be injected into analysis prompts.
        """
        paradigm = self.get_validated(paradigm_key)

        sections = []

        # Header
        sections.append(f"# {paradigm.paradigm_name} Paradigm Primer")
        sections.append(f"\n*Guiding Thinkers: {paradigm.guiding_thinkers}*")
        sections.append(f"\n{paradigm.description}\n")

        # Foundational Layer
        sections.append("## Foundational Assumptions")
        for assumption in paradigm.foundational.assumptions:
            sections.append(f"- {assumption}")

        if paradigm.foundational.core_tensions:
            sections.append("\n## Core Tensions")
            for tension in paradigm.foundational.core_tensions:
                sections.append(f"- {tension}")

        # Structural Layer
        sections.append("\n## Structural Ontology")
        sections.append("\n### Primary Entities")
        for entity in paradigm.structural.primary_entities:
            sections.append(f"- {entity}")

        if paradigm.structural.relations:
            sections.append("\n### Relations")
            for relation in paradigm.structural.relations:
                sections.append(f"- {relation}")

        # Dynamic Layer
        sections.append("\n## Dynamic Understanding")
        sections.append("\n### Change Mechanisms")
        for mechanism in paradigm.dynamic.change_mechanisms:
            sections.append(f"- {mechanism}")

        # Explanatory Layer
        sections.append("\n## Explanatory Toolkit")
        sections.append("\n### Key Concepts")
        for concept in paradigm.explanatory.key_concepts:
            sections.append(f"- {concept}")

        if paradigm.explanatory.analytical_methods:
            sections.append("\n### Analytical Methods")
            for method in paradigm.explanatory.analytical_methods:
                sections.append(f"- {method}")

        # Active Traits
        if paradigm.trait_definitions:
            sections.append("\n## Analytical Emphases")
            for trait in paradigm.trait_definitions:
                if trait.trait_name in paradigm.active_traits:
                    sections.append(f"\n### {trait.trait_name}")
                    sections.append(f"*{trait.trait_description}*")
                    for item in trait.trait_items:
                        sections.append(f"- {item}")

        return "\n".join(sections)


# Global registry instance
_registry: Optional[ParadigmRegistry] = None


def get_paradigm_registry() -> ParadigmRegistry:
    """Get the global paradigm registry instance."""
    global _registry
    if _registry is None:
        _registry = ParadigmRegistry()
        _registry.load()
    return _registry
