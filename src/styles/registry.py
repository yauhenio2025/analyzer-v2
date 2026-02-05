"""
Style Registry - loads and serves style definitions and affinities.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .schemas import (
    StyleSchool,
    StyleGuide,
    StyleGuideSummary,
    StyleAffinity,
    AffinitySet,
    EngineStyleMapping,
)

logger = logging.getLogger(__name__)

DEFINITIONS_DIR = Path(__file__).parent / "definitions"


class StyleRegistry:
    """Registry for visual style definitions and affinity mappings."""

    def __init__(self, definitions_dir: Optional[Path] = None):
        """Initialize the registry."""
        self.definitions_dir = definitions_dir or DEFINITIONS_DIR
        self._styles: dict[StyleSchool, StyleGuide] = {}
        self._engine_affinities: dict[str, list[StyleSchool]] = {}
        self._format_affinities: dict[str, list[StyleSchool]] = {}
        self._audience_affinities: dict[str, list[StyleSchool]] = {}
        self._load_all()

    def _load_all(self):
        """Load all style definitions and affinities."""
        # Load individual style definitions
        styles_dir = self.definitions_dir / "schools"
        if styles_dir.exists():
            for json_file in styles_dir.glob("*.json"):
                try:
                    with open(json_file, "r") as f:
                        data = json.load(f)
                    style = StyleGuide(**data)
                    self._styles[style.key] = style
                    logger.info(f"Loaded style: {style.key.value}")
                except Exception as e:
                    logger.error(f"Failed to load {json_file}: {e}")

        # Load affinity mappings
        affinities_file = self.definitions_dir / "affinities.json"
        if affinities_file.exists():
            try:
                with open(affinities_file, "r") as f:
                    data = json.load(f)

                # Parse engine affinities (skip keys starting with _)
                self._engine_affinities = {
                    k: [StyleSchool(s) for s in v]
                    for k, v in data.get("engine", {}).items()
                    if not k.startswith("_") and isinstance(v, list)
                }
                # Parse format affinities
                self._format_affinities = {
                    k: [StyleSchool(s) for s in v]
                    for k, v in data.get("format", {}).items()
                    if not k.startswith("_") and isinstance(v, list)
                }
                # Parse audience affinities
                self._audience_affinities = {
                    k: [StyleSchool(s) for s in v]
                    for k, v in data.get("audience", {}).items()
                    if not k.startswith("_") and isinstance(v, list)
                }
                logger.info(
                    f"Loaded affinities: {len(self._engine_affinities)} engines, "
                    f"{len(self._format_affinities)} formats, {len(self._audience_affinities)} audiences"
                )
            except Exception as e:
                logger.error(f"Failed to load affinities: {e}")

    def reload(self):
        """Reload all definitions from disk."""
        self._styles.clear()
        self._engine_affinities.clear()
        self._format_affinities.clear()
        self._audience_affinities.clear()
        self._load_all()

    # Style Guide Methods
    def list_styles(self) -> list[StyleGuideSummary]:
        """List all available style schools."""
        summaries = []
        for style in self._styles.values():
            summaries.append(StyleGuideSummary(
                key=style.key,
                name=style.name,
                philosophy_summary=style.philosophy[:200].strip() + "...",
                color_preview={
                    "primary": style.color_palette.primary,
                    "accent": style.color_palette.accent,
                    "background": style.color_palette.background,
                },
                best_for_summary=style.best_for[:3],
            ))
        return summaries

    def get_style(self, key: StyleSchool) -> Optional[StyleGuide]:
        """Get a specific style guide."""
        return self._styles.get(key)

    # Affinity Methods
    def get_engine_affinities(self) -> AffinitySet:
        """Get all engine-to-style affinities."""
        return AffinitySet(
            category="engine",
            affinities=self._engine_affinities,
            default=self._engine_affinities.get("_default", [StyleSchool.NYT_COX, StyleSchool.TUFTE]),
        )

    def get_format_affinities(self) -> AffinitySet:
        """Get all format-to-style affinities."""
        return AffinitySet(
            category="format",
            affinities=self._format_affinities,
            default=self._format_affinities.get("_default", [StyleSchool.NYT_COX, StyleSchool.TUFTE]),
        )

    def get_audience_affinities(self) -> AffinitySet:
        """Get all audience-to-style affinities."""
        return AffinitySet(
            category="audience",
            affinities=self._audience_affinities,
            default=self._audience_affinities.get("_default", [StyleSchool.NYT_COX, StyleSchool.TUFTE]),
        )

    def get_styles_for_engine(self, engine_key: str) -> list[StyleSchool]:
        """Get preferred styles for an engine."""
        return self._engine_affinities.get(
            engine_key,
            self._engine_affinities.get("_default", [StyleSchool.NYT_COX, StyleSchool.TUFTE])
        )

    def get_styles_for_format(self, format_key: str) -> list[StyleSchool]:
        """Get preferred styles for a visual format."""
        return self._format_affinities.get(
            format_key,
            self._format_affinities.get("_default", [StyleSchool.NYT_COX, StyleSchool.TUFTE])
        )

    def get_styles_for_audience(self, audience: str) -> list[StyleSchool]:
        """Get preferred styles for an audience type."""
        return self._audience_affinities.get(
            audience,
            self._audience_affinities.get("_default", [StyleSchool.NYT_COX, StyleSchool.TUFTE])
        )

    # Combined Engine Mapping (for UI)
    def get_engine_style_mapping(self, engine_key: str, engine_name: str, has_semantic_intent: bool = False, recommended_visual_patterns: list[str] = None) -> EngineStyleMapping:
        """Get complete style mapping for an engine."""
        return EngineStyleMapping(
            engine_key=engine_key,
            engine_name=engine_name,
            style_affinities=self.get_styles_for_engine(engine_key),
            has_semantic_intent=has_semantic_intent,
            recommended_visual_patterns=recommended_visual_patterns or [],
        )

    # Stats
    def get_stats(self) -> dict:
        """Get registry statistics."""
        return {
            "styles_loaded": len(self._styles),
            "engine_affinities": len(self._engine_affinities),
            "format_affinities": len(self._format_affinities),
            "audience_affinities": len(self._audience_affinities),
        }


# Global registry instance
_registry: Optional[StyleRegistry] = None


def get_style_registry() -> StyleRegistry:
    """Get the global style registry instance."""
    global _registry
    if _registry is None:
        _registry = StyleRegistry()
    return _registry
