# Refactoring Engines: From Fixed Schemas to Capability-Driven Architecture

> Date: 2026-02-16
> Status: Architectural exploration / proposal
> Context: Discussion about whether engines should define WHAT they investigate (the problematique) rather than HOW (fixed schemas, passes, UI)

---

## The Diagnosis: What's Wrong with the Current Approach

Looking at `conditions_of_possibility`, the current architecture treats it as a **prompt template with a pre-baked schema** -- 690 lines of JSON specifying exactly 13 entity types, 8 relationship types, and a fixed 3-stage pipeline (extract -> curate -> concretize). The mgmt UI reinforces this: it presents the engine as a "profile page + prompt factory."

But this engine is actually something far richer -- it's a **Foucauldian archaeological lens** with a deep intellectual identity. Forcing it into a fixed schema is like handing someone a questionnaire when what they need is a conversation.

Research confirms this worry. **"Let Me Speak Freely?" (arXiv 2408.02442)** and a CHI 2025 study show that forcing rigid structured output degrades LLM analytical quality by **17-26%**. The more complex the schema, the worse the degradation. A 690-line canonical schema for conditions_of_possibility may be actively harming the depth of analysis.

---

## Research Validation

### 1. Define WHAT, not HOW -- Capability-Based Architecture

Google Cloud's 2025 agent design patterns and Salesforce's enterprise agentic architecture both advocate defining agents by **capabilities** (what they can investigate) rather than procedures (how they execute). CrewAI's model of "role + goal + backstory" maps directly to the engine concept: the engine's definition IS its backstory (Foucauldian archaeology, conditions that make something thinkable), the goal is the analytical question, and the LLM fills in the how.

### 2. LLM as Planner -- Plan-and-Execute Separation

**LLMCompiler** (arXiv 2312.04511) and **AOP** (VLDB/CIDR 2025) both prove that separating planning from execution produces better results than having the LLM do both at once:

```
Document arrives
    |
[Planner LLM] reads document + available engine capabilities
    |
Generates execution DAG:
  - Which engines to activate (capability matching)
  - How many passes, in what order (dependency graph)
  - What depth per engine (difficulty-aware)
  - What output structure (loose guidance, not rigid schema)
    |
[Executor] runs engines per DAG
  - Each engine gets: investigative intent + document + shared context
  - Each engine returns: flexibly structured output
  - Context broker accumulates and shares findings
    |
[Synthesizer/UI Generator] merges, visualizes
```

### 3. Shared Context Across Engines -- The Microsoft Pattern

Microsoft's unified Agent Framework (AutoGen + Semantic Kernel, 2025) uses **shared memory** where agents operate over the same state. If `conditions_of_possibility` and `power_knowledge_nexus` and `discursive_formation_mapper` all run on the same document, the first engine's extraction of "key actors and institutions" should be visible to the others -- no redundant re-extraction.

The recommended pattern is **metadata-only context passing** -- shared context carries references and summaries, not full payloads.

### 4. Dynamic Schema at Runtime -- It's Production-Ready

**XGrammar 2** (NVIDIA/CMU, 2025) enables runtime schema switching at ~250 microseconds per token -- the LLM can dynamically select which output grammar to use based on what it's finding. **BAML Dynamic Types** (BoundaryML) lets you load schemas from a database at runtime. The infrastructure for "LLM decides the schema" is mature.

### 5. Adaptive UI Generation -- Google Proved It

**Google's Generative UI** (2025) showed that Gemini can generate entire interactive interfaces dynamically -- HTML/CSS/JS from prompts. Human raters "strongly preferred" it over standard text output. **Vercel AI SDK** provides the React integration pattern: LLM streams structured output, components are selected/generated based on the structure.

---

## Critical Warning: Hybrid, Not Pure LLM

The research is unanimous: **hybrid approaches beat pure LLM approaches every time.**

- **Prompt2DAG** (IEEE 2025): Pure LLM pipeline generation succeeds ~60% of the time. Hybrid (LLM + template guardrails) achieves 78.5%.
- **AOP**: Mixes "standard operators" (pre-programmed) with "semantic operators" (LLM-executed). Neither alone is sufficient.
- **Ontology research**: LLM-generated ontologies drift across runs unless anchored to a reference structure.

So the answer isn't "throw away all schemas and let the LLM figure it out." It's:

**Define the analytical DIMENSIONS (what to look for) richly and precisely, but let the LLM determine the granularity, nesting, specific fields, number of passes, and visualization based on what it actually finds in the document.**

---

## Proposed Engine Definition Format

