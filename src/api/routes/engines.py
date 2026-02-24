"""Engine API routes.

MIGRATION NOTES (2026-01-29):
- Prompt endpoints now COMPOSE prompts at runtime using StageComposer
- Added 'audience' query parameter for audience-specific vocabulary
- Added new /stages/* endpoints for template/framework access
"""

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from src.engines.registry import get_engine_registry
from src.engines.schemas import (
    EngineCategory,
    EngineDefinition,
    EngineProfile,
    EngineProfileResponse,
    EnginePromptResponse,
    EngineSchemaResponse,
    EngineSummary,
)
from src.engines.schemas_v2 import (
    CapabilityEngineDefinition,
    CapabilityEngineSummary,
)
from src.stages.capability_composer import (
    CapabilityPrompt,
    PassPrompt,
    compose_capability_prompt,
    compose_pass_prompt,
    compose_all_pass_prompts,
)
from src.stages.composer import StageComposer
from src.stages.registry import get_stage_registry

router = APIRouter(prefix="/engines", tags=["engines"])

# Lazy-loaded composer
_composer: Optional[StageComposer] = None


def get_composer() -> StageComposer:
    """Get or create the StageComposer singleton."""
    global _composer
    if _composer is None:
        _composer = StageComposer()
    return _composer


AudienceType = Literal["researcher", "analyst", "executive", "activist", "social_movements"]


@router.get("", response_model=list[EngineSummary])
async def list_engines(
    category: Optional[EngineCategory] = Query(
        None, description="Filter by category"
    ),
    paradigm: Optional[str] = Query(
        None, description="Filter by associated paradigm key"
    ),
    app: Optional[str] = Query(
        None, description="Filter by app that uses the engine (e.g., 'critic')"
    ),
    function: Optional[str] = Query(
        None, description="Filter by function (e.g., 'genealogy', 'logic')"
    ),
    search: Optional[str] = Query(
        None, description="Search in name and description"
    ),
) -> list[EngineSummary]:
    """List all engines with optional filtering."""
    registry = get_engine_registry()

    if search:
        engines = registry.search(search)
    elif category:
        engines = registry.list_by_category(category)
    elif paradigm:
        engines = registry.list_by_paradigm(paradigm)
    else:
        engines = registry.list_all()

    # Apply app filter if specified
    if app:
        engines = [e for e in engines if app in e.apps]

    # Build function lookup from capability definitions (YAML) since function
    # is primarily defined there, not in JSON engine definitions
    cap_function_map: dict[str, str] = {}
    for cap_def in registry.list_capability_definitions():
        if cap_def.function:
            cap_function_map[cap_def.engine_key] = cap_def.function

    def resolve_function(e: EngineDefinition) -> Optional[str]:
        """Get function from engine itself or its capability definition."""
        return e.function or cap_function_map.get(e.engine_key)

    # Apply function filter if specified
    if function:
        engines = [e for e in engines if resolve_function(e) == function]

    return [
        EngineSummary(
            engine_key=e.engine_key,
            engine_name=e.engine_name,
            description=e.description,
            category=e.category,
            kind=e.kind,
            version=e.version,
            paradigm_keys=e.paradigm_keys,
            has_profile=e.engine_profile is not None,
            apps=e.apps,
            function=resolve_function(e),
        )
        for e in engines
    ]


@router.get("/keys", response_model=list[str])
async def list_engine_keys() -> list[str]:
    """List all engine keys."""
    registry = get_engine_registry()
    return registry.list_keys()


@router.get("/count")
async def get_engine_count() -> dict[str, int]:
    """Get total number of engines."""
    registry = get_engine_registry()
    return {"count": registry.count()}


@router.get("/apps", response_model=list[str])
async def list_apps() -> list[str]:
    """List all unique app tags used across engines."""
    registry = get_engine_registry()
    apps = set()
    for engine in registry.list_all():
        apps.update(engine.apps)
    return sorted(apps)


@router.get("/functions", response_model=list[str])
async def list_functions() -> list[str]:
    """List all unique function tags used across engines."""
    registry = get_engine_registry()
    functions = set()
    # Check JSON engines
    for engine in registry.list_all():
        if engine.function:
            functions.add(engine.function)
    # Check capability engines (YAML) - function is primarily defined here
    for cap_engine in registry.list_capability_definitions():
        if cap_engine.function:
            functions.add(cap_engine.function)
    return sorted(functions)


