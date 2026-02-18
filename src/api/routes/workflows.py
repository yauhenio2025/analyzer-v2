"""Workflow API routes.

Provides CRUD operations for workflow definitions and phase prompt composition.
"""

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query

from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.stages.composer import StageComposer
from src.workflows.extension_points import WorkflowExtensionAnalysis
from src.workflows.extension_scorer import analyze_workflow_extensions
from src.workflows.registry import get_workflow_registry
from src.workflows.schemas import (
    WorkflowCategory,
    WorkflowDefinition,
    WorkflowPhase,
    WorkflowSummary,
)

# Lazy-loaded composer for phase prompt composition
_composer: Optional[StageComposer] = None


def get_composer() -> StageComposer:
    """Get or create the StageComposer singleton."""
    global _composer
    if _composer is None:
        _composer = StageComposer()
    return _composer


AudienceType = Literal["researcher", "analyst", "executive", "activist", "social_movements"]

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("", response_model=list[WorkflowSummary])
async def list_workflows(
    category: Optional[WorkflowCategory] = Query(
        None, description="Filter by category"
    ),
) -> list[WorkflowSummary]:
    """List all workflows with optional filtering."""
    registry = get_workflow_registry()

    if category:
        return registry.list_by_category(category)
    return registry.list_all()


@router.get("/keys", response_model=list[str])
async def list_workflow_keys() -> list[str]:
    """List all workflow keys."""
    registry = get_workflow_registry()
    return registry.get_workflow_keys()


@router.get("/count")
async def get_workflow_count() -> dict[str, int]:
    """Get total number of workflows."""
    registry = get_workflow_registry()
    return {"count": registry.count()}


@router.get("/category/{category}", response_model=list[WorkflowSummary])
async def list_workflows_by_category(category: WorkflowCategory) -> list[WorkflowSummary]:
    """List workflows in a specific category."""
    registry = get_workflow_registry()
    return registry.list_by_category(category)


@router.get("/{workflow_key}", response_model=WorkflowDefinition)
async def get_workflow(workflow_key: str) -> WorkflowDefinition:
    """Get full workflow definition."""
    registry = get_workflow_registry()
    workflow = registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )
    return workflow


@router.get("/{workflow_key}/extension-points", response_model=WorkflowExtensionAnalysis)
async def get_extension_points(
    workflow_key: str,
    depth: str = Query("standard", pattern="^(surface|standard|deep)$"),
    phase_number: Optional[float] = Query(None, description="Specific phase to analyze"),
    min_score: float = Query(0.20, description="Minimum composite score to include"),
    max_candidates: int = Query(15, description="Max candidates per phase"),
) -> WorkflowExtensionAnalysis:
    """Analyze extension points for a workflow at a given depth.

    Scores all engines in the system for composability fit with each phase
    and returns ranked candidates with rationale.
    """
    try:
        return analyze_workflow_extensions(
            workflow_key=workflow_key,
            depth=depth,
            phase_number=phase_number,
            min_score=min_score,
            max_candidates=max_candidates,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{workflow_key}/phases", response_model=list[WorkflowPhase])
async def get_workflow_phases(workflow_key: str) -> list[WorkflowPhase]:
    """Get just the phases for a workflow."""
    registry = get_workflow_registry()
    workflow = registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )
    return workflow.phases


# Deprecated alias for backwards compatibility
@router.get("/{workflow_key}/passes", response_model=list[WorkflowPhase], include_in_schema=False)
async def get_workflow_passes_deprecated(workflow_key: str) -> list[WorkflowPhase]:
    """Deprecated: use /phases instead."""
    return await get_workflow_phases(workflow_key)


@router.get("/{workflow_key}/phase/{phase_number}")
async def get_workflow_phase(workflow_key: str, phase_number: float) -> WorkflowPhase:
    """Get a specific phase from a workflow."""
    registry = get_workflow_registry()
    workflow = registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )
    for p in workflow.phases:
        if p.phase_number == phase_number:
            return p
    raise HTTPException(
        status_code=404,
        detail=f"Phase {phase_number} not found in workflow {workflow_key}",
    )


