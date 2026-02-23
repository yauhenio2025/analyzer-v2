# Memo: The Prose Pipeline — How Engine Output Becomes Rendered Views

> Date: 2026-02-23
> Status: Architectural analysis + forward-looking design notes
> Builds on: `plain_text_architecture.md`, `GENEALOGY_PIPELINE_DATA_FLOW.md`

---

## Core Principle: Schema-on-Read

All engines produce **prose** — unstructured narrative text. They never output JSON, tables, or structured data. This is by design (see `plain_text_architecture.md`): LLMs reason better in natural language, cross-engine context sharing is trivial with prose, and forcing schema-on-write costs 17-26% analytical quality.

Structure is imposed **at presentation time** by transformation templates that use an LLM (Claude Haiku) to extract structured JSON from prose. This is schema-on-read: the structure is determined by the consumer's needs, not the producer's format.

---

## The Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        EXECUTION TIME                                   │
│                                                                         │
│  Orchestrator Plan                                                      │
│       │                                                                 │
│       ▼                                                                 │
│  Engine (capability prompt + stance + operationalization)                │
│       │                                                                 │
│       ▼                                                                 │
│  PROSE OUTPUT  ──────────────────────────────►  phase_outputs table      │
│  (5-25K words of analytical narrative)           (job_id, phase,        │
│                                                   engine, pass, text)   │
│                                                                         │
│  Note: Chains pass prose between engines via pass_context.              │
│  Engine B reads Engine A's prose as shared_context. No parsing needed.  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

                              ▼ ▼ ▼

┌─────────────────────────────────────────────────────────────────────────┐
│                      PRESENTATION TIME                                  │
│                      (triggered on page request)                        │
│                                                                         │
│  Consumer requests page ──► Presenter loads view tree                   │
│                                   │                                     │
│                                   ▼                                     │
│                          Transformation Bridge                          │
│                    ┌──────────────────────────────┐                     │
│                    │  For each view with a         │                    │
│                    │  transformation template:      │                    │
│                    │                                │                    │
│                    │  1. Load prose from            │                    │
│                    │     phase_outputs              │                    │
│                    │                                │                    │
│                    │  2. Find matching              │                    │
│                    │     transformation template    │                    │
│                    │     (by engine_key)            │                    │
│                    │                                │                    │
│                    │  3. Send prose + schema +      │                    │
│                    │     prompt to Claude Haiku     │                    │
│                    │                                │                    │
│                    │  4. Receive structured JSON    │                    │
│                    │                                │                    │
│                    │  5. Cache in                   │                    │
│                    │     presentation_cache         │                    │
│                    │     (keyed by source_hash)     │                    │
│                    └──────────────────────────────┘                     │
│                                   │                                     │
│                                   ▼                                     │
│                          Page Assembly                                  │
│                    ┌──────────────────────────────┐                     │
│                    │  For each view:               │                    │
│                    │                                │                    │
│                    │  ViewPayload {                 │                    │
│                    │    raw_prose: "...",           │                    │
│                    │    structured_data: {...},     │                    │
│                    │    has_structured_data: bool,  │                    │
│                    │    renderer_type: "accordion", │                    │
│                    │    renderer_config: {...},     │                    │
│                    │    presentation_stance: "...", │                    │
│                    │    children: [...]             │                    │
│                    │  }                             │                    │
│                    └──────────────────────────────┘                     │
│                                   │                                     │
│                                   ▼                                     │
│                          Consumer App (The Critic)                      │
│                          renders using renderer_type                    │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## What Each Layer Does

### Engines (194 available)
- Input: document text + analytical stance + prior pass context (prose)
- Output: **prose only** — analytical narrative (5-25K words)
- Storage: `phase_outputs` table (job_id, phase_number, engine_key, pass_number, work_key, content)
- No awareness of views, renderers, or structure

### Stances (13 available)
- **7 analytical stances**: discovery, inference, confrontation, architecture, integration, reflection, dialectical
  - These shape HOW the engine thinks. Discovery explores openly; confrontation challenges; integration synthesizes.
  - Applied at execution time via operationalizations (engine + stance → specific instructions)
- **6 presentation stances**: summary, evidence, comparison, narrative, interactive, diagnostic
  - These shape HOW the view is displayed. Evidence stance → quote cards with citations; narrative → flowing prose.
  - Applied at presentation time via renderer/sub-renderer affinity scoring

### Transformation Templates (17 currently, all genealogy-specific)
- Input: engine prose (from phase_outputs)
- Process: LLM extraction — sends prose + schema + prompt to Claude Haiku
- Output: structured JSON matching the template's `llm_extraction_schema`
- Storage: `presentation_cache` table (output_id, section, structured_data, source_hash)
- Each template is bound to specific `applicable_engines` and `applicable_renderer_types`

### Views (21 currently, all genealogy/the-critic)
- Wiring declarations that connect data to presentation
- Each view specifies:
  - `data_source`: which engine/chain + phase + result_path to pull prose from
  - `renderer_type` + `renderer_config`: how to display
  - `presentation_stance`: what cognitive posture for rendering
  - `transformation`: which template (if any) to extract structure
  - `parent_view_key`: nesting hierarchy
  - `target_app` + `target_page`: which consumer page this appears on

