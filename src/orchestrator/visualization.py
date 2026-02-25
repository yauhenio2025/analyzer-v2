"""Pipeline visualization endpoint — assembles the full pipeline tree for a plan.

Reads from in-memory registries (no DB/LLM calls) to compose a tree showing:
  plan → phases → chains/engines → passes → stances → dimensions

This powers the Critic's pipeline visualization component, which shows the
multi-phase/multi-pass execution structure dynamically sourced from definitions.
"""

import logging
from typing import Any, Optional

from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.operationalizations.registry import get_operationalization_registry
from src.operations.registry import StanceRegistry
from src.orchestrator.planner import load_plan
from src.orchestrator.schemas import PhaseExecutionSpec, WorkflowExecutionPlan
from src.workflows.registry import get_workflow_registry

logger = logging.getLogger(__name__)


def assemble_pipeline_visualization(plan_id: str) -> dict[str, Any]:
    """Compose plan + workflow + chains + engines + operationalizations + stances.

    Returns a tree structure suitable for rendering a pipeline visualization:
    {
        plan_id, thinker_name, strategy_summary, estimated_llm_calls,
        phases: [{
            phase_number, phase_name, depth, rationale, model_hint, per_work,
            depends_on, skip,
            execution: {
                type: "chain" | "engine",
                chain_key?, chain_name?,
                engines: [{
                    engine_key, engine_name, category, depth,
                    passes: [{pass_number, stance_key, stance_name, cognitive_mode,
                              label, focus_dimensions, consumes_from}],
                    dimensions: [{key, description, depth_guidance}],
                    capabilities: [str]
                }]
            }
        }]
    }
    """
    plan = load_plan(plan_id)
    if plan is None:
        raise ValueError(f"Plan '{plan_id}' not found")

    engine_reg = get_engine_registry()
    chain_reg = get_chain_registry()
    op_reg = get_operationalization_registry()
    stance_reg = StanceRegistry()
    workflow_reg = get_workflow_registry()

    # Get the workflow definition for phase templates
    workflow = workflow_reg.get(plan.workflow_key)

    # Build phase visualizations
    phases_viz = []
    for plan_phase in plan.phases:
        phase_viz = _build_phase_viz(
            plan_phase=plan_phase,
            workflow=workflow,
            engine_reg=engine_reg,
            chain_reg=chain_reg,
            op_reg=op_reg,
            stance_reg=stance_reg,
        )
        phases_viz.append(phase_viz)

    return {
        "plan_id": plan.plan_id,
        "workflow_key": plan.workflow_key,
        "thinker_name": plan.thinker_name,
        "strategy_summary": plan.strategy_summary,
        "estimated_llm_calls": plan.estimated_llm_calls,
        "depth_profile": plan.estimated_depth_profile,
        "total_phases": len(phases_viz),
        "phases": phases_viz,
    }


def _build_phase_viz(
    plan_phase: PhaseExecutionSpec,
    workflow: Any,
    engine_reg: Any,
    chain_reg: Any,
    op_reg: Any,
    stance_reg: Any,
) -> dict[str, Any]:
    """Build visualization for a single phase."""
    # Resolve workflow phase template (if workflow exists)
    wf_phase = None
    if workflow:
        for wp in workflow.phases:
            if wp.phase_number == plan_phase.phase_number:
                wf_phase = wp
                break

    # Determine if chain-backed or engine-backed.
    # Adaptive planner fields on plan_phase take precedence over workflow template.
    chain_key = plan_phase.chain_key or (wf_phase.chain_key if wf_phase else None)
    engine_key = plan_phase.engine_key or (wf_phase.engine_key if wf_phase else None)

    # Resolve per_work flag — check adaptive iteration_mode first, then workflow
    per_work = (
        (plan_phase.iteration_mode in ("per_work", "per_work_filtered"))
        if plan_phase.iteration_mode
        else (wf_phase.requires_external_docs if wf_phase else False)
    )

    # Resolve depends_on — plan phase overrides workflow template
    depends_on = plan_phase.depends_on or (wf_phase.depends_on_phases if wf_phase else [])

    execution: dict[str, Any]
    if chain_key:
        execution = _build_chain_execution(
            chain_key=chain_key,
            plan_phase=plan_phase,
            engine_reg=engine_reg,
            chain_reg=chain_reg,
            op_reg=op_reg,
            stance_reg=stance_reg,
        )
    elif engine_key:
        execution = _build_single_engine_execution(
            engine_key=engine_key,
            plan_phase=plan_phase,
            engine_reg=engine_reg,
            op_reg=op_reg,
            stance_reg=stance_reg,
        )
    else:
        execution = {"type": "unknown", "engines": []}

    # Chapter targeting info
    document_scope = getattr(plan_phase, "document_scope", "whole") or "whole"
    chapter_targets_viz = None
    if hasattr(plan_phase, "chapter_targets") and plan_phase.chapter_targets:
        chapter_targets_viz = [
            {
                "chapter_id": ct.chapter_id,
                "chapter_title": ct.chapter_title,
                "work_key": ct.work_key,
                "rationale": ct.rationale,
            }
            for ct in plan_phase.chapter_targets
        ]

    return {
        "phase_number": plan_phase.phase_number,
        "phase_name": plan_phase.phase_name,
        "depth": plan_phase.depth,
        "rationale": plan_phase.rationale,
        "model_hint": plan_phase.model_hint,
        "per_work": per_work,
        "depends_on": depends_on,
        "skip": plan_phase.skip,
        "document_scope": document_scope,
        "chapter_targets": chapter_targets_viz,
        "execution": execution,
    }


