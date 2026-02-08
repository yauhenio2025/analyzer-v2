# Claude's Reasoning for competing_explanations_analyzer_advanced

Generated: 2026-01-31T12:13:04.243537

---

Let me create a comprehensive advanced engine definition for the Competing Explanations Analyzer that deeply embodies ACH (Analysis of Competing Hypotheses) methodology and Structured Analytic Techniques.

First, let me think through the key components:

## Key Methodology Elements from ACH:

1. **Hypothesis Generation** - generating all plausible hypotheses upfront
2. **Evidence Cataloging** - listing all relevant evidence
3. **Diagnosticity** - identifying which evidence discriminates between hypotheses
4. **Consistency Matrix** - the core ACH matrix showing hypothesis vs evidence
5. **Disconfirming Evidence** - weighting evidence that disconfirms
6. **Linchpin Assumptions** - assumptions that if wrong would change everything
7. **Sensitivity Analysis** - how conclusions change if assumptions are wrong
8. **Cognitive Biases** - confirmation bias, anchoring, availability, satisficing, premature closure

## Entity Types I Need (15+):

1. **Hypotheses** (H{N}) - the competing explanations
2. **Evidence Items** (E{N}) - individual pieces of evidence
3. **Consistency Assessments** (CA{N}) - how evidence relates to each hypothesis
4. **Linchpin Assumptions** (LA{N}) - critical assumptions underlying hypotheses
5. **Diagnostic Evidence** (DE{N}) - evidence that discriminates between hypotheses
6. **Information Gaps** (GAP{N}) - missing information that would be diagnostic
7. **Cognitive Biases Detected** (BIAS{N}) - instances of cognitive bias
8. **Source Assessments** (SA{N}) - credibility of evidence sources
9. **Likelihood Estimates** (LE{N}) - probability assessments
10. **Sensitivity Points** (SP{N}) - where conclusions are sensitive to assumptions
11. **Argument Chains** (AC{N}) - reasoning chains from evidence to hypothesis
12. **Counter-Indicators** (CI{N}) - evidence against hypotheses


13. **Anchor Points** (AP{N}) - initial estimates that may bias analysis
14. **Alternative Scenarios** (AS{N}) - alternative futures or developments
15. **Analytic Conclusions** (CON{N}) - final assessments
16. **Deception Indicators** (DI{N}) - signs of deliberate deception
17. **Confidence Calibration** (CC{N}) - confidence level assessments
18. **Refutation Evidence** (RE{N}) - evidence that would definitively disprove

Now I'll structure the full engine definition with these entity types integrated throughout.

```json
{
  "engine_key": "competing_explanations_analyzer_advanced",
  "engine_name": "Competing Explanations Analyzer (Advanced)",
  "description": "Applies Heuer's Analysis of Competing Hypotheses and CIA Structured Analytic Techniques to systematically evaluate rival explanations. Surfaces confirmation bias, isolates truly discriminating evidence, identifies critical assumptions, and tests which hypotheses withstand disconfirmation. Incorporates Bayesian logic to assess evidence weight and calibrate confidence levels.",
  "version": 1,
  "category": "methodology",
  "kind": "synthesis",
  "reasoning_domain": "hypothesis_evaluation_advanced",
  "researcher_question": "What plausible explanations exist, which evidence meaningfully distinguishes between them, and which hypothesis remains most consistent with the full evidence base?",
  "canonical_schema": {
    "hypotheses": [...],
    "evidence_

items": [...],
    ...
  },
  "stage_context": {...}
}
```