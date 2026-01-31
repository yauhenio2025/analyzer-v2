# Engine Definition System - Comprehensive Guide

You are generating an advanced engine definition for a document analysis system. This guide explains everything you need to know to create a methodologically-grounded, sophisticated engine.

## What Are Engines?

Engines are **analytical lenses** that extract structured knowledge from documents. Each engine embodies a specific methodology—a way of reading, questioning, and organizing what texts contain.

For example:
- **Inferential Commitment Mapper** uses Brandomian inferentialism to reveal what you're really signing up for when you accept ideas
- **Feedback Loop Mapper** uses Meadows/Senge systems thinking to find reinforcing and balancing loops
- **Dialectical Structure Mapper** uses Hegelian dialectics to trace how contradictions drive discourse

An "advanced" engine is one grounded in real methodology from actual theorists, with a comprehensive schema that captures the full richness of that analytical approach.

## The Engine Definition Schema

Every engine definition has these key components:

### 1. Identity & Classification

```json
{
  "engine_key": "causal_inference_auditor_advanced",
  "engine_name": "Causal Inference Auditor (Advanced)",
  "description": "Deep analysis of causal claims using Pearl's DAG framework and Rubin's potential outcomes...",
  "version": 1,
  "category": "methodology",  // See category list below
  "kind": "synthesis",        // primitive | relational | synthesis | extraction | comparison
  "reasoning_domain": "causal_inference_advanced",
  "researcher_question": "What causal claims are being made, and do they hold up to scrutiny?"
}
```

**Categories** (12 total):
- ARGUMENT, EPISTEMOLOGY, METHODOLOGY, SYSTEMS (Analytical Foundations)
- CONCEPTS, EVIDENCE, TEMPORAL (Subject Domains)
- POWER, INSTITUTIONAL, MARKET (Actor & Structure)
- RHETORIC, SCHOLARLY (Discourse Analysis)

### 2. The Canonical Schema (MOST IMPORTANT)

This is the JSON schema defining what the engine extracts. A well-grounded advanced engine has:

- **15+ major entity types** with rich fields
- **Explicit relationship fields** connecting entities (e.g., `source_idea: "idea_id (I{N})"`)
- **ID format conventions** for each entity type
- **A relationship_graph section** for network visualization
- **A meta section** with counts and highlights

#### ID Format Conventions

Each entity type has a consistent ID format:
- Ideas/Concepts: `I{N}` (I1, I2, I3...)
- Commitments: `C{N}`
- Backings: `B{N}`
- Choices: `X{N}`
- Implications: `IMP{N}`
- Tensions: `T{N}`
- Positions: `POS{N}`
- Stocks: `STK{N}`
- Flows: `FLW{N}`
- Loops: `R{N}` (reinforcing) or `B{N}` (balancing)
- And so on...

#### Entity Design Principles

Each entity type should have:
1. **ID field** with format specification
2. **Name/label field** for human-readable display
3. **Description/what_it_is field** explaining the entity
4. **Type/kind field** for classification within the type
5. **Relationship fields** pointing to other entities
6. **Source tracking** (source_articles, from_source)
7. **Assessment fields** (confidence, strength, quality)

Example entity:
```json
{
  "causal_claim_id": "string (format: 'CC{N}')",
  "claim_text": "string (the causal claim as stated)",
  "cause_variable": "string",
  "effect_variable": "string",
  "claimed_mechanism": "string (how cause produces effect)",
  "claim_strength": "deterministic | probabilistic | contributory",
  "evidence_quality": "experimental | quasi_experimental | observational | theoretical",
  "confounders_acknowledged": ["string"],
  "confounders_unacknowledged": ["string"],
  "source_articles": ["string"],
  "supports_claims": ["claim_id (CC{N}) that this evidence supports"],
  "conflicts_with": ["claim_id (CC{N}) that contradict this"],
  "depends_on_assumptions": ["assumption_id (A{N})"]
}
```

### 3. The Relationship Graph Section

Every advanced engine should include:

```json
"relationship_graph": {
  "nodes": [
    {
      "id": "string (any entity ID)",
      "type": "string (entity type name)",
      "label": "string (short display name, 2-5 words)",
      "weight": "number (0-1, centrality/importance)"
    }
  ],
  "edges": [
    {
      "from_id": "string (source entity ID)",
      "to_id": "string (target entity ID)",
      "relationship": "string (typed relationship from key_relationships)",
      "strength": "number (0-1)",
      "bidirectional": "boolean",
      "label": "string (optional edge label)"
    }
  ],
  "clusters": [
    {
      "cluster_id": "string (format: 'CL{N}')",
      "name": "string (evocative cluster name)",
      "member_ids": ["string (entity IDs)"],
      "coherence": "number (0-1)",
      "theme": "string"
    }
  ]
}
```

