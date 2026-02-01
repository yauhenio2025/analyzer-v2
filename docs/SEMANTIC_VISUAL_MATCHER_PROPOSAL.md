# Proposal: Semantic Visual Matcher

> Bridging the gap between analytical meaning and visual form

## Problem Statement

Current visualizations are "fancy tables" - they organize information but don't truly **visualize the analytical meaning**. A Feedback Loop analysis shows a generic radial diagram instead of actual loops. A Dialectical Structure analysis shows category blobs instead of thesis-antithesis-synthesis movement.

**Root cause**: The Output Curator selects visualization types based on **data structure** (nodes/edges → network_graph) rather than **semantic intent** (feedback loops → cycle diagrams with reinforcement indicators).

## Current Architecture

```
Analyzer-v2                          Visualizer
┌─────────────────┐                  ┌─────────────────────────┐
│ Engine Definition │                  │ Output Curator          │
│ - canonical_schema│                  │ - Analyzes DATA STRUCTURE│
│ - recommended_    │  ──(unused)──>  │ - Maps to generic formats│
│   visual_patterns │                  │ - Generates Gemini prompt│
│   (136/156 EMPTY) │                  │   (structural, not      │
└─────────────────┘                  │    semantic)            │
                                     └─────────────────────────┘
```

**The disconnect**: `recommended_visual_patterns` exists but is:
1. Empty for 87% of engines
2. Not passed to or used by the Visualizer's Output Curator

## Proposed Architecture

```
Analyzer-v2                          Visualizer
┌─────────────────┐                  ┌─────────────────────────┐
│ Engine Definition │                  │ Semantic Visual Matcher │
│ - semantic_visual │  ──────────>   │ - Receives engine hints │
│   _intent         │   via API      │ - Understands MEANING   │
│ - visual_grammar  │                  │ - Selects form for      │
│ - gemini_templates│                  │   semantic content      │
└─────────────────┘                  │ - Uses rich templates   │
                                     └─────────────────────────┘
```

---

## Part 1: Semantic Visual Intent (Analyzer-v2)

### New Fields in Engine Definitions

Replace the underused `recommended_visual_patterns` with a richer specification:

```json
{
  "stage_context": {
    "concretization": {
      "semantic_visual_intent": {
        "primary_concept": "feedback_dynamics",
        "visual_grammar": {
          "core_metaphor": "cycles_and_loops",
          "key_visual_elements": [
            "circular_arrows_showing_feedback",
            "reinforcing_vs_balancing_indicators",
            "causal_direction_markers",
            "loop_strength_encoding"
          ],
          "anti_patterns": [
            "generic_radial_layout",
            "static_category_wheels",
            "undirected_blob_maps"
          ]
        },
        "gemini_semantic_prompt": "This analysis reveals FEEDBACK LOOPS - self-reinforcing and self-correcting cycles in a system. Visualize the CYCLICAL NATURE: show arrows that loop back, use visual weight to indicate loop strength, distinguish reinforcing loops (that amplify) from balancing loops (that stabilize). Do NOT create a static category diagram - the essence is DYNAMIC CAUSALITY.",
        "recommended_forms": [
          {
            "form": "causal_loop_diagram",
            "when": "showing reinforcing/balancing dynamics",
            "gemini_guidance": "Draw actual loops with arrows. Use + for reinforcing links, - for balancing. Show the cycle direction clearly."
          },
          {
            "form": "system_dynamics_stock_flow",
            "when": "showing accumulation and rates",
            "gemini_guidance": "Boxes for stocks (things that accumulate), pipes for flows, clouds for sources/sinks."
          },
          {
            "form": "feedback_network",
            "when": "complex multi-loop systems",
            "gemini_guidance": "Network where edges have direction AND polarity. Highlight dominant loops. Color-code reinforcing vs balancing."
          }
        ]
      }
    }
  }
}
```

### Semantic Concept Vocabulary

Define a controlled vocabulary of analytical concepts and their visual grammars:

| Semantic Concept | Visual Grammar | Key Visual Elements | Anti-Patterns |
|-----------------|----------------|---------------------|---------------|
| `feedback_dynamics` | Cycles, loops | Circular arrows, R/B indicators, causal direction | Static radials, category wheels |
| `dialectical_movement` | Transformation, tension resolution | Thesis→Antithesis→Synthesis flow, contradiction markers | Generic network, blob positioning |
| `power_asymmetry` | Imbalance, flow direction | Weighted edges, size encoding, directionality | Symmetric layouts, equal-sized nodes |
| `temporal_evolution` | Change over time | Timeline, phase transitions, before/after | Atemporal snapshots |
| `hierarchical_dependency` | Tree structure, levels | Root→leaf direction, depth encoding | Flat networks |
| `inferential_chain` | Logical flow | Premise→conclusion arrows, commitment dependencies | Unordered lists |
| `contested_territory` | Opposition, conflict | Force diagrams, tug-of-war, camp separation | Neutral positioning |

---

## Part 2: Visual Form Library (Visualizer)

### New Visual Forms Beyond Generic Types

Current forms are too generic. Add semantically-rich alternatives:

