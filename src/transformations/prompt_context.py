"""Runtime prompt-context interpolation for transformation templates."""

from __future__ import annotations

import re

from src.prompt_contexts.registry import get_prompt_context_registry


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_prompt_template(template: str) -> str:
    """Replace prompt-context placeholders with registry-backed values."""
    if not template or "{{" not in template:
        return template

    registry = get_prompt_context_registry()

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = registry.render(key)
        return value if value is not None else match.group(0)

    return _PLACEHOLDER_RE.sub(_replace, template)
