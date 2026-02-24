"""Adaptive planner — generates bespoke analysis pipelines from objectives + book samples.

This is the LLM-first adaptive planning system. Unlike the legacy planner that
configures a fixed workflow template, the adaptive planner:

1. Reads analysis objectives (goals, quality criteria, expected deliverables)
2. Reads book samples (genre, domain, reasoning modes, engine affinities)
3. Reads the full engine/chain catalog (auto-discovered from registries)
4. Optionally reads a baseline workflow as a skeleton
5. Uses a single Opus call to compose a bespoke pipeline

The planner prompt IS the intelligence. No Python if/else heuristics —
the LLM reads the book samples and catalog and makes curatorial decisions.
"""

import json
import logging
import os
from typing import Optional

from .catalog import assemble_full_catalog, catalog_to_text
from .sampler_schemas import BookSample
from .schemas import (
    EngineExecutionSpec,
    OrchestratorPlanRequest,
    PhaseExecutionSpec,
    ViewRecommendation,
    WorkflowExecutionPlan,
)

logger = logging.getLogger(__name__)


ADAPTIVE_SYSTEM_PROMPT = """You are an expert research strategist designing a bespoke analytical pipeline.

You receive:
1. ANALYSIS OBJECTIVE — the goals, quality criteria, and expected deliverables for this analysis type
2. BOOK SAMPLES — lightweight profiles of each work (genre, reasoning modes, engine affinities)
3. CAPABILITY CATALOG — all available engines, chains, stances, and views
4. BASELINE WORKFLOW — (optional) a starting skeleton you can modify, extend, or replace

Your job: compose a WorkflowExecutionPlan that achieves the objective's goals using the best engines and chains from the catalog, adapted to what the book samples reveal about this specific corpus.

## Key Principles

1. **Goals drive selection**: Choose engines/chains that serve the objective's primary_goals. Don't include engines just because they exist.
2. **Book samples inform adaptation**: If a book uses game-theoretic reasoning, include specialized_reasoning_classifier. If it's a polemic, emphasize rhetorical engines. Let the corpus characteristics drive decisions.
3. **Auto-discovery**: You see the FULL catalog. New engines appear here automatically. Don't limit yourself to engines you've seen before — consider everything in the catalog.
4. **Phases are flexible**: You can add, remove, reorder, or modify phases. Phase numbers can use decimals (1.0, 1.5, 2.0, 2.5, 3.0, etc.). Specify depends_on for dependency ordering.
5. **Per-work iteration**: Set iteration_mode="per_work" for phases that need to run once per prior work. Use per_work_chain_map if different works need different chains.
6. **Chain vs engine**: Prefer chains for multi-faceted analysis (they compose multiple engines). Use single engines for focused tasks.
7. **Decision traceability**: Include a complete decision_trace. Every decision must cite evidence from book samples or objectives. For every engine considered, state whether selected or rejected and why. This is mandatory.

## Output Format

Return ONLY valid JSON (no markdown fences) matching this structure:

{
  "strategy_summary": "2-3 paragraphs explaining the overall analytical approach",
  "phases": [
    {
      "phase_number": 1.0,
      "phase_name": "Phase Name",
      "skip": false,
      "depth": "surface|standard|deep",
      "chain_key": "chain_key_here",
      "engine_key": null,
      "iteration_mode": "single|per_work|per_work_filtered",
      "depends_on": [],
      "requires_full_documents": true,
      "model_hint": "opus|sonnet|null",
      "engine_overrides": {},
      "context_emphasis": "What to emphasize in context threading",
      "supplementary_chains": [],
      "max_context_chars_override": null,
      "per_work_chain_map": null,
      "estimated_tokens": 50000,
      "estimated_cost_usd": 0.75,
      "rationale": "WHY this phase configuration"
    }
  ],
  "recommended_views": [
    {
      "view_key": "view_key_here",
      "priority": "primary|secondary|optional",
      "rationale": "WHY this view"
    }
  ],
  "decision_trace": {
    "sampling_insights": [
      {"work_title": "...", "role": "target|prior_work", "key_observations": ["..."], "implications": ["..."], "affinity_rationale": "..."}
    ],
    "objective_alignment": [
      {"goal": "exact goal text", "serving_engines": ["..."], "serving_chains": ["..."], "coverage_assessment": "fully covered|partially — reason"}
    ],
    "phase_decisions": [
      {"phase_number": 1.0, "phase_name": "...", "chain_or_engine": "...", "selection_rationale": "...", "depth_rationale": "...", "iteration_mode_rationale": "...", "alternatives_considered": ["alt — reason"], "dependency_rationale": "..."}
    ],
    "per_work_decisions": [
      {"phase_number": 2.0, "work_title": "...", "chain_key": "...", "rationale": "..."}
    ],
    "catalog_coverage": [
      {"engine_key": "...", "status": "selected|rejected|available_unused", "reason": "...", "used_in_phases": [1.0]}
    ],
    "overall_strategy_rationale": "High-level narrative connecting corpus characteristics to pipeline design"
  },
  "estimated_llm_calls": 30,
  "estimated_depth_profile": "description of depth across phases",
  "estimated_total_cost_usd": 15.0
}

IMPORTANT:
- Each phase MUST have either chain_key OR engine_key (not both, not neither)
- Set depends_on for ALL phases (empty list if no dependencies)
- Use phase numbers that allow future insertion (1.0, 1.5, 2.0, 2.5, 3.0, etc.)
- iteration_mode defaults to "single" if not specified
"""


