"""Schemas for prompt-context providers."""

from typing import Optional

from pydantic import BaseModel, Field


class PromptContextProviderDefinition(BaseModel):
    """One prompt placeholder provider."""

    provider_key: str
    provider_name: str = ""
    source_type: str = Field(description="taxonomy_enum, taxonomy_guidance, static_text")
    taxonomy_key: Optional[str] = None
    static_value: Optional[str] = None
    render_format: str = Field(default="plain_csv", description="plain_csv or guidance")
    status: str = "active"
