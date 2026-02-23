"""Consumer definition schemas — data models for consumer app capabilities.

ConsumerDefinitions declare what rendering and analysis capabilities
a consumer app supports. This inverts the coupling — instead of renderers
declaring which apps they work in, apps declare what they can render.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ConsumerPage(BaseModel):
    """A page within a consumer app."""

    page_key: str = Field(..., description="Unique page identifier")
    description: str = Field(default="", description="What this page shows")


class ConsumerDefinition(BaseModel):
    """A consumer application that consumes analytical definitions.

    Consumers declare their rendering capabilities so the orchestrator
    and view system can make informed decisions without hardcoding
    app names in renderer definitions.
    """

    # Identity
    consumer_key: str = Field(
        ...,
        description="Unique identifier (kebab-case, e.g. 'the-critic')",
    )
    consumer_name: str = Field(
        ...,
        description="Human-readable name (e.g. 'The Critic')",
    )
    description: str = Field(
        default="",
        description="What this consumer app does",
    )
    consumer_type: str = Field(
        default="web_app",
        description="Type: 'web_app', 'api_client', 'cli', 'mcp_server'",
    )

    # Rendering capabilities
    supported_renderers: list[str] = Field(
        default_factory=list,
        description="Renderer keys this app can render: "
        "'accordion', 'card_grid', 'prose', 'table', 'tab', etc.",
    )
    supported_sub_renderers: list[str] = Field(
        default_factory=list,
        description="Sub-renderer keys this app can render: "
        "'chip_grid', 'mini_card_list', 'key_value_table', etc.",
    )

    # Pages
    pages: list[ConsumerPage] = Field(
        default_factory=list,
        description="Pages/sections within this app",
    )

    # Connection info
    api_endpoint: Optional[str] = Field(
        default=None,
        description="Base URL for the consumer's API",
    )

    # Metadata
    status: str = Field(
        default="active",
        description="'active', 'draft', 'deprecated'",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization tags",
    )


class ConsumerSummary(BaseModel):
    """Lightweight summary for listing endpoints."""

    consumer_key: str
    consumer_name: str
    description: str = ""
    consumer_type: str = "web_app"
    supported_renderers: list[str] = Field(default_factory=list)
    supported_sub_renderers: list[str] = Field(default_factory=list)
    page_count: int = 0
    status: str = "active"