# Deprecated alias for backwards compatibility
@router.get("/{workflow_key}/pass/{pass_number}", include_in_schema=False)
async def get_workflow_pass_deprecated(workflow_key: str, pass_number: float) -> WorkflowPhase:
    """Deprecated: use /phase/{phase_number} instead."""
    return await get_workflow_phase(workflow_key, pass_number)


@router.get("/{workflow_key}/phase/{phase_number}/prompt")
async def get_workflow_phase_prompt(
    workflow_key: str,
    phase_number: float,
    audience: AudienceType = Query(
        "analyst",
        description="Target audience for vocabulary calibration",
    ),
) -> dict:
    """Get the composed prompt for a workflow phase.

    If the phase has an engine_key, composes the extraction prompt for that engine.
    If the phase has a custom prompt_template, returns that template.
    Returns an error if neither is defined.
    """
    workflow_registry = get_workflow_registry()
    workflow = workflow_registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )

    phase_def = None
    for p in workflow.phases:
        if p.phase_number == phase_number:
            phase_def = p
            break
    if phase_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"Phase {phase_number} not found in workflow {workflow_key}",
        )

    # If phase has a chain_key, compose prompts for each engine in the chain
    if phase_def.chain_key:
        chain_registry = get_chain_registry()
        chain = chain_registry.get(phase_def.chain_key)
        if chain is None:
            raise HTTPException(
                status_code=404,
                detail=f"Chain not found: {phase_def.chain_key}",
            )

        engine_registry = get_engine_registry()
        composer = get_composer()
        engine_prompts = []

        for engine_key in chain.engine_keys:
            engine = engine_registry.get(engine_key)
            if engine is None:
                engine_prompts.append({
                    "engine_key": engine_key,
                    "error": f"Engine not found: {engine_key}",
                })
                continue

            try:
                composed = composer.compose(
                    stage="extraction",
                    engine_key=engine_key,
                    stage_context=engine.stage_context,
                    audience=audience,
                    canonical_schema=engine.canonical_schema,
                )
                engine_prompts.append({
                    "engine_key": engine_key,
                    "prompt": composed.prompt,
                    "framework_used": composed.framework_used,
                })
            except ValueError as e:
                engine_prompts.append({
                    "engine_key": engine_key,
                    "error": f"Failed to compose prompt: {e}",
                })

        return {
            "workflow_key": workflow_key,
            "phase_number": phase_number,
            "phase_name": phase_def.phase_name,
            "chain_key": phase_def.chain_key,
            "engine_key": None,
            "prompt_type": "chain",
            "blend_mode": chain.blend_mode.value,
            "engine_prompts": engine_prompts,
            "context_parameters": phase_def.context_parameters,
            "context_parameter_schema": chain.context_parameter_schema,
            "audience": audience,
            "framework_used": None,
        }

    # If phase has an engine_key, compose the engine's extraction prompt
    if phase_def.engine_key:
        engine_registry = get_engine_registry()
        engine = engine_registry.get(phase_def.engine_key)
        if engine is None:
            raise HTTPException(
                status_code=404,
                detail=f"Engine not found: {phase_def.engine_key}",
            )

        composer = get_composer()
        try:
            composed = composer.compose(
                stage="extraction",
                engine_key=phase_def.engine_key,
                stage_context=engine.stage_context,
                audience=audience,
                canonical_schema=engine.canonical_schema,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to compose prompt: {e}",
            )

        return {
            "workflow_key": workflow_key,
            "phase_number": phase_number,
            "phase_name": phase_def.phase_name,
            "engine_key": phase_def.engine_key,
            "prompt_type": "extraction",
            "prompt": composed.prompt,
            "context_parameters": phase_def.context_parameters,
            "audience": audience,
            "framework_used": composed.framework_used,
        }

    # If phase has a custom prompt template, return it
    if phase_def.prompt_template:
        return {
            "workflow_key": workflow_key,
            "phase_number": phase_number,
            "phase_name": phase_def.phase_name,
            "engine_key": None,
            "prompt_type": "custom_template",
            "prompt": phase_def.prompt_template,
            "context_parameters": phase_def.context_parameters,
            "audience": audience,
            "framework_used": None,
        }

    # Neither engine, chain, nor template defined
    raise HTTPException(
        status_code=404,
        detail=f"Phase {phase_number} has no engine_key, chain_key, or prompt_template defined",
    )


