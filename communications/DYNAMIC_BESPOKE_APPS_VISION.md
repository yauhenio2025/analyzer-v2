# Dynamic Bespoke Apps: analyzer-v2 as Central Intelligence Layer

> **Status**: Vision Document + UI Readiness Audit
> **Date**: 2026-03-08 (updated with readiness audit)
> **Audience**: Architecture decision-makers, future Claude Code sessions, cross-model collaboration (Claude + Codex)
>
> **Scope Clarification**: This document focuses on the **UI composition pipeline** — everything that happens AFTER engines produce prose output. Engine selection and execution are out of scope. The question is: given full prose from the analytical pipeline, how ready is the system for an external LLM orchestrator to dynamically compose a complete rendered UI experience?

---

## 1. The Core Thesis

**analyzer-v2 is the brain. Apps are ephemeral presentations.**

The traditional software model treats frontend applications as durable artifacts: carefully designed, incrementally maintained, accumulated over years. This vision rejects that model entirely for analytical UI.

Instead, analyzer-v2 becomes the **single source of analytical intelligence** — owning every engine, every renderer, every view composition strategy, every style school, every transformation template, every design token. Consumer applications are **disposable shells**: thin wrappers that receive a fully-composed `PagePresentation` and render it. When the analytical task is done, the app can be discarded. No app is meant to outlive its analytical purpose.

This is not traditional software engineering. It is **LLM-mediated experimental composition** — where a language model orchestrates the full chain from "what question are we asking?" to "what does the user see on screen?", drawing from analyzer-v2's catalog of 203 engines, 7 renderer types, 18+ sub-renderers, 6 style schools, and a growing library of view definitions.

The consumer app contributes only what analyzer-v2 cannot: routing, authentication, project persistence, and a DOM to paint into.

---

## 2. What "Bespoke" Means

Each analysis task spawns a **unique UI composition**. Not a generic dashboard with filters — a purpose-built visual environment shaped by:

- **The analytical question** — "How does Benanav's concept of decommodification evolve across his bibliography?" demands timeline renderers, evolution cards, cross-reference panels. A different question about argumentative structure would produce entirely different views.
- **The source material** — dense theoretical text gets prose-heavy layouts with evidence trails; empirical work gets stat summaries and distribution charts.
- **The style school** — Minimalist Precision for quantitative analysis; Explanatory Narrative for conceptual genealogies; Humanist Craft for biographical intellectual portraits.
- **The audience** — academic readers get full evidence apparatus; general readers get distilled summaries with expandable depth.

"Bespoke" means: **composed for this specific conjunction of question, material, style, and audience**. When the analysis is complete and its insights absorbed, the composition has served its purpose. The building blocks return to the catalog; the composition dissolves.

This is analogous to how a researcher assembles notes, charts, and diagrams on a desk for a specific investigation, then clears the desk for the next one. The tools persist; the arrangement is temporary.

---

## 3. The LLM Composition Pipeline

The pipeline from analytical intent to rendered UI involves five orchestration stages, each mediated by an LLM drawing from analyzer-v2's registries.

### Stage 1: Engine Selection

The LLM examines the source material and user intent, then selects engines from the catalog of 203 definitions organized by category (concepts, argument, temporal, evidence, rhetoric, epistemology, scholarly, market, etc.). Each engine declares:

- `canonical_schema` — the structured output shape it produces
- `researcher_question` — the intellectual question it answers
- `reasoning_domain` — its analytical domain
- `kind` — extraction, synthesis, comparison, etc.

The planner composes a multi-phase execution strategy, chaining engines where outputs feed subsequent passes (as in the 8-pass genealogy pipeline: profiling → classification → scanning → synthesis → tactics → conditions → final synthesis).

**Current state**: Fully operational. The planner (`src/presenter/`) already performs engine selection, phase ordering, and execution strategy composition.

### Stage 2: Renderer + Sub-Renderer Selection

For each engine output, the LLM selects how to present it:

- **Renderer type** — accordion, card_grid, stat_summary, prose, table, raw_json, card
- **Sub-renderers** — 18+ options dispatched by config: chip_grid, mini_card_list, key_value_table, prose_block, stat_row, comparison_panel, timeline_strip, distribution_summary, template_card, evidence_trail, condition_cards, etc.
- **Renderer config** — layout, card_template slots, section_renderers mapping, stat selection, prose positioning

Each renderer declares its `ideal_data_shapes` and `config_schema`, enabling the LLM to match engine output shapes to appropriate visual representations.

**Current state**: Partially operational. The view refiner (`view_refiner.py`) adjusts renderer choices post-execution, and the dynamic extraction system (`dynamic_prompt.py`) can bridge any engine output to any renderer. But renderer selection is currently constrained to the pre-authored view definition catalog.

### Stage 3: Tab/Subtab Hierarchy Composition

The LLM structures views into a navigable hierarchy:

