/**
 * Design Token System - TypeScript Interfaces
 *
 * Mirrors the Pydantic schema from the backend style school generator.
 * Used for typing API responses from GET /v1/styles/tokens/{schoolKey}.
 */

export interface SemanticTriple {
  bg: string;
  text: string;
  border: string;
}

export interface CategoricalItem {
  bg: string;
  text: string;
  border: string;
  label: string;
}

export interface PrimitiveTokens {
  color_primary: string;
  color_secondary: string;
  color_tertiary: string;
  color_accent: string;
  color_accent_alt: string;
  color_background: string;
  color_highlight: string;
  color_text: string;
  color_muted: string;
  color_positive: string;
  color_negative: string;
  series_palette: string[];
  font_primary: string;
  font_title: string;
  font_caption: string;
  font_number: string;
}

export interface SurfaceTokens {
  surface_default: string;
  surface_alt: string;
  surface_elevated: string;
  surface_inset: string;
  border_default: string;
  border_light: string;
  border_accent: string;
  text_default: string;
  text_muted: string;
  text_faint: string;
  text_on_accent: string;
  text_inverse: string;
  shadow_sm: string;
  shadow_md: string;
  shadow_lg: string;
}

export interface ScaleTokens {
  type_display: string;
  type_heading: string;
  type_subheading: string;
  type_body: string;
  type_caption: string;
  type_label: string;
  weight_light: string;
  weight_regular: string;
  weight_medium: string;
  weight_semibold: string;
  weight_bold: string;
  weight_title: string;
  leading_tight: string;
  leading_normal: string;
  leading_loose: string;
  space_2xs: string;
  space_xs: string;
  space_sm: string;
  space_md: string;
  space_lg: string;
  space_xl: string;
  space_2xl: string;
  space_3xl: string;
  radius_sm: string;
  radius_md: string;
  radius_lg: string;
  radius_xl: string;
  radius_pill: string;
}

export interface SemanticTokens {
  severity_high: SemanticTriple;
  severity_medium: SemanticTriple;
  severity_low: SemanticTriple;
  visibility_explicit: SemanticTriple;
  visibility_implicit: SemanticTriple;
  visibility_hidden: SemanticTriple;
  modality_ontological: SemanticTriple;
  modality_methodological: SemanticTriple;
  modality_normative: SemanticTriple;
  modality_epistemic: SemanticTriple;
  modality_causal: SemanticTriple;
  change_stable: SemanticTriple;
  change_narrowed: SemanticTriple;
  change_expanded: SemanticTriple;
  change_inverted: SemanticTriple;
  change_metaphorized: SemanticTriple;
  centrality_core: SemanticTriple;
  centrality_supporting: SemanticTriple;
  centrality_peripheral: SemanticTriple;
  status_completed: SemanticTriple;
  status_running: SemanticTriple;
  status_pending: SemanticTriple;
  status_failed: SemanticTriple;
}

