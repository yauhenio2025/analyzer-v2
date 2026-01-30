"""LLM-powered routes for profile generation and suggestions.

Uses Claude (via Anthropic API) to generate and enhance engine profiles.
Requires ANTHROPIC_API_KEY environment variable to be set.
"""

import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.engines.registry import get_engine_registry
from src.engines.schemas import EngineProfile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])

# ============================================================================
# Request/Response Schemas
# ============================================================================


class ProfileGenerateRequest(BaseModel):
    """Request to generate a profile for an engine."""

    engine_key: str = Field(..., description="Key of the engine to generate profile for")
    regenerate_fields: Optional[list[str]] = Field(
        default=None,
        description="Specific fields to regenerate. If None, generates full profile.",
        examples=[["theoretical_foundations", "use_cases"]],
    )


class ProfileGenerateResponse(BaseModel):
    """Response from profile generation."""

    engine_key: str
    profile: EngineProfile
    fields_generated: list[str]


class ProfileSuggestionRequest(BaseModel):
    """Request to get suggestions for improving a specific profile field."""

    engine_key: str = Field(..., description="Key of the engine")
    field: str = Field(
        ...,
        description="Field to get suggestions for",
        examples=["theoretical_foundations", "use_cases", "strengths"],
    )
    improvement_goal: str = Field(
        default="",
        description="What kind of improvement is desired",
        examples=["more specific", "more practical examples", "academic rigor"],
    )


class ProfileSuggestionResponse(BaseModel):
    """Response with suggestions for improving a profile field."""

    engine_key: str
    field: str
    suggestions: list[str]
    improved_content: Optional[dict] = None


# ============================================================================
# LLM Client
# ============================================================================


def get_anthropic_client():
    """Get Anthropic client if API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic

        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic library not installed")
        return None


def generate_profile_with_llm(
    engine_key: str,
    engine_name: str,
    description: str,
    category: str,
    kind: str,
    reasoning_domain: str,
    researcher_question: str,
    schema_summary: str,
    existing_profile: Optional[EngineProfile] = None,
    regenerate_fields: Optional[list[str]] = None,
) -> EngineProfile:
    """Generate an engine profile using Claude."""
    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY environment variable.",
        )

    # Build prompt
    prompt = f"""You are an expert in analytical methodology and philosophy of science.
Generate a rich "About" profile for an analytical engine. The profile should help users understand:
- The theoretical foundations behind the engine's approach
- Key thinkers whose work informs it
- The methodology and analytical moves it makes
- What it extracts from texts
- Practical use cases
- Strengths and limitations
- Related engines

## Engine Information

**Key**: {engine_key}
**Name**: {engine_name}
**Description**: {description}
**Category**: {category}
**Kind**: {kind}
**Reasoning Domain**: {reasoning_domain}
**Researcher Question**: {researcher_question}

**Schema Summary** (what the engine outputs):
{schema_summary}

## Instructions

Generate a profile as JSON matching this structure:
{{
  "theoretical_foundations": [
    {{"name": "Foundation Name", "description": "Brief explanation", "source_thinker": "Key thinker (optional)"}}
  ],
  "key_thinkers": [
    {{"name": "Thinker Name", "contribution": "What they contributed", "works": ["Key work 1", "Key work 2"]}}
  ],
  "methodology": {{
    "approach": "Plain-language description of the methodology (2-3 sentences)",
    "key_moves": ["Step 1", "Step 2", "Step 3"],
    "conceptual_tools": ["Tool 1", "Tool 2"]
  }},
  "extracts": {{
    "primary_outputs": ["What it mainly extracts"],
    "secondary_outputs": ["Supporting extractions"],
    "relationships": ["Types of relationships identified"]
  }},
  "use_cases": [
    {{"domain": "Domain name", "description": "How the engine helps", "example": "Optional concrete example"}}
  ],
  "strengths": ["Strength 1", "Strength 2"],
  "limitations": ["Limitation 1", "Limitation 2"],
  "related_engines": [
    {{"engine_key": "related_engine_key", "relationship": "complementary|alternative|prerequisite|extends"}}
  ],
  "preamble": "A brief paragraph that could be injected into prompts to provide context about this engine's approach."
}}

Be specific and insightful. Draw on your knowledge of philosophy, methodology, and analytical frameworks.
For theoretical foundations, identify the actual philosophical or methodological traditions that inform this approach.
For key thinkers, only include those genuinely relevant - don't pad with names.
For use cases, be practical and concrete.

