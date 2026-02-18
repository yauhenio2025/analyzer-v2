"""Extension point scorer for workflow phases.

Scores every engine in the system for composability fit with a given
workflow phase. Uses a 5-tier weighted scoring algorithm:

  Tier 1: Synergy (0.30)     — explicit synergy_engines match
  Tier 2: Dimension prod (0.25) — produces dimensions consumed by phase engines
  Tier 3: Dimension novelty (0.20) — covers new dimensions
  Tier 4: Capability gap (0.15)  — fills missing capabilities
  Tier 5: Category affinity (0.10) — same category/kind

Engines with v2 capability definitions get full scoring.
Engines without v2 data get category/kind scoring only (lower confidence).
"""

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from src.chains.registry import get_chain_registry
from src.engines.registry import get_engine_registry
from src.engines.schemas import EngineCategory, EngineKind
from src.engines.schemas_v2 import CapabilityEngineDefinition
from src.workflows.extension_points import (
    CandidateEngine,
    CapabilityGap,
    DimensionCoverage,
    PhaseExtensionPoint,
    WorkflowExtensionAnalysis,
)
from src.workflows.registry import get_workflow_registry
from src.workflows.schemas import WorkflowDefinition, WorkflowPhase

logger = logging.getLogger(__name__)

# Scoring weights
WEIGHT_SYNERGY = 0.30
WEIGHT_DIMENSION_PRODUCTION = 0.25
WEIGHT_DIMENSION_NOVELTY = 0.20
WEIGHT_CAPABILITY_GAP = 0.15
WEIGHT_CATEGORY_AFFINITY = 0.10

# Recommendation tier thresholds
TIER_STRONG = 0.65
TIER_MODERATE = 0.40
TIER_EXPLORATORY = 0.20


def _get_tier(score: float) -> str:
    """Map composite score to recommendation tier."""
    if score >= TIER_STRONG:
        return "strong"
    elif score >= TIER_MODERATE:
        return "moderate"
    elif score >= TIER_EXPLORATORY:
        return "exploratory"
    return "tangential"


class PhaseContext:
    """Collected context about a phase's current engines for scoring."""

    def __init__(self):
        self.engine_keys: list[str] = []
        self.cap_engines: dict[str, CapabilityEngineDefinition] = {}

        # Aggregated from v2 definitions
        self.all_synergy_engines: set[str] = set()
        self.all_produced_dimensions: set[str] = set()
        self.all_required_dimensions: set[str] = set()
        self.all_capability_keys: set[str] = set()
        self.all_shared_dimensions: set[str] = set()
        self.all_consumed_dimensions: set[str] = set()
        self.categories: list[str] = []
        self.kinds: list[str] = []

    def add_v2_engine(self, cap_engine: CapabilityEngineDefinition) -> None:
        """Add a v2 engine's data to the context."""
        self.cap_engines[cap_engine.engine_key] = cap_engine

        # Synergy
        self.all_synergy_engines.update(cap_engine.composability.synergy_engines)

        # Dimensions
        for cap in cap_engine.capabilities:
            self.all_produced_dimensions.update(cap.produces_dimensions)
            self.all_required_dimensions.update(cap.requires_dimensions)
            self.all_capability_keys.add(cap.key)

        for dim in cap_engine.analytical_dimensions:
            self.all_produced_dimensions.add(dim.key)

        # Composability
        self.all_shared_dimensions.update(cap_engine.composability.shares_with.keys())
        self.all_consumed_dimensions.update(cap_engine.composability.consumes_from.keys())

        self.categories.append(cap_engine.category.value)
        self.kinds.append(cap_engine.kind.value)

    def add_legacy_engine(self, engine_key: str, category: str, kind: str) -> None:
        """Add a legacy engine's basic info to the context."""
        self.categories.append(category)
        self.kinds.append(kind)

    @property
    def majority_category(self) -> Optional[str]:
        if not self.categories:
            return None
        return Counter(self.categories).most_common(1)[0][0]

    @property
    def majority_kind(self) -> Optional[str]:
        if not self.kinds:
            return None
        return Counter(self.kinds).most_common(1)[0][0]