@router.get("/categories")
async def list_categories() -> dict[str, dict[str, int]]:
    """Get engine counts by category."""
    registry = get_engine_registry()
    counts: dict[str, int] = {}
    for engine in registry.list_all():
        cat = engine.category.value
        counts[cat] = counts.get(cat, 0) + 1
    return {"categories": counts}


@router.get("/category/{category}", response_model=list[EngineSummary])
async def list_engines_by_category(
    category: EngineCategory,
) -> list[EngineSummary]:
    """List engines in a specific category."""
    registry = get_engine_registry()
    engines = registry.list_by_category(category)

    # Build function lookup from capability definitions
    cap_function_map: dict[str, str] = {}
    for cap_def in registry.list_capability_definitions():
        if cap_def.function:
            cap_function_map[cap_def.engine_key] = cap_def.function

    return [
        EngineSummary(
            engine_key=e.engine_key,
            engine_name=e.engine_name,
            description=e.description,
            category=e.category,
            kind=e.kind,
            version=e.version,
            paradigm_keys=e.paradigm_keys,
            has_profile=e.engine_profile is not None,
            apps=e.apps,
            function=e.function or cap_function_map.get(e.engine_key),
        )
        for e in engines
    ]


# ── Capability definitions (v2 format) ──────────────────────


@router.get("/capability-definitions", response_model=list[CapabilityEngineSummary])
async def list_capability_definitions() -> list[CapabilityEngineSummary]:
    """List all capability engine definitions (v2 format).

    Returns lightweight summaries of engines that have capability-driven
    definitions (problematique, analytical dimensions, composability).
    """
    registry = get_engine_registry()
    return registry.list_capability_summaries()


# ── Legacy engine endpoints ──────────────────────


@router.get("/{engine_key}", response_model=EngineDefinition)
async def get_engine(engine_key: str) -> EngineDefinition:
    """Get full engine definition including stage_context and schema."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return engine


@router.get("/{engine_key}/extraction-prompt", response_model=EnginePromptResponse)
async def get_extraction_prompt(
    engine_key: str,
    audience: AudienceType = Query(
        "analyst",
        description="Target audience for vocabulary calibration",
    ),
) -> EnginePromptResponse:
    """Get COMPOSED extraction prompt for an engine.

    The prompt is composed at runtime from:
    - Generic extraction template
    - Engine's stage_context
    - Framework primer (if specified)
    - Audience-specific vocabulary
    """
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )

    composer = get_composer()
    try:
        composed = composer.compose(
            stage="extraction",
            engine_key=engine_key,
            stage_context=engine.stage_context,
            audience=audience,
            canonical_schema=engine.canonical_schema,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compose prompt: {e}",
        )

    return EnginePromptResponse(
        engine_key=engine_key,
        prompt_type="extraction",
        prompt=composed.prompt,
        audience=audience,
        framework_used=composed.framework_used,
    )


@router.get("/{engine_key}/curation-prompt", response_model=EnginePromptResponse)
async def get_curation_prompt(
    engine_key: str,
    audience: AudienceType = Query(
        "analyst",
        description="Target audience for vocabulary calibration",
    ),
) -> EnginePromptResponse:
    """Get COMPOSED curation prompt for an engine."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )

    composer = get_composer()
    try:
        composed = composer.compose(
            stage="curation",
            engine_key=engine_key,
            stage_context=engine.stage_context,
            audience=audience,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compose prompt: {e}",
        )

    return EnginePromptResponse(
        engine_key=engine_key,
        prompt_type="curation",
        prompt=composed.prompt,
        audience=audience,
        framework_used=composed.framework_used,
    )


@router.get(
    "/{engine_key}/concretization-prompt", response_model=EnginePromptResponse
)
async def get_concretization_prompt(
    engine_key: str,
    audience: AudienceType = Query(
        "analyst",
        description="Target audience for vocabulary calibration",
    ),
) -> EnginePromptResponse:
    """Get COMPOSED concretization prompt for an engine (if not skipped)."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )

    if engine.stage_context.skip_concretization:
        raise HTTPException(
            status_code=404,
            detail=f"Engine {engine_key} has no concretization stage",
        )

    composer = get_composer()
    try:
        composed = composer.compose(
            stage="concretization",
            engine_key=engine_key,
            stage_context=engine.stage_context,
            audience=audience,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compose prompt: {e}",
        )

    return EnginePromptResponse(
        engine_key=engine_key,
        prompt_type="concretization",
        prompt=composed.prompt,
        audience=audience,
        framework_used=composed.framework_used,
    )


@router.get("/{engine_key}/schema", response_model=EngineSchemaResponse)
async def get_engine_schema(engine_key: str) -> EngineSchemaResponse:
    """Get canonical schema for an engine."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return EngineSchemaResponse(
        engine_key=engine_key,
        canonical_schema=engine.canonical_schema,
    )