def _build_adaptive_user_prompt(
    request: OrchestratorPlanRequest,
    book_samples: list[BookSample],
    objective,  # AnalysisObjective
    catalog_text: str,
    baseline_workflow_text: Optional[str] = None,
) -> str:
    """Build the user prompt for adaptive planning."""
    lines = []

    # 1. Analysis Objective
    lines.append("# ANALYSIS OBJECTIVE")
    lines.append("")
    lines.append(f"## {objective.objective_name} (key: {objective.objective_key})")
    lines.append("")
    lines.append("### Primary Goals")
    for goal in objective.primary_goals:
        lines.append(f"- {goal}")
    lines.append("")
    lines.append("### Quality Criteria")
    for criterion in objective.quality_criteria:
        lines.append(f"- {criterion}")
    lines.append("")
    lines.append("### Expected Deliverables")
    for deliverable in objective.expected_deliverables:
        lines.append(f"- {deliverable}")
    lines.append("")

    if objective.preferred_engine_functions:
        lines.append(f"### Preferred Engine Functions: {', '.join(objective.preferred_engine_functions)}")
    if objective.preferred_categories:
        lines.append(f"### Preferred Categories: {', '.join(objective.preferred_categories)}")
    lines.append("")

    # 2. Book Samples
    lines.append("# BOOK SAMPLES")
    lines.append("")
    for sample in book_samples:
        lines.append(f"## {sample.title} ({sample.role})")
        lines.append(f"- Genre: {sample.genre}")
        lines.append(f"- Domain: {sample.domain}")
        lines.append(f"- Argumentative style: {sample.argumentative_style}")
        lines.append(f"- Technical level: {sample.technical_level}")
        lines.append(f"- Reasoning modes: {', '.join(sample.reasoning_modes)}")
        lines.append(f"- Length: {sample.estimated_length_chars:,} chars")
        if sample.key_vocabulary_sample:
            lines.append(f"- Key vocabulary: {', '.join(sample.key_vocabulary_sample[:15])}")
        if sample.engine_category_affinities:
            affinities = ", ".join(
                f"{cat}={score:.1f}"
                for cat, score in sorted(sample.engine_category_affinities.items(), key=lambda x: -x[1])
                if score > 0.3
            )
            lines.append(f"- Engine affinities: {affinities}")
        if sample.structural_notes:
            lines.append(f"- Structure: {sample.structural_notes}")
        lines.append("")

    # 3. Baseline workflow (if any)
    if baseline_workflow_text:
        lines.append("# BASELINE WORKFLOW (modify/extend as needed)")
        lines.append("")
        lines.append(baseline_workflow_text)
        lines.append("")

    # 4. Objective's planner strategy
    if objective.planner_strategy:
        lines.append("# PLANNING STRATEGY GUIDELINES")
        lines.append("")
        lines.append(objective.planner_strategy)
        lines.append("")

    # 5. Capability catalog
    lines.append("# CAPABILITY CATALOG")
    lines.append("")
    lines.append(catalog_text)
    lines.append("")

    # 6. Analysis request
    lines.append("---")
    lines.append("")
    lines.append("# ANALYSIS REQUEST")
    lines.append("")
    lines.append(f"## Thinker: {request.thinker_name}")
    lines.append("")
    lines.append(f"## Target Work: {request.target_work.title}")
    if request.target_work.author:
        lines.append(f"Author: {request.target_work.author}")
    if request.target_work.year:
        lines.append(f"Year: {request.target_work.year}")
    lines.append(f"Description: {request.target_work.description}")
    lines.append("")

    if request.prior_works:
        lines.append(f"## Prior Works ({len(request.prior_works)} total)")
        lines.append("")
        for i, pw in enumerate(request.prior_works, 1):
            year_str = f" ({pw.year})" if pw.year else ""
            lines.append(f"{i}. **{pw.title}**{year_str}")
            if pw.description:
                lines.append(f"   Description: {pw.description}")
            if pw.relationship_hint:
                lines.append(f"   Relationship hint: {pw.relationship_hint}")
        lines.append("")

    if request.research_question:
        lines.append(f"## Research Question")
        lines.append(request.research_question)
        lines.append("")

    if request.depth_preference:
        lines.append(f"## User Depth Preference: {request.depth_preference}")
        lines.append("")

    if request.focus_hint:
        lines.append(f"## Focus Hint: {request.focus_hint}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Now produce a bespoke WorkflowExecutionPlan (JSON only, no markdown fences) "
                 "that achieves the analysis objective for this specific corpus.")

    return "\n".join(lines)