def _build_phase_context(phase: WorkflowPhase) -> PhaseContext:
    """Build a PhaseContext from a workflow phase's current engines."""
    ctx = PhaseContext()
    engine_registry = get_engine_registry()
    chain_registry = get_chain_registry()

    # Collect engine keys from the phase
    engine_keys: list[str] = []
    if phase.engine_key:
        engine_keys.append(phase.engine_key)
    if phase.chain_key:
        chain = chain_registry.get(phase.chain_key)
        if chain:
            engine_keys.extend(chain.engine_keys)

    ctx.engine_keys = engine_keys

    # Load v2 definitions where available
    for ek in engine_keys:
        cap_engine = engine_registry.get_capability_definition(ek)
        if cap_engine:
            ctx.add_v2_engine(cap_engine)
        else:
            # Fall back to legacy definition for category/kind
            legacy = engine_registry.get(ek)
            if legacy:
                ctx.add_legacy_engine(ek, legacy.category.value, legacy.kind.value)

    return ctx


def _score_synergy(candidate: CapabilityEngineDefinition, ctx: PhaseContext) -> tuple[float, list[str], list[str]]:
    """Tier 1: Score based on explicit synergy_engines matches.

    Returns (score, synergy_with_list, rationale_items).
    """
    synergy_with = []
    rationale = []

    # Check if candidate is in any current engine's synergy list
    for ek, cap_eng in ctx.cap_engines.items():
        if candidate.engine_key in cap_eng.composability.synergy_engines:
            synergy_with.append(ek)

    # Check if any current engine is in candidate's synergy list
    for ek in ctx.engine_keys:
        if ek in candidate.composability.synergy_engines and ek not in synergy_with:
            synergy_with.append(ek)

    if not synergy_with:
        return 0.0, [], []

    # Normalize: cap at 1.0 if synergy with multiple engines
    max_possible = max(len(ctx.engine_keys), 1)
    score = min(len(synergy_with) / max_possible, 1.0)

    for ek in synergy_with:
        rationale.append(f"Explicit synergy with {ek} — designed to work together")

    return score, synergy_with, rationale


def _score_dimension_production(
    candidate: CapabilityEngineDefinition, ctx: PhaseContext
) -> tuple[float, list[str]]:
    """Tier 2: Score based on producing dimensions that phase engines consume.

    Returns (score, rationale_items).
    """
    if not ctx.all_required_dimensions and not ctx.all_consumed_dimensions:
        return 0.0, []

    needed = ctx.all_required_dimensions | ctx.all_consumed_dimensions

    # What dimensions does the candidate produce?
    candidate_produces = set()
    for cap in candidate.capabilities:
        candidate_produces.update(cap.produces_dimensions)
    for dim in candidate.analytical_dimensions:
        candidate_produces.add(dim.key)
    candidate_produces.update(candidate.composability.shares_with.keys())

    matched = needed & candidate_produces
    if not matched:
        return 0.0, []

    score = len(matched) / max(len(needed), 1)
    rationale = []
    for dim in list(matched)[:3]:  # limit rationale items
        # Find which engine needs it
        consumers = []
        for ek, cap_eng in ctx.cap_engines.items():
            for cap in cap_eng.capabilities:
                if dim in cap.requires_dimensions:
                    consumers.append(ek)
                    break
            if dim in cap_eng.composability.consumes_from:
                if ek not in consumers:
                    consumers.append(ek)
        consumer_str = ", ".join(consumers[:2]) if consumers else "phase engines"
        rationale.append(f"Produces '{dim}' consumed by {consumer_str}")

    return min(score, 1.0), rationale