def _build_chain_execution(
    chain_key: str,
    plan_phase: PhaseExecutionSpec,
    engine_reg: Any,
    chain_reg: Any,
    op_reg: Any,
    stance_reg: Any,
) -> dict[str, Any]:
    """Build execution visualization for a chain-backed phase."""
    chain = chain_reg.get(chain_key)
    if chain is None:
        logger.warning(f"Chain '{chain_key}' not found in registry")
        return {"type": "chain", "chain_key": chain_key, "chain_name": chain_key, "engines": []}

    engines_viz = []
    for ek in chain.engine_keys:
        engine_viz = _build_engine_viz(
            engine_key=ek,
            plan_phase=plan_phase,
            engine_reg=engine_reg,
            op_reg=op_reg,
            stance_reg=stance_reg,
        )
        engines_viz.append(engine_viz)

    return {
        "type": "chain",
        "chain_key": chain.chain_key,
        "chain_name": chain.chain_name,
        "blend_mode": chain.blend_mode.value,
        "engines": engines_viz,
    }


def _build_single_engine_execution(
    engine_key: str,
    plan_phase: PhaseExecutionSpec,
    engine_reg: Any,
    op_reg: Any,
    stance_reg: Any,
) -> dict[str, Any]:
    """Build execution visualization for a single-engine phase."""
    engine_viz = _build_engine_viz(
        engine_key=engine_key,
        plan_phase=plan_phase,
        engine_reg=engine_reg,
        op_reg=op_reg,
        stance_reg=stance_reg,
    )
    return {
        "type": "engine",
        "engines": [engine_viz],
    }


def _build_engine_viz(
    engine_key: str,
    plan_phase: PhaseExecutionSpec,
    engine_reg: Any,
    op_reg: Any,
    stance_reg: Any,
) -> dict[str, Any]:
    """Build visualization for a single engine within a phase."""
    # Try capability definition first (richer), fall back to standard
    cap_def = engine_reg.get_capability_definition(engine_key)
    std_def = engine_reg.get(engine_key)

    engine_name = (cap_def.engine_name if cap_def else
                   std_def.name if std_def else engine_key)
    category = (cap_def.category if cap_def else
                std_def.category.value if std_def and std_def.category else "unknown")

    # Get plan-level overrides for this engine
    override = None
    if plan_phase.engine_overrides and engine_key in plan_phase.engine_overrides:
        override = plan_phase.engine_overrides[engine_key]

    depth = override.depth if override else plan_phase.depth

    # Get operationalization (pass sequence at this depth)
    passes_viz = _build_passes_viz(
        engine_key=engine_key,
        depth=depth,
        override=override,
        op_reg=op_reg,
        stance_reg=stance_reg,
    )

    # Get dimensions from capability definition
    dimensions_viz = []
    if cap_def and hasattr(cap_def, "analytical_dimensions"):
        for dim in cap_def.analytical_dimensions:
            dim_entry = {
                "key": dim.key,
                "description": dim.description[:200] if dim.description else "",
            }
            if dim.depth_guidance:
                dim_entry["depth_guidance"] = {
                    k: v[:150] if isinstance(v, str) else v
                    for k, v in (dim.depth_guidance.items()
                                 if isinstance(dim.depth_guidance, dict)
                                 else {})
                }
            dimensions_viz.append(dim_entry)

    # Get capabilities list
    capabilities_viz = []
    if cap_def and hasattr(cap_def, "capabilities"):
        capabilities_viz = [c.key for c in cap_def.capabilities]

    return {
        "engine_key": engine_key,
        "engine_name": engine_name,
        "category": category,
        "depth": depth,
        "override_rationale": override.rationale if override else None,
        "focus_dimensions": override.focus_dimensions if override else None,
        "passes": passes_viz,
        "dimensions": dimensions_viz,
        "capabilities": capabilities_viz,
    }