### 4. Stage Context

This configures how the engine interacts with the three-stage pipeline:

```json
"stage_context": {
  "framework_key": "pearlian_rubin",  // Loads shared framework primer
  "additional_frameworks": ["angrist_pischke"],
  "extraction": {
    "analysis_type": "causal inference",
    "analysis_type_plural": "causal inferences",
    "core_question": "What causal claims are being made, and do they hold up?",
    "extraction_steps": [
      "STEP 1: Identify all causal claims (explicit and implicit)",
      "STEP 2: Draw the causal DAG for each claim",
      "STEP 3: Identify potential confounders...",
      // 10-15 detailed methodology-specific steps
    ],
    "key_fields": {
      "claim_id": "Individual causal claims",
      "confounder_id": "Potential confounding variables"
    },
    "id_field": "claim_id",
    "key_relationships": [
      "causes", "confounds", "mediates", "moderates", "blocks", "enables"
    ],
    "special_instructions": "CRITICAL: Always draw the DAG first..."
  },
  "curation": {
    "item_type": "causal claim",
    "item_type_plural": "causal claims",
    "consolidation_rules": [
      "RULE 1: Merge claims about same causal relationship",
      "RULE 2: Identify contradictory claims across documents"
    ],
    "cross_doc_patterns": ["shared_claims", "contested_claims"],
    "synthesis_outputs": ["consolidated_causal_map", "relationship_graph"],
    "special_instructions": null
  },
  "concretization": {
    "id_examples": [
      {"from": "CC1", "to": "The 'Education Causes Income' Claim"},
      {"from": "CONF1", "to": "Parental Wealth as Confounder"}
    ],
    "naming_guidance": "Use concrete variable names, not abstract labels",
    "recommended_table_types": ["claim_evidence_matrix", "confounder_checklist"],
    "recommended_visual_patterns": ["causal_dag", "evidence_strength_plot"]
  },
  "audience_vocabulary": {
    "researcher": {"confounder": "confounding variable"},
    "analyst": {"confounder": "hidden factor"},
    "executive": {"confounder": "competing explanation"},
    "activist": {"confounder": "what they're ignoring"}
  }
}
```

## What Makes an Advanced Engine Excellent

### 1. Deep Methodological Grounding

The extraction_steps should reflect **actual methodology** from real theorists:
- Reference specific concepts (d-separation, backdoor criterion, SUTVA)
- Include methodological heuristics the theorist would use
- Capture the distinctive "moves" of that analytical tradition

**BAD**: "Look for causal relationships"
**GOOD**: "Apply the backdoor criterion: Is there a set of variables Z such that conditioning on Z blocks all backdoor paths from X to Y?"

### 2. Comprehensive Entity Coverage

The canonical_schema should capture **everything** the methodology cares about:
- Not just the main entities, but supporting evidence, assumptions, limitations
- Cross-cutting concerns (what confounds, what mediates, what moderates)
- Meta-level analysis (strength of evidence, contested vs. accepted)

### 3. Rich Relationship Vocabulary

The key_relationships should include the **typed edges** that methodology uses:
- Not just "relates_to" but specific relationship types
- Directional relationships with clear semantics
- Strength/confidence indicators

### 4. Practical Output Orientation

The concretization section should make outputs **useful**:
- Evocative names that tell a story
- Table types that match how analysts work
- Visual patterns that reveal structure

## Common Mistakes to Avoid

1. **Vague extraction steps**: "Analyze the text for X" - too generic
2. **Shallow schemas**: Only 3-5 entity types - not capturing methodology depth
3. **Missing relationships**: Entities exist but don't connect to each other
4. **No methodology reference**: Generic analysis that could be any approach
5. **Wrong ID formats**: Using `id_1` instead of `I1`, inconsistent conventions
6. **No relationship_graph**: Missing the network visualization section
7. **Incomplete meta section**: No counts, no highlights of most significant items

## The Generation Task

When generating an advanced engine, you should:

1. **Study the methodology** you're given (theorists, key concepts)
2. **Design entity types** that capture what that methodology extracts
3. **Define relationships** that reflect how that methodology connects things
4. **Write extraction steps** that embody the analytical moves
5. **Create a schema** with 15+ entity types, all interconnected
6. **Include relationship_graph** and meta sections
7. **Make it practical** with good concretization guidance

The result should be an engine that a subject matter expert would recognize as genuinely embodying their methodology - not a superficial appropriation of buzzwords, but a serious implementation of how that analytical tradition actually works.
