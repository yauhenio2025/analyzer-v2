"""Chain API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.chains.registry import get_chain_registry
from src.chains.schemas import (
    BlendMode,
    ChainRecommendRequest,
    ChainRecommendResponse,
    ChainSummary,
    EngineChainSpec,
)

router = APIRouter(prefix="/chains", tags=["chains"])


@router.get("", response_model=list[ChainSummary])
async def list_chains(
    category: Optional[str] = Query(None, description="Filter by category"),
    blend_mode: Optional[BlendMode] = Query(
        None, description="Filter by blend mode"
    ),
) -> list[ChainSummary]:
    """List all engine chains with optional filtering."""
    registry = get_chain_registry()

    if category:
        chains = registry.list_by_category(category)
    elif blend_mode:
        chains = registry.list_by_blend_mode(blend_mode)
    else:
        chains = registry.list_all()

    return [
        ChainSummary(
            chain_key=c.chain_key,
            chain_name=c.chain_name,
            description=c.description,
            blend_mode=c.blend_mode,
            engine_count=len(c.engine_keys),
            category=c.category,
            has_context_parameters=c.context_parameter_schema is not None,
        )
        for c in chains
    ]


@router.get("/keys", response_model=list[str])
async def list_chain_keys() -> list[str]:
    """List all chain keys."""
    registry = get_chain_registry()
    return registry.list_keys()


@router.get("/count")
async def get_chain_count() -> dict[str, int]:
    """Get total number of chains."""
    registry = get_chain_registry()
    return {"count": registry.count()}


@router.get("/category/{category}", response_model=list[ChainSummary])
async def list_chains_by_category(category: str) -> list[ChainSummary]:
    """List chains in a specific category."""
    registry = get_chain_registry()
    chains = registry.list_by_category(category)
    return [
        ChainSummary(
            chain_key=c.chain_key,
            chain_name=c.chain_name,
            description=c.description,
            blend_mode=c.blend_mode,
            engine_count=len(c.engine_keys),
            category=c.category,
            has_context_parameters=c.context_parameter_schema is not None,
        )
        for c in chains
    ]


@router.get("/{chain_key}", response_model=EngineChainSpec)
async def get_chain(chain_key: str) -> EngineChainSpec:
    """Get full chain specification."""
    registry = get_chain_registry()
    chain = registry.get(chain_key)
    if chain is None:
        raise HTTPException(
            status_code=404,
            detail=f"Chain not found: {chain_key}",
        )
    return chain


@router.post("/recommend", response_model=ChainRecommendResponse)
async def recommend_chain(request: ChainRecommendRequest) -> ChainRecommendResponse:
    """Get chain recommendation based on intent.

    Note: This is a placeholder. Full implementation would use LLM
    to analyze intent and recommend the best chain.
    """
    registry = get_chain_registry()
    chains = registry.list_all()

    if not chains:
        raise HTTPException(
            status_code=404,
            detail="No chains available for recommendation",
        )

    # Simple heuristic: return first chain matching category keywords
    intent_lower = request.intent.lower()

    for chain in chains:
        if chain.category and chain.category.lower() in intent_lower:
            return ChainRecommendResponse(
                recommended_chain_key=chain.chain_key,
                chain_name=chain.chain_name,
                confidence=0.7,
                reasoning=f"Chain category '{chain.category}' matches intent",
                alternative_chains=[
                    c.chain_key for c in chains if c.chain_key != chain.chain_key
                ][:3],
            )

    # Default to first chain
    first_chain = chains[0]
    return ChainRecommendResponse(
        recommended_chain_key=first_chain.chain_key,
        chain_name=first_chain.chain_name,
        confidence=0.5,
        reasoning="Default recommendation - no strong category match",
        alternative_chains=[c.chain_key for c in chains[1:4]],
    )


@router.post("/reload")
async def reload_chains() -> dict[str, str]:
    """Force reload all chain definitions from disk."""
    registry = get_chain_registry()
    registry.reload()
    return {"status": "reloaded", "count": str(registry.count())}
