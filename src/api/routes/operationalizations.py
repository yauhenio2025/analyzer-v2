"""Operationalization API routes.

Serves the bridge layer between stances (HOW) and engines (WHAT).
Each engine can have an operationalization file specifying how each
stance applies and what depth sequences are available.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.operationalizations.registry import get_operationalization_registry
from src.operationalizations.schemas import (
    CoverageMatrix,
    DepthSequence,
    EngineOperationalization,
    OperationalizationSummary,
    StanceOperationalization,
)
from src.stages.capability_composer import (
    compose_pass_prompt,
    PassPrompt,
)
from src.engines.registry import get_engine_registry
from src.engines.schemas_v2 import PassDefinition

router = APIRouter(prefix="/operationalizations", tags=["operationalizations"])


# ── Registry accessor ───────────────────────────────────────────────────

def _get_registry():
    return get_operationalization_registry()


# ── List / Coverage ─────────────────────────────────────────────────────

@router.get("/", response_model=list[OperationalizationSummary])
async def list_operationalizations():
    """List all engine operationalizations (summaries)."""
    reg = _get_registry()
    return reg.list_summaries()


@router.get("/coverage", response_model=CoverageMatrix)
async def get_coverage():
    """Get the engine x stance coverage matrix."""
    reg = _get_registry()
    return reg.coverage_matrix()


# ── Single engine ───────────────────────────────────────────────────────

@router.get("/{engine_key}", response_model=EngineOperationalization)
async def get_operationalization(engine_key: str):
    """Get the full operationalization for an engine."""
    reg = _get_registry()
    op = reg.get(engine_key)
    if op is None:
        raise HTTPException(status_code=404, detail=f"No operationalization for engine '{engine_key}'")
    return op


@router.put("/{engine_key}", response_model=EngineOperationalization)
async def update_operationalization(engine_key: str, body: EngineOperationalization):
    """Update the full operationalization for an engine."""
    reg = _get_registry()
    if body.engine_key != engine_key:
        raise HTTPException(status_code=400, detail="engine_key in body must match URL")
    success = reg.save(engine_key, body)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save operationalization")
    return body


# ── Stance operationalizations ──────────────────────────────────────────

@router.get("/{engine_key}/stances", response_model=list[StanceOperationalization])
async def list_stance_ops(engine_key: str):
    """List all stance operationalizations for an engine."""
    reg = _get_registry()
    op = reg.get(engine_key)
    if op is None:
        raise HTTPException(status_code=404, detail=f"No operationalization for engine '{engine_key}'")
    return op.stance_operationalizations


@router.get("/{engine_key}/stances/{stance_key}", response_model=StanceOperationalization)
async def get_stance_op(engine_key: str, stance_key: str):
    """Get a specific stance operationalization for an engine."""
    reg = _get_registry()
    stance_op = reg.get_stance_for_engine(engine_key, stance_key)
    if stance_op is None:
        raise HTTPException(
            status_code=404,
            detail=f"No operationalization for stance '{stance_key}' on engine '{engine_key}'",
        )
    return stance_op


@router.put("/{engine_key}/stances/{stance_key}", response_model=StanceOperationalization)
async def update_stance_op(
    engine_key: str,
    stance_key: str,
    body: StanceOperationalization,
):
    """Update a specific stance operationalization for an engine."""
    reg = _get_registry()
    op = reg.get(engine_key)
    if op is None:
        raise HTTPException(status_code=404, detail=f"No operationalization for engine '{engine_key}'")

    if body.stance_key != stance_key:
        raise HTTPException(status_code=400, detail="stance_key in body must match URL")

    # Replace or append
    found = False
    for i, existing in enumerate(op.stance_operationalizations):
        if existing.stance_key == stance_key:
            op.stance_operationalizations[i] = body
            found = True
            break

    if not found:
        op.stance_operationalizations.append(body)

    reg.save(engine_key, op)
    return body


# ── Depth sequences ─────────────────────────────────────────────────────

@router.get("/{engine_key}/depths/{depth_key}", response_model=DepthSequence)
async def get_depth_sequence(engine_key: str, depth_key: str):
    """Get the depth sequence for a specific depth level."""
    reg = _get_registry()
    seq = reg.get_depth_sequence(engine_key, depth_key)
    if seq is None:
        raise HTTPException(
            status_code=404,
            detail=f"No depth sequence for '{depth_key}' on engine '{engine_key}'",
        )
    return seq


@router.put("/{engine_key}/depths/{depth_key}", response_model=DepthSequence)
async def update_depth_sequence(
    engine_key: str,
    depth_key: str,
    body: DepthSequence,
):
    """Update the depth sequence for a specific depth level."""
    reg = _get_registry()
    op = reg.get(engine_key)
    if op is None:
        raise HTTPException(status_code=404, detail=f"No operationalization for engine '{engine_key}'")

    if body.depth_key != depth_key:
        raise HTTPException(status_code=400, detail="depth_key in body must match URL")

    # Replace or append
    found = False
    for i, existing in enumerate(op.depth_sequences):
        if existing.depth_key == depth_key:
            op.depth_sequences[i] = body
            found = True
            break

    if not found:
        op.depth_sequences.append(body)

    reg.save(engine_key, op)
    return body


# ── Compose preview ─────────────────────────────────────────────────────

class ComposePreviewRequest(BaseModel):
    """Request body for compose preview."""
    depth_key: str = Field(default="standard", description="Depth level to compose for")
    pass_number: int = Field(default=1, description="Pass number to preview")


@router.post("/{engine_key}/compose-preview", response_model=PassPrompt)
async def compose_preview(engine_key: str, body: ComposePreviewRequest):
    """Preview the composed prompt for a specific pass using operationalization data.

    This builds a PassDefinition from the operationalization layer and
    composes the prompt as it would be at runtime.
    """
    op_reg = _get_registry()
    op = op_reg.get(engine_key)
    if op is None:
        raise HTTPException(status_code=404, detail=f"No operationalization for engine '{engine_key}'")

    # Get the depth sequence
    depth_seq = op.get_depth_sequence(body.depth_key)
    if depth_seq is None:
        raise HTTPException(
            status_code=404,
            detail=f"No depth sequence for '{body.depth_key}' on engine '{engine_key}'",
        )

    # Find the pass entry
    pass_entry = None
    for pe in depth_seq.passes:
        if pe.pass_number == body.pass_number:
            pass_entry = pe
            break

    if pass_entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"No pass {body.pass_number} in depth '{body.depth_key}' for engine '{engine_key}'",
        )

    # Get the stance operationalization
    stance_op = op.get_stance_op(pass_entry.stance_key)
    if stance_op is None:
        raise HTTPException(
            status_code=404,
            detail=f"No operationalization for stance '{pass_entry.stance_key}' on engine '{engine_key}'",
        )

    # Get engine capability definition
    engine_reg = get_engine_registry()
    cap_def = engine_reg.get_capability_definition(engine_key)
    if cap_def is None:
        raise HTTPException(status_code=404, detail=f"No capability definition for engine '{engine_key}'")

    # Build a PassDefinition from operationalization data
    pass_def = PassDefinition(
        pass_number=pass_entry.pass_number,
        label=stance_op.label,
        stance=pass_entry.stance_key,
        description=stance_op.description,
        focus_dimensions=stance_op.focus_dimensions,
        focus_capabilities=stance_op.focus_capabilities,
        consumes_from=pass_entry.consumes_from,
    )

    return compose_pass_prompt(
        cap_def=cap_def,
        pass_def=pass_def,
        depth=body.depth_key,
    )
