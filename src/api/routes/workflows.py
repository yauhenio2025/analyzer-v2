"""Workflow API routes.

Provides CRUD operations for workflow definitions and phase prompt composition.
"""

import json
import logging
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.chains.registry import get_chain_registry
from src.chains.schemas import BlendMode, EngineChainSpec
from src.engines.registry import get_engine_registry
from src.persistence.github_client import (
    CommitFile,
    GitHubPersistence,
    get_github_persistence,
)
from src.stages.composer import StageComposer
from src.workflows.description_generator import (
    generate_chain_description,
    generate_phase_description,
)
from src.api.routes.meta import mark_definitions_modified
from src.workflows.extension_points import WorkflowExtensionAnalysis
from src.workflows.extension_scorer import analyze_workflow_extensions
from src.workflows.registry import get_workflow_registry
from src.workflows.schemas import (
    WorkflowCategory,
    WorkflowDefinition,
    WorkflowPhase,
    WorkflowSummary,
)

logger = logging.getLogger(__name__)

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


class AddEngineRequest(BaseModel):
    """Request to add an engine to a workflow phase."""
    engine_key: str = Field(..., description="Engine key to add")
    position: Optional[int] = Field(
        default=None,
        description="Position in chain engine_keys (0-indexed). None = append at end.",
    )


class AddEngineResponse(BaseModel):
    """Response after adding an engine to a workflow phase."""
    status: str
    workflow_key: str
    phase_number: float
    engine_key: str
    chain_key: str
    chain_engine_keys: list[str]
    created_new_chain: bool
    chain_description: str = ""
    phase_description: str = ""
    git_committed: bool = False
    commit_sha: Optional[str] = None
    cascaded_workflows: list[str] = Field(default_factory=list)


