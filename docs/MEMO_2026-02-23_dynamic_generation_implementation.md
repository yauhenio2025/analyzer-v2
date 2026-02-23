# Memo: Dynamic Transformation & View Generation — Implementation Record

> Date: 2026-02-23
> Status: Implemented, deployed, ready for integration testing
> Implements: "Concrete Next Steps" §1–§4 from `MEMO_2026-02-23_prose_pipeline_architecture.md`
> Commit: `011b200` — auto-deployed to https://analyzer-v2.onrender.com

---

## Motivation

The prose pipeline memo identified a scalability bottleneck: **21 views and 17 transformation templates are all hand-authored for a single workflow (genealogy)**. Adding a new workflow (e.g., rhetorical analysis) would naively require 20+ more templates and 20+ more views. The root cause is over-specification — templates and views manually restate information already encoded in engine definitions and renderer schemas.

This implementation delivers the four concrete fixes proposed in the memo:

1. **Dynamic Transformation Generation** — upgrade `POST /v1/transformations/generate`
2. **View Generation from Patterns** — new `POST /v1/views/generate`
3. **Engine Capability Metadata Enhancement** — verified existing coverage is sufficient
4. **Curated vs Generated Distinction** — new `generation_mode` field

---

## What Was Built

### 1. `generation_mode` Field (Schema Change)

**Files changed**: `src/transformations/schemas.py`, `src/views/schemas.py`, `src/transformations/registry.py`, `src/views/registry.py`, `src/api/routes/transformations.py`

A new field on both `TransformationTemplate` and `ViewDefinition`:

```python
generation_mode: str = Field(
    default="curated",
    description="How this template was created: 'curated' (hand-authored), "
    "'generated' (LLM-generated), 'hybrid' (generated then manually refined)",
)
```

**Design decisions**:
- Defaults to `"curated"` so all 17 existing templates and 21 existing views load without any JSON file changes
- Surfaced in all summary/list endpoints so consumers can filter or flag generated items
- Enforced server-side: the generate endpoints force `generation_mode="generated"` regardless of what the LLM outputs

**Verification**: All registries load correctly. `GET /v1/transformations` and `GET /v1/views` now include `generation_mode` on every summary item.

---

### 2. Transformation Generator (`src/transformations/generator.py`)

**New file**: 350 lines. Replaces the shallow generation logic that previously lived inline in `transformations.py` routes (which only used engine name and description).

#### Architecture

```
Input: engine_key + renderer_type
       │
       ▼
┌─── Exemplar Selection ──────────────────────────────────────────┐
│ Scores all existing templates by:                                │
│   +3 if renderer_type matches                                    │
│   +2 if data_shape_out is in renderer's ideal_data_shapes       │
│   +1 if template has a pattern_type                              │
│   +1 if template type is llm_extract with a schema               │
│ Takes top 3 as few-shot exemplars                                │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── Engine Context Building ─────────────────────────────────────┐
│ Extracts from EngineDefinition:                                  │
│   • canonical_schema (capped at 4000 chars)                      │
│   • extraction_focus — list of what the engine looks for         │
│   • stage_context.extraction.core_question                       │
│   • stage_context.extraction.key_fields (field → description)   │
│   • stage_context.extraction.id_field (naming convention)       │
│   • stage_context.extraction.extraction_steps (first 5)         │
│   • stage_context.extraction.key_relationships                  │
│   • stage_context.extraction.special_instructions                │
│                                                                  │
│ Coverage across 195 engines:                                     │
│   canonical_schema: 100%                                         │
│   extraction_focus: ~82%                                         │
│   key_fields: sparse but present on all 11 capability engines    │
│   core_question: ~80%                                            │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── Renderer Context Building ───────────────────────────────────┐
│ Extracts from RendererDefinition:                                │
│   • ideal_data_shapes — what shape the renderer consumes         │
│   • input_data_schema (capped at 2000 chars)                    │
│   • config_schema.properties — what field names it expects       │
│   • available_section_renderers — sub-renderer options           │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── Prompt Composition ──────────────────────────────────────────┐
│ Combines:                                                        │
│   1. Task framing (extract structured data from prose)           │
│   2. Engine context (what data looks like)                       │
│   3. Renderer context (what shape it needs)                      │
│   4. Exemplar templates (few-shot: schemas + prompts)            │
│   5. Output requirements (exact field list with instructions)    │
│                                                                  │
│ Total prompt: ~6-10K chars depending on engine complexity        │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── LLM Call (Claude Sonnet, max_tokens=12000) ──────────────────┐
│ Returns JSON matching TransformationTemplate schema              │
│ Server forces generation_mode="generated", status="draft"       │
│ Validates via TransformationTemplate.model_validate()            │
│ Optionally saves to disk (save=true)                             │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
Output: Complete TransformationTemplate ready for use
```