- **Parent views** become tabs (e.g., "Portrait", "Genealogies", "Tactics")
- **Child views** become subtabs or accordion sections within parents
- **Position** and **priority** determine ordering and default selection
- **Visibility rules** — `if_data_exists`, `always`, `hidden` — adapt to actual output richness

The parent-child tree is assembled by `compose_tree()` in the view registry, producing a nested structure the frontend renders as tabbed navigation.

**Current state**: Operational for pre-defined hierarchies. The tree structure exists but is statically defined per view definition's `parent_view_key` field. No mechanism for the LLM to invent new hierarchies dynamically.

### Stage 4: Style School Application

The LLM selects a style school from the six available options, each providing:

- **Color palette** — primary, secondary, accent, background, text, plus semantic colors
- **Typography** — font families, sizes, weights, line heights
- **Layout principles** — spacing philosophy, density preferences, visual rhythm
- **Renderer guidance** — per-renderer style notes (e.g., "accordions should use subtle separators, not heavy borders")
- **Affinity mappings** — which engines, formats, and audiences naturally align with which schools

The style school flows through `DesignTokenContext` as CSS custom properties, consumed by all renderers via a 6-tier token hierarchy.

**Current state**: Operational. Six schools fully defined in `src/styles/definitions/schools/`. Affinity mappings in `affinities.json`. `DesignTokenContext.tsx` injects tokens. However, the polisher and design token systems are partially disconnected (Gap #6 — see Section 5).

### Stage 5: Contextual Polishing

The polisher (`polisher.py`) performs LLM-driven visual refinement:

- Takes a `ViewPayload` + full style context (school, palette, typography, renderer guidance)
- Returns enhanced `renderer_config` + `style_overrides` at 31 injection points (16 coarse-grained + 15 fine-grained)
- Section-level polishing incorporates user feedback for iterative refinement
- Enforces safety constraints (no dark backgrounds, no uppercase transforms, conservative typography)

This is the stage where the composition transitions from structurally correct to visually refined — where an LLM with curatorial taste shapes the final presentation.

**Current state**: Fully operational. Sonnet 4.6 handles polish with cached results keyed by config hash.

---

## 4. What Lives Where

### In analyzer-v2 (Everything Analytical + Presentational)

| Domain | Assets | Location |
|--------|--------|----------|
| **Engines** | 203 analytical engines with schemas | `src/engines/definitions/` |
| **Views** | Composed view definitions with data sources | `src/views/definitions/` |
| **Renderers** | 7 renderer types + 18 sub-renderers | `renderers-ui/src/` |
| **Styles** | 6 style schools + affinity mappings | `src/styles/definitions/` |
| **Design Tokens** | 6-tier token hierarchy, CSS custom properties | `renderers-ui/src/tokens/` |
| **Transformations** | Curated templates + dynamic extraction | `src/transformations/`, `src/presenter/dynamic_prompt.py` |
| **Presenter** | 3-stage pipeline (preparation → assembly → polish) | `src/presenter/` |
| **Polisher** | LLM-driven visual enhancement | `src/presenter/polisher.py` |
| **View Refiner** | Post-execution view adjustment | `src/presenter/view_refiner.py` |
| **Composition API** | View composition endpoint | `api/routes/` |

### In Consumer Apps (Thin Shell Only)

| Concern | What the app provides | What it does NOT provide |
|---------|----------------------|--------------------------|
| **Routing** | URL → page mapping | No domain-specific routes |
| **Auth** | Login, session, permissions | — |
| **Project Management** | Create/list/archive projects | — |
| **Generic Workspace** | `AnalysisWorkspacePage` — renders any `PagePresentation` | No workflow-specific pages |
| **Renderer Host** | Imports `renderers-ui`, provides DOM | No local renderer implementations |
| **API Proxy** | Forwards to analyzer-v2 | No analytical logic |

The consumer app's total domain-specific code should approach **zero**. It is a vessel, not a brain.

### In analyzer-mgmt (Design Studio)

The management interface where humans curate the building blocks LLMs compose with:

- Browse and edit engine definitions
- Author and refine view definitions
- Tune style school parameters
- Preview renderer output with sample data
- Review and approve LLM-generated view compositions
- Manage transformation templates

This is the **human-in-the-loop** layer: LLMs propose, humans review and approve, the catalog grows, and future LLM compositions draw from an ever-richer palette.

---

## 5. Gap Analysis: Current State vs. Vision

### Already Aligned (~60%)

| Capability | Evidence | Maturity |
|-----------|----------|----------|
| Config-driven view definitions | 14+ JSON view defs in `src/views/definitions/` | Production |
| Presenter assembles PagePresentation | `presentation_bridge.py` (701 lines) + `presentation_api.py` (825 lines) | Production |
| Generic AnalysisWorkspacePage | Zero-code consumer at `/p/:projectId/analysis/:workflowKey` | Production |
| LLM-driven polishing | `polisher.py` (797 lines) with 31 injection points | Production |
| Style school system | 6 schools with affinity mapping in `src/styles/` | Production |
| Dynamic extraction fallback | `dynamic_prompt.py` (314 lines) — every engine renderable without template | Production |
| Renderers-ui is domain-generic | 7 renderers + 18 sub-renderers, no domain logic | Production |
| Template card cell | Config-driven card layout via `card_template` slots | Production |
| Sub-renderer dispatch | `SubRendererDispatch.tsx` selects by config | Production |
| Design token context | 6-tier hierarchy, CSS custom properties | Production |
| View registry with lazy loading | Singleton pattern, summary/compose/filter methods | Production |
| Batch-optimized data loading | Prefetch eliminates N+1 queries (50-70 → 2) | Production |
| Scope-aware handling | Aggregated, per-item, chain-backed scopes | Production |

### Partially Aligned (~25%)

| Capability | Current State | Gap |
|-----------|---------------|-----|
| **View recommendation** | LLM recommends views post-execution via `view_refiner.py` | Can only select from fixed catalog; cannot invent new view structures or renderer configurations |
| **Tab/subtab composition** | Parent-child tree exists via `parent_view_key` + `compose_tree()` | Hierarchy is static per view def; LLM cannot dynamically restructure tab arrangement |
| **Style application** | Polisher emits `style_overrides` as raw CSS values; DesignTokenContext provides CSS custom properties | Two disconnected styling systems — polisher should emit design tokens, not raw CSS |
| **Transformation pipeline** | Dynamic extraction generates prompts; curated templates override | No schema validation on extraction output; silent failures when shape mismatches renderer expectations |
| **App consumption pattern** | AnalysisWorkspacePage is fully generic | the-critic also has bespoke `GenealogyPage.tsx` with hardcoded workflow, legacy data resolution, and inline fallback view definitions |

### Not Yet Aligned (~15%)

| Capability | What's Missing |
|-----------|----------------|
| **Dynamic view generation** | `POST /v1/views/generate` exists with `save=false` default (ephemeral), but no orchestrator-level "compose page from intent" endpoint |
| **Ephemeral project lifecycle** | Projects persist indefinitely; no "use and discard" pattern with auto-archival |
| **Full UI composition by LLM** | `/v1/views/generate` can create views from patterns (ephemeral by default), but no end-to-end "prose + intent → rendered page" pipeline |
| **Renderer input contracts** | `input_data_schema` field exists in `RendererDefinition` but is unpopulated in all renderer JSONs; no runtime validation endpoint |
| **Cross-app renderer sharing** | `renderers-ui` is an npm package but the-critic maintains local renderer copies and view-key-specific overrides |
| **Dynamic app generation** | No mechanism for an LLM to compose an entire single-use app from scratch |

---

## 6. Reconciliation Plan: Closing the Gaps

### Tier 1: Foundation (Enable LLM Composition)

These changes make analyzer-v2's building blocks composable by LLMs, not just selectable.

#### 1a. Renderer Input Contracts

**Problem**: Renderers accept `structured_data: unknown`. When the transformation pipeline produces the wrong shape, the renderer silently fails or renders garbage.

**Solution**: Each renderer declares its expected input shape as JSON Schema.

- Create `renderers-ui/src/schemas/` with per-renderer schemas (e.g., `accordion.schema.json`, `card_grid.schema.json`)
- Presenter validates `structured_data` against schema before sending to frontend
- Generate TypeScript types from schemas for compile-time safety
- LLMs use schemas to understand what each renderer needs, enabling accurate composition

**Impact**: Eliminates silent rendering failures; gives LLMs a formal contract for composition.

#### 1b. View Definition Generation API

**Problem**: View definitions are hand-authored JSON files. LLMs can select from the catalog but cannot create new compositions.

**Solution**: New endpoint where LLMs generate view definitions from engine outputs + user intent.

- `POST /v1/views/compose` — accepts engine output schemas, user intent description, style preference
- Returns a complete view definition (renderer selection, sub-renderer config, tab hierarchy, transformation spec)
- Generated view defs are **ephemeral** (session-scoped), not persisted to the file catalog
- Curated templates remain for high-quality recurring patterns; generated defs handle novel combinations

**Impact**: Transitions from "select from menu" to "compose from primitives" — the core unlock for bespoke apps.

#### 1c. Unify Style Systems

**Problem**: Polisher emits raw CSS values (`style_overrides`). DesignTokenContext provides CSS custom properties. Two disconnected systems with potential conflicts.

**Solution**: Polisher emits design tokens, not raw CSS.

- Polisher output uses token names (e.g., `--color-accent`, `--space-card-padding`) instead of hex values and pixel sizes
- DesignTokenContext consumes polisher output directly as token overrides
- Single cascade: style school → design tokens → polisher refinements → renderer CSS
- Eliminates the "which system wins?" ambiguity

**Impact**: One coherent styling pipeline from school selection to pixel rendering.

### Tier 2: Composition (LLM Builds the Whole Page)

These changes let the LLM compose entire page experiences, not just individual views.

#### 2a. Page Composition Endpoint

**Problem**: PagePresentation is assembled from pre-existing view definitions. No way to generate an entire page structure from scratch.

**Solution**: New endpoint that composes a complete page from engine outputs + intent.

- Input: list of engine output summaries + user intent + style preference + audience
- Output: complete `PagePresentation` with tab hierarchy, view assignments, style overrides
- Uses renderer input contracts (1a) to ensure valid compositions
- Uses view generation (1b) for individual views within the page
- No pre-existing view definitions required

**Impact**: The full "question → screen" pipeline with no human-authored intermediaries.

#### 2b. Ephemeral Project Pattern

**Problem**: Analysis projects persist indefinitely. No lifecycle management.

**Solution**: Projects as disposable workspaces with lifecycle states.

- States: `active` → `archived` → `deleted`
- Auto-archive after N days of inactivity
- All presentation artifacts (view defs, polish cache, transformation cache) scoped to project
- Archived projects retain results but release presentation resources
- User can "revive" archived projects (re-generates presentation from cached engine outputs)

**Impact**: Enables the "use and discard" pattern central to the bespoke vision.

#### 2c. Thin Shell App Template

**Problem**: the-critic has bespoke pages (GenealogyPage), local renderer overrides, and hardcoded data resolution — accumulating domain-specific UI code.

**Solution**: Eliminate all bespoke rendering code from consumer apps.

- GenealogyPage route redirects to `AnalysisWorkspacePage` with `workflowKey="intellectual_genealogy"`
- Remove all view-key-specific renderer registrations from the-critic
- Remove `resolveViewData()` utility and `LEGACY_VIEWS` constants
- the-critic becomes: routing → `AnalysisWorkspacePage` → `renderers-ui` imports → done
- Create a thin shell app template that any new consumer app starts from

**Impact**: Proves the thesis — consumer apps carry zero analytical UI code.

### Tier 3: Intelligence (LLM Improves Itself)

These changes create feedback loops that improve composition quality over time.

#### 3a. Feedback Capture

**Problem**: No signal about which compositions work well for users.

**Solution**: Capture implicit and explicit user feedback.

- Track: time spent per view, scroll depth, expand/collapse patterns, tab switches
- Capture: user-initiated section-level polish requests (already partially exists)
- Store feedback linked to composition parameters (engine, renderer, style school, audience)
- Feed aggregated signals back to view generation prompts

**Impact**: Compositions get better over time without manual curation.

#### 3b. A/B View Composition

**Problem**: LLM generates one composition; no way to explore alternatives.

**Solution**: Generate multiple layout options for complex analyses.

- Present 2-3 layout alternatives for the same engine output
- User selects preferred; choice feeds back to future composition
- Variations can differ in renderer type, sub-renderer selection, or style school
- Lightweight — same structured_data, different presentation

**Impact**: Users shape the composition vocabulary through selection, not specification.

---

## 7. Anti-Patterns This Vision Rejects

### Bespoke Renderers in Consumer Apps
If a renderer is useful enough to build, it belongs in `renderers-ui`. Consumer apps should never contain rendering logic — not "just this one special case", not "a quick override for this view_key". The renderer catalog is the renderer catalog; it lives in one place.

**Current violation**: the-critic registers view-key-specific renderers (`IdeaEvolutionRenderer`, `SynthesisRenderer`) in its local `initRenderers.ts`.

### Hardcoded Style Decisions Outside analyzer-v2
Colors, fonts, spacing, and layout rules belong in style school definitions and design tokens. Consumer apps should not contain hex values, font-size declarations, or layout constants.

**Current violation**: ~370 hardcoded hex values in the-critic's CSS, 8 color maps in `genealogyStyles.ts`, `ENUM_COLORS` in `AccordionRenderer`.

### Manual View Definition Authoring as Default Workflow
Hand-authoring JSON view definitions should be the exception (high-quality curated templates for recurring patterns), not the rule. The default path should be LLM composition with human review.

**Current violation**: All 14+ view definitions are hand-authored. No API for LLM-generated view defs.

### Apps That Accumulate Domain-Specific UI Code
Every line of domain-specific UI code in a consumer app is a line that should be in analyzer-v2. Consumer apps grow in only two dimensions: more routes and more auth complexity. They never grow in analytical or presentational capability.

**Current violation**: GenealogyPage (1700+ lines), `resolveViewData()`, `LEGACY_VIEWS`, genealogy-specific tab logic.

---

## 8. The Endgame

When this vision is fully realized:

1. **A user asks a question about a text** — "How does this author's concept of freedom evolve across their bibliography?"
2. **An LLM selects engines** — genealogy profiling, evolution tracking, tactic classification, synthesis
3. **Engines execute** — producing structured analytical outputs
4. **An LLM composes the UI** — selecting renderers, configuring sub-renderers, structuring tabs, choosing a style school, polishing each view
5. **A thin shell app renders it** — `AnalysisWorkspacePage` receives the `PagePresentation` and paints it
6. **The user explores, annotates, refines** — section-level polish requests feed back to the composition
7. **When done, the workspace archives** — engine outputs persist for future re-composition; the presentation dissolves

No developer touched the UI. No designer mocked up layouts. No product manager specified requirements. The LLM composed a bespoke analytical environment from analyzer-v2's catalog of primitives, shaped by the user's question and the material's character.

The app was born for this question. It will not outlive it. And the next question will birth a different app — drawing from the same catalog but composing a different experience.

This is what it means for analyzer-v2 to be the central intelligence layer: **not a backend that serves data, but a brain that composes experiences**.

---

## 9. UI Pipeline Readiness Audit (Detailed)

This section assesses, layer by layer, how ready the UI pipeline is for an external LLM orchestrator that says: *"Here's prose output from engines. Here are the available renderers, sub-renderers, style schools. Compose a full page."*

### 9.1 Transformation Layer — 95% Ready

**What works**: The dynamic extraction system (`dynamic_prompt.py`, 314 lines) can transform arbitrary prose into structured data for ANY renderer WITHOUT curated templates. It composes prompts from engine metadata (`canonical_schema`, `extraction_focus`) + renderer metadata (`ideal_data_shapes`, `config_schema`) + presentation stance. Haiku does the extraction; Sonnet is the fallback.

**Existing APIs**:
```
POST /v1/transformations/execute     — ALREADY STATELESS: accepts raw `data: Any` directly
GET  /v1/transformations/for-engine/{key}   — find templates for an engine
GET  /v1/transformations/for-renderer/{key} — find templates for a renderer
POST /v1/transformations/generate    — LLM-powered template generation
```

**Correction** (verified 2026-03-08): The `/v1/transformations/execute` endpoint does NOT require `job_id` or `output_id`. It accepts raw data directly via the `data` field and can use either a `template_key` reference or inline transformation spec (`transformation_type`, `field_mapping`, `llm_prompt_template`, etc.). An external orchestrator can already transform arbitrary prose.

**Remaining gap**: The dynamic prompt composition system (`compose_dynamic_extraction_prompt`) is used internally by `presentation_bridge.py` but not directly exposed as an API convenience. An orchestrator wanting to leverage it would need to construct the inline spec manually rather than just saying "transform this prose for this renderer type". This is a **thin wrapper opportunity**, not a fundamental capability gap.

**What could improve it**: A convenience alias that combines dynamic prompt composition + execution:
```
POST /v1/transformations/extract
{
  "prose": "...",
  "renderer_type": "accordion",
  "engine_key": "genealogy_portrait",     // for prompt composition
  "stance_key": "interactive",            // optional
}
→ { "structured_data": { ... } }
```
This would internally call `compose_dynamic_extraction_prompt()` → `execute()` — no new logic, just routing convenience.

### 9.2 View Composition — 70% Ready

**What works**: View definitions can be CRUD'd via API. `POST /v1/views` creates a view definition; `GET /v1/views/compose/{app}/{page}` returns a full parent-child tree. The registry supports filtering by workflow, chain, and app. `POST /v1/views/generate` provides LLM-powered view generation from patterns **with `save=false` by default** (ephemeral views that are returned but not persisted to disk).

**Existing APIs**:
```
GET    /v1/views                         — list summaries (filterable by app/page)
GET    /v1/views/{view_key}              — get single view definition
GET    /v1/views/compose/{app}/{page}    — get complete page view tree
GET    /v1/views/for-workflow/{key}      — views for a workflow
POST   /v1/views                         — create view definition
PUT    /v1/views/{view_key}              — update view definition
POST   /v1/views/generate               — LLM-powered view generation (save=false default!)
```

**Correction** (verified 2026-03-08): `/v1/views/generate` defaults to `save=false`. Generated views are ephemeral — returned in the response but NOT persisted to disk unless explicitly requested with `save=true`. This means the building block for ephemeral view composition already exists.

**The real gap**: There is no end-to-end "compose a page from prose + intent" endpoint that handles renderer selection + view generation + transformation + assembly + polish in one shot. The pieces exist (view generation, transformation execution, page assembly, polish) but aren't wired together in an orchestrator-facing flow.

**What's needed**: A one-shot composition endpoint:
```
POST /v1/views/compose-from-intent
{
  "prose_sections": [
    { "engine_key": "genealogy_portrait", "prose": "..." },
    { "engine_key": "genealogy_tactics", "prose": "..." }
  ],
  "user_intent": "Show me how this author's ideas evolved",
  "style_school": "humanist_craft",          // optional
  "audience": "academic",                     // optional
  "ephemeral": true                           // don't persist to disk
}
→ { "page_presentation": { ... }, "view_definitions": [ ... ] }
```

### 9.3 Renderer Dispatch & Discovery — 85% Ready

**What works**: Full renderer discovery API. Each renderer definition includes `ideal_data_shapes`, `config_schema`, `available_section_renderers`, and `stance_affinities`. LLM-powered recommendation endpoint exists. Sub-renderer dispatch is config-driven with auto-detection fallback.

**Existing APIs**:
```
GET    /v1/renderers                      — list all with summaries
GET    /v1/renderers/{key}                — full definition with config_schema
GET    /v1/renderers/for-stance/{key}     — sorted by affinity
GET    /v1/renderers/for-primitive/{key}  — by analytical type
POST   /v1/renderers/recommend            — LLM-powered recommendation
```

**Exported renderers** (`renderers-ui/src/index.ts`):
- AccordionRenderer, CardGridRenderer, CardRenderer, ProseRenderer, TableRenderer, StatSummaryRenderer, RawJsonRenderer
- `resolveSubRenderer()`, `autoDetectSubRenderer()`, `DistributionSummary`
- `DesignTokenProvider`, `useDesignTokens`, `tokenFlattener`
- `TemplateCardCell`, `ConditionCards`, `EvidenceTrail`

**The gap**: All renderers accept `data: unknown` and `config: Record<string, unknown>` at render time. The `RendererDefinition` schema already declares an `input_data_schema: Optional[dict]` field (verified in `src/renderers/schemas.py`), but **no renderer JSON file populates it yet**. The infrastructure for contracts exists; the actual contracts haven't been authored. Additionally, there is no runtime validation in the presenter path — bad data passes through silently.

**What's needed**:
1. **Populate** `input_data_schema` in each renderer's JSON definition with actual JSON Schemas (the field already exists, just needs content)
2. **Validate in presenter path** — `presentation_api.py` should validate `structured_data` against the renderer's `input_data_schema` before including it in PagePresentation, not as an optional API call
3. A validation endpoint: `POST /v1/renderers/{key}/validate` for orchestrators to pre-check data shape
4. TypeScript types generated from schemas for compile-time safety in renderers-ui

### 9.4 Style Pipeline — 80% Ready

**What works**: Complete design token system with LLM-generated tokens per style school. Six schools fully defined with color palettes, typography, layout principles, and per-renderer guidance. Affinity mappings for engine→style, format→style, audience→style. CSS custom property export. `DesignTokenProvider` injects tokens as CSS variables on the frontend.

**Existing APIs**:
```
GET    /v1/styles                         — list all style schools
GET    /v1/styles/schools/{key}           — full style guide
GET    /v1/styles/tokens/{key}            — design tokens (LLM-generated)
GET    /v1/styles/tokens/{key}/css        — as CSS custom properties
GET    /v1/styles/affinities/engine       — engine → style mappings
GET    /v1/styles/for-engine/{key}        — preferred styles for engine
POST   /v1/styles/tokens/{key}/regenerate — force regen
```

**Token hierarchy** (6 tiers): primitives → surfaces → scales → semantic → categorical → components. 130+ token keys covering colors, typography, spacing, borders, shadows, and domain-specific categories (tactic, form, idea, condition, relationship).

**The gap**: Two disconnected style systems coexist:
1. **DesignTokenContext** → CSS custom properties consumed by renderers' CSS
2. **Polisher style_overrides** → raw CSS values injected as inline styles via `config._style_overrides`

The polisher doesn't know about or emit design tokens. It emits values like `{ section_header: { backgroundColor: "#f8f5f0" } }` instead of `{ section_header: { backgroundColor: "var(--surface-section)" } }`. This means polished views may override or conflict with the design token system.

**What's needed**:
1. Polisher prompt updated to emit token references (`var(--token-name)`) instead of raw values
2. Or: polisher output translated to token overrides in a reconciliation layer
3. Style recommendation endpoint: `POST /v1/styles/recommend` accepting engine_key + renderer_type + audience → ranked school suggestions

### 9.5 Polish Pipeline — 95% Ready

**What works**: View-level and section-level polish, both API-driven. 31 injection points (section_header, card, chip, badge, timeline_node, prose, prose_lede, stat_number, hero_card, etc.). Section-level polish incorporates user feedback. Caching with config-hash invalidation. Auto-polish option in the compose endpoint.

**Existing APIs**:
```
POST   /v1/presenter/polish              — polish a view
POST   /v1/presenter/polish-section      — polish a section with feedback
DELETE /v1/presenter/polish-cache/{id}   — clear cache
POST   /v1/presenter/compose             — all-in-one (includes auto_polish=true)
```

**The gap**: Minor — polish currently requires `job_id` to locate the view payload. An orchestrator composing views without a job cannot polish them. But this is the same "requires job context" gap as transformation.

### 9.6 Frontend Consumption — Already a Thin Shell

**Critical finding**: the-critic's AnalysisWorkspacePage is **already** a thin shell. The rendering chain is:

```
AnalysisWorkspacePage
  → fetches PagePresentation from /v1/presenter/page/{jobId}?slim=true
  → fetches ComposedView tree from /v1/views/compose/{app}/{page}
  → passes both to V2TabContent
    → V2TabContent handles tab switching, polish prefetch, lazy prose loading
      → ViewRenderer dispatches to registered renderer by type
        → Renderer renders structured_data with config
```

**The minimum viable thin shell needs only**:
1. `V2TabContent.tsx` (~945 lines) — tab rendering, polish integration, section extraction
2. `ViewRenderer.tsx` (~158 lines) — renderer dispatch
3. `initRenderers.ts` + renderer files (~2500 lines) — the actual renderers
4. `useViewDefinitions.ts` (~237 lines) — fetches view definitions from analyzer-v2

**Total**: ~3,800 lines of reusable rendering infrastructure. Zero domain-specific code required.

**But**: the-critic currently maintains **local copies** of all renderers (not importing from renderers-ui npm package) and registers **view-key-specific overrides** (IdeaEvolutionRenderer, SynthesisRenderer). The renderers-ui package (`@caii/analysis-renderers`) exists but isn't consumed by the-critic as an import — instead, equivalent implementations live in `/webapp/src/components/renderers/`.

---

## 10. Implementation Priorities (Claude + Codex Consensus)

After cross-review between Claude and Codex (2026-03-08), the priorities have been refined. The original "three missing endpoints" framing overstated some gaps. Here is the corrected assessment:

### Priority 1: Renderer Contract Validation (HIGH — prerequisite for safe composition)

The `input_data_schema` field exists in `RendererDefinition` but is empty across all renderer JSONs. Before building more composition surface, enforce data contracts so bad compositions fail loudly rather than silently rendering garbage.

**Work items**:
1. Populate `input_data_schema` in each of the 7 renderer definition JSONs
2. Add validation in the presenter path (`presentation_api.py`) — reject malformed structured_data before it reaches the frontend
3. Add `POST /v1/renderers/{key}/validate` endpoint for orchestrators to pre-check

**Effort**: Medium. Schema authoring per renderer + validation plumbing.

**Codex's reasoning**: *"Renderer contract validation before more composition surface"* — without contracts, every new composition endpoint is building on sand.

### Priority 2: Consumer Consolidation (HIGH — proves the thesis)

Move the-critic to import `@caii/analysis-renderers` from analyzer-v2's renderers-ui package. Remove local renderer copies and view-key-specific overrides. This is the single most visible step toward proving the "thin shell" thesis.

**Work items**:
1. Publish `@caii/analysis-renderers` as installable package
2. Replace all local renderer files in the-critic with imports
3. Remove `IdeaEvolutionRenderer`, `SynthesisRenderer` view-key overrides — express their logic through `renderer_config`
4. Redirect GenealogyPage route to AnalysisWorkspacePage

**Effort**: Medium-Large. Renderer API surface alignment + migration.

### Priority 3: `POST /v1/presenter/compose-from-intent` (HIGH — the orchestration entrypoint)

The single endpoint an external orchestrator needs. Internally wires together existing pieces:
- `/v1/renderers/recommend` for renderer selection
- `/v1/views/generate` (save=false) for ephemeral view creation
- `/v1/transformations/execute` (already stateless) for prose → structured data
- Page assembly logic from `presentation_api.py`
- Optional auto-polish

```
POST /v1/presenter/compose-from-intent
{
  "prose_sections": [
    { "engine_key": "genealogy_portrait", "prose": "..." },
    { "engine_key": "genealogy_tactics", "prose": "..." }
  ],
  "user_intent": "Show me how this author's ideas evolved",
  "style_school": "humanist_craft",     // optional
  "audience": "academic",               // optional
  "auto_polish": true                   // optional
}
→ { "page_presentation": { ... } }
```

**Effort**: Medium. Orchestration glue over existing capabilities, not new logic.

**Codex's key insight**: *"Keep /views/generate as the primitive and build compose-from-intent as orchestrator glue over existing pieces."* Don't duplicate — compose.

### Priority 4: Style-Token Unification (MEDIUM — coherence)

Polisher should emit token references, not raw CSS values. This prevents polished views from conflicting with the design token system.

**Effort**: Small-Medium. Polisher prompt changes + optional reconciliation layer.

### Priority 5: `POST /v1/styles/recommend` (LOW — useful but non-blocking)

Heuristic-first style recommendation from existing affinity mappings. LLM reasoning optional.

**Effort**: Small. Thin wrapper over `get_styles_for_engine()` + `get_styles_for_format()` + `get_styles_for_audience()`.

### Priority 6: Ephemeral Project Lifecycle (LOW — only if "disposable apps" is core)

Project states: `active` → `archived` → `deleted`. Auto-archive after N days. Scoped artifact cleanup.

**Effort**: Medium. Data model + cleanup jobs + lifecycle API.

### What's NOT a Gap (Previously Misstated)

- **~~Stateless transformation~~**: `/v1/transformations/execute` already accepts raw `data` without job context
- **~~Views persist to disk~~**: `/v1/views/generate` defaults to `save=false` (ephemeral)
- **~~No renderer schema infrastructure~~**: `input_data_schema` field exists in RendererDefinition; needs population, not creation

### The Critical Path — DECISION PENDING

```
Priority 1 (contracts) → [ Priority 2 or 3 — order TBD ] → [ remaining ]
```

Both agents agree: **renderer contracts first**. The ordering of priorities 2 and 3 is unresolved:

| Order | Rationale | Risk |
|-------|-----------|------|
| Contracts → Consolidation → Compose | Consumption-first: forces renderer package to be consumed correctly, surfaces integration issues early (Codex) | compose-from-intent delayed; orchestrator can't be tested until later |
| Contracts → Compose → Consolidation | API-first: proves the orchestration surface works before migrating consumers to depend on it (Claude) | consolidation delayed; anti-pattern persists longer |

**Owner should pick one before implementation begins.** The wrong choice wastes at most one sprint of sequencing; either path reaches the same end state.

---

## 11. Renderer Package Consolidation

One structural issue remains independent of the three endpoints: **the-critic maintains its own renderer implementations** instead of importing from the `@caii/analysis-renderers` package.

### Current State
- `renderers-ui/` in analyzer-v2 contains the canonical implementations (7 renderers, sub-renderer dispatch, design token context)
- `the-critic/webapp/src/components/renderers/` contains equivalent implementations (~19 files, ~2500 lines)
- The two sets are **not in sync** — the-critic's copies may have diverged
- `the-critic/webapp/package.json` does not import `@caii/analysis-renderers`

### What Needs to Happen
1. Publish `@caii/analysis-renderers` as a package the-critic can npm-install
2. Replace all local renderer files in the-critic with imports from the package
3. Remove view-key-specific renderer overrides (IdeaEvolutionRenderer, SynthesisRenderer) — their logic should be expressible through renderer_config, not custom code
4. V2TabContent and ViewRenderer should also move into the package or be thin enough to stay local

### Why This Matters for the Vision
If every consumer app maintains its own renderer copies, the "single source of truth" thesis is violated. Renderers must live in one place (analyzer-v2's renderers-ui), be published as a package, and be consumed without modification.

---

## 12. Cross-Review Log

This section records assessments from different LLM agents to maintain a shared record of agreements and disagreements.

### Codex 5.3 Review (2026-03-08)

**Verified as accurate**: Engine/style counts, presenter/polisher maturity, bespoke anti-patterns in the-critic, generic workspace route.

**Corrections applied**:
1. `/v1/transformations/execute` is already stateless — accepts raw `data: Any`, no job_id required → Section 9.1 updated from 90% to 95%
2. `/v1/views/generate` supports `save=false` (default) — ephemeral views already possible → Section 9.2 updated from 60% to 70%
3. `input_data_schema` field exists in `RendererDefinition` schema — unpopulated but infrastructure is there → Section 9.3 updated

**Priority ordering** (Codex):
1. Renderer contract validation (before more composition surface)
2. Consumer consolidation (move the-critic to `@caii/analysis-renderers`)
3. `compose-from-intent` endpoint
4. Style-token unification
5. Project lifecycle states

**Key architectural opinion**: *"Don't add a brand-new extract endpoint first; factor existing extraction internals into a reusable service and expose minimal route aliases only if needed."* — Prefers composition over new primitives.

**Disagreement with Claude**: Order of priorities 2 vs 3. Codex prefers consolidation before compose-from-intent (consumption-first). Claude prefers compose-from-intent before consolidation (API-first). Both orderings documented in Section 10.

---

## 13. Collaboration Protocol

This document is designed to be read by multiple LLM agents (Claude, Codex, Gemini) working on this codebase. Each agent should:

1. **Read this document first** for architectural context
2. **Verify claims against actual code** — file paths and API endpoints listed here are accurate as of 2026-03-08 but may drift
3. **Focus on the UI pipeline** — engine selection and execution are out of scope for this phase
4. **Propose changes as PRs or memos** in `communications/` — don't silently refactor

### Key Repositories
- **analyzer-v2**: Engines, views, renderers, styles, presenter pipeline, API
- **the-critic**: Consumer app (the first thin shell candidate)
- **analyzer-mgmt**: Management UI for curating building blocks (not yet built)

### Key Files to Read
| File | What It Shows |
|------|---------------|
| `analyzer-v2/src/presenter/presentation_bridge.py` | How prose → structured data works |
| `analyzer-v2/src/presenter/presentation_api.py` | How PagePresentation is assembled |
| `analyzer-v2/src/presenter/polisher.py` | How views get visually refined |
| `analyzer-v2/src/presenter/dynamic_prompt.py` | How any engine can render in any renderer |
| `analyzer-v2/src/views/definitions/*.json` | What view definitions look like |
| `analyzer-v2/src/styles/definitions/schools/*.json` | What style schools contain |
| `analyzer-v2/renderers-ui/src/index.ts` | What the renderer package exports |
| `the-critic/webapp/src/components/V2TabContent.tsx` | How the frontend consumes PagePresentation |
| `the-critic/webapp/src/pages/AnalysisWorkspacePage.tsx` | The generic consumer pattern |
| `the-critic/webapp/src/pages/GenealogyPage.tsx` | The anti-pattern to eliminate |
