"""View polisher — LLM-powered visual enhancement of renderer configs.

Calls Sonnet 4.6 to enhance a view's renderer_config and produce style_overrides,
using style school palettes, typography, and display rules as input.

The polished config is cached in polish_cache and applied as inline styles
at defined injection points in the frontend.
"""

import hashlib
import json
import logging
import time
from typing import Any, Optional

from src.llm.client import (
    GENERATION_MODEL,
    get_anthropic_client,
    parse_llm_json_response,
)
from src.renderers.registry import get_renderer_registry
from src.styles.registry import get_style_registry
from src.styles.schemas import StyleSchool
from src.sub_renderers.registry import get_sub_renderer_registry

from .schemas import (
    PolishResult,
    PolishedViewPayload,
    SectionPolishResult,
    StyleOverrides,
    ViewPayload,
)

logger = logging.getLogger(__name__)


def polish_view(
    payload: ViewPayload,
    engine_key: Optional[str] = None,
    style_school: Optional[str] = None,
) -> PolishResult:
    """Polish a view's renderer config using an LLM.

    Args:
        payload: The current ViewPayload to enhance.
        engine_key: Engine key for style school resolution.
        style_school: Explicit style school override. Auto-resolved if not set.

    Returns:
        PolishResult with enhanced config + style overrides.
    """
    start_ms = int(time.time() * 1000)

    # 1. Resolve style school
    resolved_school = _resolve_style_school(
        engine_key or payload.engine_key,
        style_school,
    )

    # 2. Gather context
    context = _gather_polish_context(payload, resolved_school)

    # 3. Compose prompts
    system_prompt = _compose_system_prompt(context)
    user_message = _compose_user_message(payload, context)

    logger.info(
        f"[polish] Composing for view={payload.view_key} school={resolved_school} "
        f"system_len={len(system_prompt)} user_len={len(user_message)}"
    )

    # 4. Call LLM
    client = get_anthropic_client()
    if client is None:
        raise RuntimeError(
            "LLM service unavailable. Set ANTHROPIC_API_KEY environment variable."
        )

    model = GENERATION_MODEL
    try:
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
    except Exception as e:
        raise RuntimeError(f"Polish LLM call failed: {e}") from e

    # 5. Parse response
    try:
        parsed = parse_llm_json_response(raw_text)
    except json.JSONDecodeError as e:
        logger.error(f"[polish] Failed to parse LLM JSON: {e}\nRaw: {raw_text[:500]}")
        raise RuntimeError(f"Polish LLM returned invalid JSON: {e}") from e

    # 6. Build result — resilient to malformed LLM output
    try:
        raw_so = parsed.get("style_overrides", {})
        sanitized_so = {}
        for k, v in raw_so.items():
            if isinstance(v, dict):
                sanitized_so[k] = {sk: str(sv) for sk, sv in v.items()}
            else:
                sanitized_so[k] = v
        style_overrides = StyleOverrides(**sanitized_so)
    except Exception as e:
        logger.warning(f"[polish] Failed to parse style_overrides, using defaults: {e}")
        style_overrides = StyleOverrides()

    polished_config = parsed.get("polished_renderer_config", payload.renderer_config)
    section_descriptions = parsed.get("section_descriptions", {})
    changes_summary = parsed.get("changes_summary", "")

    elapsed_ms = int(time.time() * 1000) - start_ms

    result = PolishResult(
        polished_payload=PolishedViewPayload(
            original_view_key=payload.view_key,
            polished_renderer_config=polished_config,
            style_overrides=style_overrides,
            section_descriptions=section_descriptions,
        ),
        model_used=model,
        tokens_used=total_tokens,
        execution_time_ms=elapsed_ms,
        style_school=resolved_school,
        changes_summary=changes_summary,
    )

    logger.info(
        f"[polish] Done view={payload.view_key} school={resolved_school} "
        f"tokens={total_tokens} time={elapsed_ms}ms"
    )
    return result