#### For Feedback/Causal Analysis
```
causal_loop_diagram       - Actual loops with R/B polarity markers
stock_flow_diagram        - System dynamics notation (boxes, pipes, clouds)
leverage_point_map        - Donella Meadows-style intervention points
feedback_strength_matrix  - Which loops dominate under what conditions
```

#### For Dialectical/Conflict Analysis
```
dialectical_spiral        - Thesis→Antithesis→Synthesis ascending movement
contradiction_force_field - Opposing forces with resolution vectors
sublation_diagram         - How contradictions are preserved-and-overcome
position_evolution_flow   - How positions transform through engagement
```

#### For Inferential/Logical Analysis
```
commitment_cascade        - Domino-style: accept X → committed to Y → stuck with Z
inference_tree            - Premise structure with support/attack edges
entailment_network        - What follows from what, with strength indicators
logical_geography         - Conceptual space with distance = inferential distance
```

#### For Power/Resource Analysis
```
asymmetry_flow            - Sankey-like but emphasizing imbalance
extraction_diagram        - Center-periphery with direction arrows
power_topology            - Who can affect whom (directed, weighted)
resource_accumulation     - Stock piles with flow rates
```

---

## Part 3: Semantic Matcher Implementation

### New Module: `semantic_matcher.py`

```python
"""
Semantic Visual Matcher

Bridges analytical meaning to visual form by understanding
the SEMANTIC INTENT of analysis, not just data structure.
"""

class SemanticVisualMatcher:
    """
    Matches analytical content to appropriate visual forms
    based on semantic understanding, not just data structure.
    """

    def __init__(self):
        self.concept_registry = load_concept_vocabulary()
        self.form_library = load_visual_forms()

    def match(
        self,
        engine_key: str,
        semantic_intent: dict,  # From engine definition
        extracted_data: dict,
        audience: str,
    ) -> VisualFormRecommendation:
        """
        Select visual form based on SEMANTIC MEANING.

        Unlike the current curator which asks:
        "What data structure is this?" → generic format

        This matcher asks:
        "What analytical concept does this represent?" → semantic form
        """

        # 1. Get the semantic concept from engine's intent
        primary_concept = semantic_intent.get("primary_concept")
        visual_grammar = semantic_intent.get("visual_grammar", {})

        # 2. Check what the analysis actually found
        content_signals = self._analyze_content_signals(extracted_data)

        # 3. Match concept + content to appropriate form
        form = self._select_form(
            concept=primary_concept,
            grammar=visual_grammar,
            content=content_signals,
            audience=audience,
        )

        # 4. Generate semantically-aware Gemini prompt
        gemini_prompt = self._build_semantic_prompt(
            form=form,
            semantic_intent=semantic_intent,
            data=extracted_data,
        )

        return VisualFormRecommendation(
            form=form,
            gemini_prompt=gemini_prompt,
            semantic_rationale=f"This {primary_concept} analysis calls for {form.name} to show {visual_grammar.get('core_metaphor')}"
        )

    def _analyze_content_signals(self, data: dict) -> ContentSignals:
        """
        Detect what the content is actually about.

        Not just "has nodes and edges" but:
        - Are there cycles? → feedback visualization
        - Are there opposing positions? → dialectical visualization
        - Are there temporal phases? → evolution visualization
        - Are there power asymmetries? → imbalance visualization
        """
        signals = ContentSignals()

        # Detect cycles in relationship graph
        if graph := data.get("relationship_graph"):
            signals.has_cycles = self._detect_cycles(graph)
            signals.has_hierarchy = self._detect_hierarchy(graph)
            signals.has_opposing_clusters = self._detect_opposition(graph)

        # Detect temporal dimension
        if any(k in data for k in ["evolution", "phases", "timeline", "stages"]):
            signals.has_temporal = True

        # Detect power/resource asymmetry
        if flows := data.get("flows") or data.get("resource_flows"):
            signals.has_asymmetry = self._detect_asymmetry(flows)

        return signals

    def _build_semantic_prompt(
        self,
        form: VisualForm,
        semantic_intent: dict,
        data: dict,
    ) -> str:
        """
        Build Gemini prompt that encodes SEMANTIC MEANING.

        Not: "Create a network graph with nodes and edges"
        But: "Visualize these FEEDBACK LOOPS - show the cyclical
             causality, indicate which loops reinforce vs balance,
             make the dynamic nature visible"
        """

        # Start with the semantic framing
        prompt = semantic_intent.get("gemini_semantic_prompt", "")

        # Add form-specific guidance
        form_guidance = form.gemini_template

        # Add the actual data
        data_section = self._format_data_for_prompt(data)

        # Add anti-patterns to avoid
        anti_patterns = semantic_intent.get("visual_grammar", {}).get("anti_patterns", [])
        if anti_patterns:
            prompt += f"\n\nDO NOT create: {', '.join(anti_patterns)}"

        return f"""
{prompt}

VISUAL FORM: {form.name}
{form_guidance}

DATA TO VISUALIZE:
{data_section}

Remember: The goal is to make the {semantic_intent.get('primary_concept')} VISIBLE -
not just to organize information, but to reveal the underlying dynamics.
"""
```