export interface CategoricalTokens {
  // Tactics (10)
  tactic_conceptual_recycling: CategoricalItem;
  tactic_silent_revision: CategoricalItem;
  tactic_selective_continuity: CategoricalItem;
  tactic_retroactive_framing: CategoricalItem;
  tactic_escalation: CategoricalItem;
  tactic_narrative_bootstrapping: CategoricalItem;
  tactic_framework_migration: CategoricalItem;
  tactic_condition_shift: CategoricalItem;
  tactic_biographical_teleology: CategoricalItem;
  tactic_strategic_amnesia: CategoricalItem;
  // Forms (5)
  form_proto_form: CategoricalItem;
  form_full_form: CategoricalItem;
  form_contradictory_form: CategoricalItem;
  form_absent_but_implied: CategoricalItem;
  form_different_framing: CategoricalItem;
  // Idea types (11)
  idea_central_thesis: CategoricalItem;
  idea_supporting_argument: CategoricalItem;
  idea_supporting_framework: CategoricalItem;
  idea_methodological_tool: CategoricalItem;
  idea_conceptual_framework: CategoricalItem;
  idea_empirical_finding: CategoricalItem;
  idea_normative_claim: CategoricalItem;
  idea_analytical_distinction: CategoricalItem;
  idea_rhetorical_strategy: CategoricalItem;
  idea_rhetorical_device: CategoricalItem;
  idea_historical_analysis: CategoricalItem;
  // Condition types (8)
  condition_conceptual_foundation: CategoricalItem;
  condition_audience_preparation: CategoricalItem;
  condition_authority_establishment: CategoricalItem;
  condition_framework_provision: CategoricalItem;
  condition_problem_definition: CategoricalItem;
  condition_methodological_precedent: CategoricalItem;
  condition_intellectual_toolkit: CategoricalItem;
  condition_cross_domain_transfer: CategoricalItem;
  // Relationship types (8)
  relationship_direct_precursor: CategoricalItem;
  relationship_methodological_ancestor: CategoricalItem;
  relationship_counter_position: CategoricalItem;
  relationship_indirect_contextualizer: CategoricalItem;
  relationship_stylistic_influence: CategoricalItem;
  relationship_conceptual_sibling: CategoricalItem;
  relationship_different_field_relevant: CategoricalItem;
  relationship_tangential: CategoricalItem;
  // Strength (3)
  strength_strong: CategoricalItem;
  strength_moderate: CategoricalItem;
  strength_weak: CategoricalItem;
  // Awareness (3)
  awareness_explicit: CategoricalItem;
  awareness_implicit: CategoricalItem;
  awareness_unconscious: CategoricalItem;
  // Pattern types (7)
  pattern_analytical_method: CategoricalItem;
  pattern_cognitive_habit: CategoricalItem;
  pattern_recurring_metaphor: CategoricalItem;
  pattern_problem_solving_approach: CategoricalItem;
  pattern_theoretical_framework: CategoricalItem;
  pattern_argumentative_structure: CategoricalItem;
  pattern_epistemic_commitment: CategoricalItem;
  // Attack types (10)
  attack_type_empirical: CategoricalItem;
  attack_type_conceptual: CategoricalItem;
  attack_type_logical: CategoricalItem;
  attack_type_historical: CategoricalItem;
  attack_type_rhetorical: CategoricalItem;
  attack_type_scope: CategoricalItem;
  attack_type_definitional: CategoricalItem;
  attack_type_comparative: CategoricalItem;
  attack_type_structural: CategoricalItem;
  attack_type_cascade: CategoricalItem;
  // Sin types (10)
  sin_type_misreading: CategoricalItem;
  sin_type_unacknowledged_debt: CategoricalItem;
  sin_type_misappropriation: CategoricalItem;
  sin_type_decontextualization: CategoricalItem;
  sin_type_selective_citation: CategoricalItem;
  sin_type_flattening: CategoricalItem;
  sin_type_ventriloquism: CategoricalItem;
  sin_type_strategic_silence: CategoricalItem;
  sin_type_premature_synthesis: CategoricalItem;
  sin_type_legitimation_borrowing: CategoricalItem;
  // Provenance categories (11)
  provenance_target_analysis: CategoricalItem;
  provenance_relationships: CategoricalItem;
  provenance_prior_works: CategoricalItem;
  provenance_idea_evolution: CategoricalItem;
  provenance_tactics: CategoricalItem;
  provenance_conditions: CategoricalItem;
  provenance_synthesis: CategoricalItem;
  provenance_research_answers: CategoricalItem;
  provenance_research_contextualizers: CategoricalItem;
  provenance_manual: CategoricalItem;
  provenance_other: CategoricalItem;
}

export interface ComponentTokens {
  page_accent: string;
  page_accent_hover: string;
  page_accent_bg: string;
  section_header_bg: string;
  section_header_border: string;
  section_header_text: string;
  card_bg: string;
  card_border: string;
  card_border_accent: string;
  card_header_bg: string;
  card_header_text: string;
  chip_weight_0_bg: string;
  chip_weight_0_text: string;
  chip_weight_0_border: string;
  chip_weight_25_bg: string;
  chip_weight_25_text: string;
  chip_weight_25_border: string;
  chip_weight_50_bg: string;
  chip_weight_50_text: string;
  chip_weight_50_border: string;
  chip_weight_75_bg: string;
  chip_weight_75_text: string;
  chip_weight_75_border: string;
  chip_weight_100_bg: string;
  chip_weight_100_text: string;
  chip_weight_100_border: string;
  chip_header_bg: string;
  chip_header_text: string;
  prose_lede_color: string;
  prose_lede_weight: string;
  prose_blockquote_border: string;
  prose_blockquote_bg: string;
  timeline_connector: string;
  timeline_connector_width: string;
  timeline_node_bg: string;
  timeline_node_border: string;
  evidence_dot_bg: string;
  evidence_connector: string;
  stat_number_color: string;
  stat_label_color: string;
  stat_card_bg: string;
}

export interface DesignTokenSet {
  school_key: string;
  school_name: string;
  generated_at: string;
  version: string;
  primitives: PrimitiveTokens;
  surfaces: SurfaceTokens;
  scales: ScaleTokens;
  semantic: SemanticTokens;
  categorical: CategoricalTokens;
  components: ComponentTokens;
}