def _score_dimension_novelty(
    candidate: CapabilityEngineDefinition, ctx: PhaseContext
) -> tuple[float, list[str], list[str]]:
    """Tier 3: Score based on covering dimensions no current engine covers.

    Returns (score, dimensions_added, rationale_items).
    """
    # What dimensions does the candidate produce?
    candidate_produces = set()
    for cap in candidate.capabilities:
        candidate_produces.update(cap.produces_dimensions)
    for dim in candidate.analytical_dimensions:
        candidate_produces.add(dim.key)
    candidate_produces.update(candidate.composability.shares_with.keys())

    if not candidate_produces:
        return 0.0, [], []

    # Novel = candidate produces but phase doesn't already cover
    novel = candidate_produces - ctx.all_produced_dimensions
    if not novel:
        return 0.0, [], []

    score = len(novel) / max(len(candidate_produces), 1)

    # Boost if the phase has low coverage overall
    if len(ctx.all_produced_dimensions) < 3:
        score = min(score * 1.3, 1.0)

    dimensions_added = sorted(novel)
    dim_preview = ", ".join(dimensions_added[:4])
    suffix = f" (+{len(dimensions_added) - 4} more)" if len(dimensions_added) > 4 else ""
    rationale = [f"Covers new dimensions: {dim_preview}{suffix}"]

    return min(score, 1.0), dimensions_added, rationale


def _score_capability_gap(
    candidate: CapabilityEngineDefinition, ctx: PhaseContext
) -> tuple[float, list[str], list[str]]:
    """Tier 4: Score based on filling capabilities the phase lacks.

    Returns (score, capabilities_added, rationale_items).
    """
    candidate_capabilities = {cap.key for cap in candidate.capabilities}
    if not candidate_capabilities:
        return 0.0, [], []

    unique_caps = candidate_capabilities - ctx.all_capability_keys
    if not unique_caps:
        return 0.0, [], []

    score = len(unique_caps) / max(len(candidate_capabilities), 1)
    capabilities_added = sorted(unique_caps)

    cap_preview = ", ".join(capabilities_added[:3])
    rationale = [f"Adds capabilities: {cap_preview}"]

    return min(score, 1.0), capabilities_added, rationale


def _score_category_affinity(
    candidate_category: str, candidate_kind: str, ctx: PhaseContext
) -> tuple[float, list[str]]:
    """Tier 5: Score based on category/kind alignment.

    Returns (score, rationale_items).
    """
    score = 0.0
    rationale = []

    if ctx.majority_category and candidate_category == ctx.majority_category:
        score += 0.6
        rationale.append(f"Same analytical category ({candidate_category}) as phase engines")
    if ctx.majority_kind and candidate_kind == ctx.majority_kind:
        score += 0.4
    elif ctx.majority_category and candidate_category != ctx.majority_category:
        # Different category — small bonus for cross-domain potential
        score += 0.2

    return min(score, 1.0), rationale


def _score_legacy_engine(
    engine_key: str,
    engine_name: str,
    category: str,
    kind: str,
    ctx: PhaseContext,
) -> Optional[CandidateEngine]:
    """Score a legacy engine (no v2 definition) using category/kind only.

    Returns CandidateEngine or None if below threshold.
    """
    # Check synergy: if this engine appears in any current engine's synergy list
    synergy_with = []
    synergy_score = 0.0
    for ek, cap_eng in ctx.cap_engines.items():
        if engine_key in cap_eng.composability.synergy_engines:
            synergy_with.append(ek)
            synergy_score = min(len(synergy_with) / max(len(ctx.engine_keys), 1), 1.0)

    aff_score, aff_rationale = _score_category_affinity(category, kind, ctx)

    # Legacy engines only get synergy + category affinity scoring
    composite = (
        WEIGHT_SYNERGY * synergy_score
        + WEIGHT_CATEGORY_AFFINITY * aff_score
    )

    if composite < TIER_EXPLORATORY:
        return None

    rationale = []
    if synergy_with:
        for ek in synergy_with:
            rationale.append(f"Explicit synergy with {ek}")
    rationale.extend(aff_rationale)
    if not rationale:
        rationale.append(f"Category/kind alignment ({category}/{kind})")

    return CandidateEngine(
        engine_key=engine_key,
        engine_name=engine_name,
        category=category,
        kind=kind,
        synergy_score=synergy_score,
        dimension_production_score=0.0,
        dimension_novelty_score=0.0,
        category_affinity_score=aff_score,
        capability_gap_score=0.0,
        composite_score=composite,
        recommendation_tier=_get_tier(composite),
        has_full_composability=False,
        rationale=rationale,
        synergy_with=synergy_with,
        dimensions_added=[],
        capabilities_added=[],
        potential_issues=["No v2 capability definition — scoring based on category/kind only"],
    )