### Integration with Output Curator

Modify `output_curator.py` to use semantic matching when available:

```python
def curate(self, engine_key, extracted_data, audience, context):
    # NEW: Fetch semantic intent from analyzer-v2
    semantic_intent = self._fetch_semantic_intent(engine_key)

    if semantic_intent and semantic_intent.get("primary_concept"):
        # Use semantic matcher for engines with rich visual intent
        return self.semantic_matcher.match(
            engine_key=engine_key,
            semantic_intent=semantic_intent,
            extracted_data=extracted_data,
            audience=audience,
        )
    else:
        # Fall back to structure-based curation for basic engines
        return self._structure_based_curate(...)

def _fetch_semantic_intent(self, engine_key: str) -> dict:
    """Fetch semantic visual intent from analyzer-v2 API."""
    try:
        response = requests.get(
            f"{ANALYZER_V2_URL}/v1/engines/{engine_key}/stage-context"
        )
        if response.ok:
            stage_context = response.json()
            return stage_context.get("concretization", {}).get("semantic_visual_intent", {})
    except Exception as e:
        logger.warning(f"Could not fetch semantic intent for {engine_key}: {e}")
    return {}
```

---

## Part 4: Implementation Roadmap

### Phase 1: Define Semantic Vocabulary (Analyzer-v2)

1. **Create semantic concept taxonomy** - 15-20 core analytical concepts
2. **Define visual grammar for each** - metaphors, elements, anti-patterns
3. **Write Gemini semantic prompts** - meaning-focused, not structure-focused

**Engines to start with** (highest value):
- `feedback_loop_mapper` → feedback_dynamics
- `dialectical_structure` → dialectical_movement
- `inferential_commitment_mapper` → inferential_chain
- `power_asymmetry_analyzer` → power_asymmetry
- `causal_inference_auditor` → causal_reasoning

### Phase 2: Enrich Engine Definitions (Analyzer-v2)

1. **Add `semantic_visual_intent`** to the 14 v2 advanced engines first
2. **Replace empty `recommended_visual_patterns`** with rich specifications
3. **Add API endpoint** to serve semantic intent: `GET /v1/engines/{key}/visual-intent`

### Phase 3: Implement Semantic Matcher (Visualizer)

1. **Create `semantic_matcher.py`** module
2. **Add visual form library** with semantically-rich forms
3. **Integrate with output curator** - semantic first, structure fallback
4. **Create Gemini prompt templates** that encode meaning

### Phase 4: Test and Iterate

1. **Re-run Buchanan analysis** with semantic matcher
2. **Compare outputs** - do visualizations now show actual feedback loops?
3. **Iterate on prompts** - refine based on Gemini's interpretation
4. **Expand to more engines** based on results

---

## Example: Feedback Loop Mapper Before/After

### BEFORE (Current)
```
Data: {nodes: [...], edges: [...]}
Curator: "Has nodes and edges → network_graph"
Gemini prompt: "Create a network visualization with these nodes and edges..."
Result: Generic radial diagram with concepts arranged in a circle
```

### AFTER (Semantic Matcher)
```
Semantic Intent: {
  primary_concept: "feedback_dynamics",
  visual_grammar: {
    core_metaphor: "cycles_and_loops",
    key_elements: ["circular_arrows", "R/B_indicators", "causal_direction"]
  },
  gemini_semantic_prompt: "Visualize FEEDBACK LOOPS - self-reinforcing and
    self-correcting cycles. Show the CYCLICAL NATURE with arrows that loop back..."
}

Matcher: "This is feedback analysis → causal_loop_diagram"
Gemini prompt: "This analysis reveals FEEDBACK LOOPS in Buchanan's constitutional
  economics. Visualize the cyclical causality:
  - Draw actual LOOPS with arrows showing direction
  - Mark reinforcing loops with R+ (amplifying effects)
  - Mark balancing loops with B- (stabilizing effects)
  - Show which loops DOMINATE the system

  DO NOT create a static category wheel or generic network.
  The essence is DYNAMIC CAUSALITY - make the loops VISIBLE."

Result: Actual causal loop diagram showing reinforcing/balancing feedback cycles
```

---

## Success Criteria

1. **Feedback Loop Mapper** produces visualizations with actual visible loops
2. **Dialectical Structure** shows thesis→antithesis→synthesis movement
3. **Inferential Commitment Mapper** shows commitment cascades and logical dependencies
4. **Visual forms match analytical meaning**, not just data structure
5. **Reduction in "fancy table" outputs** - more genuine visualizations

---

## Open Questions

1. **How much guidance can Gemini absorb?** Need to test prompt length limits
2. **Should we pre-render some forms?** Or always generate via Gemini?
3. **How to handle engines without semantic intent?** Graceful fallback to structure-based
4. **Version control for visual forms?** As we learn what works, how to track/iterate

---

## Next Steps

1. Review this proposal
2. Start with 3-5 engines to prove the concept
3. Implement semantic intent schema in analyzer-v2
4. Build semantic matcher module in visualizer
5. Test with Buchanan corpus
6. Iterate based on results