# Deprecated alias for backwards compatibility
@router.get("/{workflow_key}/pass/{pass_number}/prompt", include_in_schema=False)
async def get_workflow_pass_prompt_deprecated(
    workflow_key: str,
    pass_number: float,
    audience: AudienceType = Query("analyst"),
) -> dict:
    """Deprecated: use /phase/{phase_number}/prompt instead."""
    return await get_workflow_phase_prompt(workflow_key, pass_number, audience)


@router.post("", response_model=WorkflowDefinition)
async def create_workflow(definition: WorkflowDefinition) -> WorkflowDefinition:
    """Create a new workflow definition.

    The workflow_key in the definition is used as the identifier.
    Returns an error if a workflow with that key already exists.
    """
    registry = get_workflow_registry()

    # Check if workflow already exists
    existing = registry.get(definition.workflow_key)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Workflow already exists: {definition.workflow_key}",
        )

    success = registry.save(definition.workflow_key, definition)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create workflow: {definition.workflow_key}",
        )

    return definition


@router.put("/{workflow_key}", response_model=WorkflowDefinition)
async def update_workflow(
    workflow_key: str, definition: WorkflowDefinition
) -> WorkflowDefinition:
    """Update an existing workflow definition.

    The workflow_key in the URL must match the definition's workflow_key.
    """
    if workflow_key != definition.workflow_key:
        raise HTTPException(
            status_code=400,
            detail="URL workflow_key must match definition's workflow_key",
        )

    registry = get_workflow_registry()

    # Check if workflow exists
    existing = registry.get(workflow_key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )

    success = registry.save(workflow_key, definition)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update workflow: {workflow_key}",
        )

    return definition


@router.put("/{workflow_key}/phase/{phase_number}", response_model=WorkflowPhase)
async def update_workflow_phase(
    workflow_key: str, phase_number: float, phase_def: WorkflowPhase
) -> WorkflowPhase:
    """Update a single phase in a workflow.

    The phase_number in the URL must match the phase_def's phase_number.
    """
    if phase_number != phase_def.phase_number:
        raise HTTPException(
            status_code=400,
            detail="URL phase_number must match phase definition's phase_number",
        )

    registry = get_workflow_registry()

    success = registry.update_phase(workflow_key, phase_number, phase_def)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update phase {phase_number} in workflow {workflow_key}",
        )

    return phase_def


# Deprecated alias for backwards compatibility
@router.put("/{workflow_key}/pass/{pass_number}", response_model=WorkflowPhase, include_in_schema=False)
async def update_workflow_pass_deprecated(
    workflow_key: str, pass_number: float, phase_def: WorkflowPhase
) -> WorkflowPhase:
    """Deprecated: use /phase/{phase_number} instead."""
    return await update_workflow_phase(workflow_key, pass_number, phase_def)


@router.delete("/{workflow_key}")
async def delete_workflow(workflow_key: str) -> dict:
    """Delete a workflow definition."""
    registry = get_workflow_registry()

    # Check if workflow exists
    existing = registry.get(workflow_key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow not found: {workflow_key}",
        )

    success = registry.delete(workflow_key)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete workflow: {workflow_key}",
        )

    return {"status": "deleted", "workflow_key": workflow_key}


@router.post("/reload")
async def reload_workflows() -> dict:
    """Force reload all workflow definitions from disk."""
    registry = get_workflow_registry()
    registry.reload()
    return {"status": "reloaded", "count": registry.count()}
