"""Capability catalog assembly for the orchestrator.

Reads from all registries and produces a structured document that the
LLM planner uses to make decisions. This is the orchestrator's "menu" —
everything it can choose from.

The catalog is cached in memory and invalidated when definitions change.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _get_thinker_name(thinker) -> str:
    """Extract thinker name from ThinkerReference or string."""
    if isinstance(thinker, str):
        return thinker
    return getattr(thinker, "name", str(thinker))


def _get_tradition_name(tradition) -> str:
    """Extract tradition name from TraditionEntry or string."""
    if isinstance(tradition, str):
        return tradition
    return getattr(tradition, "name", str(tradition))


def _get_concept_name(concept) -> str:
    """Extract concept name from KeyConceptEntry or string."""
    if isinstance(concept, str):
        return concept
    return getattr(concept, "name", str(concept))


def assemble_engine_catalog() -> list[dict[str, Any]]:
    """Assemble capability engine summaries from the engine registry.

    Returns a list of engine entries with:
    - key, name, problematique
    - analytical dimensions (key + description + depth_guidance)
    - capabilities (key + description + depth_scaling)
    - composability (shares_with, consumes_from, synergy_engines)
    - depth levels (key, typical_passes, suitable_for)
    - intellectual lineage (primary thinker, traditions, key concepts)
    """
    from src.engines.registry import get_engine_registry

    registry = get_engine_registry()
    cap_defs = registry.list_capability_definitions()

    entries = []
    for cap_def in cap_defs:
        lineage = cap_def.intellectual_lineage
        entry = {
            "engine_key": cap_def.engine_key,
            "engine_name": cap_def.engine_name,
            "category": cap_def.category.value if hasattr(cap_def.category, "value") else str(cap_def.category),
            "problematique": cap_def.problematique,
            "intellectual_lineage": {
                "primary_thinker": _get_thinker_name(lineage.primary),
                "traditions": [_get_tradition_name(t) for t in lineage.traditions],
                "key_concepts": [_get_concept_name(c) for c in lineage.key_concepts],
            },
            "analytical_dimensions": [
                {
                    "key": dim.key,
                    "description": dim.description,
                    "depth_guidance": dim.depth_guidance,
                }
                for dim in cap_def.analytical_dimensions
            ],
            "capabilities": [
                {
                    "key": cap.key,
                    "description": cap.description,
                    "depth_scaling": cap.depth_scaling,
                }
                for cap in cap_def.capabilities
            ],
            "composability": {
                "shares_with": cap_def.composability.shares_with,
                "consumes_from": cap_def.composability.consumes_from,
                "synergy_engines": cap_def.composability.synergy_engines,
            },
            "depth_levels": [
                {
                    "key": dl.key,
                    "typical_passes": dl.typical_passes,
                    "suitable_for": dl.suitable_for,
                }
                for dl in cap_def.depth_levels
            ],
        }
        entries.append(entry)

    return entries


def assemble_chain_catalog() -> list[dict[str, Any]]:
    """Assemble chain definitions for the catalog."""
    from src.chains.registry import get_chain_registry

    registry = get_chain_registry()
    chains = registry.list_summaries()

    entries = []
    for chain_summary in chains:
        chain = registry.get(chain_summary.chain_key)
        if chain is None:
            continue
        entry = {
            "chain_key": chain.chain_key,
            "chain_name": chain.chain_name,
            "description": chain.description,
            "engine_keys": chain.engine_keys,
            "blend_mode": chain.blend_mode if hasattr(chain, "blend_mode") else "sequential",
            "category": chain.category.value if hasattr(chain.category, "value") and chain.category else None,
        }
        entries.append(entry)

    return entries


def assemble_stance_catalog() -> list[dict[str, Any]]:
    """Assemble analytical and presentation stances."""
    from src.operations.registry import StanceRegistry

    registry = StanceRegistry()
    stances = registry.list_all()

    entries = []
    for stance in stances:
        # The field is 'stance' (the prompt text), not 'description'
        stance_text = getattr(stance, "stance", "") or ""
        entry = {
            "key": stance.key,
            "name": stance.name,
            "stance_type": getattr(stance, "stance_type", "analytical"),
            "cognitive_mode": getattr(stance, "cognitive_mode", ""),
            "typical_position": getattr(stance, "typical_position", ""),
            "description_excerpt": stance_text[:200] + "..." if len(stance_text) > 200 else stance_text,
        }
        entries.append(entry)

    return entries


def assemble_workflow_catalog(workflow_key: str = None) -> list[dict[str, Any]]:
    """Assemble workflow definitions.

    If workflow_key is specified, returns only that workflow.
    Otherwise returns all workflows.
    """
    from src.workflows.registry import get_workflow_registry

    registry = get_workflow_registry()

    if workflow_key:
        workflows = [registry.get(workflow_key)]
        workflows = [w for w in workflows if w is not None]
    else:
        workflows = registry.list_all()

    entries = []
    for workflow in workflows:
        entries.append({
            "workflow_key": workflow.workflow_key,
            "workflow_name": workflow.workflow_name,
            "version": workflow.version,
            "phases": [
                {
                    "phase_number": phase.phase_number,
                    "phase_name": phase.phase_name,
                    "engine_key": phase.engine_key,
                    "chain_key": phase.chain_key,
                    "depends_on_phases": phase.depends_on_phases,
                    "requires_external_docs": phase.requires_external_docs,
                    "caches_result": phase.caches_result,
                    "description": phase.phase_description or phase.base_phase_description or "",
                }
                for phase in workflow.phases
            ],
        })

    return entries


def assemble_sub_renderer_catalog() -> list[dict[str, Any]]:
    """Assemble sub-renderer definitions for the catalog.

    Included so the LLM planner can recommend sub-renderers for views.
    """
    from src.sub_renderers.registry import get_sub_renderer_registry

    registry = get_sub_renderer_registry()
    entries = []
    for sr in registry.list_all():
        entries.append({
            "sub_renderer_key": sr.sub_renderer_key,
            "sub_renderer_name": sr.sub_renderer_name,
            "description": sr.description,
            "category": sr.category,
            "ideal_data_shapes": sr.ideal_data_shapes,
            "parent_renderer_types": sr.parent_renderer_types,
            "stance_affinities": sr.stance_affinities,
        })
    return entries


def assemble_view_pattern_catalog() -> list[dict[str, Any]]:
    """Assemble view pattern definitions for the catalog.

    Included so the LLM planner can instantiate patterns for new views.
    """
    from src.views.pattern_registry import get_pattern_registry

    registry = get_pattern_registry()
    entries = []
    for p in registry.list_all():
        entries.append({
            "pattern_key": p.pattern_key,
            "pattern_name": p.pattern_name,
            "description": p.description,
            "renderer_type": p.renderer_type,
            "ideal_for": p.ideal_for,
            "data_shape_in": p.data_shape_in,
            "recommended_sub_renderers": p.recommended_sub_renderers,
            "instantiation_hints": p.instantiation_hints,
            "example_views": p.example_views,
        })
    return entries


def assemble_view_catalog(
    app: str = None,
    page: str = None,
    workflow_key: str = None,
) -> list[dict[str, Any]]:
    """Assemble view definitions with planner metadata.

    Parameterized: filter by app, page, and/or workflow_key.
    Defaults to all views if no filters specified.
    """
    from src.views.registry import get_view_registry
    from src.transformations.registry import get_transformation_registry

    registry = get_view_registry()
    transform_registry = get_transformation_registry()

    kwargs = {}
    if app:
        kwargs["app"] = app
    if page:
        kwargs["page"] = page
    views = registry.list_summaries(**kwargs) if kwargs else registry.list_summaries()

    entries = []
    for view_summary in views:
        view = registry.get(view_summary.view_key)
        if view is None:
            continue

        # Filter by workflow_key if specified
        if workflow_key and view.data_source:
            if view.data_source.workflow_key != workflow_key:
                continue

        # Check if this view has applicable transformation templates
        has_template = False
        engine_key = view.data_source.engine_key if view.data_source else None
        chain_key = view.data_source.chain_key if view.data_source else None
        if engine_key:
            has_template = len(transform_registry.for_engine(engine_key)) > 0
        elif chain_key:
            from src.chains.registry import get_chain_registry
            chain_reg = get_chain_registry()
            chain = chain_reg.get(chain_key)
            if chain:
                for ek in chain.engine_keys:
                    if len(transform_registry.for_engine(ek)) > 0:
                        has_template = True
                        break

        entry = {
            "view_key": view.view_key,
            "view_name": view.view_name,
            "description": view.description,
            "renderer_type": view.renderer_type,
            "presentation_stance": view.presentation_stance,
            "data_source": {
                "workflow_key": view.data_source.workflow_key if view.data_source else None,
                "phase_number": view.data_source.phase_number if view.data_source else None,
                "engine_key": view.data_source.engine_key if view.data_source else None,
                "chain_key": view.data_source.chain_key if view.data_source else None,
            } if view.data_source else None,
            "visibility": view.visibility if hasattr(view, "visibility") else "always",
            "position": view.position if hasattr(view, "position") else 0,
            "parent_view_key": view.parent_view_key if hasattr(view, "parent_view_key") else None,
            "planner_hint": getattr(view, "planner_hint", ""),
            "planner_eligible": getattr(view, "planner_eligible", True),
            "has_transformation_template": has_template,
        }
        entries.append(entry)

    return entries


def assemble_operationalization_summary() -> list[dict[str, Any]]:
    """Assemble operationalization summary — what stances are available per engine."""
    from src.operationalizations.registry import get_operationalization_registry

    registry = get_operationalization_registry()
    registry.load()
    summaries = registry.list_summaries()

    entries = []
    for summary in summaries:
        entry = {
            "engine_key": summary.engine_key,
            "stances_available": summary.stance_keys if hasattr(summary, "stance_keys") else [],
            "depth_sequences": summary.depth_keys if hasattr(summary, "depth_keys") else [],
        }
        entries.append(entry)

    return entries


def assemble_transformation_catalog() -> list[dict[str, Any]]:
    """Assemble transformation template summaries for planner awareness.

    Lets the planner know which engines already have curated templates
    vs which would need dynamic generation.
    """
    from src.transformations.registry import get_transformation_registry

    registry = get_transformation_registry()
    entries = []
    for t in registry.list_all():
        if t.status == "deprecated":
            continue
        entries.append({
            "template_key": t.template_key,
            "description": t.description[:150] if t.description else "",
            "applicable_engines": t.applicable_engines,
            "applicable_renderers": t.applicable_renderer_types,
            "pattern_type": t.pattern_type,
            "data_shape_out": t.data_shape_out,
            "domain": t.domain,
            "generation_mode": t.generation_mode,
        })
    return entries


def assemble_full_catalog(
    app: str = None,
    page: str = None,
    workflow_key: str = None,
) -> dict[str, Any]:
    """Assemble the complete capability catalog.

    This is what the LLM planner reads to make decisions.
    Parameterized to support domain-independent planning.
    """
    catalog = {
        "capability_engines": assemble_engine_catalog(),
        "chains": assemble_chain_catalog(),
        "stances": assemble_stance_catalog(),
        "workflow": assemble_workflow_catalog(workflow_key=workflow_key),
        "views": assemble_view_catalog(app=app, page=page, workflow_key=workflow_key),
        "sub_renderers": assemble_sub_renderer_catalog(),
        "view_patterns": assemble_view_pattern_catalog(),
        "transformation_templates": assemble_transformation_catalog(),
        "operationalizations": assemble_operationalization_summary(),
        "depth_levels_explanation": {
            "surface": "Quick overview, 1 pass per engine, ~15 LLM calls total. Good for initial scoping.",
            "standard": "Balanced analysis, 2 passes per engine, ~25 LLM calls. Suitable for most analyses.",
            "deep": "Thorough analysis, 3-4 passes per engine with dialectical stance, ~35 LLM calls. For dense philosophical works.",
        },
    }

    # Add stats
    catalog["stats"] = {
        "capability_engines": len(catalog["capability_engines"]),
        "chains": len(catalog["chains"]),
        "stances": len(catalog["stances"]),
        "views": len(catalog["views"]),
        "sub_renderers": len(catalog["sub_renderers"]),
        "view_patterns": len(catalog["view_patterns"]),
        "transformation_templates": len(catalog["transformation_templates"]),
        "operationalizations": len(catalog["operationalizations"]),
    }

    return catalog


def catalog_to_text(catalog: dict[str, Any], workflow_name: str = None) -> str:
    """Convert the catalog to a text document suitable for LLM consumption.

    Produces a structured markdown document that the planner's system prompt
    references. Optimized for readability by the LLM, not humans.
    """
    title = workflow_name or "Intellectual Genealogy Analysis"
    lines = []
    lines.append(f"# CAPABILITY CATALOG: {title}")
    lines.append("")

    # Depth levels
    lines.append("## DEPTH LEVELS")
    lines.append("")
    for key, desc in catalog["depth_levels_explanation"].items():
        lines.append(f"- **{key}**: {desc}")
    lines.append("")

    # Workflow
    for wf in catalog.get("workflow", []):
        phase_count = len(wf.get("phases", []))
        lines.append(f"## WORKFLOW: {wf.get('workflow_key', 'unknown')} ({phase_count} phases)")
        lines.append("")
        for phase in wf.get("phases", []):
            engine_or_chain = phase.get("chain_key") or phase.get("engine_key") or "N/A"
            deps = ", ".join(str(d) for d in phase.get("depends_on_phases", [])) or "none"
            lines.append(f"### Phase {phase['phase_number']}: {phase['phase_name']}")
            lines.append(f"- Engine/Chain: `{engine_or_chain}`")
            lines.append(f"- Depends on: {deps}")
            lines.append(f"- External docs: {phase.get('requires_external_docs', False)}")
            lines.append(f"- {phase.get('description', '')[:300]}")
            lines.append("")

    # Chains
    lines.append("## CHAINS")
    lines.append("")
    for chain in catalog.get("chains", []):
        engines = " → ".join(chain.get("engine_keys", []))
        lines.append(f"### `{chain['chain_key']}`")
        lines.append(f"- {chain.get('description', '')[:200]}")
        lines.append(f"- Engines: {engines}")
        lines.append("")

    # Supplementary chains note
    lines.append("### Note: Supplementary Chains for Phase 1.0")
    lines.append("Any general-purpose chain (non-genealogy-specific) can be selected as a")
    lines.append("**supplementary chain** for Phase 1.0. Supplementary chains run AFTER the core")
    lines.append("genealogy_target_profiling chain, receiving its output as upstream context.")
    lines.append("Their outputs concatenate into a rich multi-engine target analysis that")
    lines.append("downstream per-work phases (1.5, 2.0) consume as distilled context")
    lines.append("instead of the raw target text. Good candidates: argument_analysis_chain,")
    lines.append("rhetorical_analysis_chain, conceptual_deep_dive_chain, anomaly_evidence_chain.")
    lines.append("")

    # Capability Engines
    lines.append("## CAPABILITY ENGINES (11 total)")
    lines.append("")
    for engine in catalog.get("capability_engines", []):
        lines.append(f"### `{engine['engine_key']}` — {engine['engine_name']}")
        lines.append(f"**Problematique**: {engine['problematique'][:400]}")
        lineage = engine.get("intellectual_lineage", {})
        lines.append(f"**Lineage**: {lineage.get('primary_thinker', '?')} | Traditions: {', '.join(lineage.get('traditions', []))}")
        lines.append("")

        # Dimensions
        dims = engine.get("analytical_dimensions", [])
        if dims:
            lines.append(f"**Dimensions** ({len(dims)}):")
            for dim in dims:
                lines.append(f"  - `{dim['key']}`: {dim['description'][:100]}")
                dg = dim.get("depth_guidance", {})
                if dg:
                    for dk, dv in dg.items():
                        lines.append(f"    - {dk}: {dv[:80]}")
            lines.append("")

        # Capabilities
        caps = engine.get("capabilities", [])
        if caps:
            lines.append(f"**Capabilities** ({len(caps)}):")
            for cap in caps:
                lines.append(f"  - `{cap['key']}`: {cap['description'][:100]}")
            lines.append("")

        # Composability
        comp = engine.get("composability", {})
        synergy = comp.get("synergy_engines", [])
        if synergy:
            lines.append(f"**Synergy engines**: {', '.join(synergy)}")
            lines.append("")

        # Depth levels
        depths = engine.get("depth_levels", [])
        if depths:
            depth_summary = ", ".join(f"{d['key']}({d['typical_passes']} passes)" for d in depths)
            lines.append(f"**Depth levels**: {depth_summary}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Stances
    lines.append("## ANALYTICAL STANCES")
    lines.append("")
    for stance in catalog.get("stances", []):
        lines.append(f"- `{stance['key']}` ({stance.get('stance_type', '?')}, {stance.get('typical_position', '?')}): {stance.get('description_excerpt', '')}")
    lines.append("")

    # Views
    view_count = len(catalog.get("views", []))
    lines.append(f"## VIEWS ({view_count} total)")
    lines.append("")
    for view in catalog.get("views", []):
        ds = view.get("data_source", {}) or {}
        source = ds.get("chain_key") or ds.get("engine_key") or "N/A"
        phase = ds.get("phase_number", "?")
        eligible = view.get("planner_eligible", True)
        has_template = view.get("has_transformation_template", False)
        template_tag = "HAS_TEMPLATE" if has_template else "NO_TEMPLATE"
        visibility = view.get("visibility", "if_data_exists")
        planner_hint = view.get("planner_hint", "")

        if not eligible:
            lines.append(f"### `{view['view_key']}` — {view['view_name']} [NOT ELIGIBLE]")
            lines.append(f"- Debug/utility view, not recommended for plans")
            lines.append("")
            continue

        lines.append(f"### `{view['view_key']}` — {view['view_name']}")
        lines.append(f"- Renderer: {view.get('renderer_type', '?')} | Phase {phase} | Source: `{source}` | [{template_tag}]")
        lines.append(f"- Stance: {view.get('presentation_stance', 'N/A')} | Visibility: {visibility}")
        if view.get("parent_view_key"):
            lines.append(f"- Parent: `{view['parent_view_key']}` (auto-included as child)")
        if planner_hint:
            lines.append(f"- **Planner guidance**: {planner_hint}")
        lines.append("")

    # Sub-renderers
    sub_renderers = catalog.get("sub_renderers", [])
    if sub_renderers:
        lines.append(f"## SUB-RENDERERS ({len(sub_renderers)} total)")
        lines.append("")
        for sr in sub_renderers:
            parents = ", ".join(sr.get("parent_renderer_types", []))
            shapes = ", ".join(sr.get("ideal_data_shapes", []))
            lines.append(f"### `{sr['sub_renderer_key']}` — {sr['sub_renderer_name']}")
            lines.append(f"- {sr.get('description', '')[:200]}")
            lines.append(f"- Category: {sr.get('category', '?')} | Parents: {parents} | Data shapes: {shapes}")
            lines.append("")

    # Transformation templates
    templates = catalog.get("transformation_templates", [])
    if templates:
        lines.append(f"## TRANSFORMATION TEMPLATES ({len(templates)} total)")
        lines.append("")
        lines.append("These templates extract structured JSON from engine prose output.")
        lines.append("Engines without curated templates can use dynamic generation via")
        lines.append("POST /v1/transformations/generate (engine_key + renderer_type).")
        lines.append("")
        for t in templates:
            engines = ", ".join(t.get("applicable_engines", []))
            renderers = ", ".join(t.get("applicable_renderers", []))
            mode = t.get("generation_mode", "curated")
            lines.append(f"- `{t['template_key']}` [{mode}]: engines={engines} | renderers={renderers} | shape={t.get('data_shape_out', '?')}")
        lines.append("")

    # View patterns
    patterns = catalog.get("view_patterns", [])
    if patterns:
        lines.append(f"## VIEW PATTERNS ({len(patterns)} total)")
        lines.append("")
        for p in patterns:
            lines.append(f"### `{p['pattern_key']}` — {p['pattern_name']}")
            lines.append(f"- {p.get('description', '')[:200]}")
            lines.append(f"- Renderer: {p.get('renderer_type', '?')} | Data shape: {p.get('data_shape_in', '?')}")
            lines.append(f"- Ideal for: {', '.join(p.get('ideal_for', []))}")
            if p.get("instantiation_hints"):
                lines.append(f"- **Hints**: {p['instantiation_hints'][:200]}")
            lines.append("")

    return "\n".join(lines)
