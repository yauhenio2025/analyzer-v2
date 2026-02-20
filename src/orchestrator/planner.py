"""LLM-powered plan generation for the orchestrator.

Calls Claude Opus with the capability catalog + thinker context
and returns a validated WorkflowExecutionPlan.

The planner is an LLM call, not Python engineering. The LLM reads
the full capability catalog and makes curatorial decisions that
adapt the workflow to the specific thinker's intellectual profile.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from .catalog import assemble_full_catalog, catalog_to_text
from .schemas import (
    OrchestratorPlanRequest,
    PlanRefinementRequest,
    WorkflowExecutionPlan,
)

logger = logging.getLogger(__name__)

# Plan storage (file-based for now)
PLANS_DIR = Path(__file__).parent / "plans"

SYSTEM_PROMPT = """You are a research strategist planning an intellectual genealogy analysis.

You have access to a CAPABILITY CATALOG describing all available analytical engines, chains, stances, and views. Your job is to produce a WorkflowExecutionPlan that adapts the standard 5-phase genealogy workflow to a specific thinker and corpus.

## Your Task

Given:
- A thinker's name and intellectual profile
- A target work (the work being analyzed)
- Prior works (earlier works to scan for genealogical traces)
- An optional research question

Produce a WorkflowExecutionPlan (JSON) that configures:
1. **Depth per phase** — surface/standard/deep based on what the thinker's corpus demands
2. **Engine overrides** — per-engine depth and focus dimensions within phases
3. **Context emphasis** — what to emphasize when threading context between phases
4. **View recommendations** — which views best present this analysis
5. **Strategy rationale** — WHY each decision was made

## Decision Guidelines

### Depth Selection
- Use **deep** for phases where the thinker's intellectual profile demands it:
  - Deep target profiling when the author has complex conceptual vocabulary
  - Deep evolution tactics detection when the author is known for reframing/appropriating ideas
  - Deep conditions analysis when the author's intellectual context is rich
- Use **standard** for most phases — it's the sweet spot of quality vs. cost
- Use **surface** only for triage or when the corpus is small/simple

### Engine Focus
- Not all dimensions need equal attention for every thinker
- For a Marxist economist like Varoufakis, prioritize: vocabulary_evolution, methodology_evolution, framing_evolution
- For a philosopher like Benanav, prioritize: conceptual_framework, inferential_commitments, metaphor_evolution
- For a historian like Slobodian, prioritize: conditions_of_possibility, intellectual context, path dependencies

### View Recommendations
The VIEWS section of the catalog includes per-view planner guidance with `Planner guidance:` annotations. Follow those hints when selecting views. General rules:
- Only recommend views with `planner_eligible: true` (views marked [NOT ELIGIBLE] are debug/utility views)
- Prioritize views with [HAS_TEMPLATE] — these produce structured data for rich rendering
- Views with `visibility: on_demand` should NOT be primary recommendations
- Child views (those with a `Parent:` field) are auto-included when their parent is recommended — no need to recommend them separately
- Read each view's planner guidance carefully and match it to the thinker's profile

### Phase Skipping
- You CAN recommend skipping phases, but this should be rare
- Only skip if the corpus clearly doesn't warrant it (e.g., single prior work → simplified scanning)

### Expanded Target Analysis (Phase 1.0) — Supplementary Chains
Phase 1.0 runs a core 4-engine chain (genealogy_target_profiling). You can ALSO select 1-3 supplementary chains from the catalog to run AFTER the core chain. Their outputs concatenate with the core analysis, creating a richer distilled target profile.

**When to add supplementary chains**:
- Thinker has a rich argumentative style → add `argument_analysis_chain` (argument_architecture + rhetorical_strategy)
- Thinker has complex rhetorical patterns → add `rhetorical_analysis_chain`
- Thinker draws from specific intellectual traditions → add `conceptual_deep_dive_chain`
- Thinker is known for anomalous claims → add `anomaly_evidence_chain`
- When in doubt, add 1-2 supplementary chains. The cost is moderate but the downstream benefit is significant.

**When you add supplementary chains**, also set `max_context_chars_override: 150000` on Phase 1.0 so the expanded analysis passes through to downstream phases without being truncated at the default 50K limit.

**Supplementary chains field**: `"supplementary_chains": ["argument_analysis_chain", "rhetorical_analysis_chain"]`

### Document Strategy for Per-Work Phases (1.5, 2.0)
Per-work phases (1.5 Relationship Classification, 2.0 Prior Work Scanning) now receive the DISTILLED target analysis from Phase 1.0 instead of the raw target text. This means:
- `requires_full_documents` on Phases 1.5 and 2.0 should be `false` (the distilled analysis is ~100-150K chars, not 500K+)
- Phase 1.0 should have `requires_full_documents: true` (it processes the raw target text)
- The per-work phases depend on Phase 1.0 completing first (1.5 now has `depends_on_phases: [1.0]`)
- Each per-work call sees: ~37K distilled analysis + ~200K prior work text = ~237K total (vs. ~370K before)

