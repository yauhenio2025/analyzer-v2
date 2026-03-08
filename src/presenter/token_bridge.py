"""Token bridge — connects the design token system to the polisher.

Provides:
- Token reference builder for polisher prompts
- Property classification (color vs layout)
- Post-polish compliance validator with structured metrics
"""

import logging
from typing import Optional

from src.styles.token_schema import DesignTokenSet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Property classification
# ---------------------------------------------------------------------------

# CSS properties (camelCase) that represent colors and should use token refs
COLOR_PROPERTIES: frozenset[str] = frozenset({
    "color",
    "backgroundColor",
    "borderColor",
    "borderLeftColor",
    "borderTopColor",
    "borderBottomColor",
    "borderRightColor",
    "outlineColor",
    "textDecorationColor",
})

# Properties where the VALUE may contain a color (e.g. "3px solid #hex")
COMPOUND_COLOR_PROPERTIES: frozenset[str] = frozenset({
    "border",
    "borderLeft",
    "borderRight",
    "borderTop",
    "borderBottom",
})

# ---------------------------------------------------------------------------
# Injection point → token mapping
# ---------------------------------------------------------------------------

# Maps polisher injection points to {cssProp: '--dt-token-name'}
# Derived from ComponentTokens fields in token_schema.py:263-322
INJECTION_TO_TOKEN_MAP: dict[str, dict[str, str] | str] = {
    "section_header": {
        "backgroundColor": "--dt-section-header-bg",
        "borderColor": "--dt-section-header-border",
        "color": "--dt-section-header-text",
    },
    "card": {
        "backgroundColor": "--dt-card-bg",
        "borderColor": "--dt-card-border",
    },
    "card_header": {
        "backgroundColor": "--dt-card-header-bg",
        "color": "--dt-card-header-text",
    },
    "prose_lede": {
        "color": "--dt-prose-lede-color",
    },
    "prose_quote": {
        "borderColor": "--dt-prose-blockquote-border",
        "backgroundColor": "--dt-prose-blockquote-bg",
    },
    "timeline_node": {
        "backgroundColor": "--dt-timeline-node-bg",
        "borderColor": "--dt-timeline-node-border",
    },
    "timeline_connector": {
        "backgroundColor": "--dt-timeline-connector",
    },
    "stat_number": {
        "color": "--dt-stat-number-color",
    },
    "stat_label": {
        "color": "--dt-stat-label-color",
    },
    "hero_card": {
        "backgroundColor": "--dt-card-bg",
    },
    "accent_color": "--dt-page-accent",
}


# ---------------------------------------------------------------------------
# Sync token fetch (no async hacks)
# ---------------------------------------------------------------------------

def get_tokens_for_polisher(school_key: str) -> Optional[DesignTokenSet]:
    """Sync token fetch for polisher context. Memory cache -> DB cache -> None.

    Does NOT trigger LLM generation — returns None if no cached tokens exist.
    """
    from src.styles.token_generator import _memory_cache, _get_cached_from_db, _hash_style_json
    from src.styles.registry import get_style_registry
    from src.styles.schemas import StyleSchool

    if school_key in _memory_cache:
        return _memory_cache[school_key]

    try:
        school_enum = StyleSchool(school_key)
    except ValueError:
        return None

    registry = get_style_registry()
    style = registry.get_style(school_enum)
    if style is None:
        return None

    style_hash = _hash_style_json(style.model_dump())
    cached_dict = _get_cached_from_db(school_key, style_hash)
    if cached_dict is not None:
        try:
            tokens = DesignTokenSet(**cached_dict)
            _memory_cache[school_key] = tokens
            return tokens
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Token reference builder
# ---------------------------------------------------------------------------

