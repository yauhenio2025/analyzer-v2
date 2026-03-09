"""Project lifecycle API routes.

Endpoints:
    POST   /v1/projects                          Create project
    GET    /v1/projects                          List projects (?status=active|archived)
    GET    /v1/projects/{project_id}             Get project + job summary
    PATCH  /v1/projects/{project_id}             Update name, description, auto_archive_days
    POST   /v1/projects/{project_id}/archive     Archive (release presentation resources)
    POST   /v1/projects/{project_id}/revive      Revive archived project
    DELETE /v1/projects/{project_id}?confirm=true Hard delete project + all data
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.executor.project_manager import (
    archive_project,
    create_project,
    delete_project,
    get_project,
    list_projects,
    revive_project,
    update_project,
)
from src.executor.schemas import (
    LifecycleActionResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201)
async def create_new_project(request: ProjectCreate) -> ProjectResponse:
    """Create a new project workspace."""
    project = create_project(
        name=request.name,
        description=request.description,
        auto_archive_days=request.auto_archive_days,
    )
    return ProjectResponse(**project)


@router.get("")
async def list_all_projects(
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
):
    """List projects, optionally filtered by status."""
    projects = list_projects(status=status, limit=limit)
    return {
        "projects": [ProjectResponse(**p).model_dump() for p in projects],
        "count": len(projects),
    }


@router.get("/{project_id}")
async def get_project_detail(project_id: str) -> ProjectResponse:
    """Get a project with job counts."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return ProjectResponse(**project)


@router.patch("/{project_id}")
async def update_project_metadata(project_id: str, request: ProjectUpdate) -> ProjectResponse:
    """Update project name, description, or auto_archive_days."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        project = get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return ProjectResponse(**project)

    project = update_project(project_id, **updates)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
    return ProjectResponse(**project)


@router.post("/{project_id}/archive")
async def archive_project_endpoint(project_id: str) -> LifecycleActionResponse:
    """Archive a project: delete presentation artifacts, retain engine outputs."""
    try:
        result = archive_project(project_id)
        return LifecycleActionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{project_id}/revive")
async def revive_project_endpoint(project_id: str) -> LifecycleActionResponse:
    """Revive an archived project. Presentation regenerated lazily on demand."""
    try:
        result = revive_project(project_id)
        return LifecycleActionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{project_id}")
async def delete_project_endpoint(
    project_id: str,
    confirm: bool = Query(default=False),
) -> LifecycleActionResponse:
    """Hard-delete a project and ALL associated data. Requires confirm=true."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Destructive operation requires ?confirm=true query parameter",
        )
    try:
        result = delete_project(project_id)
        return LifecycleActionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
