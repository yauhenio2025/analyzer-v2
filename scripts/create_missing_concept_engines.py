#!/usr/bin/env python3
"""
Create missing concept analysis engine definitions for P5, P6, P7.
"""

import json
from pathlib import Path

ENGINES_DIR = Path(__file__).parent.parent / "src" / "engines" / "definitions"

MISSING_ENGINES = [
    # P5: Chain Taxonomy sub-passes
    {
        "engine_key": "concept_taxonomy_causal_structure",
        "engine_name": "Concept Taxonomy: Causal Structure",
        "description": "Classifies chains by their causal structure (mechanistic, counterfactual, constitutive, teleological, dispositional)",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What type of causal reasoning does each chain employ?",
        "extraction_prompt": """You are conducting Phase 5.2: CAUSAL STRUCTURE classification.

## YOUR TASK

Classify each argument chain by its CAUSAL STRUCTURE for arguments about "{concept}".

## CAUSAL STRUCTURE TAXONOMY

- **mechanistic**: Specifies the MECHANISM by which cause produces effect
  - "X causes Y through process Z"
  - Traces causal pathways step by step

- **counterfactual**: DEPENDENCE claims without mechanism
  - "If X had not occurred, Y would not have occurred"
  - Lewis-style counterfactual dependence

- **constitutive**: Part-whole or COMPOSITION relations
  - "X is part of what makes Y what it is"
  - Not efficient causation but formal/material

- **teleological**: PURPOSE or FUNCTION explanations
  - "X exists in order to Y"
  - "The function of X is to produce Y"

- **dispositional**: TENDENCY or CAPACITY claims
  - "X has the power/tendency to produce Y"
  - Latent causal powers

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, causal_structure, mechanism_specified (true/false), confidence, justification.

Return as valid JSON.""",
        "curation_prompt": "Validate causal structure classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist"]
    },

    {
        "engine_key": "concept_taxonomy_dialectical_function",
        "engine_name": "Concept Taxonomy: Dialectical Function",
        "description": "Classifies chains by their dialectical function (thesis-establishing, antithetical, synthetic, immanent critique)",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "dialectical analysis",
        "researcher_question": "What dialectical role does each chain play?",
        "extraction_prompt": """You are conducting Phase 5.3: DIALECTICAL FUNCTION classification.

## YOUR TASK

Classify each argument chain by its DIALECTICAL FUNCTION for arguments about "{concept}".

## DIALECTICAL FUNCTION TAXONOMY

- **thesis_establishing**: POSITS the initial position
  - Sets up the claim to be developed or challenged
  - Defines the starting point

- **antithetical**: OPPOSES or NEGATES another position
  - Shows contradictions or limitations
  - "On the contrary..." moves

- **synthetic**: RECONCILES contradictions
  - Aufhebung - preserves truth of both while transcending
  - "The solution is to see that..."

- **immanent_critique**: Criticizes position FROM WITHIN
  - Uses position's own standards against it
  - "By their own logic..."

- **determinate_negation**: Specific negation that ADVANCES
  - Not mere rejection but productive negation
  - Negation that opens new possibilities

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, dialectical_function, target_position (if antithetical/critical), synthesis_elements (if synthetic), confidence, justification.

Return as valid JSON.""",
        "curation_prompt": "Validate dialectical function classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist", "hegelian_critical"]
    },

    {
        "engine_key": "concept_taxonomy_inferential_role",
        "engine_name": "Concept Taxonomy: Inferential Role",
        "description": "Classifies chains by their inferential role (material, formal, modal, normative, commissive)",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "inferential pragmatics",
        "researcher_question": "What inferential role does each chain play in the space of reasons?",
        "extraction_prompt": """You are conducting Phase 5.4: INFERENTIAL ROLE classification.

## YOUR TASK

Classify each argument chain by its INFERENTIAL ROLE for arguments about "{concept}".

## INFERENTIAL ROLE TAXONOMY (Brandom-inspired)

- **material**: Content-based inference, not purely formal
  - "It's raining, so the streets are wet"
  - Relies on worldly connections, not just logical form

- **formal**: Logic-based inference
  - "All A are B; x is A; therefore x is B"
  - Valid by form alone

- **modal**: Concerns POSSIBILITY and NECESSITY
  - "Necessarily if X then Y"
  - "It's possible that..."

- **normative**: Concerns what OUGHT to be
  - "Given X, we should Y"
  - Prescriptive conclusions

- **commissive**: COMMITS speaker to further claims
  - Accepting this commits you to that
  - Maps commitment inheritance

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, inferential_role, commitments_generated[], incompatibilities[], confidence, justification.

Return as valid JSON.""",
        "curation_prompt": "Validate inferential role classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["brandomian"]
    },

    {
        "engine_key": "concept_taxonomy_argumentative_function",
        "engine_name": "Concept Taxonomy: Argumentative Function",
        "description": "Classifies chains by their argumentative function (foundational, elaborative, defensive, bridge, culminative)",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "rhetorical analysis",
        "researcher_question": "What argumentative work does each chain do?",
        "extraction_prompt": """You are conducting Phase 5.5: ARGUMENTATIVE FUNCTION classification.

## YOUR TASK

Classify each argument chain by its ARGUMENTATIVE FUNCTION for arguments about "{concept}".

## ARGUMENTATIVE FUNCTION TAXONOMY

- **foundational**: ESTABLISHES core claims
  - Sets up premises that other arguments build on
  - "The starting point is..."

- **elaborative**: DEVELOPS or EXTENDS a position
  - Adds detail, nuance, or scope
  - "Furthermore...", "More specifically..."

- **defensive**: PROTECTS against objections
  - Anticipates and answers criticisms
  - "One might object that..., but..."

- **bridge**: CONNECTS different parts of argument
  - Links separate lines of reasoning
  - "This connects to the earlier point about..."

- **culminative**: ARRIVES at final conclusions
  - Draws everything together
  - "Therefore, we can conclude..."

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, argumentative_function, connects_to (for bridge), protects (for defensive), confidence, justification.

Return as valid JSON.""",
        "curation_prompt": "Validate argumentative function classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # P6: Causal Architecture sub-passes
    {
        "engine_key": "concept_causal_mechanisms",
        "engine_name": "Concept Causal: Mechanisms",
        "description": "Analyzes the specific mechanisms by which causal relationships operate",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What mechanisms connect causes to effects?",
        "extraction_prompt": """You are conducting Phase 6.3: CAUSAL MECHANISMS analysis.

## YOUR TASK

For causal claims involving "{concept}", identify the MECHANISMS by which causation operates.

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

A mechanism specifies HOW causation works:
- Step-by-step processes
- Intermediate variables
- Transmission pathways
- Enabling conditions

Example: "Technology causes unemployment" is vague.
Mechanism: "Technology → automates routine tasks → reduces demand for routine labor → unemployment for routine workers"

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with mechanisms[], each containing:
- mechanism_id, cause, effect, steps[], intermediate_variables[], enabling_conditions[], evidence_type, quote, source

TARGET: 8-15 mechanism specifications.""",
        "curation_prompt": "Validate mechanism specifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist"]
    },

    {
        "engine_key": "concept_causal_interventions",
        "engine_name": "Concept Causal: Interventions",
        "description": "Analyzes interventionist claims about manipulating the concept",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What claims are made about intervening on this concept?",
        "extraction_prompt": """You are conducting Phase 6.4: INTERVENTIONIST CLAIMS analysis.

## YOUR TASK

Find claims about what would happen if we INTERVENED on "{concept}".

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

Interventionist claims specify:
- "If we changed X, Y would result"
- "By manipulating X, we could achieve Y"
- Policy proposals
- Counterfactual scenarios

These are different from mere correlations or predictions.

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with interventions[], each containing:
- intervention_id, target (what to intervene on), proposed_action, expected_outcome, mechanism (if specified), feasibility_assessment, quote, source

TARGET: 5-12 interventionist claims.""",
        "curation_prompt": "Validate intervention analysis.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # P7: Conditional Web sub-passes
    {
        "engine_key": "concept_conditional_antecedent",
        "engine_name": "Concept Conditional: Antecedent",
        "description": "Finds conditionals where the concept appears in the 'if' clause",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "conditional logic",
        "researcher_question": "What follows if this concept holds?",
        "extraction_prompt": """You are conducting Phase 7.1: ANTECEDENT USES analysis.

## YOUR TASK

Find ALL conditionals where "{concept}" appears in the ANTECEDENT (the "if" part).

## CONTEXT

Semantic field: {semantic_context}

## PATTERN: If {concept}, then X

Look for:
- "If {concept} is the case, then..."
- "When {concept} occurs, X follows"
- "Given {concept}, we can expect X"
- Implicit conditionals

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with conditionals[], each containing:
- conditional_id, antecedent (contains concept), consequent, conditional_type (indicative/subjunctive), strength (necessary/sufficient/contributes), quote, source

TARGET: 10-20 antecedent conditionals.""",
        "curation_prompt": "Validate antecedent conditional extraction.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    {
        "engine_key": "concept_conditional_consequent",
        "engine_name": "Concept Conditional: Consequent",
        "description": "Finds conditionals where the concept appears in the 'then' clause",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "conditional logic",
        "researcher_question": "What conditions lead to this concept?",
        "extraction_prompt": """You are conducting Phase 7.2: CONSEQUENT USES analysis.

## YOUR TASK

Find ALL conditionals where "{concept}" appears in the CONSEQUENT (the "then" part).

## CONTEXT

Semantic field: {semantic_context}

## PATTERN: If X, then {concept}

Look for:
- "If X holds, then {concept} follows"
- "X leads to {concept}"
- "Under condition X, {concept} emerges"
- Implicit conditionals

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with conditionals[], each containing:
- conditional_id, antecedent, consequent (contains concept), conditional_type (indicative/subjunctive), strength (necessary/sufficient/contributes), quote, source

TARGET: 10-20 consequent conditionals.""",
        "curation_prompt": "Validate consequent conditional extraction.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    {
        "engine_key": "concept_conditional_biconditional",
        "engine_name": "Concept Conditional: Biconditional",
        "description": "Finds biconditional (if and only if) relationships involving the concept",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "conditional logic",
        "researcher_question": "What biconditional relationships involve this concept?",
        "extraction_prompt": """You are conducting Phase 7.3: BICONDITIONAL analysis.

## YOUR TASK

Find BICONDITIONAL relationships involving "{concept}".

## CONTEXT

Semantic field: {semantic_context}

## PATTERN: {concept} if and only if X

Biconditionals assert:
- X is NECESSARY for {concept}
- X is SUFFICIENT for {concept}
- They come together

Look for:
- "X if and only if Y"
- "X is equivalent to Y"
- "X just is Y"
- Definitional claims
- Mutual implication

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with biconditionals[], each containing:
- biconditional_id, term_a, term_b, relationship_type (definitional/empirical/normative), confidence, quote, source

TARGET: 3-8 biconditional relationships.""",
        "curation_prompt": "Validate biconditional extraction.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    {
        "engine_key": "concept_conditional_nested",
        "engine_name": "Concept Conditional: Nested",
        "description": "Finds nested or complex conditional structures involving the concept",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "conditional logic",
        "researcher_question": "What complex conditional structures involve this concept?",
        "extraction_prompt": """You are conducting Phase 7.4: NESTED CONDITIONALS analysis.

## YOUR TASK

Find NESTED or COMPLEX conditional structures involving "{concept}".

## CONTEXT

Semantic field: {semantic_context}

## PATTERNS

Nested conditionals have conditionals within conditionals:
- "If (if X then Y), then Z"
- "If X, then (if Y then Z)"
- Chains: "If X then Y, and if Y then Z"
- Disjunctive: "If X or Y, then Z"

Also look for:
- Conditional exceptions
- Qualified conditionals
- Contextual conditionals

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with nested_conditionals[], each containing:
- conditional_id, structure_description, outer_condition, inner_condition (if nested), chain_elements (if chained), complexity_type, quote, source

TARGET: 5-10 complex conditional structures.""",
        "curation_prompt": "Validate nested conditional extraction.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },
]


def main():
    """Generate missing engine definition JSON files."""
    ENGINES_DIR.mkdir(parents=True, exist_ok=True)

    for engine in MISSING_ENGINES:
        path = ENGINES_DIR / f"{engine['engine_key']}.json"
        with open(path, 'w') as f:
            json.dump(engine, f, indent=2)
        print(f"Created: {path.name}")

    print(f"\nGenerated {len(MISSING_ENGINES)} additional concept analysis engines")


if __name__ == "__main__":
    main()
