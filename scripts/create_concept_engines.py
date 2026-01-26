#!/usr/bin/env python3
"""
Create concept analysis engine definitions for the 12-phase concept analyzer.

Run this to generate JSON files in src/engines/definitions/
"""

import json
from pathlib import Path

ENGINES_DIR = Path(__file__).parent.parent / "src" / "engines" / "definitions"

# Engine definitions with extraction_prompt templates
# Placeholders: {concept}, {documents_text}, {args_text}, {chains_text}, etc.

CONCEPT_ENGINES = [
    # Phase 1: Semantic Constellation
    {
        "engine_key": "concept_semantic_constellation",
        "engine_name": "Concept Semantic Constellation",
        "description": "Maps the semantic field of a concept: related terms, synonyms, boundaries, usage patterns",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "semantic analysis",
        "researcher_question": "What is the full semantic field of this concept?",
        "extraction_prompt": """You are conducting Phase 1 of a multi-pass conceptual analysis.

## YOUR TASK: SEMANTIC CONSTELLATION

Before we extract any arguments or claims about "{concept}", we need to understand its SEMANTIC FIELD.

Your goal is to map ALL terms that are semantically related to "{concept}" in the texts:
- Near-synonyms used interchangeably
- Related theoretical terms from the same tradition
- Broader/narrower terms (hypernyms/hyponyms)
- Evaluatively colored variants
- Terms that function as metonyms or stand-ins

## WHY THIS MATTERS

In political economy and critical theory, authors often use multiple terms for the same concept:
- "work" / "labor" / "activity" / "praxis" / "toil"
- "capitalism" / "bourgeois society" / "market society"
- "efficiency" / "productivity" / "rationalization"

If we don't map this semantic field FIRST, we'll miss arguments that use related terms.

## ANALYSIS TASKS

1. **Find ALL semantically related terms** used when discussing "{concept}"

2. **Classify each term's relationship** to the primary concept:
   - near_synonym: Almost identical meaning
   - theoretical_synonym: Same in specific theoretical framework
   - hypernym: More general category
   - hyponym: More specific instance
   - metonym: Part-whole or associated concept
   - evaluative_variant: Same concept with evaluative coloring
   - antonym: Opposite concept
   - complementary: Paired concept

3. **Document author usage patterns**:
   - Which phrasings are preferred?
   - When do they switch between terms?
   - What theoretical register is used?

4. **Map concept boundaries**:
   - What clearly falls UNDER this concept?
   - What is explicitly EXCLUDED?
   - What cases are CONTESTED or ambiguous?

## DOCUMENTS

{documents_text}

## REMINDER

You are ONLY mapping the semantic field of "{concept}".
Do NOT yet extract arguments or make analytical claims.
Just map the TERMS and their RELATIONSHIPS.

Return your analysis as valid JSON.""",
        "curation_prompt": "Validate and enhance the semantic constellation mapping.",
        "canonical_schema": {
            "type": "object",
            "properties": {
                "primary_term": {"type": "string"},
                "semantic_equivalents": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term": {"type": "string"},
                            "relationship": {"type": "string"},
                            "usage_contexts": {"type": "array", "items": {"type": "string"}},
                            "frequency": {"type": "string"},
                            "notes": {"type": "string"}
                        }
                    }
                },
                "author_usage_patterns": {"type": "object"},
                "concept_boundaries": {"type": "object"},
                "semantic_field_summary": {"type": "string"},
                "key_collocations": {"type": "array", "items": {"type": "string"}},
                "theoretical_lineage": {"type": "string"}
            }
        },
        "paradigm_keys": ["marxist", "brandomian"]
    },

    # Phase 2: Structural Landscape
    {
        "engine_key": "concept_structural_landscape",
        "engine_name": "Concept Structural Landscape",
        "description": "Maps the argumentative terrain where a concept appears: sections, clusters, argumentative arc",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "structural analysis",
        "researcher_question": "Where and how does this concept appear in the argumentative structure?",
        "extraction_prompt": """You are conducting Phase 2 of a multi-pass conceptual analysis.

## YOUR TASK: STRUCTURAL LANDSCAPE

Map the ARGUMENTATIVE TERRAIN where "{concept}" appears.

## CONTEXT: SEMANTIC FIELD FROM PHASE 1

{semantic_context}

Use this to catch ALL occurrences, including synonyms and related terms.

## ANALYSIS TASKS

1. **Section Mapping**: Where does "{concept}" appear?
   - In which documents/sections?
   - In what argumentative contexts?
   - How prominently?

2. **Cluster Identification**: Group related passages
   - What distinct argumentative clusters use this concept?
   - What is each cluster's role?

3. **Arc Tracing**: How does the concept evolve?
   - How does treatment differ between documents?
   - Is there development or contradiction?

4. **Strategic Positioning**: Why is it placed here?
   - What argumentative work does it do?
   - What comes before/after?

## DOCUMENTS

{documents_text}

Return your analysis as valid JSON with sections: concept_locations, argumentative_clusters, cross_document_arc, strategic_positioning.""",
        "curation_prompt": "Validate structural mapping and enhance cross-document analysis.",
        "canonical_schema": {
            "type": "object",
            "properties": {
                "concept_locations": {"type": "array"},
                "argumentative_clusters": {"type": "array"},
                "cross_document_arc": {"type": "object"},
                "strategic_positioning": {"type": "object"}
            }
        },
        "paradigm_keys": ["marxist"]
    },

    # Phase 3: Argument Formalization
    {
        "engine_key": "concept_argument_formalization",
        "engine_name": "Concept Argument Formalization",
        "description": "Extracts and formalizes arguments involving the target concept",
        "version": 1,
        "category": "concepts",
        "kind": "synthesis",
        "reasoning_domain": "argument extraction",
        "researcher_question": "What specific arguments are made about this concept?",
        "extraction_prompt": """You are conducting Phase 3 of a multi-pass conceptual analysis.

## YOUR TASK: ARGUMENT FORMALIZATION

Extract ALL arguments that involve "{concept}" from the current document.

## CONTEXT FROM PREVIOUS PHASES

Semantic field (catch synonyms): {semantic_context}
Structural landscape (where to look): {structural_context}

## WHAT COUNTS AS AN ARGUMENT

An argument is:
1. A CLAIM (conclusion) about "{concept}"
2. One or more PREMISES (reasons/evidence)
3. An INFERENTIAL LINK connecting them

## FOR EACH ARGUMENT

1. State the CONCLUSION clearly
2. List all PREMISES (stated and implied)
3. Identify the INFERENCE TYPE:
   - Deductive (conclusion follows necessarily)
   - Inductive (conclusion is probable)
   - Abductive (best explanation)
   - Normative (ought-claim from values)
   - Causal (effect from cause)

4. Note QUALIFICATIONS and SCOPE
5. Provide DIRECT QUOTES as evidence

## DOCUMENT TO ANALYZE: {document_name}

{document_text}

## OUTPUT FORMAT

Return JSON with array of arguments, each containing:
- argument_id, conclusion, premises[], inference_type, qualifications, quotes[], source

TARGET: 15-25 distinct arguments from this document.""",
        "curation_prompt": "Validate argument extraction and ensure logical formalization is correct.",
        "canonical_schema": {
            "type": "object",
            "properties": {
                "arguments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "argument_id": {"type": "string"},
                            "conclusion": {"type": "string"},
                            "premises": {"type": "array", "items": {"type": "string"}},
                            "inference_type": {"type": "string"},
                            "qualifications": {"type": "string"},
                            "quotes": {"type": "array"},
                            "source": {"type": "string"}
                        }
                    }
                }
            }
        },
        "paradigm_keys": ["brandomian"]
    },

    # Phase 4: Chain Building
    {
        "engine_key": "concept_chain_building",
        "engine_name": "Concept Chain Building",
        "description": "Groups arguments into inferential chains showing how conclusions build on each other",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "inferential structure",
        "researcher_question": "How do arguments connect into larger inferential chains?",
        "extraction_prompt": """You are conducting Phase 4 of a multi-pass conceptual analysis.

## YOUR TASK: CHAIN BUILDING

Group the extracted arguments about "{concept}" into INFERENTIAL CHAINS.

## WHAT IS AN INFERENTIAL CHAIN?

A chain shows how arguments BUILD ON EACH OTHER:
- Argument A's conclusion becomes Argument B's premise
- Or multiple arguments combine to support a higher-level claim
- Or arguments form a sequence of reasoning

## ARGUMENTS FROM PHASE 3

{arguments_json}

## FOR EACH CHAIN

1. Name the chain (its main thesis)
2. List arguments in INFERENTIAL ORDER
3. Show DEPENDENCY relationships
4. Identify the ULTIMATE CONCLUSION
5. Note any GAPS or WEAK LINKS

## OUTPUT FORMAT

Return JSON with:
- chains[]: array of chains, each with chain_id, thesis, argument_ids[], dependencies, ultimate_conclusion, weak_links[]
- orphan_arguments[]: arguments that don't fit chains
- master_structure: how chains relate to each other

TARGET: 5-15 distinct chains.""",
        "curation_prompt": "Validate chain structure and dependency relationships.",
        "canonical_schema": {
            "type": "object",
            "properties": {
                "chains": {"type": "array"},
                "orphan_arguments": {"type": "array"},
                "master_structure": {"type": "object"}
            }
        },
        "paradigm_keys": ["brandomian"]
    },

    # Phase 5 sub-passes: Taxonomy Classification
    {
        "engine_key": "concept_taxonomy_inferential_mode",
        "engine_name": "Concept Taxonomy: Inferential Mode",
        "description": "Classifies argument chains by their inferential mode (deductive, inductive, abductive, etc.)",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "logical classification",
        "researcher_question": "What type of inference does each chain employ?",
        "extraction_prompt": """You are conducting Phase 5.1: INFERENTIAL MODE classification.

## YOUR TASK

Classify each chain's PRIMARY INFERENTIAL MODE for arguments about "{concept}".

## INFERENTIAL MODES

1. **Deductive**: Conclusion follows NECESSARILY from premises
2. **Inductive**: Conclusion is PROBABLE given evidence
3. **Abductive**: Conclusion is BEST EXPLANATION
4. **Normative**: OUGHT-claim from values/principles
5. **Transcendental**: NECESSARY CONDITIONS for possibility
6. **Dialectical**: SYNTHESIS from contradictions
7. **Genealogical**: HISTORICAL EMERGENCE explains features

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain, provide: chain_id, primary_mode, secondary_mode, confidence, justification.

Return as valid JSON.""",
        "curation_prompt": "Validate inferential mode classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["brandomian"]
    },

    {
        "engine_key": "concept_taxonomy_strength",
        "engine_name": "Concept Taxonomy: Strength Assessment",
        "description": "Assesses the logical strength of argument chains",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "argument evaluation",
        "researcher_question": "How strong is each inferential chain?",
        "extraction_prompt": """You are conducting Phase 5.2: STRENGTH ASSESSMENT.

## YOUR TASK

Assess the LOGICAL STRENGTH of each chain about "{concept}".

## STRENGTH CRITERIA

- **Validity**: Do conclusions follow from premises?
- **Soundness**: Are premises true/defensible?
- **Completeness**: Are all necessary premises stated?
- **Coherence**: Is the chain internally consistent?

## CHAINS TO ASSESS

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, overall_strength (1-10), validity_score, soundness_score, completeness_score, coherence_score, weakest_link, justification.

Return as valid JSON.""",
        "curation_prompt": "Validate strength assessments.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    {
        "engine_key": "concept_taxonomy_function",
        "engine_name": "Concept Taxonomy: Argumentative Function",
        "description": "Identifies the argumentative function of each chain (establishing, defending, extending, etc.)",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "rhetorical analysis",
        "researcher_question": "What argumentative work does each chain do?",
        "extraction_prompt": """You are conducting Phase 5.3: ARGUMENTATIVE FUNCTION classification.

## YOUR TASK

Identify each chain's ARGUMENTATIVE FUNCTION for "{concept}".

## FUNCTIONS

1. **Establishing**: Introduces and defines the concept
2. **Defending**: Responds to objections/alternatives
3. **Extending**: Applies concept to new domains
4. **Limiting**: Specifies boundaries/exceptions
5. **Historicizing**: Places in historical context
6. **Politicizing**: Draws political implications

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, primary_function, secondary_function, target_audience, strategic_purpose.

Return as valid JSON.""",
        "curation_prompt": "Validate function classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    {
        "engine_key": "concept_taxonomy_theoretical_register",
        "engine_name": "Concept Taxonomy: Theoretical Register",
        "description": "Identifies the theoretical tradition each chain draws from",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "intellectual history",
        "researcher_question": "What theoretical tradition does each chain employ?",
        "extraction_prompt": """You are conducting Phase 5.4: THEORETICAL REGISTER classification.

## YOUR TASK

Identify each chain's THEORETICAL REGISTER for "{concept}".

## REGISTERS

1. **Classical Marxist**: Marx, Engels, value theory
2. **Post-Keynesian**: Demand, employment, instability
3. **Autonomist**: Labor refusal, composition, exodus
4. **Critical Theory**: Frankfurt School, dialectics
5. **Analytical Marxist**: Rational choice, game theory
6. **Liberal/Reformist**: Market corrections, redistribution

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, primary_register, secondary_register, key_references, tension_with_other_registers.

Return as valid JSON.""",
        "curation_prompt": "Validate theoretical register classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist"]
    },

    {
        "engine_key": "concept_taxonomy_epistemic_status",
        "engine_name": "Concept Taxonomy: Epistemic Status",
        "description": "Assesses the epistemic status of claims in each chain",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "epistemology",
        "researcher_question": "What is the epistemic status of each chain's claims?",
        "extraction_prompt": """You are conducting Phase 5.5: EPISTEMIC STATUS classification.

## YOUR TASK

Assess the EPISTEMIC STATUS of claims in each chain about "{concept}".

## EPISTEMIC CATEGORIES

1. **Empirical**: Claims about observable facts
2. **Theoretical**: Claims within a theoretical framework
3. **Normative**: Claims about what ought to be
4. **Definitional**: Claims about meaning/classification
5. **Historical**: Claims about past events
6. **Predictive**: Claims about future states

## CHAINS TO CLASSIFY

{chains_json}

## OUTPUT FORMAT

For each chain: chain_id, primary_status, supporting_evidence_type, falsifiability, certainty_level.

Return as valid JSON.""",
        "curation_prompt": "Validate epistemic status classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 6 sub-passes: Causal Architecture
    {
        "engine_key": "concept_causal_as_cause",
        "engine_name": "Concept Causal: As Cause",
        "description": "Analyzes where the concept is treated as a CAUSE of other phenomena",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What effects does this concept cause?",
        "extraction_prompt": """You are conducting Phase 6.1: CONCEPT AS CAUSE analysis.

## YOUR TASK

Find all places where "{concept}" is treated as a CAUSE of other phenomena.

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

- "{concept} leads to X"
- "{concept} produces X"
- "{concept} enables/prevents X"
- "Because of {concept}, X happens"

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with causal_claims[], each containing:
- claim_id, concept_role: "cause", effect, mechanism, evidence_type, confidence, quote, source

TARGET: 10-20 causal claims where concept is the cause.""",
        "curation_prompt": "Validate causal claims where concept is cause.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist"]
    },

    {
        "engine_key": "concept_causal_as_effect",
        "engine_name": "Concept Causal: As Effect",
        "description": "Analyzes where the concept is treated as an EFFECT of other factors",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What causes this concept to emerge or change?",
        "extraction_prompt": """You are conducting Phase 6.2: CONCEPT AS EFFECT analysis.

## YOUR TASK

Find all places where "{concept}" is treated as an EFFECT of other factors.

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

- "X leads to {concept}"
- "X produces {concept}"
- "{concept} results from X"
- "{concept} emerges due to X"

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with causal_claims[], each containing:
- claim_id, concept_role: "effect", cause, mechanism, evidence_type, confidence, quote, source

TARGET: 10-20 causal claims where concept is the effect.""",
        "curation_prompt": "Validate causal claims where concept is effect.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist"]
    },

    {
        "engine_key": "concept_causal_bidirectional",
        "engine_name": "Concept Causal: Bidirectional",
        "description": "Analyzes feedback loops and mutual causation involving the concept",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What feedback loops involve this concept?",
        "extraction_prompt": """You are conducting Phase 6.3: BIDIRECTIONAL CAUSATION analysis.

## YOUR TASK

Find FEEDBACK LOOPS and MUTUAL CAUSATION involving "{concept}".

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

- "{concept} and X reinforce each other"
- "X increases {concept}, which in turn increases X"
- Vicious/virtuous cycles
- Dialectical relationships

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with feedback_loops[], each containing:
- loop_id, elements[], direction (reinforcing/balancing), mechanism, stability, quote, source

TARGET: 5-10 feedback loops.""",
        "curation_prompt": "Validate feedback loop identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist"]
    },

    {
        "engine_key": "concept_causal_conditions",
        "engine_name": "Concept Causal: Necessary/Sufficient Conditions",
        "description": "Identifies necessary and sufficient conditions for the concept",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "causal analysis",
        "researcher_question": "What are the necessary/sufficient conditions for this concept?",
        "extraction_prompt": """You are conducting Phase 6.4: CONDITIONS analysis.

## YOUR TASK

Find NECESSARY and SUFFICIENT CONDITIONS for "{concept}".

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

NECESSARY: "Without X, {concept} cannot exist"
SUFFICIENT: "If X, then necessarily {concept}"
CONTRIBUTING: "X makes {concept} more likely"

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with conditions[], each containing:
- condition_id, condition_type (necessary/sufficient/contributing), condition_description, justification, quote, source

TARGET: 10-15 conditions.""",
        "curation_prompt": "Validate condition identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 7: Conditional Web
    {
        "engine_key": "concept_conditional_web",
        "engine_name": "Concept Conditional Web",
        "description": "Extracts if-then relationships involving the concept",
        "version": 1,
        "category": "concepts",
        "kind": "relational",
        "reasoning_domain": "conditional logic",
        "researcher_question": "What conditional relationships involve this concept?",
        "extraction_prompt": """You are conducting Phase 7: CONDITIONAL WEB analysis.

## YOUR TASK

Extract ALL if-then relationships involving "{concept}".

## CONTEXT

Semantic field: {semantic_context}

## WHAT TO LOOK FOR

- "If {concept}, then X"
- "If X, then {concept}"
- "Only if X, {concept}"
- "Unless X, not {concept}"
- Counterfactuals: "If {concept} had been different..."

## DOCUMENTS

{documents_text}

## OUTPUT FORMAT

Return JSON with conditionals[], each containing:
- conditional_id, antecedent, consequent, type (indicative/counterfactual/normative), scope, confidence, quote, source

Also include: conditional_clusters[] grouping related conditionals.

TARGET: 15-25 conditional relationships.""",
        "curation_prompt": "Validate conditional extraction and typing.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 8: Argumentative Weight
    {
        "engine_key": "concept_argumentative_weight",
        "engine_name": "Concept Argumentative Weight",
        "description": "Classifies arguments by their importance (load-bearing, supporting, peripheral)",
        "version": 1,
        "category": "concepts",
        "kind": "synthesis",
        "reasoning_domain": "argument evaluation",
        "researcher_question": "Which arguments are most important to the overall thesis?",
        "extraction_prompt": """You are conducting Phase 8: ARGUMENTATIVE WEIGHT analysis.

## YOUR TASK

Classify each argument about "{concept}" by its IMPORTANCE to the overall thesis.

## WEIGHT CATEGORIES

1. **LOAD-BEARING**: Remove this and the thesis collapses
2. **SUPPORTING**: Strengthens thesis but not essential
3. **ILLUSTRATIVE**: Provides examples, not logical support
4. **DEFENSIVE**: Responds to objections
5. **PERIPHERAL**: Tangential to main thesis

## ARGUMENTS AND CHAINS

{arguments_json}

{chains_json}

## OUTPUT FORMAT

For each argument: argument_id, weight_class, justification, dependency_count, if_removed_impact.

Also provide: thesis_core_arguments[], most_vulnerable_arguments[].

Return as valid JSON.""",
        "curation_prompt": "Validate weight classifications.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 9 sub-passes: Vulnerability Analysis
    {
        "engine_key": "concept_vulnerability_unstated_premises",
        "engine_name": "Concept Vulnerability: Unstated Premises",
        "description": "Finds arguments that rely on hidden assumptions",
        "version": 1,
        "category": "concepts",
        "kind": "critique",
        "reasoning_domain": "argument analysis",
        "researcher_question": "What hidden assumptions do these arguments rely on?",
        "extraction_prompt": """You are conducting Phase 9.1: UNSTATED PREMISES vulnerability analysis.

## YOUR TASK

Find arguments about "{concept}" that rely on HIDDEN ASSUMPTIONS.

## WHAT TO LOOK FOR

An unstated premise is an assumption that:
- Is REQUIRED for the argument to work
- Is NOT explicitly stated
- COULD BE CHALLENGED

Examples:
- Assuming capitalism is the only alternative
- Assuming human nature is fixed
- Assuming efficiency metrics are valid

## ARGUMENTS TO ANALYZE

{args_text}

## CHAINS FOR CONTEXT

{chains_text}

## OUTPUT FORMAT

Return JSON with vulnerabilities[], each containing:
- vulnerability_id, vulnerability_type: "unstated_premise", argument_id, chain_id, description, hidden_assumption, potential_challenge, severity, quote, source

TARGET: 5-10 vulnerabilities.""",
        "curation_prompt": "Validate unstated premise identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["brandomian"]
    },

    {
        "engine_key": "concept_vulnerability_inferential_gaps",
        "engine_name": "Concept Vulnerability: Inferential Gaps",
        "description": "Finds places where conclusions don't follow from premises",
        "version": 1,
        "category": "concepts",
        "kind": "critique",
        "reasoning_domain": "argument analysis",
        "researcher_question": "Where are there logical leaps in the reasoning?",
        "extraction_prompt": """You are conducting Phase 9.2: INFERENTIAL GAPS vulnerability analysis.

## YOUR TASK

Find places where conclusions about "{concept}" don't clearly FOLLOW from premises.

## WHAT TO LOOK FOR

An inferential gap is where:
- The CONCLUSION is asserted
- The PREMISES don't fully support it
- There's a LEAP in the reasoning

Examples:
- Going from "X is bad" to "therefore we should do Y" (why Y?)
- Going from specific cases to universal claims
- Going from correlation to causation

## ARGUMENTS TO ANALYZE

{args_text}

## CHAINS FOR CONTEXT

{chains_text}

## OUTPUT FORMAT

Return JSON with vulnerabilities[], each containing:
- vulnerability_id, vulnerability_type: "inferential_gap", argument_id, chain_id, description, missing_link, gap_type, severity, quote, source

TARGET: 5-10 vulnerabilities.""",
        "curation_prompt": "Validate inferential gap identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["brandomian"]
    },

    {
        "engine_key": "concept_vulnerability_equivocations",
        "engine_name": "Concept Vulnerability: Equivocations",
        "description": "Finds arguments where key terms shift meaning",
        "version": 1,
        "category": "concepts",
        "kind": "critique",
        "reasoning_domain": "semantic analysis",
        "researcher_question": "Where do key terms shift meaning within arguments?",
        "extraction_prompt": """You are conducting Phase 9.3: EQUIVOCATIONS vulnerability analysis.

## YOUR TASK

Find arguments about "{concept}" where KEY TERMS SHIFT MEANING.

## WHAT TO LOOK FOR

An equivocation is where:
- A term is used with MULTIPLE MEANINGS
- The argument's validity DEPENDS on the ambiguity
- Switching meanings would BREAK the argument

## ARGUMENTS TO ANALYZE

{args_text}

## OUTPUT FORMAT

Return JSON with vulnerabilities[], each containing:
- vulnerability_id, vulnerability_type: "equivocation", argument_id, term_that_shifts, meaning_1, meaning_2, where_shift_occurs, severity, quote, source

TARGET: 3-7 vulnerabilities.""",
        "curation_prompt": "Validate equivocation identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["brandomian"]
    },

    {
        "engine_key": "concept_vulnerability_question_begging",
        "engine_name": "Concept Vulnerability: Question Begging",
        "description": "Finds circular reasoning where conclusion is assumed in premises",
        "version": 1,
        "category": "concepts",
        "kind": "critique",
        "reasoning_domain": "argument analysis",
        "researcher_question": "Where is circular reasoning present?",
        "extraction_prompt": """You are conducting Phase 9.4: QUESTION BEGGING vulnerability analysis.

## YOUR TASK

Find arguments about "{concept}" with CIRCULAR REASONING.

## WHAT TO LOOK FOR

Question-begging is where:
- The CONCLUSION is assumed in a PREMISE
- The argument is circular
- It appears to prove something but doesn't

## ARGUMENTS TO ANALYZE

{args_text}

## CHAINS FOR CONTEXT

{chains_text}

## OUTPUT FORMAT

Return JSON with vulnerabilities[], each containing:
- vulnerability_id, vulnerability_type: "question_begging", argument_id, chain_id, description, how_circular, restated_without_circularity, severity, quote, source

TARGET: 3-5 vulnerabilities.""",
        "curation_prompt": "Validate question-begging identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["brandomian"]
    },

    {
        "engine_key": "concept_vulnerability_false_dichotomies",
        "engine_name": "Concept Vulnerability: False Dichotomies",
        "description": "Finds arguments that present false either/or choices",
        "version": 1,
        "category": "concepts",
        "kind": "critique",
        "reasoning_domain": "argument analysis",
        "researcher_question": "Where are false either/or choices presented?",
        "extraction_prompt": """You are conducting Phase 9.5: FALSE DICHOTOMIES vulnerability analysis.

## YOUR TASK

Find arguments about "{concept}" that present FALSE EITHER/OR CHOICES.

## WHAT TO LOOK FOR

A false dichotomy is where:
- Two options are presented as EXHAUSTIVE
- But there are OTHER POSSIBILITIES
- The argument's force depends on the limited options

## ARGUMENTS TO ANALYZE

{args_text}

## OUTPUT FORMAT

Return JSON with vulnerabilities[], each containing:
- vulnerability_id, vulnerability_type: "false_dichotomy", argument_id, presented_options[], missed_alternatives[], why_dichotomy_false, severity, quote, source

TARGET: 3-7 vulnerabilities.""",
        "curation_prompt": "Validate false dichotomy identification.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 10: Cross-Text Comparison
    {
        "engine_key": "concept_cross_text_comparison",
        "engine_name": "Concept Cross-Text Comparison",
        "description": "Tracks how the concept's treatment evolves across documents",
        "version": 1,
        "category": "concepts",
        "kind": "synthesis",
        "reasoning_domain": "comparative analysis",
        "researcher_question": "How does treatment of this concept change across texts?",
        "extraction_prompt": """You are conducting Phase 10: CROSS-TEXT COMPARISON.

## YOUR TASK

Compare how "{concept}" is treated ACROSS DIFFERENT DOCUMENTS.

## DOCUMENTS

{documents_summary}

## WHAT TO LOOK FOR

1. **Definitional shifts**: Does the meaning change?
2. **Emphasis changes**: Different aspects highlighted?
3. **New arguments**: Arguments appearing in later texts?
4. **Contradictions**: Claims that conflict?
5. **Development**: How does understanding deepen?

## CONTEXT FROM PREVIOUS PHASES

{previous_outputs_summary}

## OUTPUT FORMAT

Return JSON with:
- definitional_evolution: how meaning changes
- emphasis_shifts[]: what changes in focus
- new_elements[]: what appears in later texts
- potential_contradictions[]: conflicting claims
- development_trajectory: overall arc

Return as valid JSON.""",
        "curation_prompt": "Validate cross-text comparison.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 11: Quote Retrieval
    {
        "engine_key": "concept_quote_retrieval",
        "engine_name": "Concept Quote Retrieval",
        "description": "Extracts key illustrative quotes for each major finding",
        "version": 1,
        "category": "concepts",
        "kind": "primitive",
        "reasoning_domain": "evidence collection",
        "researcher_question": "What are the key quotes that illustrate each finding?",
        "extraction_prompt": """You are conducting Phase 11: QUOTE RETRIEVAL.

## YOUR TASK

Find KEY QUOTES that ILLUSTRATE each major finding about "{concept}".

## FINDINGS TO ILLUSTRATE

{findings_summary}

## DOCUMENTS

{documents_text}

## FOR EACH FINDING

Find 2-3 quotes that:
- DIRECTLY illustrate the finding
- Are SUBSTANTIVE (not just mentions)
- Can STAND ALONE as evidence

## OUTPUT FORMAT

Return JSON with quote_sets[], each containing:
- finding_id, finding_summary, quotes[{text, source, page_approx, why_illustrative}]

TARGET: 25-40 high-quality quotes total.""",
        "curation_prompt": "Validate quote selection and relevance.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": []
    },

    # Phase 12: Synthesis
    {
        "engine_key": "concept_synthesis",
        "engine_name": "Concept Synthesis",
        "description": "Creates a unified summary integrating all previous analysis phases",
        "version": 1,
        "category": "concepts",
        "kind": "synthesis",
        "reasoning_domain": "integration",
        "researcher_question": "What is the unified picture of how this concept functions?",
        "extraction_prompt": """You are conducting Phase 12: SYNTHESIS.

## YOUR TASK

Create a UNIFIED ANALYSIS of "{concept}" integrating all previous phases.

## PHASE OUTPUTS TO SYNTHESIZE

{all_phase_outputs}

## SYNTHESIS STRUCTURE

1. **Semantic Core**: What "{concept}" means in this corpus
2. **Argumentative Architecture**: How arguments about it are structured
3. **Logical Assessment**: Strengths and vulnerabilities
4. **Cross-Text Evolution**: How treatment develops
5. **Critical Verdict**: Overall assessment with key quotes

## OUTPUT FORMAT

Return JSON with:
- semantic_core: {definition, key_collocations, theoretical_lineage}
- argumentative_architecture: {core_chains, supporting_chains, key_arguments}
- logical_assessment: {strengths[], vulnerabilities[], overall_soundness}
- evolution: {trajectory, key_shifts, contradictions}
- critical_verdict: {summary, key_quotes[], recommendations}

This is the FINAL SYNTHESIS. Make it comprehensive and well-supported.""",
        "curation_prompt": "Validate synthesis completeness and integration.",
        "canonical_schema": {"type": "object"},
        "paradigm_keys": ["marxist", "brandomian"]
    },
]


def main():
    """Generate engine definition JSON files."""
    ENGINES_DIR.mkdir(parents=True, exist_ok=True)

    for engine in CONCEPT_ENGINES:
        path = ENGINES_DIR / f"{engine['engine_key']}.json"
        with open(path, 'w') as f:
            json.dump(engine, f, indent=2)
        print(f"Created: {path.name}")

    print(f"\nGenerated {len(CONCEPT_ENGINES)} concept analysis engines")


if __name__ == "__main__":
    main()