def build_token_reference(tokens: DesignTokenSet) -> dict[str, str]:
    """Build compact token reference for the polisher prompt.

    Returns dict like:
      {"card background": "var(--dt-card-bg)",
       "card border": "var(--dt-card-border)",
       "section header bg": "var(--dt-section-header-bg)",
       "primary accent": "var(--dt-page-accent)",
       "default surface": "var(--dt-surface-default)", ...}
    """
    refs: dict[str, str] = {}

    # Tier 6: Component tokens (~41 fields — most important for polisher)
    comp = tokens.components
    component_map = {
        "page accent": "page_accent",
        "page accent hover": "page_accent_hover",
        "page accent bg": "page_accent_bg",
        "section header bg": "section_header_bg",
        "section header border": "section_header_border",
        "section header text": "section_header_text",
        "card bg": "card_bg",
        "card border": "card_border",
        "card border accent": "card_border_accent",
        "card header bg": "card_header_bg",
        "card header text": "card_header_text",
        "chip weight 0 bg": "chip_weight_0_bg",
        "chip weight 0 text": "chip_weight_0_text",
        "chip weight 0 border": "chip_weight_0_border",
        "chip weight 25 bg": "chip_weight_25_bg",
        "chip weight 25 text": "chip_weight_25_text",
        "chip weight 25 border": "chip_weight_25_border",
        "chip weight 50 bg": "chip_weight_50_bg",
        "chip weight 50 text": "chip_weight_50_text",
        "chip weight 50 border": "chip_weight_50_border",
        "chip weight 75 bg": "chip_weight_75_bg",
        "chip weight 75 text": "chip_weight_75_text",
        "chip weight 75 border": "chip_weight_75_border",
        "chip weight 100 bg": "chip_weight_100_bg",
        "chip weight 100 text": "chip_weight_100_text",
        "chip weight 100 border": "chip_weight_100_border",
        "chip header bg": "chip_header_bg",
        "chip header text": "chip_header_text",
        "prose lede color": "prose_lede_color",
        "prose blockquote border": "prose_blockquote_border",
        "prose blockquote bg": "prose_blockquote_bg",
        "timeline connector": "timeline_connector",
        "timeline node bg": "timeline_node_bg",
        "timeline node border": "timeline_node_border",
        "evidence dot bg": "evidence_dot_bg",
        "evidence connector": "evidence_connector",
        "stat number color": "stat_number_color",
        "stat label color": "stat_label_color",
        "stat card bg": "stat_card_bg",
    }
    for label, field in component_map.items():
        refs[label] = f"var(--dt-{field.replace('_', '-')})"

    # Tier 2: Key surface tokens
    surf = tokens.surfaces
    surface_map = {
        "default surface": "surface_default",
        "alt surface": "surface_alt",
        "elevated surface": "surface_elevated",
        "inset surface": "surface_inset",
        "default border": "border_default",
        "light border": "border_light",
        "accent border": "border_accent",
        "default text": "text_default",
        "muted text": "text_muted",
    }
    for label, field in surface_map.items():
        refs[label] = f"var(--dt-{field.replace('_', '-')})"

    # Tier 1: Key primitive colors
    prim = tokens.primitives
    primitive_map = {
        "color primary": "color_primary",
        "color accent": "color_accent",
        "color secondary": "color_secondary",
        "color tertiary": "color_tertiary",
    }
    for label, field in primitive_map.items():
        refs[label] = f"var(--dt-{field.replace('_', '-')})"

    return refs


# ---------------------------------------------------------------------------
# Post-polish compliance validator
# ---------------------------------------------------------------------------

def validate_style_overrides(
    overrides: "StyleOverrides",  # noqa: F821 — forward ref
    view_key: str,
    style_school: str,
) -> dict:
    """Check token compliance of style overrides. Returns metrics dict.

    Checks each injection point's properties: if it's a COLOR_PROPERTY
    and the value is NOT a var(--dt-*) reference, count it as non-compliant.

    Returns: {
        "total_color_props": int,
        "token_referenced": int,
        "raw_hex_remaining": int,
        "compliance_pct": float,
        "warnings": list[str],
    }
    """
    total_color = 0
    token_refs = 0
    warnings: list[str] = []

    overrides_dict = overrides.model_dump(exclude_none=True)

    for point_name, point_value in overrides_dict.items():
        if isinstance(point_value, dict):
            for prop, val in point_value.items():
                if prop in COLOR_PROPERTIES:
                    total_color += 1
                    if isinstance(val, str) and val.startswith("var(--dt-"):
                        token_refs += 1
                    else:
                        warnings.append(
                            f"{point_name}.{prop}: raw value '{val}' "
                            f"(expected var(--dt-*))"
                        )
        elif isinstance(point_value, str) and point_name == "accent_color":
            total_color += 1
            if point_value.startswith("var(--dt-"):
                token_refs += 1
            else:
                warnings.append(
                    f"accent_color: raw value '{point_value}' "
                    f"(expected var(--dt-*))"
                )

    raw_remaining = total_color - token_refs
    compliance_pct = (token_refs / total_color * 100.0) if total_color > 0 else 100.0

    return {
        "total_color_props": total_color,
        "token_referenced": token_refs,
        "raw_hex_remaining": raw_remaining,
        "compliance_pct": compliance_pct,
        "warnings": warnings,
    }