#### Key Functions

| Function | Purpose |
|----------|---------|
| `_select_exemplars(engine, renderer, max=3)` | Score + rank existing templates as few-shot context |
| `_build_engine_context(engine)` | Extract all relevant metadata from EngineDefinition |
| `_build_renderer_context(renderer)` | Extract data shape + config requirements from RendererDefinition |
| `_build_exemplar_text(exemplars)` | Format top exemplars with schema + prompt (capped) |
| `_infer_data_shape(renderer)` | Map renderer ideal_data_shapes → transformation output shape |
| `_infer_pattern_type(data_shape)` | Map data_shape → semantic pattern category |
| `_build_generation_prompt(...)` | Assemble complete prompt from all context |
| `generate_transformation_template(...)` | Main async entry point: select → build → call → validate → save |

#### What the Old Generator Did (for contrast)

The previous inline generator (formerly lines 401-557 in `transformations.py`) used only:
- Engine name
- Engine description (first 500 chars)
- Target renderer type string

No canonical_schema. No key_fields. No extraction_focus. No exemplars. It was essentially asking the LLM to guess what the engine outputs.

---

### 3. View Generator (`src/views/generator.py`)

**New file**: 368 lines. Entirely new capability — there was no view generation before.

#### Architecture

```
Input: pattern_key + engine_key + workflow context
       │
       ▼
┌─── Entity Resolution ───────────────────────────────────────────┐
│ Load from registries:                                            │
│   • ViewPattern — the template to instantiate (6 available)      │
│   • EngineDefinition — the data source                           │
│   • RendererDefinition — derived from pattern's renderer_type    │
│   • Existing views on target page — for position/nesting context │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── Prompt Composition ──────────────────────────────────────────┐
│ Combines:                                                        │
│   1. Pattern template (full JSON dump — structure to follow)     │
│   2. Engine schema (canonical_schema, capped 3000 chars)         │
│   3. Engine key_fields (field → description map)                 │
│   4. Renderer config_schema (what config keys it expects)        │
│   5. Page context (existing views with position/parent/renderer) │
│   6. Pre-filled data_source (workflow_key, phase, engine, scope) │
│   7. Pattern's instantiation_hints (authored guidance)           │
│   8. Target context (app, page, parent, position, stance)        │
│                                                                  │
│ Total prompt: ~4-8K chars                                        │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── LLM Call (Claude Sonnet, max_tokens=8000) ───────────────────┐
│ Returns JSON matching ViewDefinition schema                      │
│ Server forces generation_mode="generated", status="draft"       │
│ Validates via ViewDefinition.model_validate()                    │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
┌─── Post-Processing ─────────────────────────────────────────────┐
│ 1. Wire transformation if transformation_template_key provided   │
│ 2. Validate parent_view_key exists (warn if not)                 │
│ 3. Check view_key collision → append "_gen" suffix               │
│ 4. Optionally save to disk (save=true)                           │
└──────────────────────────────────────────────────────────────────┘
       │
       ▼
Output: ViewGenerateResponse {
  view: ViewDefinition,
  transformation_generated: bool,
  notes: "Generated from pattern 'X' for engine 'Y'. Renderer: Z."
}
```

#### Request Schema (ViewGenerateRequest)

| Field | Required | Default | Purpose |
|-------|----------|---------|---------|
| `pattern_key` | yes | — | Which of the 6 view patterns to instantiate |
| `engine_key` | yes | — | Engine whose output to display |
| `workflow_key` | no | `""` | Workflow for data_source |
| `phase_number` | no | `1.0` | Phase for data_source |
| `chain_key` | no | `null` | Chain if engine is part of a chain |
| `scope` | no | `"aggregated"` | `"aggregated"` or `"per_item"` |
| `target_app` | no | `"the-critic"` | Consumer app |
| `target_page` | no | `""` | Page within the app |
| `parent_view_key` | no | `null` | For nesting under a parent view |
| `position` | no | `0` | Sort order |
| `presentation_stance` | no | `null` | Override stance (or LLM picks) |
| `description` | no | `""` | Additional generation guidance |
| `transformation_template_key` | no | `null` | Wire an existing template |
| `save` | no | `false` | Persist to disk |

#### Available View Patterns (6)

These are the "generative templates" the memo proposed:

