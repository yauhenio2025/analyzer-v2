# Intellectual Genealogy Pipeline: Data Flow Walkthrough

> Updated: 2026-02-18
> Workflow: `intellectual_genealogy` (v3)
> 11 capability engines, 3 chains, 5 workflow passes

## Pipeline Overview

```
Pass 1: Target Profiling     Pass 1.5: Relationship Classification
  (chain: 3 engines)           (standalone engine)
  [parallel execution]         [parallel execution]
         │                              │
         └──────────┬───────────────────┘
                    │
                    ▼
         Pass 2: Prior Work Scanning
           (chain: 2 engines, per prior work)
                    │
                    ▼
         Pass 3: Analysis & Synthesis
           (chain: 4 engines)
                    │
                    ▼
         Pass 4: Final Synthesis
           (standalone engine)
```

---

## Pass 1: Deep Target Work Profiling

**Chain**: `genealogy_target_profiling` (sequential, pass_context: true)
**Depends on**: nothing
**Input**: target corpus

### Engine 1.1: `conceptual_framework_extraction`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → architecture |
| deep | 3 | discovery → architecture → integration |

**What it produces**: Vocabulary map (terms, definitions, registers, neologisms), methodological signature (approach, evidence standards, causal models), metaphor inventory (systematic metaphors, entailments), framing analysis (problem definition, boundaries, audience positioning), conceptual architecture (foundational vs derived, dependency chains), domain crossings (imports/exports between fields).

**Shares downstream (via pass_context)**: vocabulary_profile, methodological_fingerprint, metaphor_inventory, framing_landscape, framework_architecture, domain_crossing_map, genealogical_hints

### Engine 1.2: `concept_semantic_constellation`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → architecture |
| deep | 4 | discovery → architecture → dialectical → integration |

**Consumes**: conceptual_framework_extraction output (via chain pass_context)
**What it produces**: Semantic fields (term clusters, proximity maps), concept clusters (co-occurrence patterns, thematic groupings), boundary terms (contested concepts, definitional edges), usage patterns (register shifts, audience adaptation), connotation landscapes (implicit value systems, emotional registers).

**Shares downstream**: semantic_field_map, concept_cluster_graph, boundary_analysis, connotation_profiles

### Engine 1.3: `inferential_commitment_mapper`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → confrontation |
| deep | 4 | discovery → confrontation → dialectical → integration |

**Consumes**: conceptual_framework_extraction + concept_semantic_constellation output
**What it produces**: Explicit commitments (with centrality, originality, evidential basis), implicit commitments (presuppositions, entailments, background assumptions), commitment conflicts (tensions, contradictions, navigation strategies), logical dependencies (what must be true for what), hidden implications (what follows that the author may not intend).

**Pass 1 total output**: Comprehensive multi-dimensional profile of the target work — vocabulary, methodology, metaphors, framing, semantic fields, concept clusters, commitments, conflicts, dependencies, implications.

---

## Pass 1.5: Relationship Classification

**Engine**: `genealogy_relationship_classification` (standalone)
**Depends on**: nothing (runs parallel with Pass 1)
**Input**: prior works collection (truncated excerpts) + target work excerpts

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → architecture |
| deep | 3 | discovery → architecture → confrontation |

**What it produces**: Per prior work:
- **Relationship type**: direct_precursor, indirect_contextualizer, methodological_ancestor, contradicted_position, or parallel_development
- **Relationship strength**: strong / moderate / weak
- **Relationship evidence**: citations, vocabulary overlap, structural parallels, conspicuous absences
- **Influence channels**: which of vocabulary / methodology / audience / authority / framing are active
- **Scanning strategy**: priority dimensions and expected trace types for Pass 2

**Key design decision**: This is a triage instrument. Speed matters. It operates on truncated excerpts and classifies rapidly, determining HOW Pass 2 analyzes each work.

---

## Pass 2: Prior Work Scanning

**Chain**: `genealogy_prior_work_scanning` (sequential, pass_context: true)
**Depends on**: Pass 1 (target profile) + Pass 1.5 (relationship classifications)
**Input**: each prior work + target profile + relationship classification
**Execution**: runs ONCE PER PRIOR WORK (parallelizable across works)

