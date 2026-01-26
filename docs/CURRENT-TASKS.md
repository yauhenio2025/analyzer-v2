# Current Tasks - Analyzer Disaggregation Project

> Tasks actively in progress. Check this file at session start to continue pending work.

## Project Context

**Goal**: Extract pure analytical definitions into Analyzer v2 (lightweight service), while current Analyzer keeps all process/rendering code.

**Why "Reversed Approach"**:
- Instead of moving ~35K lines of renderers/process FROM Analyzer TO Visualizer
- We extract ~10-15K lines of clean definitions OUT of Analyzer into this new service
- Current Analyzer keeps working unchanged during transition
- Consumers (Critic, Visualizer, IE) call Analyzer v2 for definitions

**Architecture**:
```
┌─────────────────────────────────────────────────────────────────┐
│                     ANALYZER v2 (THIS SERVICE)                  │
│           https://analyzer-v2.onrender.com                      │
│                                                                 │
│  • 123 Engine Definitions (prompts, schemas) ✓                  │
│  • 4 Paradigm Definitions (IE 4-layer ontology) ✓               │
│  • 19 Engine Chains (pipeline specs) ✓                          │
│  • API: GET /v1/engines, /v1/paradigms, /v1/chains              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Fetch definitions (Phase 4)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              CURRENT ANALYZER (to be wired)                      │
│              /home/evgeny/projects/analyzer                      │
│                                                                 │
│  • Pipeline orchestration (extraction → curation → rendering)   │
│  • Renderers (Gemini, tables, reports, mermaid, d3)             │
│  • Job management, caching                                       │
│                                                                 │
│  Will call Analyzer v2 API for engine prompts/schemas           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Completed Work

### Phase 1: Create Analyzer v2 Service ✓
- **Status**: COMPLETE
- **Files Created**:
  - `src/engines/schemas.py` - EngineDefinition Pydantic model
  - `src/engines/registry.py` - EngineRegistry loads from JSON
  - `src/engines/definitions/*.json` - 123 engine definitions extracted
  - `src/paradigms/schemas.py` - ParadigmDefinition with 4-layer ontology
  - `src/paradigms/registry.py` - ParadigmRegistry + primer generation
  - `src/chains/schemas.py` - EngineChainSpec model
  - `src/chains/registry.py` - ChainRegistry
  - `src/api/main.py` - FastAPI app
  - `src/api/routes/{engines,paradigms,chains}.py` - API routes
- **Deployed**: https://analyzer-v2.onrender.com
- **GitHub**: https://github.com/yauhenio2025/analyzer-v2

### Phase 2: Add Paradigms ✓
- **Status**: COMPLETE
- **Completed**:
  - `src/paradigms/instances/marxist.json` - Ported from IE mockParadigmData.js
  - `src/paradigms/instances/brandomian.json` - New, for inferential analysis
  - `src/paradigms/instances/hegelian_critical.json` - Rose, Adorno, Hegel
  - `src/paradigms/instances/pragmatist_praxis.json` - Márkus, Joas, Dewey
  - 12 engines linked to paradigms via paradigm_keys

---

## Phase 3: Expand Engine Chains ✓

### Task: Create Chain Definitions ✓
- **Status**: COMPLETE
- **Description**: Created 19 engine chains covering all major analysis categories
- **Chains Created**:
  - `concept_analysis_suite` - Concept centrality, evolution, affordances (llm_selection)
  - `critical_analysis_chain` - Argument + epistemology + power analysis (sequential)
  - `argument_analysis_chain` - Logical architecture, assumptions, fallacies (llm_selection)
  - `power_politics_chain` - Stakeholders, capture, resource flows (llm_selection)
  - `epistemological_critique_chain` - Certainty, profundity, calibration (parallel)
  - `methodology_critique_chain` - Confounds, bias, replication (llm_selection)
  - `systems_thinking_chain` - Feedback loops, emergence, leverage (sequential)
  - `historical_temporal_chain` - Timelines, cycles, path dependency (llm_selection)
  - `rhetorical_analysis_chain` - Persuasion, amplification, metaphors (llm_selection)
  - `evidence_quality_chain` - Data quality, triangulation, provenance (sequential)
  - `scholarly_debate_chain` - Citations, genealogy, paradigm conflicts (llm_selection)
  - `institutional_analysis_chain` - Principal-agent, bureaucracy, capture (llm_selection)
  - `philosophical_foundations_chain` - Conditions, absent centers (sequential)
  - `strategic_forecasting_chain` - Scenarios, early warning, escalation (sequential)
  - `economic_financial_chain` - Financial flows, market positioning (llm_selection)
  - `causal_mechanism_chain` - Causality, counterfactuals (sequential)
  - `trend_emergence_chain` - Trends, anomalies, gaps (parallel)
  - `comparative_synthesis_chain` - Thematic synthesis, cross-cultural (sequential)
  - `adversarial_stress_test_chain` - Robustness, boundary probing (sequential)

### Task: Implement LLM Chain Recommendation
- **Status**: DEFERRED
- **Description**: Replace placeholder in `/v1/chains/recommend` with actual LLM call
- **Notes**: Current implementation returns heuristic match, sufficient for now

---

## Phase 4: Wire Current Analyzer to v2 ✓

### Task: Add Analyzer v2 Client ✓
- **Status**: COMPLETE
- **Files Created** in `/home/evgeny/projects/analyzer`:
  - `src/clients/__init__.py` - Package exports
  - `src/clients/analyzer_v2.py` - Full async httpx client with:
    - In-memory cache with TTL (24h default)
    - Automatic retry on transient failures (tenacity)
    - Graceful degradation - never breaks pipeline
    - Support for all prompt types + paradigms + schemas

### Task: Add Caching Layer ✓
- **Status**: COMPLETE
- **Implementation**: In-memory cache with TTL (simpler, sufficient)
- **Location**: `src/clients/analyzer_v2.py` - `CacheEntry` class

### Task: Modify Prompt Loading ✓
- **Status**: COMPLETE
- **Key Changes**:
  - `src/core/extraction.py` - v2 client is priority 1
  - `src/core/curation.py` - v2 client is priority 1
- **Config**: `config/settings.py` - Added `analyzer_v2_*` settings

Prompt resolution priority is now:
1. Analyzer v2 (remote definitions service)
2. Database prompts
3. Hardcoded engine prompts

### Task: Optional Rename
- **Status**: DEFERRED
- **Description**: Rename current Analyzer → "Renderer" or "Executor"
- **Notes**: Cosmetic, can do later or skip

---

## Phase 5: Consumer Integration ✓

### Task: Critic Integration
- **Status**: SKIPPED (project doesn't exist)
- **Notes**: `/home/evgeny/projects/critic` does not exist

### Task: Visualizer MCP Integration ✓
- **Status**: COMPLETE
- **Location**: `/home/evgeny/projects/visualizer/mcp_server/mcp_server.py`
- **Changes**:
  - Added `paradigm_key` parameter to `analyze()` tool
  - Paradigm key passed to Analyzer in context
  - Paradigm primer injected into extraction and curation prompts

### Task: Analyzer Backend Integration ✓
- **Status**: COMPLETE
- **Location**: `/home/evgeny/projects/analyzer`
- **Changes**:
  - `src/core/schemas.py` - Added `paradigm_key` to `AnalysisContext`
  - `src/core/extraction.py` - Injects paradigm primer into extraction
  - `src/core/curation.py` - Injects paradigm primer into curation

### Task: IE API Client ✓
- **Status**: COMPLETE
- **Location**: `/home/evgeny/projects/ie/ie/src/services/analyzerV2Client.ts`
- **Features**:
  - `fetchParadigms()` - Get all paradigm summaries
  - `fetchParadigm(key)` - Get full 4-layer ontology
  - `fetchParadigmPrimer(key)` - Get LLM-ready primer
  - `convertToIEFormat()` - Bridge v2 → IE format
  - `fetchParadigmsForIE()` - Fetch + convert in one call

---

## Implementation Order

1. **Phase 2** - Complete paradigms (current session)
   - Add hegelian_critical.json
   - Add pragmatist_praxis.json
   - Link engines to paradigms
   - Push to GitHub (auto-deploys to Render)

2. **Phase 4** - Wire current Analyzer
   - Add v2 client with caching
   - Modify prompt loading
   - Test thoroughly

3. **Phase 5** - Consumer integration
   - Critic adapter
   - Visualizer MCP paradigm support
   - IE coordination

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/paradigms/instances/marxist.json` | Reference for paradigm structure |
| `src/paradigms/schemas.py` | Pydantic models for 4-layer ontology |
| `src/engines/definitions/*.json` | Engine definitions to update with paradigm_keys |
| `/home/evgeny/projects/ie/ie/src/data/mockParadigmData.js` | IE paradigm data source |
| `/home/evgeny/projects/analyzer/src/engines/base.py` | Current Analyzer engine base class |