@router.post("/{workflow_key}/phases/{phase_number}/add-engine", response_model=AddEngineResponse)
async def add_engine_to_phase(
    workflow_key: str,
    phase_number: float,
    request: AddEngineRequest,
) -> AddEngineResponse:
    """Add an engine to a workflow phase with full propagation.

    If the phase uses a chain, appends the engine to the chain's engine_keys.
    If the phase uses a standalone engine_key, creates a new sequential chain
    containing both the existing engine and the new one, then updates the phase.

    Propagation:
    1. Updates chain engine_keys
    2. Auto-regenerates chain description (if base_description exists)
    3. Auto-regenerates phase description in all workflows using this chain
    4. Commits all modified files to GitHub atomically
    """
    workflow_registry = get_workflow_registry()
    chain_registry = get_chain_registry()
    engine_registry = get_engine_registry()

    # Validate workflow exists
    workflow = workflow_registry.get(workflow_key)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_key}")

    # Validate engine exists
    engine = engine_registry.get(request.engine_key)
    if engine is None:
        raise HTTPException(status_code=404, detail=f"Engine not found: {request.engine_key}")

    # Find the phase
    phase_def = None
    phase_idx = None
    for i, p in enumerate(workflow.phases):
        if p.phase_number == phase_number:
            phase_def = p
            phase_idx = i
            break
    if phase_def is None:
        raise HTTPException(
            status_code=404,
            detail=f"Phase {phase_number} not found in workflow {workflow_key}",
        )

    created_new_chain = False
    updated_chain: Optional[EngineChainSpec] = None
    result_chain_key = ""
    result_engine_keys: list[str] = []

    # Case 1: Phase already has a chain_key — add engine to chain
    if phase_def.chain_key:
        chain = chain_registry.get(phase_def.chain_key)
        if chain is None:
            raise HTTPException(
                status_code=404,
                detail=f"Chain not found: {phase_def.chain_key}",
            )

        # Check if engine is already in the chain
        if request.engine_key in chain.engine_keys:
            raise HTTPException(
                status_code=409,
                detail=f"Engine '{request.engine_key}' is already in chain '{chain.chain_key}'",
            )

        # Insert at position or append
        new_engine_keys = list(chain.engine_keys)
        if request.position is not None and 0 <= request.position <= len(new_engine_keys):
            new_engine_keys.insert(request.position, request.engine_key)
        else:
            new_engine_keys.append(request.engine_key)

        # Build updated chain with new engine list
        chain_updates = {
            "engine_keys": new_engine_keys,
            "max_engines": len(new_engine_keys),
        }

        # Auto-regenerate chain description if base_description exists
        updated_chain = chain.model_copy(update=chain_updates)
        if updated_chain.base_description:
            updated_chain = updated_chain.model_copy(update={
                "description": generate_chain_description(updated_chain, engine_registry),
            })

        # Save chain locally
        success = chain_registry.save(chain.chain_key, updated_chain)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save chain")

        result_chain_key = chain.chain_key
        result_engine_keys = new_engine_keys
        created_new_chain = False

    # Case 2: Phase has a standalone engine_key — create new chain
    elif phase_def.engine_key:
        existing_engine_key = phase_def.engine_key

        # Check not adding the same engine
        if request.engine_key == existing_engine_key:
            raise HTTPException(
                status_code=409,
                detail=f"Engine '{request.engine_key}' is already in this phase",
            )

        # Generate a chain key from the phase name
        phase_slug = phase_def.phase_name.lower().replace(" ", "_").replace("-", "_")
        new_chain_key = f"{workflow_key}_{phase_slug}_chain"

        # Check if this chain key already exists
        if chain_registry.get(new_chain_key) is not None:
            new_chain_key = f"{new_chain_key}_{int(phase_number)}"

        # Build engine list
        engine_keys = [existing_engine_key, request.engine_key]
        if request.position == 0:
            engine_keys = [request.engine_key, existing_engine_key]

        # Create chain with base_description for future auto-updates
        base_desc = f"{phase_def.phase_name} chain"
        new_chain = EngineChainSpec(
            chain_key=new_chain_key,
            chain_name=f"{phase_def.phase_name} Chain",
            description="",  # Will be auto-generated below
            base_description=base_desc,
            version=1,
            engine_keys=engine_keys,
            blend_mode=BlendMode.SEQUENTIAL,
            pass_context=True,
            category=workflow.category.value if workflow.category else None,
        )
        # Auto-generate description from base + engines
        new_chain = new_chain.model_copy(update={
            "description": generate_chain_description(new_chain, engine_registry),
        })

        # Save the new chain
        success = chain_registry.save(new_chain_key, new_chain)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to create chain")

        # Update the phase: swap engine_key for chain_key
        updated_phase = phase_def.model_copy(update={
            "engine_key": None,
            "chain_key": new_chain_key,
        })
        workflow.phases[phase_idx] = updated_phase

        updated_chain = new_chain
        result_chain_key = new_chain_key
        result_engine_keys = engine_keys
        created_new_chain = True

    # Case 3: Phase has neither chain_key nor engine_key
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Phase {phase_number} has no chain_key or engine_key — cannot add engine",
        )

    # ── Cascade: update descriptions in all workflows using this chain ──

    cascaded_workflows: list[str] = []
    affected_workflow_keys: set[str] = set()

    # Find all workflow phases referencing this chain
    chain_refs = workflow_registry.find_by_chain_key(result_chain_key)

    for wf_key, phase_i in chain_refs:
        wf = workflow_registry.get(wf_key)
        if wf is None:
            continue
        phase = wf.phases[phase_i]

        # Auto-regenerate phase description if base exists
        if phase.base_phase_description and updated_chain:
            new_phase_desc = generate_phase_description(
                phase, updated_chain, engine_registry
            )
            wf.phases[phase_i] = phase.model_copy(
                update={"phase_description": new_phase_desc}
            )
            affected_workflow_keys.add(wf_key)

    # Save all affected workflows
    for wf_key in affected_workflow_keys:
        wf = workflow_registry.get(wf_key)
        if wf:
            workflow_registry.save(wf_key, wf)
            if wf_key != workflow_key:
                cascaded_workflows.append(wf_key)

    # Also save the primary workflow if it wasn't already saved via cascade
    if workflow_key not in affected_workflow_keys:
        workflow_registry.save(workflow_key, workflow)

    # ── Git commit: persist all changes atomically ──

    github = get_github_persistence()
    commit_result = None

    if github.enabled:
        files_to_commit: list[CommitFile] = []

        # Chain file
        chain_file_path = chain_registry._file_map.get(result_chain_key)
        if chain_file_path and updated_chain:
            repo_path = GitHubPersistence.absolute_to_repo_path(chain_file_path)
            chain_json = json.dumps(updated_chain.model_dump(), indent=2) + "\n"
            files_to_commit.append(CommitFile(repo_path=repo_path, content=chain_json))

        # All affected workflow files
        for wf_key in affected_workflow_keys | {workflow_key}:
            wf = workflow_registry.get(wf_key)
            if wf:
                wf_file = workflow_registry.definitions_dir / f"{wf_key}.json"
                repo_path = GitHubPersistence.absolute_to_repo_path(wf_file)
                wf_json = json.dumps(wf.model_dump(), indent=2) + "\n"
                files_to_commit.append(CommitFile(repo_path=repo_path, content=wf_json))

        if files_to_commit:
            commit_msg = (
                f"Add {request.engine_key} to {result_chain_key} "
                f"(workflow: {workflow_key}, phase {phase_number})"
            )
            commit_result = await github.commit_files(files_to_commit, commit_msg)

    # Get final descriptions for response
    final_chain = chain_registry.get(result_chain_key)
    final_workflow = workflow_registry.get(workflow_key)
    final_phase_desc = ""
    if final_workflow:
        for p in final_workflow.phases:
            if p.phase_number == phase_number:
                final_phase_desc = p.phase_description
                break

    # Mark definitions as modified for cache versioning
    mark_definitions_modified()

    logger.info(
        f"Added engine '{request.engine_key}' to chain '{result_chain_key}' "
        f"in workflow '{workflow_key}' phase {phase_number} "
        f"(git_committed={commit_result.success if commit_result else False}, "
        f"cascaded={cascaded_workflows})"
    )

    return AddEngineResponse(
        status="added",
        workflow_key=workflow_key,
        phase_number=phase_number,
        engine_key=request.engine_key,
        chain_key=result_chain_key,
        chain_engine_keys=result_engine_keys,
        created_new_chain=created_new_chain,
        chain_description=final_chain.description if final_chain else "",
        phase_description=final_phase_desc,
        git_committed=commit_result.success if commit_result else False,
        commit_sha=commit_result.sha if commit_result else None,
        cascaded_workflows=cascaded_workflows,
    )


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
