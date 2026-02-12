"""Function definition schemas for the analyzer ecosystem.

Functions are the primary activity unit — each represents an LLM-powered
capability (not just a prompt). The function is the organizing primitive;
prompts, model config, and I/O contracts are properties of the function.

Key design: each function links back to its source code implementations
across projects, enabling quick "zoom in" from definition to actual software.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================


class FunctionCategory(str, Enum):
    """Categories for function organization."""

    COORDINATION = "coordination"       # Decision-making, strategy selection
    GENERATION = "generation"           # Creating content, items, questions
    ANALYSIS = "analysis"               # Analyzing patterns, quality checking
    SYNTHESIS = "synthesis"             # Combining, synthesizing across data
    TOOL = "tool"                       # Interactive tools (IDEAS/PROCESS tracks)
    INFRASTRUCTURE = "infrastructure"   # Supporting functions (grids, quality)


class FunctionTier(str, Enum):
    """Model tier indicating complexity and cost.

    Maps to which Claude model is typically used.
    """

    STRATEGIC = "strategic"       # Opus + extended thinking — high-stakes decisions
    TACTICAL = "tactical"         # Sonnet — core generation and analysis
    LIGHTWEIGHT = "lightweight"   # Haiku — fast, cheap, classification tasks


class InvocationPattern(str, Enum):
    """How frequently this function is invoked."""

    EVERY_QUESTION = "every_question"       # Called for every question cycle
    PERIODIC = "periodic"                   # Called periodically (e.g., every N answers)
    ON_DEMAND = "on_demand"                 # Called when specific conditions met
    ONCE_PER_SESSION = "once_per_session"   # Called once at session start/end
    PER_VECTOR = "per_vector"               # Called once per vector initialization


# ============================================================================
# Sub-models
# ============================================================================


class PromptTemplate(BaseModel):
    """A prompt template used by a function."""

    role: str = Field(
        ...,
        description="Prompt role: 'system' or 'user'",
        examples=["system", "user"],
    )
    template_text: str = Field(
        ...,
        description="The actual prompt text (may contain {variable} placeholders)",
    )
    variables: list[str] = Field(
        default_factory=list,
        description="Template variables that must be provided at runtime",
        examples=[["decision_context", "items_json", "recent_questions"]],
    )
    notes: str = Field(
        default="",
        description="Notes about when/how this template is used",
    )


class ModelConfigSpec(BaseModel):
    """Model configuration for an LLM function.

    Note: Field name avoids 'model_config' which is reserved in Pydantic v2.
    """

    model: str = Field(
        ...,
        description="Claude model identifier",
        examples=["claude-opus-4-5-20251101", "claude-sonnet-4-5-20250929", "claude-haiku-4-5-20251001"],
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum output tokens",
    )
    thinking_budget: Optional[int] = Field(
        default=None,
        description="Extended thinking token budget (None = no extended thinking)",
    )
    streaming: bool = Field(
        default=False,
        description="Whether streaming is used",
    )
    temperature: Optional[float] = Field(
        default=None,
        description="Temperature override (None = model default)",
    )


class IOContract(BaseModel):
    """Input/output contract for a function."""

    input_description: str = Field(
        default="",
        description="Human-readable description of expected inputs",
    )
    output_description: str = Field(
        default="",
        description="Human-readable description of expected outputs",
    )
    input_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for function input (if structured)",
    )
    output_schema: Optional[dict[str, Any]] = Field(
        default=None,
        description="JSON Schema for function output (if structured)",
    )


class Implementation(BaseModel):
    """A code location where a function is implemented.

    This is the key field for "zoom in" — from a function definition
    to the actual source code in a specific project.
    """

    project: str = Field(
        ...,
        description="Project name where this implementation lives",
        examples=["decider-v2", "the-decider"],
    )
    file_path: str = Field(
        ...,
        description="Relative file path within the project",
        examples=["backend/app/services/coordinator_service.py"],
    )
    symbol: Optional[str] = Field(
        default=None,
        description="Function or class name at this location",
        examples=["_build_system_prompt", "generate_question"],
    )
    line_start: Optional[int] = Field(
        default=None,
        description="Starting line number",
    )
    line_end: Optional[int] = Field(
        default=None,
        description="Ending line number",
    )
    repo_url: Optional[str] = Field(
        default=None,
        description="GitHub/GitLab repository URL for link generation",
        examples=["https://github.com/user/decider-v2"],
    )
    is_primary: bool = Field(
        default=False,
        description="Whether this is the primary implementation",
    )
    description: str = Field(
        default="",
        description="What this implementation does",
    )


# ============================================================================
# Main Definition
# ============================================================================


class FunctionDefinition(BaseModel):
    """Complete definition of an LLM-powered function.

    The function is the organizing primitive — not the prompt.
    Each function captures what it does, how it's configured,
    what prompts it uses, and where it's implemented.
    """

    # Identity
    function_key: str = Field(
        ...,
        description="Unique identifier (snake_case)",
        examples=["coordinator_decision", "question_generation"],
    )
    function_name: str = Field(
        ...,
        description="Human-readable name",
        examples=["Coordinator Decision", "Question Generation"],
    )
    description: str = Field(
        ...,
        description="What this function does and why it exists",
    )
    version: int = Field(default=1, description="Definition version")

    # Classification
    category: FunctionCategory = Field(
        ...,
        description="Functional category for UI grouping",
    )
    tier: FunctionTier = Field(
        ...,
        description="Model tier (strategic/tactical/lightweight)",
    )
    invocation_pattern: InvocationPattern = Field(
        ...,
        description="How frequently this function is invoked",
    )

    # LLM Configuration
    model_config_spec: ModelConfigSpec = Field(
        ...,
        description="Model and generation configuration",
    )
    prompt_templates: list[PromptTemplate] = Field(
        default_factory=list,
        description="System and user prompt templates",
    )

    # I/O Contract
    io_contract: IOContract = Field(
        default_factory=IOContract,
        description="Input/output contract",
    )

    # Implementation locations (the "zoom in" feature)
    implementations: list[Implementation] = Field(
        default_factory=list,
        description="Source code locations across projects",
    )

    # Project tracking
    source_projects: list[str] = Field(
        default_factory=list,
        description="Projects that use this function",
        examples=[["decider-v2"]],
    )

    # DAG relationships
    depends_on_functions: list[str] = Field(
        default_factory=list,
        description="Function keys this function depends on (upstream)",
    )
    feeds_into_functions: list[str] = Field(
        default_factory=list,
        description="Function keys that consume this function's output (downstream)",
    )

    # Metadata
    track: Optional[str] = Field(
        default=None,
        description="Which track this function operates on: ideas, process, or both",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Searchable tags",
    )
    notes: str = Field(
        default="",
        description="Additional notes or context",
    )


class FunctionSummary(BaseModel):
    """Lightweight function info for listing endpoints."""

    function_key: str
    function_name: str
    description: str
    category: FunctionCategory
    tier: FunctionTier
    invocation_pattern: InvocationPattern
    source_projects: list[str] = Field(default_factory=list)
    implementation_count: int = Field(default=0)
    track: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class FunctionPromptsResponse(BaseModel):
    """Response for prompt retrieval endpoints."""

    function_key: str
    function_name: str
    prompt_count: int
    prompts: list[PromptTemplate]


class FunctionImplementationsResponse(BaseModel):
    """Response for implementation retrieval endpoints."""

    function_key: str
    function_name: str
    implementation_count: int
    implementations: list[Implementation]
