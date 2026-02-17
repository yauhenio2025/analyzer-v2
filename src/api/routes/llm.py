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
from src.operationalizations.registry import get_operationalization_registry
from src.operationalizations.schemas import (
    DepthPassEntry,
    DepthSequence,
    EngineOperationalization,
    StanceOperationalization,
)
from src.operations.registry import StanceRegistry

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


# ============================================================================
# Operationalization Generation
# ============================================================================


class OpGenerateRequest(BaseModel):
    """Request to generate a stance operationalization for an engine."""

    engine_key: str = Field(..., description="Engine to generate for")
    stance_key: str = Field(..., description="Stance to operationalize")


class OpGenerateResponse(BaseModel):
    """Response with a generated stance operationalization."""

    engine_key: str
    stance_key: str
    operationalization: StanceOperationalization


class OpGenerateAllRequest(BaseModel):
    """Request to generate operationalizations for all stances on an engine."""

    engine_key: str = Field(..., description="Engine to generate for")
    stance_keys: Optional[list[str]] = Field(
        default=None,
        description="Specific stances to generate for. If None, generates for all known stances.",
    )


class OpGenerateAllResponse(BaseModel):
    """Response with generated operationalizations for an engine."""

    engine_key: str
    engine_name: str
    operationalizations: list[StanceOperationalization]


class OpGenerateSequenceRequest(BaseModel):
    """Request to generate a depth sequence for an engine."""

    engine_key: str = Field(..., description="Engine to generate for")
    depth_key: str = Field(..., description="Depth level (surface, standard, deep)")
    stance_keys: list[str] = Field(
        ...,
        description="Ordered list of stance keys for the passes",
    )


class OpGenerateSequenceResponse(BaseModel):
    """Response with a generated depth sequence."""

    engine_key: str
    depth_sequence: DepthSequence


# Stance registry reference (set during lifespan)
_stance_registry: Optional[StanceRegistry] = None


def init_stance_registry_for_llm(reg: StanceRegistry) -> None:
    """Initialize the stance registry reference for LLM generation."""
    global _stance_registry
    _stance_registry = reg


def _get_stance_registry() -> StanceRegistry:
    """Get the stance registry, failing gracefully."""
    if _stance_registry is not None:
        return _stance_registry
    # Fallback: load fresh
    reg = StanceRegistry()
    return reg


def _build_engine_context(engine_key: str) -> str:
    """Build rich context about an engine for LLM prompts."""
    engine_reg = get_engine_registry()
    cap_def = engine_reg.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(status_code=404, detail=f"No capability definition for engine '{engine_key}'")

    parts = [
        f"## Engine: {cap_def.engine_name}",
        f"**Key**: {cap_def.engine_key}",
        "",
        "### Problematique",
        cap_def.problematique,
        "",
        "### Analytical Dimensions",
    ]

    for dim in cap_def.analytical_dimensions:
        parts.append(f"- **{dim.key}**: {dim.description[:200]}")

    parts.append("")
    parts.append("### Capabilities")

    for cap in cap_def.capabilities:
        parts.append(
            f"- **{cap.key}**: {cap.description} "
            f"(produces: {cap.produces_dimensions}, requires: {cap.requires_dimensions})"
        )

    return "\n".join(parts)


def _build_stance_context(stance_key: str) -> str:
    """Build context about a stance for LLM prompts."""
    reg = _get_stance_registry()
    stance = reg.get(stance_key)
    if stance is None:
        return f"Stance '{stance_key}' (no definition found)"

    return (
        f"## Stance: {stance.name}\n"
        f"**Key**: {stance.key}\n"
        f"**Cognitive mode**: {stance.cognitive_mode}\n"
        f"**Typical position**: {stance.typical_position}\n\n"
        f"### Prose\n{stance.stance}"
    )