Output ONLY valid JSON, no markdown code fences or other text."""

    if regenerate_fields:
        prompt += f"\n\nNote: Only regenerate these specific fields: {', '.join(regenerate_fields)}. For other fields, use reasonable defaults or leave empty."

    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        content = response.content[0].text
        # Clean up potential markdown fences
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        profile_data = json.loads(content)
        return EngineProfile(**profile_data)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse LLM response: {e}",
        )
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM generation failed: {e}",
        )


def get_schema_summary(schema: dict) -> str:
    """Extract a summary of key fields from a JSON schema."""
    if not schema:
        return "No schema available"

    # Get top-level keys and their types
    summary_parts = []
    for key, value in schema.items():
        if isinstance(value, list) and len(value) > 0:
            if isinstance(value[0], dict):
                inner_keys = list(value[0].keys())[:5]
                summary_parts.append(f"- {key}: list of objects with {', '.join(inner_keys)}")
            else:
                summary_parts.append(f"- {key}: list")
        elif isinstance(value, dict):
            inner_keys = list(value.keys())[:5]
            summary_parts.append(f"- {key}: object with {', '.join(inner_keys)}")
        else:
            summary_parts.append(f"- {key}")

    return "\n".join(summary_parts[:20])  # Limit to top 20 fields


# ============================================================================
# Routes
# ============================================================================


@router.post("/profile-generate", response_model=ProfileGenerateResponse)
async def generate_profile(request: ProfileGenerateRequest) -> ProfileGenerateResponse:
    """Generate a full or partial profile for an engine using LLM.

    This endpoint uses Claude to analyze the engine's definition and
    generate rich metadata including theoretical foundations, methodology,
    use cases, and more.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    registry = get_engine_registry()
    engine = registry.get(request.engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {request.engine_key}",
        )

    # Get schema summary
    schema_summary = get_schema_summary(engine.canonical_schema)

    # Generate profile
    profile = generate_profile_with_llm(
        engine_key=engine.engine_key,
        engine_name=engine.engine_name,
        description=engine.description,
        category=engine.category.value,
        kind=engine.kind.value,
        reasoning_domain=engine.reasoning_domain,
        researcher_question=engine.researcher_question,
        schema_summary=schema_summary,
        existing_profile=engine.engine_profile,
        regenerate_fields=request.regenerate_fields,
    )

    fields_generated = request.regenerate_fields or [
        "theoretical_foundations",
        "key_thinkers",
        "methodology",
        "extracts",
        "use_cases",
        "strengths",
        "limitations",
        "related_engines",
        "preamble",
    ]

    return ProfileGenerateResponse(
        engine_key=request.engine_key,
        profile=profile,
        fields_generated=fields_generated,
    )


@router.post("/profile-suggestions", response_model=ProfileSuggestionResponse)
async def get_profile_suggestions(
    request: ProfileSuggestionRequest,
) -> ProfileSuggestionResponse:
    """Get AI suggestions for improving a specific profile field.

    Analyzes the engine and current profile to suggest improvements
    for a specific field like theoretical_foundations, use_cases, etc.

    Requires ANTHROPIC_API_KEY environment variable.
    """
    registry = get_engine_registry()
    engine = registry.get(request.engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {request.engine_key}",
        )

    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY environment variable.",
        )

    # Build context about current profile
    current_value = None
    if engine.engine_profile:
        current_value = getattr(engine.engine_profile, request.field, None)
        if current_value is not None:
            if hasattr(current_value, "model_dump"):
                current_value = current_value.model_dump()
            elif isinstance(current_value, list):
                current_value = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in current_value
                ]

    prompt = f"""You are an expert in analytical methodology.
Suggest improvements for the "{request.field}" field of an engine profile.

## Engine Information
**Name**: {engine.engine_name}
**Description**: {engine.description}
**Category**: {engine.category.value}
**Reasoning Domain**: {engine.reasoning_domain}

## Current Value
{json.dumps(current_value, indent=2) if current_value else "No current value"}

## Improvement Goal
{request.improvement_goal or "General improvement"}

## Instructions
Provide:
1. 3-5 specific suggestions for improving this field
2. An improved version of the content if applicable

Output as JSON:
{{
  "suggestions": ["Suggestion 1", "Suggestion 2", ...],
  "improved_content": {{ ... }} // The improved field value, or null if not applicable
}}

Output ONLY valid JSON."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        result = json.loads(content)

        return ProfileSuggestionResponse(
            engine_key=request.engine_key,
            field=request.field,
            suggestions=result.get("suggestions", []),
            improved_content=result.get("improved_content"),
        )

    except Exception as e:
        logger.error(f"Suggestion generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Suggestion generation failed: {e}",
        )


@router.get("/status")
async def llm_status() -> dict:
    """Check if LLM service is available."""
    client = get_anthropic_client()
    return {
        "available": client is not None,
        "model": "claude-opus-4-5-20251101" if client else None,
        "message": "LLM service ready" if client else "Set ANTHROPIC_API_KEY to enable LLM features",
    }
