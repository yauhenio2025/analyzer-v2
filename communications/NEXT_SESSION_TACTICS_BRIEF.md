# Next Session Brief: Tactics & Strategies View Enhancement + Views Editor Audit

## Context

The Tactics & Strategies view (`genealogy_tactics`) renders in the consumer app (`the-critic`) as a card_grid with tactic cards grouped by `tactic_type`. It works but has two categories of issues:

1. **Visual design in the consumer app** — the card grid is functional but not polished; needs editorial-quality treatment
2. **Views editor completeness** — the view's architecture isn't fully reflected in the editor tabs (Identity, Renderer, Data Source, Transformation)

## Part 1: Enhance Tactics & Strategies Visual Design in the-critic

### Current State
- URL: `the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy` → "Tactics & Strategies" tab
- Renderer: `card_grid` with `cell_renderer: tactic_card`, `group_by: tactic_type`, `columns: 2`, `expandable: true`
- Data: 12 tactic items grouped into ~8 types (Vocabulary Migration, Position Reversal, Strategic Ambiguity, etc.)
- Each tactic card shows: title, severity badge, description, ideas involved, prior work references, current work evidence, assessment

### Design Goals
- **Editorial quality** — cards should feel like research findings, not database rows
- **Type-based color coding** — each tactic_type gets a distinct color palette (like the idea cards in Idea Evolution Map)
- **Evidence trail visualization** — prior work refs → current work evidence → assessment should read as a narrative chain, not a flat list
- **Severity hierarchy** — Major tactics should visually dominate over Moderate ones
- **Cross-references** — "Ideas involved" chips should link to the Idea Evolution Map's idea cards
- **Group headers** — tactic_type headers should include count + a brief typological description

### Files to Modify
- `/home/evgeny/projects/the-critic/src/components/genealogy/` — look for the card_grid renderer or tactic-specific component
- View definition: `/home/evgeny/projects/analyzer-v2/src/views/definitions/genealogy_tactics.json`
- Renderer config may need: `group_descriptions`, `severity_colors`, `evidence_layout` fields

### Reference for Design Quality
Look at how the Idea Evolution Map tab renders (same page, second tab) — it has:
- Color-coded idea cards with type-based left border accents
- Timeline visualization with gradient connectors
- Cross-cutting patterns synthesis panel
Match that level of editorial polish for Tactics.

## Part 2: Audit Views Editor Tabs for Architecture Completeness

### Problem
The Views editor (`analyzer-mgmt-frontend.onrender.com/views/genealogy_tactics`) has tabs: Identity, Target, Renderer, Data Source, Transformation, Preview. But some of these tabs may not properly reflect the view's actual architecture:

1. **Identity tab** — Does it show the config_hints (cell_renderer, group_by, columns, expandable)? Or just name/description?
2. **Renderer tab** — We added the Intelligent Renderer Selector + Wiring Explainer. Does it show the FULL renderer_config (cell_renderer, group_by, group_style_map, expandable)?
3. **Data Source tab** — Shows the engine/chain + result_path. But does it show secondary_sources?
4. **Transformation tab** — The view definition may have a `transformation` field with extraction specs. Is it editable?
5. **Preview tab** — Does it show a preview of how the view would render?

### Audit Scope
Check ALL 14 genealogy views — not just Tactics. For each, verify:
- [ ] Identity tab shows all metadata (name, key, description, status, position, visibility, target_app, target_page)
- [ ] Renderer tab shows full renderer_config including cell_renderer, sections, section_renderers, group_by, etc.
- [ ] Data Source tab shows primary data_source AND secondary_sources
- [ ] The Wiring Explainer correctly describes the view's data flow
- [ ] Config hints on the list page match the actual view definition

### Known Gaps (from earlier session)
- The `renderer_config` editor on the Renderer tab only shows a "Show Raw JSON" toggle — it doesn't have structured editors for common config fields
- The `section_renderers` field (used by Target Work Profile and its children) has no visual editor
- The `cell_renderer` field (used by card_grid views) has no picker/editor

### Priority Views for Audit
1. `genealogy_tactics` — card_grid with cell_renderer, group_by, expandable
2. `genealogy_relationship_landscape` — card_grid with cell_renderer, group_by
3. `genealogy_conditions` — accordion with 4 sections (prose)
4. `genealogy_target_profile` — accordion with section_renderers (complex nested)
5. `genealogy_tp_conceptual_framework` — accordion with 7 sections and 5 sub-renderer types

## Part 3: Specific Improvements to Implement

### 3a. Renderer Config Editor (Structured)
Replace the raw JSON editor for `renderer_config` with structured form fields based on renderer type:
- **card_grid**: cell_renderer picker, columns slider (1-4), group_by field, expandable toggle, group_style_map editor
- **accordion**: sections list editor, expand_first toggle, section_renderers editor (nested)
- **table**: columns list, sortable toggle, filterable toggle
- **prose**: show_reading_time, show_section_nav, max_preview_lines
- **timeline**: orientation, label/date/description fields, group_by, variant picker

### 3b. Section Renderers Editor
For views using accordion with `section_renderers`, build a visual editor that shows:
- Each section name → its renderer_type → its sub_renderers
- Allow adding/removing sections and changing sub-renderer types
- Show the nested hierarchy visually (tree-like)

### 3c. Data Source Completeness
Ensure the Data Source tab shows:
- Primary: engine_key + chain_key + result_path + aggregation_mode
- Secondary sources list: each with its own engine/chain/path
- Warning if data source references a chain/engine that doesn't exist

## Technical Notes

### Renderer Affinity Calibration (Just Fixed)
- card_grid evidence affinity: 0.5 → 0.8 (was underweighted)
- timeline evidence: 0.5 → 0.65, narrative: 0.7 → 0.8
- tab evidence: 0.4 → 0.55, comparison: 0.5 → 0.6
- Adaptive scoring weights: structured renderers (list/diagnostic) weight data shape at 0.40 vs 0.30, stance at 0.25 vs 0.35

### API Endpoints
- View list with config hints: `GET /v1/views` (now includes sections_count, has_sub_renderers, config_hints[])
- Full view definition: `GET /v1/views/{key}` (includes complete renderer_config)
- Renderer catalog: `GET /v1/renderers` and `GET /v1/renderers/{key}`
- LLM recommendation: `POST /v1/renderers/recommend`

### Key File Paths
- View definitions: `/home/evgeny/projects/analyzer-v2/src/views/definitions/*.json`
- Renderer definitions: `/home/evgeny/projects/analyzer-v2/src/renderers/definitions/*.json`
- Views editor: `/home/evgeny/projects/analyzer-mgmt/frontend/src/pages/views/[key].tsx`
- Views list: `/home/evgeny/projects/analyzer-mgmt/frontend/src/pages/views/index.tsx`
- API types: `/home/evgeny/projects/analyzer-mgmt/frontend/src/types/index.ts`
- API client: `/home/evgeny/projects/analyzer-mgmt/frontend/src/lib/api.ts`
- Consumer app: `/home/evgeny/projects/the-critic/`

## Success Criteria
1. Tactics & Strategies tab in the-critic looks editorial-quality with color-coded types and evidence chains
2. All 14 views have complete, accurate editor tabs
3. Renderer config has structured editors (not just raw JSON)
4. The Intelligent Renderer Selector correctly ranks card_grid #1 for Tactics & Strategies
5. All changes tested with Playwright before declaring done