@router.post("/operationalization-generate", response_model=OpGenerateResponse)
async def generate_operationalization(request: OpGenerateRequest) -> OpGenerateResponse:
    """Generate a stance operationalization for a specific engine-stance pair.

    Uses Claude to understand the engine's problematique, dimensions, and
    capabilities, then generates a prose description of how this stance
    applies to this specific engine — the operationalization.

    Does NOT auto-save. Returns the generated operationalization for review.
    """
    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY environment variable.",
        )

    engine_context = _build_engine_context(request.engine_key)
    stance_context = _build_stance_context(request.stance_key)

    # Check if there's an existing operationalization for reference
    op_reg = get_operationalization_registry()
    existing = op_reg.get_stance_for_engine(request.engine_key, request.stance_key)
    existing_context = ""
    if existing:
        existing_context = (
            f"\n\n## Existing Operationalization (for reference/improvement)\n"
            f"**Label**: {existing.label}\n"
            f"**Description**: {existing.description}\n"
            f"**Focus dimensions**: {existing.focus_dimensions}\n"
            f"**Focus capabilities**: {existing.focus_capabilities}\n"
        )

    prompt = f"""You are an expert in analytical methodology and philosophical practice.

Your task: Generate an OPERATIONALIZATION of an analytical stance for a specific engine.

An operationalization specifies HOW a particular cognitive posture (the stance) applies
to a particular analytical tool (the engine). It bridges the abstract "think like a
discoverer" with the concrete "here's what discovery means for THIS engine's dimensions."

{engine_context}

{stance_context}
{existing_context}

## Instructions

Generate a JSON object with:
- "label": A concise, engine-specific name for this stance application (e.g., "Commitment Discovery" for discovery + inferential_commitment_mapper)
- "description": 2-4 paragraphs of prose describing what this stance does for THIS engine. Be specific about which dimensions and capabilities to focus on, what the LLM should look for, and how the stance's cognitive mode manifests in this engine's domain.
- "focus_dimensions": List of dimension keys (from the engine's dimensions above) that this stance focuses on
- "focus_capabilities": List of capability keys (from the engine's capabilities above) that this stance exercises

The description should be written as instructions to an LLM analyst — it will be injected
into the analysis prompt alongside the stance's general prose. Make it rich, specific,
and intellectually honest about what this stance can and cannot reveal through this engine.

Output ONLY valid JSON, no markdown code fences."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        data = json.loads(content)
        op = StanceOperationalization(
            stance_key=request.stance_key,
            label=data["label"],
            description=data["description"],
            focus_dimensions=data.get("focus_dimensions", []),
            focus_capabilities=data.get("focus_capabilities", []),
        )

        return OpGenerateResponse(
            engine_key=request.engine_key,
            stance_key=request.stance_key,
            operationalization=op,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {e}")
    except Exception as e:
        logger.error(f"Operationalization generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@router.post("/operationalization-generate-all", response_model=OpGenerateAllResponse)
async def generate_all_operationalizations(request: OpGenerateAllRequest) -> OpGenerateAllResponse:
    """Generate operationalizations for all (or selected) stances on an engine.

    Generates a StanceOperationalization for each stance, using the engine's
    full context. This is useful when adding a new engine or refreshing all
    operationalizations.

    Does NOT auto-save.
    """
    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY environment variable.",
        )

    engine_reg = get_engine_registry()
    cap_def = engine_reg.get_capability_definition(request.engine_key)
    if cap_def is None:
        raise HTTPException(status_code=404, detail=f"No capability definition for engine '{request.engine_key}'")

    engine_context = _build_engine_context(request.engine_key)

    # Get stance keys to generate for
    stance_reg = _get_stance_registry()
    if request.stance_keys:
        stance_keys = request.stance_keys
    else:
        stance_keys = [s.key for s in stance_reg.list_all()]

    # Build stance descriptions
    stance_descriptions = []
    for sk in stance_keys:
        stance_descriptions.append(_build_stance_context(sk))

    stances_block = "\n\n---\n\n".join(stance_descriptions)

    prompt = f"""You are an expert in analytical methodology and philosophical practice.

Your task: Generate OPERATIONALIZATIONS for ALL of the following analytical stances
applied to a specific engine.