def _score_v2_engine(
    candidate: CapabilityEngineDefinition, ctx: PhaseContext
) -> Optional[CandidateEngine]:
    """Score a v2 engine against a phase context.

    Returns CandidateEngine or None if below threshold.
    """
    synergy_score, synergy_with, synergy_rationale = _score_synergy(candidate, ctx)
    dim_prod_score, dim_prod_rationale = _score_dimension_production(candidate, ctx)
    dim_nov_score, dimensions_added, dim_nov_rationale = _score_dimension_novelty(candidate, ctx)
    cap_gap_score, capabilities_added, cap_gap_rationale = _score_capability_gap(candidate, ctx)
    cat_aff_score, cat_aff_rationale = _score_category_affinity(
        candidate.category.value, candidate.kind.value, ctx
    )

    composite = (
        WEIGHT_SYNERGY * synergy_score
        + WEIGHT_DIMENSION_PRODUCTION * dim_prod_score
        + WEIGHT_DIMENSION_NOVELTY * dim_nov_score
        + WEIGHT_CAPABILITY_GAP * cap_gap_score
        + WEIGHT_CATEGORY_AFFINITY * cat_aff_score
    )

    if composite < TIER_EXPLORATORY:
        return None

    rationale = synergy_rationale + dim_prod_rationale + dim_nov_rationale + cap_gap_rationale + cat_aff_rationale

    # Detect potential issues
    potential_issues = []
    # Check for high overlap (redundancy)
    if candidate.engine_key in ctx.engine_keys:
        return None  # Already in the phase

    candidate_dims = set()
    for cap in candidate.capabilities:
        candidate_dims.update(cap.produces_dimensions)
    overlap = candidate_dims & ctx.all_produced_dimensions
    if overlap and len(overlap) > len(candidate_dims) * 0.7:
        potential_issues.append(
            f"High dimension overlap with existing engines ({len(overlap)}/{len(candidate_dims)} dimensions shared)"
        )

    return CandidateEngine(
        engine_key=candidate.engine_key,
        engine_name=candidate.engine_name,
        category=candidate.category.value,
        kind=candidate.kind.value,
        synergy_score=synergy_score,
        dimension_production_score=dim_prod_score,
        dimension_novelty_score=dim_nov_score,
        category_affinity_score=cat_aff_score,
        capability_gap_score=cap_gap_score,
        composite_score=round(composite, 3),
        recommendation_tier=_get_tier(composite),
        has_full_composability=True,
        rationale=rationale,
        synergy_with=synergy_with,
        dimensions_added=dimensions_added[:10],
        capabilities_added=capabilities_added[:10],
        potential_issues=potential_issues,
    )


def _compute_dimension_coverage(ctx: PhaseContext, all_v2_engines: list[CapabilityEngineDefinition]) -> list[DimensionCoverage]:
    """Compute dimension coverage for a phase."""
    # Collect all dimensions produced by current engines
    dim_covered_by: dict[str, list[str]] = {}
    dim_descriptions: dict[str, str] = {}

    for ek, cap_eng in ctx.cap_engines.items():
        for dim in cap_eng.analytical_dimensions:
            dim_covered_by.setdefault(dim.key, []).append(ek)
            dim_descriptions[dim.key] = dim.description
        for cap in cap_eng.capabilities:
            for dk in cap.produces_dimensions:
                dim_covered_by.setdefault(dk, []).append(ek)

    # Also check what OTHER engines could cover these dimensions + add uncovered ones
    all_dim_keys: set[str] = set(dim_covered_by.keys())
    dim_gap_engines: dict[str, list[str]] = {}

    for v2_eng in all_v2_engines:
        if v2_eng.engine_key in ctx.engine_keys:
            continue
        for dim in v2_eng.analytical_dimensions:
            all_dim_keys.add(dim.key)
            if dim.key not in dim_descriptions:
                dim_descriptions[dim.key] = dim.description
            if dim.key not in dim_covered_by or not dim_covered_by[dim.key]:
                dim_gap_engines.setdefault(dim.key, []).append(v2_eng.engine_key)
        for cap in v2_eng.capabilities:
            for dk in cap.produces_dimensions:
                all_dim_keys.add(dk)
                if dk not in dim_covered_by or not dim_covered_by[dk]:
                    dim_gap_engines.setdefault(dk, []).append(v2_eng.engine_key)

    # Only report dimensions relevant to this phase (currently covered or from synergy engines)
    relevant_dims = set(dim_covered_by.keys())
    # Add dimensions that gap engines could provide if phase has few dimensions
    if len(relevant_dims) < 5:
        for dk in dim_gap_engines:
            relevant_dims.add(dk)

    coverage = []
    for dk in sorted(relevant_dims):
        covered_by = dim_covered_by.get(dk, [])
        gap_engines = dim_gap_engines.get(dk, [])[:5]  # limit
        total_possible = len(covered_by) + len(gap_engines) if gap_engines else max(len(covered_by), 1)
        ratio = len(covered_by) / total_possible if total_possible > 0 else 1.0
        coverage.append(DimensionCoverage(
            dimension_key=dk,
            dimension_description=dim_descriptions.get(dk, ""),
            covered_by=list(set(covered_by)),
            gap_engines=gap_engines,
            coverage_ratio=round(ratio, 2),
        ))

    return sorted(coverage, key=lambda d: d.coverage_ratio)


