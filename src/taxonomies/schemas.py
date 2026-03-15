"""Schemas for classification taxonomies."""

from typing import Any

from pydantic import BaseModel, Field


class TaxonomyValueDefinition(BaseModel):
    """One label/value in a taxonomy."""

    key: str
    name: str
    use_when: str = ""
    avoid_when: str = ""
    secondary_when: str = ""
    notes: list[str] = Field(default_factory=list)


class TaxonomyDefinition(BaseModel):
    """A reusable classifier taxonomy definition."""

    taxonomy_key: str
    domain: str = "generic"
    description: str = ""
    values: list[TaxonomyValueDefinition] = Field(default_factory=list)
    guidance: list[str] = Field(default_factory=list)
    normalization_hints: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def value_keys(self) -> list[str]:
        return [item.key for item in self.values]

    def render_guidance(self) -> str:
        lines: list[str] = []
        for item in self.values:
            line = f"- `{item.key}`: use when {item.use_when}" if item.use_when else f"- `{item.key}`"
            if item.avoid_when:
                line += f" Avoid when {item.avoid_when}"
            if item.secondary_when:
                line += f" Secondary role: {item.secondary_when}"
            if item.notes:
                line += " " + " ".join(item.notes)
            lines.append(line)
        for guidance in self.guidance:
            lines.append(f"- {guidance}")
        return "\n".join(lines)