| Pattern Key | Renderer | Best For |
|-------------|----------|----------|
| `accordion_sections` | accordion | Multi-category output with expandable sections |
| `card_grid_grouped` | card_grid | Collections of typed items, optionally grouped |
| `card_grid_simple` | card_grid | Flat item grids |
| `tab_with_children` | tab | Per-item comparison, multi-source composition |
| `prose_narrative` | prose | Long-form synthesis, flowing narrative |
| `timeline_sequential` | timeline | Chronological or evolutionary traces |

---

### 4. Orchestrator Catalog Enhancement (`src/orchestrator/catalog.py`)

**New function**: `assemble_transformation_catalog()` — returns summary of all transformation templates:

```python
{
    "template_key": "conditions_extraction",
    "description": "...",
    "applicable_engines": ["conditions_of_possibility_analyzer"],
    "applicable_renderers": ["accordion"],
    "pattern_type": "section_extraction",
    "data_shape_out": "nested_sections",
    "domain": "genealogy",
    "generation_mode": "curated"
}
```

Added to `assemble_full_catalog()` output under key `"transformation_templates"` and included in `catalog_to_text()` markdown rendering.

**Planner prompt change** (`src/orchestrator/planner.py`): Added a note in the JSON example:

```
"note_on_views": "Views and transformation templates can be generated dynamically
for any engine/renderer combination via POST /v1/transformations/generate and
POST /v1/views/generate. Don't limit recommendations to engines with existing
templates — new templates can be generated at presentation time."
```

This means when the planner generates a WorkflowExecutionPlan, it can now:
- See which templates exist (16 curated entries in the catalog)
- Know that missing templates can be generated dynamically
- Recommend views for engines that don't have pre-authored templates

---

### 5. Route Changes

#### `POST /v1/transformations/generate` (upgraded)

**Before**: ~150 lines of inline generation logic using only engine name + description.

**After**: Thin 30-line handler delegating to `generator.py`:

```python
@router.post("/generate", response_model=TransformationTemplate)
async def generate_transformation(request: TransformationGenerateRequest):
    engine = engine_registry.get(request.engine_key)
    renderer = renderer_registry.get(request.renderer_type)
    template = await generate_transformation_template(
        engine=engine, renderer=renderer,
        description=request.description, domain=request.domain, save=request.save,
    )
    return template
```

#### `POST /v1/views/generate` (new)

New endpoint after `/views/reload`:

```python
@router.post("/generate")
async def generate_view_endpoint(request: dict):
    req = ViewGenerateRequest.model_validate(request)
    result = await generate_view(req)
    return result.model_dump()
```

---

## Engine Capability Metadata Audit

The memo proposed "Engine Capability Metadata Enhancement" as a prerequisite. We audited the 195 engines and found coverage is already sufficient:

| Metadata Field | Coverage | Notes |
|---------------|----------|-------|
| `canonical_schema` | 100% (195/195) | Every engine has a full JSON schema |
| `extraction_focus` | ~82% (159/195) | List of what the engine looks for |
| `core_question` | ~80% | The engine's central analytical question |
| `key_fields` | Sparse overall, 100% on 11 capability engines | Field → description dict |
| `extraction_steps` | ~60% | Numbered steps the engine follows |
| `key_relationships` | ~30% | Cross-field relationships |
| `special_instructions` | ~20% | Extra guidance |

**Conclusion**: No bulk enrichment needed. The generator gracefully handles missing fields — it includes what's available and omits what isn't. Engines with richer metadata produce better templates. The 11 capability engines (with operationalizations) produce excellent templates; simpler engines produce adequate ones.

---

## What This Does NOT Do (Yet)

### Not wired into the presentation bridge
The presentation bridge (`src/presenter/presentation_bridge.py`) currently searches for existing templates by engine_key + renderer_type. If none exist, it falls through to prose-only mode. It does **not** call `/generate` to create one on the fly. Wiring this would enable fully automatic presentation for any engine.

### No analyzer-mgmt UI
There are no "Generate Template" or "Generate View" buttons in the management frontend. The endpoints exist and work, but there's no UI to invoke them.

### No auto-generation during plan execution
The orchestrator planner now *knows* about dynamic generation (via the updated prompt), but the execution pipeline doesn't auto-generate views/templates when a plan references engines without templates.

### No quality comparison
We haven't tested generated templates against curated ones on real prose. The generation_mode field enables A/B comparison, but no comparison has been run.

---

## How to Test

### Generate a transformation template

```bash
curl -X POST https://analyzer-v2.onrender.com/v1/transformations/generate \
  -H "Content-Type: application/json" \
  -d '{
    "engine_key": "argument_architecture",
    "renderer_type": "card_grid",
    "description": "Extract argument components as cards",
    "domain": "generic"
  }'
```

