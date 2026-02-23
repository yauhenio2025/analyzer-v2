# Memo: Dynamic Extraction Fallback — Templates Are Now Optional

**Date**: 2026-02-23
**Commit**: `350345d`
**Status**: Deployed (auto-deploy to Render)

## The Problem

The presentation bridge required a hand-authored transformation template for every engine + renderer combination. If no template existed, the view was silently skipped. This created a scaling bottleneck: the genealogy workflow alone needed 17 templates for 7 engines across a few renderers. Adding a second workflow (e.g., rhetoric analysis) would double that count. Every new engine was invisible until someone wrote a template for it.

Templates were mandatory prerequisites. They shouldn't be.

## The Insight

Engines already contain rich metadata about what they produce:
- `canonical_schema` — the definitive output structure (100% coverage across 160+ engines)
- `extraction_focus` — the analytical dimensions the engine looks for
- `stage_context.extraction.core_question` — the question the engine answers
- `stage_context.extraction.key_fields` — field name → description mappings
- `stage_context.extraction.key_relationships` — relationship types

Renderers already declare what shape they consume:
- `ideal_data_shapes` — `object_array`, `nested_sections`, `key_value_pairs`, etc.
- `config_schema.properties` — the field names they map: `title_field`, `badge_field`, `subtitle_field`, `description_field`
- `available_section_renderers` — for containers like accordion, what sub-renderers are available

Presentation stances already describe the cognitive posture:
- 6 stances (summary, evidence, comparison, narrative, interactive, diagnostic) each with prose descriptions of how to approach the extraction

This is enough for Haiku to figure out what to extract. No template needed.

## What Changed

### New: `src/presenter/dynamic_prompt.py` (260 lines)

Core function: `compose_dynamic_extraction_prompt(engine_key, renderer_type, stance_key)`

Loads engine, renderer, and stance metadata, then composes a system prompt that tells Haiku:

1. **What the prose is about** — engine description, core question, extraction focus dimensions
2. **What JSON shape to produce** — derived from renderer's ideal_data_shapes + config_schema field names
3. **What presentation posture to adopt** — stance prose (capped at 500 chars)
4. **What's available in the prose** — engine's canonical_schema as reference (capped at 3000 chars)
5. **Shape-specific structural guidance** — e.g., `object_array` → "return a JSON array of objects with fields like {title, subtitle, description, badge}"; `nested_sections` → "return a sections array with key, title, items"

Returns a dict with `system_prompt`, `transformation_type`, `model`, `model_fallback`, `max_tokens` — everything the TransformationExecutor needs.

### Modified: `src/presenter/presentation_bridge.py`

The critical change is in `_build_transformation_tasks()` (lines 158-192). Previously:

```
Find template → if none found → skip view (view lost forever)
```

Now:

```
Find curated template → if found, use it (unchanged behavior)
                       → if none found, compose dynamic prompt → create task with dynamic_config
```

Both `_execute_tasks_async()` and `_execute_tasks_sync()` now branch on whether the task has a `template_key` (curated path) or `dynamic_config` (dynamic path). The `TransformationExecutor.execute()` itself was not changed — it already accepts raw prompt strings.

### Modified: `src/presenter/schemas.py`

- `TransformationTask.template_key` — now `Optional[str]` (was required)
- `TransformationTask.dynamic_config` — new field, carries the composed prompt for template-less extraction
- `TransformationTaskResult.extraction_source` — new field: `"curated"` or `"dynamic"`
- `PresentationBridgeResult.dynamic_extractions` — new counter: how many views used dynamic extraction

## What Didn't Change

- **TransformationExecutor** — untouched. It already accepts `llm_prompt_template` as a string parameter
- **Presentation cache** — same table, same schema. Dynamic extractions are cached identically
- **Page assembly** (`presentation_api.py`) — doesn't care how the cache was populated
- **All 17 existing templates** — continue to match and be used as before. Dynamic path only activates on cache miss + template miss
- **No API endpoint changes** — this is internal to the presenter module

## Section Keys for Cache

Curated tasks use `template.template_key` as the cache section key (e.g., `conditions_extraction`). Dynamic tasks use `dyn:{engine_key}:{renderer_type}` (e.g., `dyn:stakeholder_mapper:card_grid`). This keeps cache entries deterministic and unique.

## Observability

- `[dynamic-prompt]` log tag when a prompt is composed (engine, renderer, stance, prompt length)
- `[dynamic-fallback]` log tag in the bridge when falling back (which view, why no template)
- `[dynamic]` tag on transformation completion logs
- `extraction_source` field on every `TransformationTaskResult` — queryable in the response
- `dynamic_extractions` counter on `PresentationBridgeResult` — visible at a glance

## What This Means

**Before**: Adding a new workflow required authoring ~17 transformation templates before any structured rendering worked. Templates were the bottleneck between "engine produces good prose" and "user sees structured UI."

**After**: Every engine is renderable in any renderer immediately. The dynamic prompt reads the engine's own metadata to understand what the prose contains, reads the renderer's schema to understand what shape is needed, and lets Haiku bridge the gap. Curated templates are optional quality overrides — they produce better results (editorial guidance like "aim for 6-12 conditions" or "rich prose, not bullet points") but aren't required.

**The architecture is now**: engine metadata + renderer shape + stance = sufficient information for LLM-mediated extraction. Templates are editorial refinements, not structural necessities.

## Example: Dynamic Prompt for conditions_of_possibility_analyzer + accordion

The composed system prompt (5744 chars) includes:
- Engine name, analysis type, core question
- All 6 extraction focus dimensions
- Accordion renderer description, ideal shapes, section structure guidance
- Interactive stance prose
- The full canonical_schema (enabling_conditions, constraining_conditions, path_dependencies, etc.)

This is comparable to what the curated `conditions_extraction.json` template provides — minus the editorial hints about cardinality ("6-12 enabling conditions") and prose quality ("rich paragraphs, not bullet points").