**Runtime context parameters** injected from upstream:
- `relationship_type` — from Pass 1.5
- `target_ideas` — from Pass 1 conceptual framework
- `target_vocabulary` — from Pass 1 vocabulary map
- `target_methodological_signature` — from Pass 1 methodology profile

### Engine 2.1: `concept_evolution`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → inference |
| deep | 3 | discovery → architecture → integration |

**Consumes**: target work profile (Pass 1), relationship classification (Pass 1.5)
**What it produces**: Per prior work dimensional comparison — vocabulary_evolution (term adoption, drift, replacement), methodology_evolution (approach continuity/shift), metaphor_evolution (metaphor persistence, mutation, abandonment), framing_evolution (problem redefinition, scope changes), concept_trajectory (how each idea moved between works), dimensional_comparison_matrix (systematic side-by-side on all dimensions).

### Engine 2.2: `concept_appropriation_tracker`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → inference |
| deep | 3 | discovery → architecture → integration |

**Consumes**: concept_evolution output (via chain pass_context)
**What it produces**: Migration paths (how ideas physically moved between works), semantic mutations (meaning changes during migration), appropriation patterns (what types of borrowing occurred), distortion maps (how ideas were changed during appropriation), recombination (how ideas from multiple prior works combined), acknowledgment status (which migrations are acknowledged, which concealed).

**Pass 2 total output per prior work**: Complete dimensional comparison + appropriation analysis between the prior work and the target, calibrated by relationship type.

---

## Pass 3: Analysis & Synthesis

**Chain**: `genealogy_synthesis` (sequential, pass_context: true)
**Depends on**: Pass 1 (target profile) + Pass 2 (all prior work scans)
**Input**: aggregated per-work scan results + target profile

### Engine 3.1: `concept_synthesis`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | integration |
| standard | 2 | discovery → integration |
| deep | 4 | discovery → confrontation → dialectical → integration |

**Consumes**: all Pass 2 per-work traces, Pass 1 target profile
**What it produces**: Cross-work evolution timelines (per-idea chronological trace across all prior works), multi_work_trace_aggregation (which ideas appear in which works), convergence_divergence (ideas that converge across works vs diverge), indirect_enablers (foundational patterns from contextualizer works, cross-domain imports), semantic_core (the stable meaning kernel vs shifting periphery of each concept), critical_verdict (assessment of evolution quality — progressive refinement vs degenerative drift).

### Engine 3.2: `concept_taxonomy_argumentative_function`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → architecture |
| deep | 4 | discovery → architecture → confrontation → dialectical |

**Consumes**: concept_synthesis output
**What it produces**: Functional classification (each conceptual chain as foundational / elaborative / defensive / bridge / culminative), argumentative architecture (how classified chains compose into larger structures), load-bearing analysis (which chains are structurally essential), redundancy map (overlapping functions), vulnerability assessment (points of maximum weakness).

### Engine 3.3: `evolution_tactics_detector`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → architecture |
| deep | 3 | discovery → architecture → reflection |

**Consumes**: concept_synthesis + concept_taxonomy_argumentative_function output
**What it produces**: Tactic detection (specific instances of conceptual_recycling, silent_revision, strategic_escalation, framework_migration, strategic_amnesia, vocabulary_laundering, authority_bootstrapping, hedging_reclassification, complexity_shielding, legacy_management — each with vocabulary/framing/methodological evidence), tactic patterns (distribution, clusters, management style), tactic evolution (how repertoire changes over career), tactic effectiveness (audience-relative success assessment), tactic taxonomy instantiation (which types present, hybrids, novel types).

### Engine 3.4: `conditions_of_possibility_analyzer`

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | discovery |
| standard | 2 | discovery → confrontation |
| deep | 3 | discovery → confrontation → integration |