def _build_passes_viz(
    engine_key: str,
    depth: str,
    override: Optional[Any],
    op_reg: Any,
    stance_reg: Any,
) -> list[dict[str, Any]]:
    """Build pass sequence visualization for an engine at a depth level.

    Each pass represents exactly ONE LLM API call. The visualization shows:
    - What cognitive stance drives this call
    - What data flows in from prior passes (consumes_from)
    - What dimensions/capabilities this call focuses on
    - The full stance prose (cognitive instructions sent to the LLM)
    - The operationalization description (engine-specific guidance)
    """
    op = op_reg.get(engine_key)
    if op is None:
        # No operationalization — single-pass engine
        return [{
            "pass_number": 1,
            "stance_key": "discovery",
            "stance_name": "Discovery",
            "cognitive_mode": "divergent",
            "label": f"Single-pass {depth}",
            "focus_dimensions": [],
            "focus_capabilities": [],
            "consumes_from": [],
            "stance_prose": "",
            "description": "",
            "input_summary": "Target work text + phase context",
            "output_summary": "Analytical prose",
        }]

    depth_seq = op.get_depth_sequence(depth)
    if depth_seq is None:
        # Fall back to surface or first available
        for fallback in ("surface", "standard", "deep"):
            depth_seq = op.get_depth_sequence(fallback)
            if depth_seq:
                break
        if depth_seq is None:
            return []

    total_passes = len(depth_seq.passes)
    passes_viz = []
    for entry in depth_seq.passes:
        # Get stance details
        stance = stance_reg.get(entry.stance_key)
        stance_name = stance.name if stance else entry.stance_key
        cognitive_mode = stance.cognitive_mode if stance else "unknown"
        stance_prose = stance.stance if stance else ""

        # Get engine-specific stance label from operationalization
        stance_op = op.get_stance_op(entry.stance_key)
        label = stance_op.label if stance_op else stance_name
        focus_dims = stance_op.focus_dimensions if stance_op else []
        focus_caps = stance_op.focus_capabilities if stance_op else []
        description = stance_op.description if stance_op else ""

        # Build human-readable input summary
        # The full source document is ALWAYS included in every pass
        input_parts = ["Full source document (always included)"]
        if entry.consumes_from:
            refs = ", ".join(f"#{p}" for p in entry.consumes_from)
            input_parts.append(f"analytical output from pass {refs}")
        input_parts.append("engine intellectual framing")
        input_parts.append("stance cognitive instructions")
        if focus_dims:
            dim_names = ", ".join(d.replace("_", " ") for d in focus_dims[:3])
            suffix = f" + {len(focus_dims) - 3} more" if len(focus_dims) > 3 else ""
            input_parts.append(f"focused dimensions: {dim_names}{suffix}")
        input_summary = " | ".join(input_parts)

        # Build human-readable output summary
        if entry.pass_number == total_passes:
            output_summary = "Final analytical prose (synthesized from all passes)"
        elif entry.pass_number == 1:
            output_summary = "Foundational analytical prose (feeds into subsequent passes)"
        else:
            output_summary = "Intermediate analytical prose (feeds forward)"

        passes_viz.append({
            "pass_number": entry.pass_number,
            "stance_key": entry.stance_key,
            "stance_name": stance_name,
            "cognitive_mode": cognitive_mode,
            "label": label,
            "focus_dimensions": focus_dims,
            "focus_capabilities": focus_caps,
            "consumes_from": entry.consumes_from,
            "stance_prose": stance_prose,
            "description": description,
            "input_summary": input_summary,
            "output_summary": output_summary,
        })

    return passes_viz