@router.get("/{engine_key}/stage-context")
async def get_stage_context(engine_key: str) -> dict:
    """Get raw stage context for an engine (for debugging/inspection)."""
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return engine.stage_context.model_dump()


@router.get("/{engine_key}/visual-intent")
async def get_visual_intent(engine_key: str) -> dict:
    """Get semantic visual intent for an engine.

    Returns the semantic_visual_intent specification that tells the Visualizer
    what this analysis MEANS and how to make that meaning visible.

    This bridges analytical meaning to visual form - not just "this data has
    nodes and edges" but "this is feedback analysis, show actual loops with
    reinforcing/balancing indicators."

    Returns:
        - primary_concept: The core analytical concept
        - visual_grammar: Core metaphor, key elements, anti-patterns
        - gemini_semantic_prompt: Meaning-focused prompt for Gemini
        - recommended_forms: Visual forms appropriate for this analysis
        - form_selection_logic: Logic for choosing among forms
        - style_affinity: Preferred dataviz styles

    Returns empty dict with has_semantic_intent=false if engine has no
    semantic visual intent specified.
    """
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )

    concretization = engine.stage_context.concretization
    semantic_intent = concretization.semantic_visual_intent

    if semantic_intent is None:
        return {
            "engine_key": engine_key,
            "has_semantic_intent": False,
            "semantic_visual_intent": None,
            # Fall back to legacy recommended_visual_patterns if available
            "legacy_visual_patterns": concretization.recommended_visual_patterns or [],
        }

    return {
        "engine_key": engine_key,
        "has_semantic_intent": True,
        "semantic_visual_intent": semantic_intent.model_dump(),
    }


@router.get("/{engine_key}/profile", response_model=EngineProfileResponse)
async def get_engine_profile(engine_key: str) -> EngineProfileResponse:
    """Get rich profile/about section for an engine.

    Returns theoretical foundations, methodology, use cases, strengths,
    limitations, and related engines. Returns has_profile=false if
    no profile exists yet.
    """
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )
    return EngineProfileResponse(
        engine_key=engine_key,
        engine_name=engine.engine_name,
        has_profile=engine.engine_profile is not None,
        profile=engine.engine_profile,
    )


@router.put("/{engine_key}/profile", response_model=EngineProfileResponse)
async def save_engine_profile(
    engine_key: str, profile: EngineProfile
) -> EngineProfileResponse:
    """Save or update the profile for an engine.

    This persists the profile to the engine's JSON definition file.
    """
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )

    success = registry.save_profile(engine_key, profile)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save profile for engine: {engine_key}",
        )

    return EngineProfileResponse(
        engine_key=engine_key,
        engine_name=engine.engine_name,
        has_profile=True,
        profile=profile,
    )


@router.delete("/{engine_key}/profile")
async def delete_engine_profile(engine_key: str) -> dict:
    """Delete the profile for an engine.

    This removes the profile from the engine's JSON definition file.
    """
    registry = get_engine_registry()
    engine = registry.get(engine_key)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine not found: {engine_key}",
        )

    if engine.engine_profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine {engine_key} has no profile to delete",
        )

    success = registry.delete_profile(engine_key)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete profile for engine: {engine_key}",
        )

    return {"status": "deleted", "engine_key": engine_key}


@router.get("/{engine_key}/capability-definition", response_model=CapabilityEngineDefinition)
async def get_capability_definition(engine_key: str) -> CapabilityEngineDefinition:
    """Get capability-driven engine definition (v2 format).

    Returns the rich intellectual description of what this engine investigates:
    problematique, analytical dimensions with probing questions, capabilities
    with dependency graph, composability spec, and depth levels.

    This is the NEW format that describes WHAT the engine investigates,
    not HOW it formats output.
    """
    registry = get_engine_registry()
    cap_def = registry.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"No capability definition found for engine: {engine_key}. "
            f"Available: {registry.list_capability_keys()}",
        )
    return cap_def


