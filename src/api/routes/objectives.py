"""API routes for analysis objectives.

Objectives define what an analysis type is trying to achieve — goals,
quality criteria, expected deliverables, preferred engines/categories.
They drive the adaptive planner's pipeline composition.
"""

import logging
from fastapi import APIRouter, HTTPException
from src.objectives.registry import get_objective, list_objectives

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