```yaml
engine_key: conditions_of_possibility
name: Conditions of Possibility Mapper

# THE WHAT -- richly specified
problematique: |
  What had to be true -- epistemically, institutionally, materially,
  discursively -- for these ideas to become thinkable and these
  practices possible? What conditions enabled this particular
  configuration of knowledge/power, and what alternatives were
  thereby foreclosed?

intellectual_lineage:
  primary: foucault
  traditions: [archaeology, genealogy, critical_theory]
  key_concepts: [episteme, dispositif, discursive_formation, apparatus]

analytical_dimensions:  # NOT a schema -- dimensions to explore
  - epistemic_conditions: "What knowledge structures had to exist"
  - institutional_conditions: "What institutions enabled/constrained"
  - material_conditions: "What technologies/infrastructure were necessary"
  - discursive_conditions: "What could and couldn't be said"
  - power_knowledge_nexus: "How knowledge and power reinforced each other"
  - exclusions: "What was made unthinkable, who was silenced"
  - ruptures: "Where did discontinuities appear"
  - subject_positions: "What kinds of subjects were constituted"

# CAPABILITIES -- what this engine CAN do
capabilities:
  - identify_conditions: "Map the conditions that enabled a phenomenon"
  - trace_exclusions: "Identify what was foreclosed or silenced"
  - map_apparatus: "Reconstruct the heterogeneous ensemble"
  - detect_ruptures: "Find epistemic breaks and discontinuities"

# COMPOSABILITY -- how it plays with others
shares_with:  # dimensions other engines can consume
  - actors_and_institutions  # power_knowledge_nexus can use these
  - temporal_markers          # any temporal engine can use these
  - discursive_rules          # discursive_formation_mapper needs these
consumes_from:  # dimensions it benefits from receiving
  - conceptual_framework      # from conceptual_framework_extraction
  - key_commitments           # from inferential_commitment_mapper

# DEPTH GUIDANCE -- not fixed passes, but depth levels
depth_levels:
  surface: "Identify obvious conditions (1 pass)"
  standard: "Map conditions + exclusions + apparatus (2-3 passes)"
  deep: "Full archaeological analysis with cross-document patterns (4-6 passes)"
```

## The Mega-Orchestrator LLM Would:

1. **Read the document** and assess its complexity/richness
2. **Select relevant engines** based on capability matching
3. **Determine depth** per engine (surface/standard/deep) based on document difficulty
4. **Plan shared context**: "conditions_of_possibility and power_knowledge_nexus both need actors -- extract once, share"
5. **Generate execution DAG**: which engines run in what order, with what pass count
6. **For each pass**: compose the prompt using the engine's problematique + analytical dimensions + shared context -- but NOT force a rigid schema
7. **After all passes**: synthesize, then generate appropriate UI (graph? table? narrative? depends on what was found)

### Tools for the Orchestrator:

- **Advanced UI Builder** -- can generate visualization components on the fly
- **Advanced DB Manager/Saver** -- can create appropriate storage schema on the fly
- **Engine Capability Catalog** -- the rich descriptions of what each engine investigates
- **Shared Context Broker** -- reads/writes shared findings

---

## The Investment Shift

| Before (Current) | After (Proposed) |
|---|---|
| Over-specify schemas (690 lines of JSON) | Over-specify the problematique (rich intellectual description) |
| Fixed 3-stage pipeline | LLM-determined pass structure |
| Fixed canonical schema | LLM-determined output structure |
| Pre-built UI components per output mode | LLM-generated UI per analysis result |
| Sequential chains only | DAG-based parallel/sequential execution |
| Each engine re-extracts everything | Shared context broker, extract once |
| Same depth regardless of document | Difficulty-aware adaptive depth |

**Invest in the WHAT (analytical depth of engine descriptions). LLMs handle the HOW (schemas, passes, UI, composition).**

---

## Risk Mitigation

The research warns about three failure modes to plan for:

1. **Ontology drift** -- LLM generates subtly incompatible output structures across runs. Mitigation: anchor to the analytical_dimensions as a reference vocabulary, even if the LLM decides the nesting/granularity.

2. **Planning failure (~20%)** -- Pure LLM planning fails on some documents. Mitigation: keep current fixed chains as fallback modes. If the orchestrator's plan looks weird, fall back to the known-good pipeline.

3. **Debugging opacity** -- When the LLM decides everything dynamically, it's hard to reproduce issues. Mitigation: aggressive logging of the orchestrator's plan + the actual execution.

---

## Sources

- [XGrammar 2: Dynamic Structured Generation](https://arxiv.org/abs/2601.04426)
- [BAML Dynamic Types](https://docs.boundaryml.com/guide/baml-advanced/dynamic-types)
- [LLM-Supported Collaborative Ontology Design](https://www.frontiersin.org/journals/big-data/articles/10.3389/fdata.2025.1676477/full)
- [Google: Generative UI](https://research.google/blog/generative-ui-a-rich-custom-visual-interactive-user-experience-for-any-prompt/)
- [LLMCompiler](https://arxiv.org/pdf/2312.04511)
- [Plan-and-Execute Agents](https://blog.langchain.com/planning-agents/)
- [Prompt2DAG](https://arxiv.org/abs/2509.13487)
- [AOP: Automated Pipeline Orchestration](https://vldb.org/cidrdb/papers/2025/p32-wang.pdf)
- [DAAO: Difficulty-Aware Adaptive Orchestration](https://arxiv.org/abs/2509.11079)
- [Let Me Speak Freely? Format Restrictions Harm LLM Performance](https://arxiv.org/html/2408.02442v1)
- [Structured Output Degrades Creativity (OpenReview)](https://openreview.net/forum?id=vYkz5tzzjV)
- [Microsoft Agent Framework](https://devblogs.microsoft.com/semantic-kernel/microsofts-agentic-ai-frameworks-autogen-and-semantic-kernel/)
- [Multi-Agent Orchestration via Evolving Strategies](https://arxiv.org/abs/2505.19591)
- [Google Cloud Agent Design Patterns](https://docs.google.com/architecture/choose-design-pattern-agentic-ai-system)
- [Salesforce Enterprise Agentic Architecture](https://architect.salesforce.com/fundamentals/enterprise-agentic-architecture)
- [Multi-Agent LLM Systems: Structured Collective Intelligence](https://www.preprints.org/manuscript/202511.1370)
