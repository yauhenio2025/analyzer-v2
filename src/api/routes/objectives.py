"""API routes for analysis objectives.

Objectives define what an analysis type is trying to achieve — goals,
quality criteria, expected deliverables, preferred engines/categories.
They drive the adaptive planner's pipeline composition.
"""

import json
import logging

from fastapi import APIRouter, HTTPException
from src.objectives.registry import (
    DEFINITIONS_DIR,
    get_objective,
    list_objectives,
    reload,
)
from src.objectives.schemas import AnalysisObjective

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/objectives", tags=["objectives"])


@router.get("")
async def get_objectives():
    """List all analysis objectives.

    Returns all available objectives with their primary goals,
    quality criteria, and preferred engine functions/categories.
    """
    objectives = list_objectives()
    return {
        "objectives": [obj.model_dump() for obj in objectives],
        "count": len(objectives),
    }


@router.get("/{key}")
async def get_objective_detail(key: str):
    """Get a specific analysis objective by key.

    Returns full objective definition including planner strategy,
    expected deliverables, and baseline workflow reference.
    """
    objective = get_objective(key)
    if objective is None:
        raise HTTPException(
            status_code=404,
            detail=f"Objective '{key}' not found. Available: genealogical, logical",
        )
    return objective.model_dump()


@router.post("", status_code=201)
async def create_objective(body: AnalysisObjective):
    """Create a new analysis objective.

    Writes a JSON definition file and reloads the registry.
    """
    existing = get_objective(body.objective_key)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Objective '{body.objective_key}' already exists. Use PUT to update.",
        )

    file_path = DEFINITIONS_DIR / f"{body.objective_key}.json"
    DEFINITIONS_DIR.mkdir(parents=True, exist_ok=True)

    with open(file_path, "w") as f:
        json.dump(body.model_dump(), f, indent=2, ensure_ascii=False)

    logger.info(f"Created objective: {body.objective_key} -> {file_path}")
    reload()

    return body.model_dump()


@router.put("/{key}")
async def update_objective(key: str, body: AnalysisObjective):
    """Update an existing analysis objective.

    If objective_key in the body differs from the URL key, the old
    definition file is removed and a new one is created (rename).
    """
    existing = get_objective(key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Objective '{key}' not found. Use POST to create.",
        )

    old_file = DEFINITIONS_DIR / f"{key}.json"
    new_file = DEFINITIONS_DIR / f"{body.objective_key}.json"

    # If the key changed, check that the new key doesn't collide
    if body.objective_key != key:
        collision = get_objective(body.objective_key)
        if collision is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot rename to '{body.objective_key}': that key already exists.",
            )
        # Remove old file
        if old_file.exists():
            old_file.unlink()
            logger.info(f"Removed old definition file: {old_file}")

    with open(new_file, "w") as f:
        json.dump(body.model_dump(), f, indent=2, ensure_ascii=False)

    logger.info(f"Updated objective: {key} -> {body.objective_key} at {new_file}")
    reload()

    return body.model_dump()


@router.delete("/{key}")
async def delete_objective(key: str):
    """Delete an analysis objective.

    Removes the JSON definition file and reloads the registry.
    """
    existing = get_objective(key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Objective '{key}' not found.",
        )

    file_path = DEFINITIONS_DIR / f"{key}.json"
    if file_path.exists():
        file_path.unlink()
        logger.info(f"Deleted objective file: {file_path}")
    else:
        logger.warning(f"Objective '{key}' was in registry but file {file_path} not found on disk")

    reload()

    return {"deleted": key}