def polish_section(
    payload: ViewPayload,
    section_key: str,
    user_feedback: Optional[str] = None,
    engine_key: Optional[str] = None,
    style_school: Optional[str] = None,
) -> SectionPolishResult:
    """Polish a single section of an accordion view using an LLM.

    Unlike polish_view() which polishes the entire view, this focuses on
    one section only and incorporates user feedback.

    Args:
        payload: The current ViewPayload containing structured data.
        section_key: Key of the section to polish (e.g. 'path_dependencies').
        user_feedback: User's natural-language instructions for this section.
        engine_key: Engine key for style school resolution.
        style_school: Explicit style school override.

    Returns:
        SectionPolishResult with section-specific style overrides.
    """
    start_ms = int(time.time() * 1000)

    # 1. Resolve style school
    resolved_school = _resolve_style_school(
        engine_key or payload.engine_key,
        style_school,
    )

    # 2. Gather context (same as view-level, but narrowed to section's sub-renderer)
    context = _gather_polish_context(payload, resolved_school)

    # 3. Extract section data shape
    section_data = None
    if payload.structured_data and isinstance(payload.structured_data, dict):
        section_data = payload.structured_data.get(section_key)

    # 4. Find the section's sub-renderer config
    section_renderers = payload.renderer_config.get("section_renderers", {})
    section_hint = section_renderers.get(section_key, {})
    section_renderer_type = section_hint.get("renderer_type", "")

    # Narrow sub-renderer context to just this section
    sub_registry = get_sub_renderer_registry()
    section_sub_info = {}
    if section_renderer_type:
        sr_def = sub_registry.get(section_renderer_type)
        if sr_def:
            section_sub_info[section_renderer_type] = {
                "name": sr_def.sub_renderer_name,
                "description": sr_def.description,
                "config_schema": sr_def.config_schema,
            }
    context["sub_renderers"] = section_sub_info

    # 5. Compose section-specific prompts
    system_prompt = _compose_section_system_prompt(context, section_key)
    user_message = _compose_section_user_message(
        payload, section_key, section_data, section_hint, user_feedback,
    )

    logger.info(
        f"[polish-section] Composing for view={payload.view_key} "
        f"section={section_key} school={resolved_school} "
        f"feedback={'yes' if user_feedback else 'no'} "
        f"system_len={len(system_prompt)} user_len={len(user_message)}"
    )

    # 6. Call LLM
    client = get_anthropic_client()
    if client is None:
        raise RuntimeError(
            "LLM service unavailable. Set ANTHROPIC_API_KEY environment variable."
        )

    model = GENERATION_MODEL
    try:
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = response.content[0].text
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
    except Exception as e:
        raise RuntimeError(f"Section polish LLM call failed: {e}") from e

    # 7. Parse response
    try:
        parsed = parse_llm_json_response(raw_text)
    except json.JSONDecodeError as e:
        logger.error(
            f"[polish-section] Failed to parse LLM JSON: {e}\n"
            f"Raw: {raw_text[:500]}"
        )
        raise RuntimeError(f"Section polish LLM returned invalid JSON: {e}") from e

    # 8. Build result — resilient to malformed LLM output
    try:
        raw_so = parsed.get("style_overrides", {})
        # Coerce all values to strings in nested dicts (LLM sometimes returns ints)
        sanitized_so = {}
        for k, v in raw_so.items():
            if isinstance(v, dict):
                sanitized_so[k] = {sk: str(sv) for sk, sv in v.items()}
            else:
                sanitized_so[k] = v
        style_overrides = StyleOverrides(**sanitized_so)
    except Exception as e:
        logger.warning(
            f"[polish-section] Failed to parse style_overrides, using defaults: {e}"
        )
        style_overrides = StyleOverrides()

    config_patch = parsed.get("renderer_config_patch", {})
    section_description = parsed.get("section_description", "")
    changes_summary = parsed.get("changes_summary", "")

    elapsed_ms = int(time.time() * 1000) - start_ms

    result = SectionPolishResult(
        section_key=section_key,
        style_overrides=style_overrides,
        renderer_config_patch=config_patch,
        section_description=section_description,
        changes_summary=changes_summary,
        model_used=model,
        tokens_used=total_tokens,
        execution_time_ms=elapsed_ms,
        style_school=resolved_school,
        user_feedback_applied=user_feedback,
    )

    logger.info(
        f"[polish-section] Done view={payload.view_key} section={section_key} "
        f"school={resolved_school} tokens={total_tokens} time={elapsed_ms}ms"
    )
    return result