def generate_adaptive_plan(
    request: OrchestratorPlanRequest,
    book_samples: list[BookSample],
    objective,  # AnalysisObjective
) -> WorkflowExecutionPlan:
    """Generate an adaptive analysis plan using Opus.

    This is the core function. It:
    1. Assembles the full capability catalog
    2. Optionally loads the baseline workflow
    3. Builds a rich prompt with objective + samples + catalog
    4. Calls Opus for strategic planning
    5. Parses and validates the plan
    6. Saves to disk

    Args:
        request: The analysis request (thinker context, works metadata)
        book_samples: Pre-computed book samples from the sampler
        objective: The analysis objective driving this plan

    Returns:
        A WorkflowExecutionPlan with adaptive fields populated
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("LLM service unavailable. Set ANTHROPIC_API_KEY.")

    # Assemble catalog — no workflow_key filter so we see ALL engines
    catalog = assemble_full_catalog()
    catalog_text = catalog_to_text(catalog)

    # Load baseline workflow text if objective references one
    baseline_workflow_text = None
    if objective.baseline_workflow_key:
        baseline_catalog = assemble_full_catalog(
            workflow_key=objective.baseline_workflow_key
        )
        if baseline_catalog.get("workflow"):
            baseline_workflow_text = catalog_to_text(
                {"workflow": baseline_catalog["workflow"], "depth_levels_explanation": {}},
                workflow_name=baseline_catalog["workflow"][0].get("workflow_name"),
            )

    # Build prompts
    system_prompt = ADAPTIVE_SYSTEM_PROMPT.strip()
    user_prompt = _build_adaptive_user_prompt(
        request=request,
        book_samples=book_samples,
        objective=objective,
        catalog_text=catalog_text,
        baseline_workflow_text=baseline_workflow_text,
    )

    logger.info(
        f"Generating adaptive plan for {request.thinker_name} — "
        f"objective: {objective.objective_key}, "
        f"target: {request.target_work.title}, "
        f"{len(request.prior_works)} prior works, "
        f"{len(book_samples)} book samples"
    )

    # Call Opus for adaptive planning (needs deep reasoning)
    model = "claude-opus-4-6"
    raw_text = ""
    total_input = 0
    total_output = 0

    try:
        import httpx
        from anthropic import Anthropic
        client = Anthropic(
            timeout=httpx.Timeout(connect=60.0, read=600.0, write=60.0, pool=60.0),
        )

        response = client.messages.create(
            model=model,
            max_tokens=48000,
            thinking={
                "type": "enabled",
                "budget_tokens": 16000,
            },
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response (skip thinking blocks)
        for block in response.content:
            if hasattr(block, "text"):
                raw_text = block.text
                break

        total_input = response.usage.input_tokens
        total_output = response.usage.output_tokens

    except Exception as e:
        logger.error(f"Adaptive plan generation failed: {e}")
        raise RuntimeError(f"Adaptive plan generation failed: {e}") from e

    logger.info(
        f"Adaptive plan generation complete — "
        f"input: {total_input:,}, output: {total_output:,} tokens"
    )

    # Parse LLM response
    try:
        content = raw_text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()
        plan_data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse adaptive plan JSON: {e}")
        logger.error(f"Raw response (first 500 chars): {raw_text[:500]}")
        raise RuntimeError(
            f"LLM returned invalid JSON. First 200 chars: {raw_text[:200]}"
        ) from e

    # Build plan with adaptive fields
    plan = WorkflowExecutionPlan(
        workflow_key=objective.baseline_workflow_key or "adaptive",
        thinker_name=request.thinker_name,
        target_work=request.target_work,
        prior_works=request.prior_works,
        research_question=request.research_question,
        strategy_summary=plan_data.get("strategy_summary", ""),
        phases=[],
        recommended_views=[],
        estimated_llm_calls=plan_data.get("estimated_llm_calls", 0),
        estimated_depth_profile=plan_data.get("estimated_depth_profile", ""),
        model_used=model,
        generation_tokens=total_input + total_output,
        # Adaptive fields
        objective_key=objective.objective_key,
        book_samples=[s.model_dump() for s in book_samples],
        estimated_total_cost_usd=plan_data.get("estimated_total_cost_usd", 0.0),
    )

    # Parse phases
    for phase_data in plan_data.get("phases", []):
        engine_overrides = None
        if phase_data.get("engine_overrides"):
            engine_overrides = {}
            for ek, ev in phase_data["engine_overrides"].items():
                engine_overrides[ek] = EngineExecutionSpec(
                    engine_key=ev.get("engine_key", ek),
                    depth=ev.get("depth", "standard"),
                    focus_dimensions=ev.get("focus_dimensions"),
                    focus_capabilities=ev.get("focus_capabilities"),
                    rationale=ev.get("rationale", ""),
                )

        phase = PhaseExecutionSpec(
            phase_number=phase_data.get("phase_number", 0),
            phase_name=phase_data.get("phase_name", ""),
            skip=phase_data.get("skip", False),
            skip_reason=phase_data.get("skip_reason"),
            depth=phase_data.get("depth", "standard"),
            engine_overrides=engine_overrides,
            context_emphasis=phase_data.get("context_emphasis"),
            rationale=phase_data.get("rationale", ""),
            model_hint=phase_data.get("model_hint"),
            requires_full_documents=phase_data.get("requires_full_documents", False),
            per_work_overrides=phase_data.get("per_work_overrides"),
            supplementary_chains=phase_data.get("supplementary_chains"),
            max_context_chars_override=phase_data.get("max_context_chars_override"),
            # Adaptive fields
            chain_key=phase_data.get("chain_key"),
            engine_key=phase_data.get("engine_key"),
            iteration_mode=phase_data.get("iteration_mode"),
            per_work_chain_map=phase_data.get("per_work_chain_map"),
            depends_on=phase_data.get("depends_on"),
            estimated_tokens=phase_data.get("estimated_tokens", 0),
            estimated_cost_usd=phase_data.get("estimated_cost_usd", 0.0),
        )
        plan.phases.append(phase)

    # Parse view recommendations
    for view_data in plan_data.get("recommended_views", []):
        view = ViewRecommendation(
            view_key=view_data.get("view_key", ""),
            priority=view_data.get("priority", "secondary"),
            presentation_stance_override=view_data.get("presentation_stance_override"),
            rationale=view_data.get("rationale", ""),
        )
        plan.recommended_views.append(view)

    # Parse decision trace
    trace_data = plan_data.get("decision_trace")
    if trace_data:
        from .schemas import (
            PlannerDecisionTrace, SamplingInsight, ObjectiveAlignmentEntry,
            PhaseDecision, PerWorkDecision, CatalogCoverageEntry,
        )
        try:
            plan.decision_trace = PlannerDecisionTrace(
                sampling_insights=[SamplingInsight(**si) for si in trace_data.get("sampling_insights", [])],
                objective_alignment=[ObjectiveAlignmentEntry(**oa) for oa in trace_data.get("objective_alignment", [])],
                phase_decisions=[PhaseDecision(**pd) for pd in trace_data.get("phase_decisions", [])],
                per_work_decisions=[PerWorkDecision(**pwd) for pwd in trace_data.get("per_work_decisions", [])],
                catalog_coverage=[CatalogCoverageEntry(**cc) for cc in trace_data.get("catalog_coverage", [])],
                overall_strategy_rationale=trace_data.get("overall_strategy_rationale", ""),
            )
            logger.info(f"Decision trace parsed: {len(plan.decision_trace.phase_decisions)} phase decisions, "
                        f"{len(plan.decision_trace.catalog_coverage)} catalog entries")
        except Exception as e:
            logger.warning(f"Failed to parse decision_trace: {e}")

    # Save using the same mechanism as legacy planner
    from .planner import _save_plan
    _save_plan(plan)

    logger.info(
        f"Adaptive plan {plan.plan_id} generated — "
        f"objective: {objective.objective_key}, "
        f"{len(plan.phases)} phases, "
        f"{plan.estimated_llm_calls} estimated LLM calls, "
        f"${plan.estimated_total_cost_usd:.2f} estimated cost"
    )

    return plan
