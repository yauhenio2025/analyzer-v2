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
    StyleRecommendation,
    RecommendationReasoning,
    StyleRecommendContextSummary,
    StyleRecommendResponse,
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
            default=self._engine_affinities.get("_default", [StyleSchool.EXPLANATORY_NARRATIVE, StyleSchool.MINIMALIST_PRECISION]),
        )

    def get_format_affinities(self) -> AffinitySet:
        """Get all format-to-style affinities."""
        return AffinitySet(
            category="format",
            affinities=self._format_affinities,
            default=self._format_affinities.get("_default", [StyleSchool.EXPLANATORY_NARRATIVE, StyleSchool.MINIMALIST_PRECISION]),
        )

    def get_audience_affinities(self) -> AffinitySet:
        """Get all audience-to-style affinities."""
        return AffinitySet(
            category="audience",
            affinities=self._audience_affinities,
            default=self._audience_affinities.get("_default", [StyleSchool.EXPLANATORY_NARRATIVE, StyleSchool.MINIMALIST_PRECISION]),
        )

    def get_styles_for_engine(self, engine_key: str) -> list[StyleSchool]:
        """Get preferred styles for an engine."""
        return self._engine_affinities.get(
            engine_key,
            self._engine_affinities.get("_default", [StyleSchool.EXPLANATORY_NARRATIVE, StyleSchool.MINIMALIST_PRECISION])
        )

    def get_styles_for_format(self, format_key: str) -> list[StyleSchool]:
        """Get preferred styles for a visual format."""
        return self._format_affinities.get(
            format_key,
            self._format_affinities.get("_default", [StyleSchool.EXPLANATORY_NARRATIVE, StyleSchool.MINIMALIST_PRECISION])
        )

    def get_styles_for_audience(self, audience: str) -> list[StyleSchool]:
        """Get preferred styles for an audience type."""
        return self._audience_affinities.get(
            audience,
            self._audience_affinities.get("_default", [StyleSchool.EXPLANATORY_NARRATIVE, StyleSchool.MINIMALIST_PRECISION])
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

    # Style Recommendation
    RENDERER_FORMAT_MAP: dict[str, list[str]] = {
        "table":        ["matrix_heatmap", "ach_matrix"],
        "stat_summary": ["indicator_dashboard", "bar_chart"],
    }

    def recommend_styles(
        self,
        engine_keys: list[str] | None = None,
        renderer_types: list[str] | None = None,
        audience: str | None = None,
        limit: int = 3,
    ) -> StyleRecommendResponse:
        """Rank style schools by combined affinity signals."""
        # Deduplicate inputs preserving order
        engines = list(dict.fromkeys(engine_keys or []))
        renderers = list(dict.fromkeys(renderer_types or []))

        all_schools = list(StyleSchool)

        # Track context summary
        engines_with_explicit = sum(1 for k in engines if k in self._engine_affinities)
        engines_using_default = len(engines) - engines_with_explicit

        # Map renderer types to format keys
        mapped_formats: list[str] = []
        renderer_types_mapped = 0
        for rt in renderers:
            fmt_keys = self.RENDERER_FORMAT_MAP.get(rt)
            if fmt_keys:
                renderer_types_mapped += 1
                mapped_formats.extend(fmt_keys)
        mapped_formats = list(dict.fromkeys(mapped_formats))  # deduplicate

        formats_with_explicit = sum(1 for f in mapped_formats if f in self._format_affinities)
        formats_using_default = len(mapped_formats) - formats_with_explicit

        audience_used_default = False
        if audience is not None and audience not in self._audience_affinities:
            audience_used_default = True

        # Count effective signals
        total_signals = len(engines) + len(mapped_formats) + (1 if audience is not None else 0)
        max_possible = 2.0 * total_signals if total_signals > 0 else 1.0

        # Score each school
        school_data: dict[StyleSchool, dict] = {}
        for school in all_schools:
            raw_score = 0.0
            primary_count = 0
            engine_matches: dict[str, int] = {}
            format_matches: dict[str, int] = {}
            audience_match_pos = -1
            matched_signals = 0

            # Engine signals
            for ek in engines:
                styles = self.get_styles_for_engine(ek)
                if school in styles:
                    pos = styles.index(school)
                    engine_matches[ek] = pos
                    points = 2.0 if pos == 0 else 1.0
                    raw_score += points
                    matched_signals += 1
                    if pos == 0:
                        primary_count += 1
                else:
                    engine_matches[ek] = -1

            # Format signals (from mapped renderer types)
            for fk in mapped_formats:
                styles = self.get_styles_for_format(fk)
                if school in styles:
                    pos = styles.index(school)
                    format_matches[fk] = pos
                    points = 2.0 if pos == 0 else 1.0
                    raw_score += points
                    matched_signals += 1
                    if pos == 0:
                        primary_count += 1
                else:
                    format_matches[fk] = -1

            # Audience signal
            if audience is not None:
                styles = self.get_styles_for_audience(audience)
                if school in styles:
                    pos = styles.index(school)
                    audience_match_pos = pos
                    points = 2.0 if pos == 0 else 1.0
                    raw_score += points
                    matched_signals += 1
                    if pos == 0:
                        primary_count += 1
                else:
                    audience_match_pos = -1

            score = raw_score / max_possible if total_signals > 0 else 0.0

            school_data[school] = {
                "raw_score": raw_score,
                "score": score,
                "primary_count": primary_count,
                "matched_signals": matched_signals,
                "reasoning": RecommendationReasoning(
                    engine_matches=engine_matches,
                    format_matches=format_matches,
                    audience_match=audience_match_pos,
                    total_signals=total_signals,
                    matched_signals=matched_signals,
                ),
            }

        # Sort: score desc, primary_count desc, alphabetical asc
        sorted_schools = sorted(
            all_schools,
            key=lambda s: (-school_data[s]["score"], -school_data[s]["primary_count"], s.value),
        )

        recommendations = []
        for rank, school in enumerate(sorted_schools[:limit], start=1):
            d = school_data[school]
            recommendations.append(StyleRecommendation(
                school=school,
                score=round(d["score"], 4),
                raw_score=d["raw_score"],
                rank=rank,
                reasoning=d["reasoning"],
            ))

        context_summary = StyleRecommendContextSummary(
            engines_provided=len(engines),
            engines_with_explicit_mapping=engines_with_explicit,
            engines_using_default=engines_using_default,
            renderer_types_provided=len(renderers),
            renderer_types_mapped=renderer_types_mapped,
            formats_with_explicit_mapping=formats_with_explicit,
            formats_using_default=formats_using_default,
            audience_provided=audience,
            audience_used_default=audience_used_default,
            effective_signals=total_signals,
        )

        return StyleRecommendResponse(
            recommendations=recommendations,
            context_summary=context_summary,
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