## Output Format

Return ONLY valid JSON matching this exact structure (no markdown fences, no explanation outside JSON):

{
  "strategy_summary": "2-3 paragraphs explaining the overall analytical approach for this thinker",
  "phases": [
    {
      "phase_number": 1.0,
      "phase_name": "Deep Target Work Profiling",
      "skip": false,
      "depth": "deep",
      "requires_full_documents": true,
      "supplementary_chains": ["argument_analysis_chain", "rhetorical_analysis_chain"],
      "max_context_chars_override": 150000,
      "engine_overrides": {
        "conceptual_framework_extraction": {
          "engine_key": "conceptual_framework_extraction",
          "depth": "deep",
          "focus_dimensions": ["vocabulary_map", "methodological_signature"],
          "rationale": "Varoufakis coins new terms and imports economic methodology"
        }
      },
      "context_emphasis": "Focus on economic vocabulary and Marxist conceptual framework",
      "rationale": "Deep profiling with supplementary argument + rhetorical analysis needed because Varoufakis has a complex vocabulary and distinctive argumentative style..."
    },
    {
      "phase_number": 1.5,
      "phase_name": "Relationship Classification",
      "skip": false,
      "depth": "standard",
      "requires_full_documents": false,
      "rationale": "Uses distilled target analysis from Phase 1.0, not raw text..."
    }
  ],
  "recommended_views": [
    {
      "view_key": "genealogy_portrait",
      "priority": "primary",
      "rationale": "The synthesis narrative is essential for understanding..."
    }
  ],
  "estimated_llm_calls": 30,
  "estimated_depth_profile": "deep profiling, standard classification, standard scanning, deep synthesis, deep final"
}
"""


def _get_client():
    """Get Anthropic client for plan generation.

    Configured with HTTP timeouts to prevent infinite hangs on dead sockets.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
        import anthropic
        return anthropic.Anthropic(
            api_key=api_key,
            timeout=httpx.Timeout(
                connect=60.0,
                read=300.0,   # 5 min max silence on socket
                write=60.0,
                pool=60.0,
            ),
        )
    except ImportError:
        logger.warning("anthropic library not installed")
        return None


def _build_user_prompt(request: OrchestratorPlanRequest, catalog_text: str) -> str:
    """Build the user prompt with catalog + thinker context."""
    lines = []

    lines.append(catalog_text)
    lines.append("")
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
    lines.append("Now produce a WorkflowExecutionPlan (JSON only, no markdown fences) for this thinker and corpus.")

    return "\n".join(lines)


def _save_plan(plan: WorkflowExecutionPlan) -> None:
    """Persist plan to disk."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    plan_path = PLANS_DIR / f"{plan.plan_id}.json"
    with open(plan_path, "w") as f:
        f.write(plan.model_dump_json(indent=2))
    logger.info(f"Plan saved to {plan_path}")


def load_plan(plan_id: str) -> Optional[WorkflowExecutionPlan]:
    """Load a plan from disk."""
    plan_path = PLANS_DIR / f"{plan_id}.json"
    if not plan_path.exists():
        return None
    with open(plan_path, "r") as f:
        data = json.load(f)
    return WorkflowExecutionPlan.model_validate(data)


def list_plans() -> list[dict]:
    """List all saved plans (summary only)."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    plans = []
    for plan_path in sorted(PLANS_DIR.glob("*.json"), reverse=True):
        try:
            with open(plan_path, "r") as f:
                data = json.load(f)
            plans.append({
                "plan_id": data.get("plan_id", plan_path.stem),
                "thinker_name": data.get("thinker_name", "?"),
                "target_work": data.get("target_work", {}).get("title", "?"),
                "status": data.get("status", "draft"),
                "created_at": data.get("created_at", ""),
                "estimated_depth_profile": data.get("estimated_depth_profile", ""),
            })
        except Exception as e:
            logger.warning(f"Failed to read plan {plan_path}: {e}")
    return plans