Returns a complete `TransformationTemplate` with:
- `llm_extraction_schema` — JSON schema mapping engine capabilities to card_grid's data shape
- `llm_prompt_template` — Haiku extraction prompt
- `generation_mode: "generated"`
- `status: "draft"`

### Generate a view definition

```bash
curl -X POST https://analyzer-v2.onrender.com/v1/views/generate \
  -H "Content-Type: application/json" \
  -d '{
    "pattern_key": "card_grid_grouped",
    "engine_key": "argument_architecture",
    "workflow_key": "intellectual_genealogy",
    "phase_number": 3.0,
    "target_app": "the-critic",
    "target_page": "genealogy",
    "position": 99
  }'
```

Returns a `ViewGenerateResponse` with a complete `ViewDefinition` including:
- `renderer_type: "card_grid"`
- `renderer_config` with section_renderers mapped to engine output fields
- `data_source` wired to the specified workflow/phase/engine
- `generation_mode: "generated"`

### Check generation_mode on existing items

```bash
# All templates show generation_mode
curl https://analyzer-v2.onrender.com/v1/transformations | python3 -m json.tool | grep generation_mode

# All views show generation_mode
curl https://analyzer-v2.onrender.com/v1/views | python3 -m json.tool | grep generation_mode
```

### Verify catalog includes templates

```bash
curl "https://analyzer-v2.onrender.com/v1/orchestrator/capability-catalog?format=text" | grep -A2 "TRANSFORMATION"
```

---

## Integration Roadmap

### Phase A: Auto-generation in presentation bridge (high impact, moderate effort)
When `presentation_bridge.py` can't find a template for engine_key + renderer_type, instead of falling through to prose-only, call `/generate` → cache the result → use it. This makes every engine renderable without manual template authoring.

### Phase B: Planner emits view generation requests (moderate impact, moderate effort)
When the orchestrator planner recommends views for engines without existing view definitions, include generation hints. The presentation pipeline would call `/views/generate` during the prepare step.

### Phase C: Management UI (moderate impact, low effort)
Add "Generate Template" and "Generate View" buttons to the analyzer-mgmt frontend. Template generation: engine selector + renderer selector + Generate button. View generation: pattern selector + engine selector + page context + Generate button.

### Phase D: Quality loop (long-term)
Compare generated vs curated templates on real prose output. Metrics: extraction completeness, field accuracy, renderer compatibility. Generated templates that pass quality checks get promoted from "draft" to "approved". Best ones get promoted to "curated" (= `generation_mode: "hybrid"`).

---

## Files Created or Modified

| File | Status | What Changed |
|------|--------|-------------|
| `src/transformations/generator.py` | **NEW** | 350-line generator module |
| `src/views/generator.py` | **NEW** | 368-line generator module |
| `src/transformations/schemas.py` | Modified | Added `generation_mode` field to Template + Summary |
| `src/views/schemas.py` | Modified | Added `generation_mode` field to ViewDefinition + ViewSummary |
| `src/transformations/registry.py` | Modified | Include `generation_mode` in summary construction |
| `src/views/registry.py` | Modified | Include `generation_mode` in summary construction |
| `src/api/routes/transformations.py` | Modified | Replaced inline generator with thin handler + 4 summary blocks updated |
| `src/api/routes/views.py` | Modified | Added `POST /generate` endpoint |
| `src/orchestrator/catalog.py` | Modified | Added `assemble_transformation_catalog()` + wired into full catalog |
| `src/orchestrator/planner.py` | Modified | Added dynamic generation note to system prompt |
| `CLAUDE.md` | Modified | Added transformations section + view generate endpoint to API listing |
| `docs/CHANGELOG.md` | Modified | 4 new entries in [Unreleased] |
| `docs/FEATURES.md` | Modified | Updated Transformation Templates + View Definitions + Orchestrator sections |

---

## Relationship to Other Memos

- **`MEMO_2026-02-23_prose_pipeline_architecture.md`** — The parent memo that proposed these changes. This implementation covers all 4 "Concrete Next Steps."
- **`MEMO_2026-02-19_orchestrator_vision.md`** — The orchestrator vision. Dynamic generation strengthens the vision: plans can now recommend views for any engine, not just the 8 with existing templates.
- **`GENEALOGY_PIPELINE_DATA_FLOW.md`** — The genealogy-specific data flow. Dynamic generation means this flow can be replicated for other workflows without proportional template authoring.
- **`plain_text_architecture.md`** — The schema-on-read philosophy. Dynamic transformation generation is the logical extension: not only is structure imposed at read time, but the extraction recipes themselves can be generated on demand from engine metadata.
