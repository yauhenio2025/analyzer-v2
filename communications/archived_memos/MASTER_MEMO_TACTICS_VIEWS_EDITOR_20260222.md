# Master Implementation Memo: Tactics Enhancement + Views Editor Audit

> Project: Multi-project (analyzer-v2, the-critic, analyzer-mgmt)
> Created: 2026-02-22
> Source: NEXT_SESSION_TACTICS_BRIEF.md

## Project Overview

Three-part enhancement spanning the consumer app visual design, the views editor completeness, and structured config editors. The Tactics & Strategies view works but needs editorial polish; the views editor needs audit and structured form-based editing for renderer configs.

## Architecture Decisions

- All view/renderer definitions live in analyzer-v2
- Consumer rendering lives in the-critic
- Editor UI lives in analyzer-mgmt/frontend
- Changes to definitions may need API schema updates in analyzer-v2

## Phase Overview

| Phase | Description | Dependencies | Project |
|-------|-------------|--------------|---------|
| 1 | Enhance Tactics visual design in the-critic | None | the-critic |
| 2 | Audit views editor tabs + fix gaps | None | analyzer-mgmt |
| 3 | Structured renderer config editors | Phase 2 findings | analyzer-mgmt |

## Phase 1: Tactics & Strategies Visual Enhancement (the-critic)

### Scope
- Color-coded tactic_type cards with distinct palettes
- Evidence trail visualization (prior work → current work → assessment as narrative chain)
- Severity hierarchy (Major visually dominant over Moderate)
- Group headers with count + typological description
- Cross-reference chips for ideas involved
- Match editorial quality of Idea Evolution Map tab

### Files to Modify
- `/home/evgeny/projects/the-critic/src/components/genealogy/` — card_grid/tactic components
- View definition: `/home/evgeny/projects/analyzer-v2/src/views/definitions/genealogy_tactics.json`

### Success Criteria
- [ ] Tactic types have distinct color palettes
- [ ] Evidence chain reads as narrative, not flat list
- [ ] Major severity tactics visually dominate
- [ ] Group headers show count + description
- [ ] Matches editorial quality of Idea Evolution Map

## Phase 2: Views Editor Audit + Completeness (analyzer-mgmt)

### Scope
- Audit all 14 genealogy views in the editor
- Verify Identity/Renderer/Data Source/Transformation tabs show complete data
- Identify specific gaps in editor coverage
- Fix any data display issues found

### Priority Views
1. genealogy_tactics — card_grid with cell_renderer, group_by, expandable
2. genealogy_relationship_landscape — card_grid with cell_renderer, group_by
3. genealogy_conditions — accordion with 4 sections
4. genealogy_target_profile — accordion with section_renderers
5. genealogy_tp_conceptual_framework — accordion with 7 sections, 5 sub-renderer types

### Files to Examine/Modify
- Editor: `/home/evgeny/projects/analyzer-mgmt/frontend/src/pages/views/[key].tsx`
- List: `/home/evgeny/projects/analyzer-mgmt/frontend/src/pages/views/index.tsx`
- Types: `/home/evgeny/projects/analyzer-mgmt/frontend/src/types/index.ts`
- API: `/home/evgeny/projects/analyzer-mgmt/frontend/src/lib/api.ts`

### Success Criteria
- [ ] All 14 views have complete, accurate editor tabs
- [ ] Identity tab shows all metadata fields
- [ ] Renderer tab shows full renderer_config
- [ ] Data Source tab shows primary AND secondary sources
- [ ] Wiring Explainer correctly describes data flow

## Phase 3: Structured Renderer Config Editors (analyzer-mgmt)

### Scope
Build structured form editors for renderer_config based on renderer type:
- card_grid: cell_renderer picker, columns slider, group_by, expandable toggle, group_style_map
- accordion: sections list, expand_first toggle, section_renderers (nested tree)
- table: columns list, sortable, filterable
- prose: show_reading_time, show_section_nav, max_preview_lines
- timeline: orientation, label/date/description fields, group_by, variant

### Also
- Section renderers visual editor (tree-like hierarchy)
- Data source completeness (primary + secondary sources + validation)

### Success Criteria
- [ ] Renderer config has structured editors per type
- [ ] Section renderers have visual tree editor
- [ ] Data sources show primary + secondary with validation

## Integration Points
- Phase 1 is fully independent (different project)
- Phase 2 audit findings inform Phase 3 implementation
- Phase 3 builds on Phase 2's codebase understanding

## Out of Scope
- New view definitions
- Engine/chain modifications
- Orchestrator/executor changes
- Backend API changes (unless needed for missing data)