### Renderers (9) + Sub-Renderers (11)
- Renderers own entire views (accordion, card_grid, prose, table, tab, timeline, etc.)
- Sub-renderers are section-level components inside containers (chip_grid, mini_card_list, prose_block, etc.)
- Selected by affinity to the view's presentation stance + data shape

---

## How Stances and Transformations Relate

The user asked: "aren't stances and transformations kind of alike?"

**Yes — they're the same principle applied at different pipeline stages:**

| Aspect | Analytical Stances | Presentation Stances | Transformations |
|--------|-------------------|---------------------|-----------------|
| **When** | Execution time | Presentation time | Presentation time |
| **What they shape** | How the engine THINKS | How the view LOOKS | What STRUCTURE is extracted |
| **Input** | Engine prompt | Renderer selection | Engine prose |
| **Output** | Prose (shaped by stance) | Visual rendering (shaped by stance) | Structured JSON |
| **Mechanism** | Operationalization instructions | Renderer/sub-renderer affinity scores | LLM extraction with schema |

Analytical stances and transformations are the most similar: both use LLMs to shape output. The difference:
- **Analytical stance** = "think about this from a confrontational perspective" → produces stance-shaped prose
- **Transformation** = "extract these specific fields from the prose" → produces structured data

A unified view: **stances shape the content, transformations shape the container.** The stance decides WHAT the engine says; the transformation decides HOW it's packaged for the renderer.

---

## Engine → View Relationship Patterns

Views are NOT 1:1 with engines. The 21 genealogy views come from just 8 unique data sources:

### Pattern 1: Single Engine → Single View (6 views)
```
genealogy_final_synthesis engine → genealogy_portrait view (prose renderer)
evolution_tactics_detector engine → genealogy_tactics view (card_grid renderer)
```
Simplest case. One engine's full prose → one view.

### Pattern 2: Single Engine → Multiple Field-Path Views (7 views)
```
conditions_of_possibility_analyzer engine
  → prose stored once
  → conditions_extraction template extracts 7 fields
  → 7 child views, each with a different result_path:
      .enabling_conditions → card_grid
      .constraining_conditions → card_grid
      .path_dependencies → timeline
      .unacknowledged_debts → card_grid
      .alternative_paths → card_grid
      .counterfactual_analysis → prose
      .synthetic_judgment → prose
```
One engine, one transformation, many views. The transformation is the multiplier.

### Pattern 3: Chain → Parent View with Engine Children (4 views)
```
genealogy_target_profiling chain (4 sequential engines)
  → genealogy_target_profile parent view (accordion)
  → 4 child views, one per chain engine:
      conceptual_framework_extraction → accordion
      concept_semantic_constellation → accordion
      inferential_commitment_mapper → accordion
      concept_evolution → accordion
```
Chain produces composite output; parent view groups it; children show per-engine detail.

### Pattern 4: Multi-Phase Composition (2 views)
```
genealogy_idea_evolution view:
  PRIMARY: concept_synthesis (phase 3.0)
  SECONDARY: genealogy_target_profiling chain (phase 1.0)
  SECONDARY: genealogy_prior_work_scanning chain (phase 2.0, per_item scope)
```
True multi-source views that synthesize across workflow phases.

### Pattern 5: Diagnostic/Meta (2 views)
```
genealogy_raw_output → all engine results as raw JSON
genealogy_chain_log → execution metadata as table
```
Debug views, not analytical.

---

## The Abstraction Problem: Why Views and Transformations Will Proliferate

Currently: 21 views + 17 transformations for ONE workflow (genealogy) in ONE app (the-critic).

If we add 3 more workflows to the-critic (e.g., rhetorical analysis, paradigm comparison, influence mapping), naive approach = 60+ views + 50+ transformations. If we add 2 more apps, we could hit 100+ views + 100+ transformations. This is unsustainable.

### Why the Current Approach Causes Proliferation

1. **Transformation templates are engine-specific**: `conditions_extraction` only works with `conditions_of_possibility_analyzer`. If a new workflow uses the same engine with a different renderer, you need a new template.

2. **Views are hardcoded to workflow + engine + renderer**: `genealogy_cop_path_dependencies` is wired to a specific workflow, phase, engine, field path, and renderer. Nothing is reusable.

3. **The extraction schema is baked into the template**: The `conditions_extraction` template has a 60-line schema defining exactly what fields to extract. A different app wanting different fields from the same engine prose needs an entirely new template.

### Why Proliferation Is Unnecessary

**The key insight: transformation templates are over-specified because engines have known capabilities.**

Every engine has:
- A set of **analytical dimensions** (what it looks at)
- A set of **capabilities** (what it can produce)
- A **problematique** (what question it asks)

These are already cataloged in the engine definitions. A transformation template is essentially saying: "extract the outputs corresponding to these capabilities from the prose." But the engine already KNOWS its capabilities — we're just restating them in JSON extraction format.