def _compute_capability_gaps(ctx: PhaseContext, all_v2_engines: list[CapabilityEngineDefinition]) -> list[CapabilityGap]:
    """Find capabilities that no current engine in this phase provides."""
    # Collect all capability keys from v2 engines NOT in the phase
    external_caps: dict[str, list[str]] = {}  # cap_key -> [engine_keys]
    external_cap_desc: dict[str, str] = {}

    for v2_eng in all_v2_engines:
        if v2_eng.engine_key in ctx.engine_keys:
            continue
        for cap in v2_eng.capabilities:
            if cap.key not in ctx.all_capability_keys:
                external_caps.setdefault(cap.key, []).append(v2_eng.engine_key)
                if cap.key not in external_cap_desc:
                    external_cap_desc[cap.key] = cap.description

    # Score relevance by how many of the capability's required dimensions the phase covers
    gaps = []
    for cap_key, available_in in external_caps.items():
        # Simple relevance: based on category overlap
        relevance = 0.3  # base relevance
        # If any engine providing this cap is a synergy engine, boost
        for ek in available_in:
            if ek in ctx.all_synergy_engines:
                relevance = 0.8
                break

        gaps.append(CapabilityGap(
            capability_key=cap_key,
            capability_description=external_cap_desc.get(cap_key, ""),
            available_in=available_in[:5],
            relevance_score=round(relevance, 2),
        ))

    return sorted(gaps, key=lambda g: g.relevance_score, reverse=True)[:15]