def generate_plan(request: OrchestratorPlanRequest) -> WorkflowExecutionPlan:
    """Generate a WorkflowExecutionPlan using Claude Opus.

    1. Assembles capability catalog from all registries
    2. Builds prompt with catalog + thinker context
    3. Calls Claude Opus for strategic planning
    4. Parses and validates response
    5. Saves plan to disk

    Raises:
        RuntimeError: If LLM is unavailable or response is invalid
    """
    client = _get_client()
    if client is None:
        raise RuntimeError(
            "LLM service unavailable. Set ANTHROPIC_API_KEY environment variable."
        )

    # Assemble catalog
    catalog = assemble_full_catalog()
    catalog_text = catalog_to_text(catalog)

    # Build prompt
    user_prompt = _build_user_prompt(request, catalog_text)

    logger.info(
        f"Generating plan for {request.thinker_name} — "
        f"target: {request.target_work.title}, "
        f"{len(request.prior_works)} prior works"
    )

    # Call Claude Sonnet 4.6 — sync API for speed on Render (no thinking needed
    # for structured JSON output; thinking adds latency without improving plans).
    model = "claude-sonnet-4-6"

    raw_text = ""
    total_input = 0
    total_output = 0

    try:
        import httpx
        from anthropic import Anthropic
        sync_client = Anthropic(
            timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=60.0),
        )
        response = sync_client.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        for block in response.content:
            if hasattr(block, "text"):
                raw_text = block.text
                break

        total_input = response.usage.input_tokens
        total_output = response.usage.output_tokens

    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise RuntimeError(f"Plan generation failed: {e}") from e

    logger.info(
        f"Plan generation complete — "
        f"input: {total_input}, output: {total_output} tokens"
    )

    # Parse LLM response
    try:
        # Strip markdown fences if present
        content = raw_text.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        plan_data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response (first 500 chars): {raw_text[:500]}")
        raise RuntimeError(
            f"LLM returned invalid JSON. First 200 chars: {raw_text[:200]}"
        ) from e

    # Build full plan from LLM output + request context
    plan = WorkflowExecutionPlan(
        workflow_key="intellectual_genealogy",
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
    )

    # Parse phases
    from .schemas import PhaseExecutionSpec, EngineExecutionSpec, ViewRecommendation

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
            # Milestone 2 fields
            model_hint=phase_data.get("model_hint"),
            requires_full_documents=phase_data.get("requires_full_documents", False),
            per_work_overrides=phase_data.get("per_work_overrides"),
            # Milestone 5 fields
            supplementary_chains=phase_data.get("supplementary_chains"),
            max_context_chars_override=phase_data.get("max_context_chars_override"),
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

    # Save
    _save_plan(plan)

    return plan


def refine_plan(
    plan: WorkflowExecutionPlan,
    refinement: PlanRefinementRequest,
) -> WorkflowExecutionPlan:
    """Refine an existing plan based on user feedback.

    Calls Claude with the existing plan + feedback and produces an updated plan.
    """
    client = _get_client()
    if client is None:
        raise RuntimeError("LLM service unavailable.")

    # Apply specific changes first (if any)
    if refinement.specific_changes:
        plan_dict = plan.model_dump()
        for key, value in refinement.specific_changes.items():
            if key in plan_dict:
                plan_dict[key] = value
        plan = WorkflowExecutionPlan.model_validate(plan_dict)

    # Build refinement prompt
    refinement_prompt = f"""Here is the current WorkflowExecutionPlan:

```json
{plan.model_dump_json(indent=2)}
```

The user has provided the following feedback:

{refinement.feedback}

Please produce an UPDATED plan (complete JSON, same schema) that addresses this feedback.
Preserve everything that doesn't need changing. Explain your changes in the rationale fields.

Return ONLY the JSON — no markdown fences, no explanation outside the JSON."""

    model = "claude-sonnet-4-6"

    try:
        import httpx
        from anthropic import Anthropic
        sync_client = Anthropic(
            timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=60.0),
        )
        response = sync_client.messages.create(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": refinement_prompt}],
        )

        raw_text = ""
        for block in response.content:
            if hasattr(block, "text"):
                raw_text = block.text
                break

    except Exception as e:
        raise RuntimeError(f"Refinement failed: {e}") from e

    # Parse
    content = raw_text.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]

    try:
        updated_data = json.loads(content.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON during refinement: {e}") from e

    # Rebuild plan preserving identity and context
    updated_plan = WorkflowExecutionPlan(
        plan_id=plan.plan_id,  # Keep same ID
        created_at=plan.created_at,
        workflow_key=plan.workflow_key,
        thinker_name=plan.thinker_name,
        target_work=plan.target_work,
        prior_works=plan.prior_works,
        research_question=plan.research_question,
        strategy_summary=updated_data.get("strategy_summary", plan.strategy_summary),
        estimated_llm_calls=updated_data.get("estimated_llm_calls", plan.estimated_llm_calls),
        estimated_depth_profile=updated_data.get("estimated_depth_profile", plan.estimated_depth_profile),
        model_used=model,
        generation_tokens=plan.generation_tokens + response.usage.input_tokens + response.usage.output_tokens,
        status="draft",
    )

    # Parse phases from updated data
    from .schemas import PhaseExecutionSpec, EngineExecutionSpec, ViewRecommendation

    for phase_data in updated_data.get("phases", []):
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
        )
        updated_plan.phases.append(phase)

    for view_data in updated_data.get("recommended_views", []):
        view = ViewRecommendation(
            view_key=view_data.get("view_key", ""),
            priority=view_data.get("priority", "secondary"),
            presentation_stance_override=view_data.get("presentation_stance_override"),
            rationale=view_data.get("rationale", ""),
        )
        updated_plan.recommended_views.append(view)

    _save_plan(updated_plan)
    return updated_plan
