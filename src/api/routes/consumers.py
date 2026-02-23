"""API routes for consumer definitions.

Consumer definitions declare what rendering and analysis capabilities
a consumer app supports. This inverts the coupling — apps declare
what they can render, not renderers declaring which apps they support.
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.routes.meta import mark_definitions_modified
from src.consumers.registry import get_consumer_registry
from src.consumers.schemas import (
    ConsumerDefinition,
    ConsumerSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consumers", tags=["consumers"])


def _get_or_404(consumer_key: str) -> ConsumerDefinition:
    """Get a consumer by key or raise 404."""
    registry = get_consumer_registry()
    consumer = registry.get(consumer_key)
    if consumer is None:
        available = registry.list_keys()
        raise HTTPException(
            status_code=404,
            detail=f"Consumer '{consumer_key}' not found. Available: {available}",
        )
    return consumer


# -- List endpoints --


@router.get("", response_model=list[ConsumerSummary])
async def list_consumers():
    """List all consumer definitions (summaries)."""
    registry = get_consumer_registry()
    return registry.list_summaries()


# -- Detail endpoint --


@router.get("/{consumer_key}", response_model=ConsumerDefinition)
async def get_consumer(consumer_key: str):
    """Get a single consumer definition by key."""
    return _get_or_404(consumer_key)


# -- Query endpoints --


@router.get("/{consumer_key}/renderers")
async def consumer_renderers(consumer_key: str):
    """Get the list of renderer keys supported by a consumer."""
    consumer = _get_or_404(consumer_key)
    return {
        "consumer_key": consumer_key,
        "supported_renderers": consumer.supported_renderers,
        "supported_sub_renderers": consumer.supported_sub_renderers,
    }


# -- CRUD --


@router.post("", response_model=ConsumerDefinition, status_code=201)
async def create_consumer(consumer: ConsumerDefinition):
    """Create a new consumer definition."""
    registry = get_consumer_registry()

    if registry.get(consumer.consumer_key) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Consumer '{consumer.consumer_key}' already exists",
        )

    success = registry.save(consumer.consumer_key, consumer)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save consumer '{consumer.consumer_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Created consumer: {consumer.consumer_key}")
    return consumer


@router.put("/{consumer_key}", response_model=ConsumerDefinition)
async def update_consumer(consumer_key: str, consumer: ConsumerDefinition):
    """Update an existing consumer definition."""
    registry = get_consumer_registry()

    if registry.get(consumer_key) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Consumer '{consumer_key}' not found",
        )

    if consumer.consumer_key != consumer_key:
        raise HTTPException(
            status_code=400,
            detail=f"consumer_key in body ('{consumer.consumer_key}') "
            f"must match URL ('{consumer_key}')",
        )

    success = registry.save(consumer_key, consumer)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save consumer '{consumer_key}'",
        )

    mark_definitions_modified()
    logger.info(f"Updated consumer: {consumer_key}")
    return consumer


@router.delete("/{consumer_key}")
async def delete_consumer(consumer_key: str):
    """Delete a consumer definition."""
    registry = get_consumer_registry()

    success = registry.delete(consumer_key)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Consumer '{consumer_key}' not found",
        )

    mark_definitions_modified()
    logger.info(f"Deleted consumer: {consumer_key}")
    return {"deleted": consumer_key}


# -- Reload --


@router.post("/reload")
async def reload_consumers():
    """Force reload consumer definitions from disk."""
    registry = get_consumer_registry()
    registry.reload()
    return {"reloaded": True, "count": registry.count()}
