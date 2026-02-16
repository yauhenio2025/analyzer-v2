# Plain Text Architecture: Why Schemas Are Mostly Unnecessary

> Date: 2026-02-16
> Status: Architectural exploration / proposal
> Builds on: `docs/refactoring_engines.md`
> Core question: What if we save intermediate LLM responses as plain text and only generate structured data at presentation time?

---

## The Insight

If the only consumer of structured data is the UI at the moment of presentation, and everything upstream — pass-to-pass, engine-to-engine, analysis-to-visualization — works better with natural text, then **we don't need schemas at all** for the analytical pipeline. We need them only at the edges, when a human is looking at something.

---

## Who Consumes Engine Output?

| Consumer | Needs structured data? | Why / Why not |
|---|---|---|
| **Next LLM pass** (deeper analysis) | **No.** | LLMs read text better than JSON. Feeding pass 1's prose output into pass 2 is literally what LLMs are best at. |
| **Gemini visualization** | **No.** | Gemini generates images from text descriptions. You give it "here are the power dynamics I found..." and it draws. No schema needed. |
| **Textual memo / report** | **No.** | This IS text. Asking an LLM to produce structured JSON and then converting it back to prose is a pointless round-trip. |
| **Another engine** (shared context) | **No.** | The consuming LLM can read the producing engine's text output directly. It doesn't need to parse JSON fields. |
| **UI table / interactive component** | **Yes.** | Rendering a sortable table or a filterable graph requires structured data -- but only at the moment of rendering. |
| **Search / filter across analyses** | **Partially.** | "Show me all analyses where Foucault was identified as a key thinker" needs some structure. But it could be as simple as an LLM extracting that metadata on demand. |

**The only consumer that genuinely needs structured data is the UI, and only at the moment of presentation.** Everything upstream works better with natural text.

---

## The Minimal Schema: A Flat Text Archive with Lineage

```
analysis_outputs (the only table needed)
--------------------------------------------
id              UUID
job_id          UUID (groups related passes)
engine_key      TEXT
pass_number     INT
role            TEXT (extraction / synthesis /
                     critique / visualization)
content         TEXT (the actual LLM output)
token_count     INT
model_used      TEXT
created_at      TIMESTAMP
parent_id       UUID (which output fed this)
document_ids    TEXT[] (source documents)
metadata        JSONB (loose bag for tags,
                      difficulty score, etc)
```

That's it. Every LLM output -- whether it's a conditions_of_possibility extraction, a cross-engine synthesis, or a critique -- is just a row of text with minimal bookkeeping metadata.

The `parent_id` creates a tree: pass 1 output -> pass 2 output -> synthesis -> visualization prompt. You can trace the full analytical lineage without any canonical schema.

---

## Why Plain Text Is Actually Better

### 1. LLMs read prose better than JSON

When pass 2 needs to build on pass 1's findings, which is more useful?

**Structured (current approach -- force output then re-serialize):**
```json
{
  "epistemic_conditions": [
    {
      "condition_id": "EC1",
      "name": "Post-structuralist epistemology",
      "description": "The availability of...",
      "enabling_factors": ["factor1", "factor2"],
      "temporal_range": "1960s-1980s"
    }
  ]
}
```

**Plain text (proposed -- let the LLM think freely):**
```
The most critical epistemic condition was the availability of
post-structuralist epistemology in French academic circles of the
1960s-80s. Without Saussure's linguistic turn having already
destabilized the referential theory of meaning, Foucault's
archaeological method would have been literally unthinkable.
This created a cascade: once you could treat "knowledge" as a
system of signs rather than a mirror of reality, it became
possible to ask what RULES governed that system...
```

The second version is richer, more nuanced, preserves the analytical reasoning, and is exactly what the next LLM pass needs to go deeper. The first version is a lossy compression of the second.

### 2. Schema-on-read, not schema-on-write

When you DO need structure (for a UI table, for a specific visualization), you ask an LLM to extract it at that moment:

```
"Here is an analysis of conditions of possibility.
 Extract the key actors as a JSON array with fields:
 name, role, institution, relationship_to_phenomenon."
```

