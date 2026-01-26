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
│  • Paradigm Definitions (IE 4-layer ontology) - 2 of 4 done     │
│  • Engine chains / pipeline specs ✓                             │
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

### Phase 2 (Partial): Add Paradigms
- **Status**: IN_PROGRESS
- **Completed**:
  - `src/paradigms/instances/marxist.json` - Ported from IE mockParadigmData.js
  - `src/paradigms/instances/brandomian.json` - New, for inferential analysis
- **Remaining**: See task below

---

## Phase 2: Complete Paradigms (IN PROGRESS)

### Task: Add Hegelian Critical Paradigm
- **Status**: PENDING
- **Description**: Create `src/paradigms/instances/hegelian_critical.json` based on Gillian Rose, Adorno, and critical theory tradition
- **Key Elements**:
  - Guiding thinkers: Gillian Rose, Theodor Adorno, Hegel
  - Focus: Determinate negation, broken middle, speculative identity
  - 4-layer ontology structure matching marxist.json format
- **Reference**: Look at IE mockParadigmData.js for Foucauldian paradigm structure as additional example

### Task: Add Pragmatist Praxis Paradigm
- **Status**: PENDING
- **Description**: Create `src/paradigms/instances/pragmatist_praxis.json` based on György Márkus, Hans Joas, and pragmatist tradition
- **Key Elements**:
  - Guiding thinkers: György Márkus, Hans Joas, John Dewey
  - Focus: Technical normativity, creative action, practice theory
  - Critique of reification of communicative sphere
- **Reference**: Márkus's "Language and Production" for technical normativity concepts

### Task: Link Engines to Paradigms
- **Status**: PENDING
- **Description**: Update engine JSON files to include `paradigm_keys` field
- **Files to Modify**:
  - `src/engines/definitions/dialectical_structure.json` → add `["marxist", "hegelian_critical"]`
  - `src/engines/definitions/inferential_commitment_mapper*.json` → add `["brandomian"]`
  - `src/engines/definitions/reification_detector.json` → add `["marxist", "pragmatist_praxis"]`
  - Review all 123 engines for paradigm associations

---

## Phase 3: Expand Engine Chains (DEFERRED)

### Task: Create More Chain Definitions
- **Status**: DEFERRED
- **Description**: Add chains for argument analysis, evidence synthesis, etc.
- **Notes**: Skip for now, can add incrementally as needed

### Task: Implement LLM Chain Recommendation
- **Status**: DEFERRED
- **Description**: Replace placeholder in `/v1/chains/recommend` with actual LLM call
- **Notes**: Current implementation returns heuristic match, sufficient for now

---

## Phase 4: Wire Current Analyzer to v2 (PENDING)

### Task: Add Analyzer v2 Client
- **Status**: PENDING
- **Description**: Add httpx client to current Analyzer that fetches prompts from v2
- **Files to Create/Modify** in `/home/evgeny/projects/analyzer`:
  - `src/clients/analyzer_v2.py` - New client class
  - Add to `src/core/config.py`:
    ```python
    ANALYZER_V2_URL = os.getenv("ANALYZER_V2_URL", "https://analyzer-v2.onrender.com")
    ```

### Task: Add Caching Layer
- **Status**: PENDING
- **Description**: Cache engine definitions locally to avoid hitting v2 API every request
- **Implementation Options**:
  1. In-memory cache with TTL (simple)
  2. Redis cache (if already using Redis)
  3. File-based cache with periodic refresh

### Task: Modify Prompt Loading
- **Status**: PENDING
- **Description**: Change engine classes to fetch prompts from v2 instead of local
- **Key Changes**:
  - `src/engines/base.py` - Add `get_prompt_from_v2()` method
  - Or: Create adapter that wraps v2 definitions as engine classes
- **Test**: Verify current Analyzer works identically with prompts from v2

### Task: Optional Rename
- **Status**: PENDING (LOW PRIORITY)
- **Description**: Rename current Analyzer → "Renderer" or "Executor"
- **Notes**: Cosmetic, can do later or skip

---

## Phase 5: Consumer Integration (PENDING)

### Task: Critic Integration
- **Status**: PENDING
- **Description**: Add adapter to Critic that uses Analyzer v2 engine definitions
- **Location**: `/home/evgeny/projects/critic` (if exists)

### Task: Visualizer MCP Integration
- **Status**: PENDING
- **Description**: Add paradigm-aware analysis options to Visualizer MCP
- **Location**: `/home/evgeny/projects/visualizer`
- **Changes**:
  - Add paradigm selection to analysis requests
  - Fetch paradigm primer from v2 and inject into prompts

### Task: IE Shared Paradigm Library
- **Status**: PENDING
- **Description**: Consider sharing paradigm definitions between IE and Analyzer v2
- **Location**: `/home/evgeny/projects/ie`
- **Options**:
  1. IE calls Analyzer v2 API for paradigms
  2. Extract paradigms to shared npm/pip package
  3. Keep separate, sync manually

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