def analyze_workflow_extensions(
    workflow_key: str,
    depth: str = "standard",
    phase_number: Optional[float] = None,
    min_score: float = 0.20,
    max_candidates: int = 15,
) -> WorkflowExtensionAnalysis:
    """Analyze extension points for a workflow.

    For each phase (or a specific phase), scores all engines in the system
    for composability fit and returns ranked candidates.
    """
    workflow_registry = get_workflow_registry()
    engine_registry = get_engine_registry()

    workflow = workflow_registry.get(workflow_key)
    if workflow is None:
        raise ValueError(f"Workflow not found: {workflow_key}")

    # Load all v2 capability definitions
    all_v2_engines = engine_registry.list_capability_definitions()
    # Load all legacy engines for fallback scoring
    all_legacy_engines = engine_registry.list_all()

    # Build set of v2 engine keys for quick lookup
    v2_keys = {e.engine_key for e in all_v2_engines}

    # Determine which phases to analyze
    phases_to_analyze = workflow.phases
    if phase_number is not None:
        phases_to_analyze = [p for p in workflow.phases if p.phase_number == phase_number]
        if not phases_to_analyze:
            raise ValueError(f"Phase {phase_number} not found in workflow {workflow_key}")

    phase_extensions = []
    all_candidate_keys: set[str] = set()
    all_strong_count = 0
    dimension_coverage_across: dict[str, int] = {}  # dim_key -> count of phases covering it

    for phase in phases_to_analyze:
        ctx = _build_phase_context(phase)

        # Score all v2 engines
        candidates: list[CandidateEngine] = []
        for v2_eng in all_v2_engines:
            if v2_eng.engine_key in ctx.engine_keys:
                continue  # Skip engines already in phase
            result = _score_v2_engine(v2_eng, ctx)
            if result and result.composite_score >= min_score:
                candidates.append(result)

        # Score legacy engines (those without v2 definitions)
        for legacy_eng in all_legacy_engines:
            if legacy_eng.engine_key in ctx.engine_keys:
                continue
            if legacy_eng.engine_key in v2_keys:
                continue  # Already scored as v2
            result = _score_legacy_engine(
                legacy_eng.engine_key,
                legacy_eng.engine_name,
                legacy_eng.category.value,
                legacy_eng.kind.value,
                ctx,
            )
            if result and result.composite_score >= min_score:
                candidates.append(result)

        # Sort by composite score, limit
        candidates.sort(key=lambda c: c.composite_score, reverse=True)
        candidates = candidates[:max_candidates]

        # Compute dimension coverage and capability gaps
        dim_coverage = _compute_dimension_coverage(ctx, all_v2_engines)
        cap_gaps = _compute_capability_gaps(ctx, all_v2_engines)

        # Track coverage across workflow
        for dc in dim_coverage:
            if dc.covered_by:
                dimension_coverage_across[dc.dimension_key] = (
                    dimension_coverage_across.get(dc.dimension_key, 0) + 1
                )

        # Determine extension potential
        strong_count = sum(1 for c in candidates if c.recommendation_tier == "strong")
        moderate_count = sum(1 for c in candidates if c.recommendation_tier == "moderate")

        if strong_count >= 3:
            extension_potential = "high"
        elif strong_count >= 1 or moderate_count >= 3:
            extension_potential = "moderate"
        else:
            extension_potential = "low"

        # Build summary
        summary_parts = []
        if strong_count:
            summary_parts.append(f"{strong_count} strong candidate{'s' if strong_count > 1 else ''}")
        if moderate_count:
            summary_parts.append(f"{moderate_count} moderate")
        low_coverage = [dc for dc in dim_coverage if dc.coverage_ratio < 0.3]
        if low_coverage:
            summary_parts.append(f"{len(low_coverage)} underserved dimension{'s' if len(low_coverage) > 1 else ''}")

        summary = ". ".join(summary_parts) + "." if summary_parts else "No strong extension candidates found."

        all_candidate_keys.update(c.engine_key for c in candidates)
        all_strong_count += strong_count

        phase_extensions.append(PhaseExtensionPoint(
            phase_number=phase.phase_number,
            phase_name=phase.phase_name,
            current_engines=ctx.engine_keys,
            current_chain_key=phase.chain_key,
            dimension_coverage=dim_coverage,
            capability_gaps=cap_gaps,
            candidate_engines=candidates,
            extension_potential=extension_potential,
            summary=summary,
        ))

    # Workflow-level insights
    total_phases = len(workflow.phases)
    underserved = [
        dk for dk, count in dimension_coverage_across.items()
        if count <= 1 and total_phases > 1
    ]

    # Workflow summary
    wf_summary_parts = []
    if all_strong_count:
        wf_summary_parts.append(f"{all_strong_count} strong recommendations across {len(phase_extensions)} phases")
    if underserved:
        wf_summary_parts.append(f"{len(underserved)} dimensions underserved across the workflow")
    high_phases = [pe for pe in phase_extensions if pe.extension_potential == "high"]
    if high_phases:
        names = ", ".join(pe.phase_name for pe in high_phases[:3])
        wf_summary_parts.append(f"Highest extension potential: {names}")

    workflow_summary = ". ".join(wf_summary_parts) + "." if wf_summary_parts else "Extension analysis complete."

    return WorkflowExtensionAnalysis(
        workflow_key=workflow_key,
        workflow_name=workflow.workflow_name,
        depth=depth,
        analysis_timestamp=datetime.now(timezone.utc).isoformat(),
        phase_extensions=phase_extensions,
        total_candidate_engines=len(all_candidate_keys),
        strong_recommendations=all_strong_count,
        underserved_dimensions=sorted(underserved)[:20],
        workflow_summary=workflow_summary,
    )