@router.get("/{engine_key}/capability-definition/history")
async def get_capability_history(
    engine_key: str,
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
) -> dict:
    """Get change history for a capability engine definition.

    Returns timestamped history entries with field-level diffs,
    sorted newest first. History is auto-detected by comparing
    YAML files against stored snapshots on startup/reload.
    """
    registry = get_engine_registry()
    cap_def = registry.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"No capability definition found for engine: {engine_key}",
        )

    from src.engines.history_tracker import load_history

    history = load_history(engine_key)
    return {
        "engine_key": engine_key,
        "entry_count": len(history.entries),
        "entries": [e.model_dump(mode="json") for e in history.entries[:limit]],
    }


@router.get("/{engine_key}/capability-prompt", response_model=CapabilityPrompt)
async def get_capability_prompt(
    engine_key: str,
    depth: str = Query(
        "standard",
        description="Analysis depth: surface, standard, or deep",
        pattern="^(surface|standard|deep)$",
    ),
    dimensions: Optional[str] = Query(
        None,
        description="Comma-separated dimension keys to focus on (default: all)",
    ),
) -> CapabilityPrompt:
    """Get a prose-focused prompt composed from the capability definition.

    This prompt asks the LLM for analytical PROSE output — not JSON.
    It includes the engine's problematique, selected analytical dimensions
    with probing questions, and depth-specific guidance.

    Use this for the new schema-on-read architecture where LLM output
    is saved as plain text and structured data is extracted at presentation time.
    """
    registry = get_engine_registry()
    cap_def = registry.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"No capability definition found for engine: {engine_key}. "
            f"Available: {registry.list_capability_keys()}",
        )

    focus_dims = dimensions.split(",") if dimensions else None

    return compose_capability_prompt(
        cap_def=cap_def,
        depth=depth,
        focus_dimensions=focus_dims,
    )


@router.get("/{engine_key}/pass-prompts", response_model=list[PassPrompt])
async def get_pass_prompts(
    engine_key: str,
    depth: str = Query(
        "standard",
        description="Analysis depth: surface, standard, or deep",
        pattern="^(surface|standard|deep)$",
    ),
) -> list[PassPrompt]:
    """Get per-pass prompts for a capability engine at a given depth.

    Returns one prompt per pass, each with:
    - The engine's intellectual framing
    - The analytical stance (cognitive posture) for that pass
    - Only the dimensions that pass focuses on
    - Pass-specific description

    Shared context is NOT filled in (that happens at runtime when prior
    pass output is available). This endpoint is for previewing the full
    pass structure.

    Returns empty list if the engine has no pass definitions at this depth.
    Falls back gracefully — engines without pass definitions still work
    via the whole-engine capability-prompt endpoint.
    """
    registry = get_engine_registry()
    cap_def = registry.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"No capability definition found for engine: {engine_key}. "
            f"Available: {registry.list_capability_keys()}",
        )

    prompts = compose_all_pass_prompts(cap_def=cap_def, depth=depth)
    return prompts


@router.get("/{engine_key}/pass-prompts/{pass_number}", response_model=PassPrompt)
async def get_single_pass_prompt(
    engine_key: str,
    pass_number: int,
    depth: str = Query(
        "standard",
        description="Analysis depth: surface, standard, or deep",
        pattern="^(surface|standard|deep)$",
    ),
) -> PassPrompt:
    """Get the prompt for a single pass of a capability engine.

    Useful for inspecting what a specific pass does, or for runtime
    prompt generation when you want to supply shared_context separately.
    """
    registry = get_engine_registry()
    cap_def = registry.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"No capability definition found for engine: {engine_key}",
        )

    # Find the depth level
    depth_level = None
    for dl in cap_def.depth_levels:
        if dl.key == depth:
            depth_level = dl
            break

    if not depth_level or not depth_level.passes:
        raise HTTPException(
            status_code=404,
            detail=f"No pass definitions for {engine_key} at depth={depth}. "
            f"Use the /capability-prompt endpoint for whole-engine prompts.",
        )

    # Find the specific pass
    pass_def = None
    for p in depth_level.passes:
        if p.pass_number == pass_number:
            pass_def = p
            break

    if pass_def is None:
        available = [p.pass_number for p in depth_level.passes]
        raise HTTPException(
            status_code=404,
            detail=f"Pass {pass_number} not found. Available passes: {available}",
        )

    return compose_pass_prompt(
        cap_def=cap_def,
        pass_def=pass_def,
        depth=depth,
    )


@router.post("/reload")
async def reload_engines() -> dict[str, str]:
    """Force reload all engine definitions from disk."""
    registry = get_engine_registry()
    registry.reload()
    # Also reload stage templates/frameworks
    stage_registry = get_stage_registry()
    stage_registry.reload()
    return {"status": "reloaded", "count": str(registry.count())}