**The transformation should be derivable from the engine definition + the target renderer's data shape.**

Example: `conditions_of_possibility_analyzer` has capabilities including "enabling conditions analysis", "constraining conditions analysis", "path dependency tracing", etc. The `conditions_extraction` template manually specifies extraction fields that mirror these capabilities. This is redundant — an LLM could generate the extraction schema from the engine's capability list + the target renderer's expected data shape.

### The Abstraction Path: Engine-Driven Dynamic Transformations

Instead of pre-authored transformation templates, the pipeline should work like:

```
1. View says: "show conditions_of_possibility_analyzer output using accordion renderer"
2. System looks up engine capabilities → [enabling_conditions, constraining_conditions, ...]
3. System looks up accordion renderer data shape → nested_sections with typed items
4. LLM generates extraction schema on-the-fly:
   "Given these engine capabilities and this target data shape,
    extract structured JSON from the prose"
5. Extracted JSON is cached (keyed by engine + renderer + source_hash)
6. No pre-authored transformation template needed
```

**Pre-authored templates become optimizations, not requirements.** You'd keep `conditions_extraction` as a curated template because it's battle-tested. But a new engine's output could be extracted dynamically using its capability metadata + the renderer's data shape expectations.

### The View Abstraction: Pattern-Based Generation

Similarly, views should be generated from patterns rather than hand-authored:

```
1. Orchestrator plans workflow with engines/phases
2. For each engine output, planner selects a view pattern:
   - "accordion_sections" for multi-category output
   - "card_grid_grouped" for collection of typed items
   - "prose_narrative" for long-form synthesis
   - "tab_with_children" for per-item comparison
3. Pattern + engine capabilities + transformation = concrete view definition
4. View is generated, stored, and served — no manual JSON authoring
```

The 21 genealogy views become reference implementations. The 6 view patterns become generative templates. New workflows get views automatically.

---

## What Stays Domain-Specific vs What Becomes Generic

| Component | Now | Should Be | Why |
|-----------|-----|-----------|-----|
| **Engines** | Already generic (194) | Stay generic | They analyze; domain comes from stance/operationalization |
| **Analytical stances** | Already generic (7) | Stay generic | Cognitive modes are universal |
| **Presentation stances** | Already generic (6) | Stay generic | Display modes are universal |
| **Workflows** | Domain-specific | Stay domain-specific | They define WHAT to analyze and in what order |
| **Operationalizations** | Domain-specific | Stay domain-specific | They translate stance → domain-specific instructions |
| **Transformation templates** | 17 hand-authored, all genealogy | Mostly auto-generated | Engine capabilities + renderer shape → schema |
| **Views** | 21 hand-authored, all genealogy | Mostly auto-generated | View patterns + engine + transformation → view |
| **Renderers** | Already generic (9) | Stay generic | They render data shapes, not domain content |
| **Sub-renderers** | Already generic (11) | Stay generic | They display atomic data shapes |

**The proliferation risk lives in transformations and views.** Everything else is already generic or intentionally domain-specific (workflows, operationalizations).

---

## Concrete Next Steps

### 1. Dynamic Transformation Generation (high impact)
Add an LLM-powered endpoint that generates extraction schemas from engine capability metadata:
```
POST /v1/transformations/generate-schema
{
  "engine_key": "stakeholder_mapper",
  "target_renderer": "card_grid",
  "hints": "Group by stakeholder type, include influence score"
}
→ Returns extraction schema + prompt template
→ Can be cached, saved as template, or used ephemerally
```

### 2. View Generation from Patterns (high impact)
Extend the orchestrator planner to emit view definitions alongside execution plans:
```
Plan output includes:
  phases: [...]
  views: [
    { pattern: "accordion_sections", engine: "conditions_analyzer", ... },
    { pattern: "card_grid_grouped", engine: "tactics_detector", ... }
  ]
```

### 3. Engine Capability Metadata Enhancement (prerequisite)
Ensure every engine definition includes structured capability descriptors that transformation generation can use. Many engines already have `dimensions` and `capabilities` fields — these need to be complete enough for automatic schema derivation.

### 4. Curated vs Generated Distinction
Add a `generation_mode` field to transformations and views:
- `curated`: hand-authored, tested, optimized (the current 17 templates)
- `generated`: auto-created from patterns, may need refinement
- `hybrid`: generated then manually tuned

This prevents quality regression while enabling scale.

---

## Summary

The pipeline is: **Engines (prose) → Transformation Bridge (LLM extraction) → Presentation Cache → Views (wiring) → Renderers (display)**.

Engines are already abstract. Renderers are already abstract. The bottleneck is **transformations and views** — both are over-specified for genealogy and will proliferate with new domains. The fix is engine-driven dynamic transformation generation + pattern-based view generation. Pre-authored templates become quality-curated optimizations, not the primary path for new functionality.

Stances and transformations are philosophically aligned: both shape output through an LLM. Stances shape the content (how the engine thinks); transformations shape the container (how the prose becomes structured data). They operate at different pipeline stages but share the same "LLM as mediator" architecture.