**Consumes**: all prior chain output + Pass 1 target profile + Pass 1.5 classifications + Pass 2 scans
**What it produces**: Enabling conditions (conceptual, institutional, material, discursive preconditions), constraining conditions (binding prior commitments, lock-in effects), path dependencies (causal chains of intellectual accumulation), unacknowledged debts (hidden borrowings), alternative paths (branching points and paths not taken), counterfactual analysis (what remains without the author's history), cross-domain transfers (imported intellectual toolkits), synthetic judgment (enabling vs constraining overall).

**Pass 3 total output**: Rich analytical synthesis covering evolution patterns, argumentative architecture, intellectual self-management tactics, and Foucauldian conditions of possibility.

---

## Pass 4: Final Synthesis

**Engine**: `genealogy_final_synthesis` (standalone)
**Depends on**: Pass 1 + Pass 1.5 + Pass 2 + Pass 3 (all upstream)
**Input**: all upstream pass outputs as shared context

| Depth | Passes | Stance Sequence |
|-------|--------|-----------------|
| surface | 1 | integration |
| standard | 2 | discovery → integration |
| deep | 3 | discovery → architecture → integration |

**What it produces**:
1. **Executive summary** — 2-3 paragraph distillation of the genealogical picture
2. **Genealogical portrait** — sustained analytical narrative through descent (herkunft) and emergence (entstehung)
3. **Idea genealogies** — per-idea timelines with evolution narratives
4. **Author intellectual profile** — prosopographic characterization (habits, strengths, weaknesses, debt-handling)
5. **Key findings** — the 3-5 discoveries that most change how to read the current work
6. **Methodological notes** — confidence levels, limitations, recommended follow-up investigations

---

## Depth Control

The workflow chooses a depth level (surface/standard/deep) that applies to ALL engines. Each engine's depth level determines:
- How many internal passes it runs (1-4)
- Which analytical stances it employs
- How much detail it extracts per dimension

| Workflow Depth | Typical Total LLM Calls | Best For |
|----------------|------------------------|----------|
| surface | ~15 (1 pass × ~11 engines + chain overhead) | Quick overview, preliminary scoping |
| standard | ~25 (2 passes × ~11 engines) | Most academic texts, 3-7 prior works |
| deep | ~35 (3-4 passes × ~11 engines) | Dense philosophical works, 10+ prior works |

Note: Pass 2 multiplies by number of prior works. With 5 prior works at standard depth, Pass 2 alone is ~10 LLM calls (2 engines × 2 passes × ~5 works, minus chain efficiencies).

---

## Context Threading

**Intra-chain**: Handled by `pass_context: true` in chain definitions. Each engine's output becomes prose context for the next engine in the chain.

**Inter-pass**: Handled by `context_parameters` in workflow pass definitions + `depends_on_passes`. The workflow executor collects output from dependency passes and injects it as shared_context into the current pass's prompt composition.

**Prompt composition** (capability_composer.py): For each engine at each pass:
1. Engine's **problematique** (intellectual framing)
2. **Analytical stance** text (cognitive posture from operationalization)
3. **Operationalized instructions** (engine+stance-specific guidance)
4. **Focus dimensions** with depth_guidance
5. **Focus capabilities** with depth_scaling
6. **Shared context** from prior passes (plain text prose)

---

## Key Architectural Decisions

1. **No new engines**: All 11 existing capability engines suffice. The modular architecture means genealogy-specific behavior emerges from stance selection and operationalization, not from monolithic genealogy-specific code.

2. **No new stances**: The 7 existing stances (discovery, inference, confrontation, architecture, integration, reflection, dialectical) cover all cognitive modes needed for genealogy. "Tracing across works" = discovery + inference; "side-by-side comparison" = confrontation; "genealogical questioning" = confrontation + architecture.

3. **Chains handle engine composition**: The 3 genealogy chains correctly group engines that share context and build on each other's output. No chain modifications were needed.

4. **Operationalization layer provides genealogy specificity**: The operationalizations translate abstract stances into genealogy-specific instructions without requiring bespoke prompt engineering. The capability_composer generates prompts automatically from dimensions + capabilities + operationalizations.

5. **Pass 2 iteration**: The "once per prior work" execution is handled by the workflow executor, not by the workflow definition itself. The workflow declares the chain and its dependencies; the executor handles iteration over prior works.