This is **schema-on-read** -- the structure is determined by the consumer's needs at consumption time, not by the producer's guess at production time. This is fundamentally more flexible because:

- Different consumers want different structures from the same analysis
- The visualizer wants a network graph -> extract nodes and edges
- The critic wants a vulnerability matrix -> extract claims and evidence gaps
- A textual memo wants nothing -- the text IS the output

### 3. Eliminate the 17-26% quality degradation

If the LLM doesn't have to simultaneously think deeply AND format its output into a 690-line schema, it can devote its full reasoning capacity to the analysis itself. Research is clear: forcing structured output costs analytical quality (arXiv 2408.02442, OpenReview CHI 2025). Plain text is the LLM's native output mode.

### 4. Cross-engine context sharing becomes trivial

Currently, for engine B to use engine A's output, you'd need to parse A's schema, extract relevant fields, and reformat them for B's input. With plain text:

```
"Previous analysis from Conditions of Possibility engine:

[paste the text output]

Now, as the Power-Knowledge Nexus engine, deepen the analysis
of the power dynamics identified above..."
```

No schema translation. No field mapping. The LLM reads the prose and picks up exactly what's relevant.

### 5. Visualization doesn't need pre-structured data either

**For Gemini image generation:**
```
"Based on this analysis, create a network diagram showing
the relationships between epistemic conditions, institutional
actors, and discursive formations..."
[paste analysis text]
```

**For smart tables** (the one case where you do need structure), you ask an LLM to extract tabular data from the analysis text at render time. The table schema is determined by what the USER wants to see, not by what the engine pre-decided.

---

## What You Lose (and Why It's Mostly Fine)

1. **Deterministic UI rendering** -- You can't pre-build a "conditions_of_possibility viewer" component because you don't know the shape. But if we're already proposing LLM-generated UI, this is moot.

2. **Cross-run comparability** -- If you analyze two documents with the same engine, the outputs might be structured differently. But is that actually a problem? Different documents surface different conditions. Forcing identical structure across different documents is the same false uniformity that makes standardized tests bad at measuring intelligence.

3. **Programmatic querying** -- You can't `SELECT * FROM analysis WHERE epistemic_conditions.temporal_range > '1960'`. But you could do `SELECT content FROM analysis_outputs WHERE engine_key = 'conditions_of_possibility'` and then ask an LLM "which of these mention conditions from the 1960s?" -- which is more flexible and handles edge cases better.

---

## The Resulting Architecture

```
Document -> Orchestrator LLM plans passes
                |
         Pass 1: Engine A analyzes -> save text to DB
                |
         Pass 2: Engine B analyzes (reading A's text) -> save text to DB
                |
         Pass 3: Synthesis across engines -> save text to DB
                |
         User requests visualization ->
           LLM reads relevant texts ->
           generates structured data for THAT specific UI need ->
           renders (or Gemini generates image)
```

No canonical schemas. No schema migration when you refine an engine. No "does power_knowledge_nexus output match what conditions_of_possibility expects as input?" The LLMs handle all the translation, because that's what they're good at.

The database becomes a **text archive with lineage tracking**, not a structured data warehouse. And engine definitions become pure intellectual descriptions -- the problematique, the analytical dimensions, the depth levels -- with zero concern for output format.

---

## The Hybrid Nuance: Two Places Where Structure Lives

1. **The shallow flat schema** -- the `analysis_outputs` table with job_id, engine_key, pass_number, content, parent_id. Just enough to organize and retrieve.

2. **Presentation-time schemas** -- when the UI needs a table or interactive component, the rendering LLM extracts structured data from the text. These schemas are ephemeral, consumer-defined, and never stored (or stored only as a cache).

Everything else is text. The 690-line canonical schemas, the stage_context extraction steps, the curation consolidation rules -- these all dissolve into the engine's intellectual description, which the LLM uses as guidance for HOW to think, not a mold for the output shape.

---

## Key Principle

> **Schema-on-read, not schema-on-write.**
> Save the richest possible output (prose), and extract structure only when a specific consumer needs it, in the shape that consumer needs.
> The analytical pipeline is text-in, text-out. Structure is a presentation concern.