def compute_config_hash(renderer_config: dict) -> str:
    """Compute a hash of the renderer config for cache invalidation."""
    raw = json.dumps(renderer_config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# --- Internal helpers ---


def _resolve_style_school(
    engine_key: Optional[str],
    explicit_school: Optional[str] = None,
) -> str:
    """Resolve which style school to use.

    Priority: explicit override > engine affinity > default.
    """
    if explicit_school:
        return explicit_school

    if engine_key:
        style_registry = get_style_registry()
        schools = style_registry.get_styles_for_engine(engine_key)
        if schools:
            return schools[0].value

    return StyleSchool.HUMANIST_CRAFT.value


def _gather_polish_context(
    payload: ViewPayload,
    style_school_key: str,
) -> dict[str, Any]:
    """Gather all context needed for the polish prompt."""
    context: dict[str, Any] = {}

    # Style school
    style_registry = get_style_registry()
    try:
        school_enum = StyleSchool(style_school_key)
        style = style_registry.get_style(school_enum)
    except ValueError:
        style = None

    if style:
        context["style_school"] = {
            "name": style.name,
            "philosophy": style.philosophy[:500],
            "color_palette": style.color_palette.model_dump(exclude_none=True),
            "typography": style.typography.model_dump(),
            "layout_principles": style.layout_principles[:6],
            "renderer_guidance": style.renderer_guidance or {},
        }
    else:
        context["style_school"] = {"name": style_school_key, "philosophy": "", "renderer_guidance": {}}

    # Renderer definition
    renderer_registry = get_renderer_registry()
    renderer = renderer_registry.get(payload.renderer_type)
    if renderer:
        context["renderer"] = {
            "key": renderer.renderer_key,
            "name": renderer.renderer_name,
            "description": renderer.description,
            "ideal_data_shapes": renderer.ideal_data_shapes,
            "config_schema": renderer.config_schema,
            "available_section_renderers": renderer.available_section_renderers,
        }

    # Sub-renderer definitions (for section_renderers in config)
    sub_registry = get_sub_renderer_registry()
    section_renderers = payload.renderer_config.get("section_renderers", {})
    sub_renderer_info = {}
    for section_key, sr_config in section_renderers.items():
        sr_type = sr_config.get("renderer_type", "")
        sr_def = sub_registry.get(sr_type)
        if sr_def:
            sub_renderer_info[sr_type] = {
                "name": sr_def.sub_renderer_name,
                "description": sr_def.description,
                "config_schema": sr_def.config_schema,
            }
    context["sub_renderers"] = sub_renderer_info

    # Display rules (subset — label formatting, hidden fields)
    try:
        from src.display.registry import get_display_registry
        display_reg = get_display_registry()
        display_config = display_reg.get_display_config()
        if display_config:
            dc = display_config.model_dump() if hasattr(display_config, "model_dump") else display_config
            context["display_rules"] = {
                "label_formatting": dc.get("instructions", {}).get("label_formatting", ""),
                "hidden_fields": dc.get("hidden_fields", {}).get("hidden_fields", [])[:10],
            }
    except Exception:
        context["display_rules"] = {}

    return context


def _compose_system_prompt(context: dict[str, Any]) -> str:
    """Compose the system prompt for the polish LLM call."""
    school = context.get("style_school", {})
    palette = school.get("color_palette", {})
    typography = school.get("typography", {})
    layout = school.get("layout_principles", [])
    renderer = context.get("renderer", {})
    display_rules = context.get("display_rules", {})

    parts = [
        "You are a UI presentation designer. Your job is to enhance a React component's",
        "renderer_config and produce CSS-like style_overrides that make the view visually",
        "polished and aesthetically cohesive.",
        "",
        "## Style School: " + school.get("name", "Unknown"),
        school.get("philosophy", ""),
        "",
        "## Color Palette",
        json.dumps(palette, indent=2) if palette else "(no palette)",
        "",
        "## Typography",
        json.dumps(typography, indent=2) if typography else "(no typography)",
        "",
        "## Layout Principles",
    ]
    for lp in layout:
        parts.append(f"- {lp}")

    if renderer:
        parts.extend([
            "",
            "## Renderer: " + renderer.get("name", ""),
            renderer.get("description", ""),
            "",
            "Available section renderers: " + ", ".join(
                renderer.get("available_section_renderers", [])
            ),
        ])

    sub_renderers = context.get("sub_renderers", {})
    if sub_renderers:
        parts.extend(["", "## Sub-Renderer Schemas"])
        for sr_key, sr_info in sub_renderers.items():
            parts.append(f"### {sr_key}: {sr_info.get('name', '')}")
            parts.append(sr_info.get("description", ""))
            schema = sr_info.get("config_schema", {})
            if schema:
                parts.append(f"Config: {json.dumps(schema)}")

    if display_rules:
        parts.extend([
            "",
            "## Display Rules",
            display_rules.get("label_formatting", ""),
        ])
        hidden = display_rules.get("hidden_fields", [])
        if hidden:
            parts.append(f"Hidden fields (never display): {', '.join(hidden[:8])}")

    # Renderer guidance from the style school
    renderer_guidance = school.get("renderer_guidance", {})
    if renderer_guidance:
        parts.extend(["", "## Style School Renderer Guidance"])
        for renderer_type, guidance in renderer_guidance.items():
            parts.append(f"- **{renderer_type}**: {guidance}")

    parts.extend([
        "",
        "## Your Output",
        "Return a single JSON object with these keys:",
        "",
        "1. `polished_renderer_config` — A complete replacement of the current renderer_config.",
        "   Preserve all section keys and renderer_types. You may:",
        "   - Add/modify section_description text for richer context",
        "   - Adjust sub-renderer config values",
        "   - Reorder sections for better narrative flow",
        "   - Add config hints like expand_first",
        "",
        "2. `style_overrides` — CSS-like style objects for injection points.",
        "   These overrides are applied as inline styles on React elements across ALL",
        "   sub-renderers (timeline_strip, mini_card_list, chip_grid, etc.), not just",
        "   the accordion shell.",
        "",
        "   INJECTION POINTS (existing — coarse-grained):",
        "   - `section_header`: accordion/tab section headers (h3 elements)",
        "   - `section_content`: section content wrappers",
        "   - `card`: condition cards, mini-cards, entity cards, stat cards",
        "   - `chip`: type/category chips, tag chips, string-array chips",
        "   - `badge`: managed/status badges, subtitle badges",
        "   - `timeline_node`: individual timeline stage pills",
        "   - `prose`: prose/text blocks, descriptions, section descriptions",
        "   - `accent_color`: single hex color for primary accent",
        "   - `view_wrapper`: outer view container",
        "   - `items_container`: the container wrapping lists of items (cards, timeline",
        "     paths, chips). Use this to control LAYOUT: CSS grid for 2-column layouts,",
        "     reduced gap for compact views, etc.",
        "",
        "   INJECTION POINTS (new — finer-grained control):",
        "   - `section_title`: text styling for section header titles only (not the clickable bar)",
        "   - `section_description`: subtitle text below section headers",
        "   - `card_header`: card title/header area",
        "   - `card_body`: card description/body text",
        "   - `chip_label`: chip text content styling",
        "   - `chip_expanded`: expanded detail panel below chips",
        "   - `prose_lede`: first paragraph (rendered larger/bolder by default)",
        "   - `prose_body`: subsequent prose paragraphs",
        "   - `prose_quote`: blockquote/pull-quote styling",
        "   - `timeline_connector`: line/arrow between timeline nodes",
        "   - `stat_number`: statistic number display",
        "   - `stat_label`: statistic label text",
        "   - `hero_card`: featured/first card (larger, full-width)",
        "   - `view_header`: introduction area at top of view",
        "",
        "   Use camelCase CSS property names (React style). Example:",
        '   {"card": {"borderLeft": "3px solid #c41e3a", "backgroundColor": "#faf7f2"},',
        '    "card_header": {"fontWeight": "600", "letterSpacing": "0.01em"},',
        '    "prose_lede": {"fontSize": "1.05rem", "fontWeight": "500"},',
        '    "stat_number": {"color": "#c41e3a", "fontWeight": "700"},',
        '    "hero_card": {"backgroundColor": "#faf7f2", "padding": "1.25rem"},',
        '    "items_container": {"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "0.5rem"}}',
        "",
        "3. `section_descriptions` — object mapping section keys to enhanced descriptions.",
        "   Make descriptions inviting and informative (1-2 sentences).",
        "",
        "4. `changes_summary` — brief human-readable summary of what you changed and why.",
        "",
        "## Typography & Visual Design",
        "The renderers use a CSS custom property type scale. Your style overrides",
        "work WITH this scale. You can adjust:",
        "- fontSize (overrides the scale for emphasis — use sparingly)",
        "- fontWeight (300-700, to create visual hierarchy)",
        "- letterSpacing (for labels and headings)",
        "- color (text color within the element)",
        "- background/backgroundColor (subtle tints)",
        "- borderLeft, borderBottom (accent bars and separators)",
        "- padding, margin (spatial adjustments)",
        "",
        "DO NOT set font-family (the type scale handles this).",
        "DO leverage the style school's personality through color choices,",
        "spacing decisions, and visual weight distribution.",
        "USE the new finer-grained injection points to create rich typographic",
        "hierarchy — differentiate hero cards from standard cards, lede from body,",
        "stat numbers from labels, section titles from descriptions.",
        "",
        "## Constraints",
        "- Use ONLY colors from the style school palette",
        "- Use valid CSS values in camelCase (React style objects)",
        "- Preserve ALL section keys from the original config",
        "- Preserve renderer_type for each section_renderer",
        "- Do NOT add new sections that don't exist in the data",
        "- Keep the design professional and readable — enhance, don't overwhelm",
        "- Return ONLY the JSON object, no markdown fences or explanation",
        "",
        "## Layout Density Guidelines",
        "- REDUCE SCROLLING. Analytical views contain many items and users should not",
        "  have to scroll excessively. Use compact layouts:",
        "  * For sections with 4+ items: use `items_container` with CSS grid (2 columns)",
        "    e.g. {\"display\": \"grid\", \"gridTemplateColumns\": \"1fr 1fr\", \"gap\": \"0.5rem\"}",
        "  * Reduce vertical padding: cards should be tight (8-10px), not spacious (16-24px)",
        "  * Timeline nodes should be compact with smaller text (0.7rem) and less padding",
        "  * Use smaller font sizes for body/labels (0.75-0.85rem body, 0.68-0.72rem labels)",
        "- For sections with few items (1-3): single column is fine, keep spacious",
        "- Chips and badges should be small and tight (padding: 2px 6px)",
        "- The goal is a DENSE, INFORMATION-RICH layout like a newspaper or academic journal",
        "- CRITICAL: Do NOT increase padding, margins, or font sizes beyond the defaults",
        "  EXCEPT via the finer-grained injection points (prose_lede, stat_number, hero_card)",
        "  where controlled emphasis is intentional.",
        "  Keep card padding <= 10px, prose line-height <= 1.6, section_content padding <= 16px.",
        "  The total scroll height must not increase after polishing.",
        "- For items_container grid, use 'minmax(0, 1fr)' instead of plain '1fr'",
        "  to prevent content overflow in grid children. Example:",
        '  {"display": "grid", "gridTemplateColumns": "minmax(0,1fr) minmax(0,1fr)", "gap": "0.5rem"}',
    ])

    return "\n".join(parts)


def _compose_user_message(
    payload: ViewPayload,
    context: dict[str, Any],
) -> str:
    """Compose the user message with the current config and data shape."""
    parts = [
        "## Current Renderer Config",
        json.dumps(payload.renderer_config, indent=2),
        "",
        "## View Metadata",
        f"- view_key: {payload.view_key}",
        f"- view_name: {payload.view_name}",
        f"- renderer_type: {payload.renderer_type}",
        f"- presentation_stance: {payload.presentation_stance or 'none'}",
        f"- description: {payload.description}",
        "",
    ]

    # Data shape summary (not full data — just structure)
    if payload.structured_data:
        shape = _summarize_data_shape(payload.structured_data)
        parts.extend(["## Structured Data Shape", shape, ""])

    if payload.children:
        parts.append("## Child Views")
        for child in payload.children:
            child_shape = ""
            if child.structured_data:
                child_shape = f" | data keys: {list(child.structured_data.keys())[:5]}" if isinstance(child.structured_data, dict) else ""
            parts.append(
                f"- {child.view_key} ({child.renderer_type}){child_shape}"
            )
        parts.append("")

    parts.append(
        "Please produce the polished renderer_config, style_overrides, "
        "section_descriptions, and changes_summary as a JSON object."
    )

    return "\n".join(parts)


def _summarize_data_shape(data: Any, depth: int = 0) -> str:
    """Produce a concise summary of structured data shape."""
    if depth > 2:
        return "..."

    if isinstance(data, dict):
        lines = []
        for key, val in list(data.items())[:12]:
            if isinstance(val, list):
                sample = val[0] if val else {}
                item_keys = list(sample.keys())[:5] if isinstance(sample, dict) else []
                lines.append(f"  {key}: array[{len(val)}] items with keys {item_keys}")
            elif isinstance(val, dict):
                lines.append(f"  {key}: object with keys {list(val.keys())[:5]}")
            elif isinstance(val, str):
                lines.append(f"  {key}: string ({len(val)} chars)")
            else:
                lines.append(f"  {key}: {type(val).__name__}")
        return "\n".join(lines)
    elif isinstance(data, list):
        if data and isinstance(data[0], dict):
            return f"array[{len(data)}] of objects with keys {list(data[0].keys())[:6]}"
        return f"array[{len(data)}]"
    else:
        return str(type(data).__name__)


# --- Section-level prompt helpers ---


def _compose_section_system_prompt(
    context: dict[str, Any],
    section_key: str,
) -> str:
    """Compose the system prompt for a single-section polish call."""
    school = context.get("style_school", {})
    palette = school.get("color_palette", {})
    typography = school.get("typography", {})
    layout = school.get("layout_principles", [])
    display_rules = context.get("display_rules", {})

    parts = [
        "You are a UI presentation designer. Your job is to enhance the visual styling",
        f"of a SINGLE accordion section ('{section_key}') by producing CSS-like style_overrides.",
        "You may also suggest config changes for the section's sub-renderer.",
        "",
        "## Style School: " + school.get("name", "Unknown"),
        school.get("philosophy", ""),
        "",
        "## Color Palette",
        json.dumps(palette, indent=2) if palette else "(no palette)",
        "",
        "## Typography",
        json.dumps(typography, indent=2) if typography else "(no typography)",
        "",
        "## Layout Principles",
    ]
    for lp in layout:
        parts.append(f"- {lp}")

    sub_renderers = context.get("sub_renderers", {})
    if sub_renderers:
        parts.extend(["", "## Sub-Renderer for This Section"])
        for sr_key, sr_info in sub_renderers.items():
            parts.append(f"### {sr_key}: {sr_info.get('name', '')}")
            parts.append(sr_info.get("description", ""))
            schema = sr_info.get("config_schema", {})
            if schema:
                parts.append(f"Config schema: {json.dumps(schema)}")

    if display_rules:
        parts.extend([
            "",
            "## Display Rules",
            display_rules.get("label_formatting", ""),
        ])

    # Renderer guidance from the style school
    renderer_guidance = school.get("renderer_guidance", {})
    if renderer_guidance:
        parts.extend(["", "## Style School Renderer Guidance (for this section's type)"])
        for renderer_type, guidance in renderer_guidance.items():
            parts.append(f"- **{renderer_type}**: {guidance}")

    parts.extend([
        "",
        "## Your Output",
        "Return a single JSON object with these keys:",
        "",
        "1. `style_overrides` — CSS-like style objects for injection points,",
        "   applied ONLY to this section.",
        "",
        "   Available injection points (coarse-grained):",
        "   section_header, section_content, card, chip, badge, timeline_node,",
        "   prose, accent_color, view_wrapper, items_container.",
        "",
        "   Available injection points (finer-grained):",
        "   section_title, section_description, card_header, card_body,",
        "   chip_label, chip_expanded, prose_lede, prose_body, prose_quote,",
        "   timeline_connector, stat_number, stat_label, hero_card, view_header.",
        "",
        "   Use camelCase CSS property names (React style).",
        "",
        "2. `renderer_config_patch` — partial config to merge into this section's",
        "   sub-renderer config (e.g. changing display mode, reordering fields).",
        "   Only include keys you want to change.",
        "",
        "3. `section_description` — enhanced description for this section (1-2 sentences).",
        "",
        "4. `changes_summary` — brief human-readable summary of what you changed and why.",
        "",
        "## CRITICAL DESIGN CONSTRAINTS",
        "Your styling must be SUBTLE and CONSERVATIVE. Think academic journal, not billboard.",
        "",
        "### ABSOLUTELY FORBIDDEN (violating these ruins the UI):",
        "- NO dark/saturated backgrounds on cards (no backgroundColor darker than #f0f0f0)",
        "- NO text-transform: uppercase or ALL CAPS on any element",
        "- NO colors that reduce contrast (dark bg + dark text)",
        "- NO dramatic color blocks — this is a reading interface, not a dashboard",
        "",
        "### ALLOWED for typography hierarchy (via finer-grained injection points):",
        "- fontWeight up to 700 on stat_number, hero_card headers, and section_title",
        "- fontWeight up to 600 on card_header, prose_lede, and section_description",
        "- fontSize adjustments on prose_lede (up to 1.05rem), stat_number (up to 1.25rem),",
        "  hero_card text (up to 1.1rem). Body text (card_body, prose_body) stays <= 0.85rem",
        "- letterSpacing on stat_label, section_title, chip_label for typographic refinement",
        "",
        "### ENCOURAGED:",
        "- Subtle left borders on cards (2-3px solid, muted palette color)",
        "- Very light background tints (#fafbfc, #f8fafc, #fef7ed — near-white only)",
        "- Compact multi-column layouts via items_container CSS grid",
        "- Reduced spacing (card padding 6-8px, gap 0.4-0.5rem)",
        "- Small accent colors on labels/badges only (keep body text dark #1e293b)",
        "- Clean typographic hierarchy using the finer-grained injection points",
        "- Differentiated hero cards vs standard cards via hero_card override",
        "- Distinctive prose_lede treatment to establish the key argument",
        "",
        "### Layout Guidelines:",
        "- For 4+ items: use items_container with CSS grid",
        '  {"display": "grid", "gridTemplateColumns": "minmax(0,1fr) minmax(0,1fr)", "gap": "0.5rem"}',
        "- For 1-3 items: single column, modest spacing",
        "- Cards should look like quiet, well-typeset entries — not flashy tiles",
        "- The page background is white (#fff) — your cards should barely stand out",
        "",
        "- Use ONLY colors from the style school palette",
        "- Return ONLY the JSON object, no markdown fences or explanation",
    ])

    return "\n".join(parts)


def _compose_section_user_message(
    payload: ViewPayload,
    section_key: str,
    section_data: Any,
    section_hint: dict[str, Any],
    user_feedback: Optional[str] = None,
) -> str:
    """Compose the user message for a single-section polish call."""
    parts = [
        f"## Section: {section_key}",
        f"- view_key: {payload.view_key}",
        f"- view_name: {payload.view_name}",
        "",
        "## Section Sub-Renderer Config",
        json.dumps(section_hint, indent=2) if section_hint else "(no config)",
        "",
    ]

    # Data shape for this section only
    if section_data is not None:
        shape = _summarize_data_shape(section_data)
        parts.extend([
            "## Section Data Shape",
            shape,
            "",
        ])

    # User feedback — the key differentiator
    if user_feedback:
        parts.extend([
            "## User Instructions",
            "The user has provided the following feedback for this section.",
            "PRIORITIZE these instructions above general aesthetics:",
            "",
            user_feedback,
            "",
        ])

    parts.append(
        "Please produce the style_overrides, renderer_config_patch, "
        "section_description, and changes_summary as a JSON object."
    )

    return "\n".join(parts)