{engine_context}

## Stances to Operationalize

{stances_block}

## Instructions

For EACH stance, generate a JSON object. Return a JSON array of objects, one per stance:
[
  {{
    "stance_key": "the_stance_key",
    "label": "Engine-specific label for this stance application",
    "description": "2-4 paragraphs of prose describing what this stance does for THIS engine...",
    "focus_dimensions": ["dim1", "dim2"],
    "focus_capabilities": ["cap1", "cap2"]
  }},
  ...
]

Each description should be specific to this engine, referencing its dimensions and capabilities.
The label should be a concise name like "Commitment Discovery" or "Framework Architecture."

Output ONLY valid JSON array, no markdown code fences."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5-20251101",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )

        content = response.content[0].text
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        data = json.loads(content)
        ops = [
            StanceOperationalization(
                stance_key=item["stance_key"],
                label=item["label"],
                description=item["description"],
                focus_dimensions=item.get("focus_dimensions", []),
                focus_capabilities=item.get("focus_capabilities", []),
            )
            for item in data
        ]

        return OpGenerateAllResponse(
            engine_key=request.engine_key,
            engine_name=cap_def.engine_name,
            operationalizations=ops,
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {e}")
    except Exception as e:
        logger.error(f"Bulk operationalization generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")


@router.post("/operationalization-generate-sequence", response_model=OpGenerateSequenceResponse)
async def generate_depth_sequence(request: OpGenerateSequenceRequest) -> OpGenerateSequenceResponse:
    """Generate a depth sequence for an engine given an ordered list of stances.

    The LLM determines the data flow (consumes_from) between passes based on
    the engine's dimensions and what each stance produces.

    Does NOT auto-save.
    """
    client = get_anthropic_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="LLM service unavailable. Set ANTHROPIC_API_KEY environment variable.",
        )

    engine_context = _build_engine_context(request.engine_key)

    # Get operationalizations for the stances
    op_reg = get_operationalization_registry()
    stance_details = []
    for i, sk in enumerate(request.stance_keys, 1):
        stance_op = op_reg.get_stance_for_engine(request.engine_key, sk)
        if stance_op:
            stance_details.append(
                f"Pass {i}: **{sk}** — {stance_op.label}\n"
                f"  Focus dimensions: {stance_op.focus_dimensions}\n"
                f"  Focus capabilities: {stance_op.focus_capabilities}"
            )
        else:
            stance_details.append(f"Pass {i}: **{sk}** (no operationalization yet)")

    stances_block = "\n".join(stance_details)

    prompt = f"""You are an expert in multi-pass analytical workflows.

Given an engine and an ordered sequence of analytical stances, determine the data flow
between passes. Each later pass may consume the output of earlier passes.

{engine_context}

## Proposed Sequence for depth="{request.depth_key}"

{stances_block}

## Instructions

For each pass, determine which earlier passes it should consume from (consumes_from).
A pass should consume from an earlier pass when it needs that pass's analytical output
as context to do its work effectively.

Return a JSON array:
[
  {{"pass_number": 1, "stance_key": "{request.stance_keys[0] if request.stance_keys else ''}", "consumes_from": []}},
  ...
]

Rules:
- Pass 1 always has consumes_from: [] (nothing to consume)
- Later passes typically consume from at least one earlier pass
- Integration/synthesis passes usually consume from ALL prior passes
- Confrontation passes typically consume from the discovery pass
- Not every pass needs to consume from every prior pass — be intentional

Output ONLY valid JSON array."""

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

        data = json.loads(content)
        passes = [
            DepthPassEntry(
                pass_number=item["pass_number"],
                stance_key=item["stance_key"],
                consumes_from=item.get("consumes_from", []),
            )
            for item in data
        ]

        return OpGenerateSequenceResponse(
            engine_key=request.engine_key,
            depth_sequence=DepthSequence(
                depth_key=request.depth_key,
                passes=passes,
            ),
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM response: {e}")
    except Exception as e:
        logger.error(f"Sequence generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
