/**
 * DesignTokenContext - Provides design tokens to the component tree.
 *
 * Fetches tokens from the style school API endpoint, flattens them to CSS
 * custom properties, and applies them to a wrapper div. Falls back to
 * FALLBACK_TOKENS (a snapshot of the current humanist_craft visual values)
 * when the API is unavailable.
 *
 * Usage:
 *   <DesignTokenProvider schoolKey="humanist_craft" jobId={jobId}>
 *     <YourComponents />
 *   </DesignTokenProvider>
 *
 *   const { getCategoryColor, getSemanticColor, getLabel } = useDesignTokens();
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from 'react';
import {
  DesignTokenSet,
  SemanticTriple,
  CategoricalItem,
  SemanticTokens,
  CategoricalTokens,
} from '../types/designTokens';
import { flattenTokens } from '../utils/tokenFlattener';

// ── API base URL ────────────────────────────────────────────────
// Consumer apps set this via env var. Supports both CRA and Next.js conventions.
const ANALYZER_V2_URL =
  (typeof process !== 'undefined' && process.env?.REACT_APP_ANALYZER_V2_URL) ||
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_ANALYZER_V2_URL) ||
  'http://localhost:8001';

// ── FALLBACK_TOKENS ─────────────────────────────────────────────
// Hardcoded snapshot of the current humanist_craft visual values.
// Extracted from:
//   - webapp/src/constants/genealogyStyles.ts (all color maps)
//   - webapp/src/pages/GenealogyPage.css (CSS custom properties)
//   - webapp/src/components/renderers/AccordionRenderer.tsx (ENUM_COLORS)

const FALLBACK_TOKENS: DesignTokenSet = {
  school_key: 'humanist_craft',
  school_name: 'Humanist Craft',
  generated_at: '2026-03-02T00:00:00Z',
  version: '1.0.0-fallback',

  primitives: {
    color_primary: '#b5343a',
    color_secondary: '#1e40af',
    color_tertiary: '#166534',
    color_accent: '#b5343a',
    color_accent_alt: '#9a2c32',
    color_background: '#ffffff',
    color_highlight: 'rgba(181, 52, 58, 0.08)',
    color_text: '#1a1d23',
    color_muted: '#6b7280',
    color_positive: '#16a34a',
    color_negative: '#dc2626',
    series_palette: [
      '#b5343a', '#1e40af', '#166534', '#92400e', '#6b21a8',
      '#155e75', '#9f1239', '#3730a3', '#9a3412', '#334155',
    ],
    font_primary: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    font_title: "'Georgia', 'Times New Roman', serif",
    font_caption: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    font_number: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace",
  },

  surfaces: {
    surface_default: '#ffffff',
    surface_alt: '#f8f9fa',
    surface_elevated: '#f5f3f0',
    surface_inset: '#f0ede8',
    border_default: '#e2e5e9',
    border_light: '#eef0f2',
    border_accent: '#b5343a',
    text_default: '#1a1d23',
    text_muted: '#6b7280',
    text_faint: '#9ca3af',
    text_on_accent: '#ffffff',
    text_inverse: '#ffffff',
    shadow_sm: '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
    shadow_md: '0 4px 6px rgba(0,0,0,0.05), 0 2px 4px rgba(0,0,0,0.04)',
    shadow_lg: '0 10px 15px rgba(0,0,0,0.06), 0 4px 6px rgba(0,0,0,0.03)',
  },

  scales: {
    // Typography sizes from GenealogyPage.css --type-* custom properties
    type_display: '2rem',
    type_heading: '1.375rem',
    type_subheading: '1.125rem',
    type_body: '0.9375rem',
    type_caption: '0.8125rem',
    type_label: '0.6875rem',
    // Font weights from GenealogyPage.css --weight-* custom properties
    weight_light: '300',
    weight_regular: '400',
    weight_medium: '500',
    weight_semibold: '600',
    weight_bold: '700',
    weight_title: '700',
    // Line heights from GenealogyPage.css --leading-* custom properties
    leading_tight: '1.2',
    leading_normal: '1.5',
    leading_loose: '1.8',
    // Spacing scale from GenealogyPage.css --space-* custom properties
    space_2xs: '0.125rem',
    space_xs: '0.25rem',
    space_sm: '0.5rem',
    space_md: '1rem',
    space_lg: '1.5rem',
    space_xl: '2rem',
    space_2xl: '3rem',
    space_3xl: '4rem',
    // Border radii from GenealogyPage.css --radius-* custom properties
    radius_sm: '4px',
    radius_md: '8px',
    radius_lg: '12px',
    radius_xl: '16px',
    radius_pill: '9999px',
  },

  semantic: {
    // Severity - from SEVERITY_STYLES in genealogyStyles.ts + ENUM_COLORS in AccordionRenderer.tsx
    severity_high: { bg: 'rgba(239, 68, 68, 0.15)', text: '#dc2626', border: '#fecaca' },
    severity_medium: { bg: 'rgba(234, 179, 8, 0.15)', text: '#ca8a04', border: '#fde68a' },
    severity_low: { bg: 'rgba(34, 197, 94, 0.15)', text: '#16a34a', border: '#bbf7d0' },
    // Visibility - from ENUM_COLORS in AccordionRenderer.tsx
    visibility_explicit: { bg: 'rgba(34, 197, 94, 0.12)', text: '#16a34a', border: '#bbf7d0' },
    visibility_implicit: { bg: 'rgba(234, 179, 8, 0.12)', text: '#ca8a04', border: '#fde68a' },
    visibility_hidden: { bg: 'rgba(239, 68, 68, 0.12)', text: '#dc2626', border: '#fecaca' },
    // Modality - from ENUM_COLORS in AccordionRenderer.tsx
    modality_ontological: { bg: '#eff6ff', text: '#1e40af', border: '#bfdbfe' },
    modality_methodological: { bg: '#f0fdf4', text: '#166534', border: '#bbf7d0' },
    modality_normative: { bg: '#fef2f2', text: '#991b1b', border: '#fecaca' },
    modality_epistemic: { bg: '#fdf4ff', text: '#86198f', border: '#e9d5ff' },
    modality_causal: { bg: '#fff7ed', text: '#9a3412', border: '#fed7aa' },
    // Change types - from ENUM_COLORS in AccordionRenderer.tsx
    change_stable: { bg: 'rgba(34, 197, 94, 0.12)', text: '#16a34a', border: '#bbf7d0' },
    change_narrowed: { bg: 'rgba(234, 179, 8, 0.12)', text: '#ca8a04', border: '#fde68a' },
    change_expanded: { bg: 'rgba(59, 130, 246, 0.12)', text: '#2563eb', border: '#93c5fd' },
    change_inverted: { bg: 'rgba(239, 68, 68, 0.12)', text: '#dc2626', border: '#fecaca' },
    change_metaphorized: { bg: 'rgba(139, 92, 246, 0.12)', text: '#7c3aed', border: '#c4b5fd' },
    // Centrality - derived from severity pattern (core=high, supporting=medium, peripheral=low)
    centrality_core: { bg: 'rgba(239, 68, 68, 0.12)', text: '#dc2626', border: '#fecaca' },
    centrality_supporting: { bg: 'rgba(59, 130, 246, 0.12)', text: '#2563eb', border: '#93c5fd' },
    centrality_peripheral: { bg: 'rgba(148, 163, 184, 0.12)', text: '#64748b', border: '#cbd5e1' },
    // Status
    status_completed: { bg: 'rgba(34, 197, 94, 0.12)', text: '#16a34a', border: '#bbf7d0' },
    status_running: { bg: 'rgba(59, 130, 246, 0.12)', text: '#2563eb', border: '#93c5fd' },
    status_pending: { bg: 'rgba(234, 179, 8, 0.12)', text: '#ca8a04', border: '#fde68a' },
    status_failed: { bg: 'rgba(239, 68, 68, 0.12)', text: '#dc2626', border: '#fecaca' },
  },

  categorical: {
    // ── Tactics (from TACTIC_COLORS + TACTIC_LABELS in genealogyStyles.ts) ──
    tactic_conceptual_recycling: { bg: '#eff6ff', text: '#1e40af', border: '#bfdbfe', label: 'Conceptual Recycling' },
    tactic_silent_revision: { bg: '#fef2f2', text: '#991b1b', border: '#fecaca', label: 'Silent Revision' },
    tactic_selective_continuity: { bg: '#fffbeb', text: '#92400e', border: '#fde68a', label: 'Selective Continuity' },
    tactic_retroactive_framing: { bg: '#faf5ff', text: '#6b21a8', border: '#e9d5ff', label: 'Retroactive Framing' },
    tactic_escalation: { bg: '#fff7ed', text: '#9a3412', border: '#fed7aa', label: 'Escalation' },
    tactic_narrative_bootstrapping: { bg: '#f0fdf4', text: '#166534', border: '#bbf7d0', label: 'Narrative Bootstrapping' },
    tactic_framework_migration: { bg: '#ecfeff', text: '#155e75', border: '#a5f3fc', label: 'Framework Migration' },
    tactic_condition_shift: { bg: '#fff1f2', text: '#9f1239', border: '#fecdd3', label: 'Condition Shift' },
    tactic_biographical_teleology: { bg: '#eef2ff', text: '#3730a3', border: '#c7d2fe', label: 'Biographical Teleology' },
    tactic_strategic_amnesia: { bg: '#f8fafc', text: '#334155', border: '#e2e8f0', label: 'Strategic Amnesia' },

    // ── Forms (from FORM_LABELS in genealogyStyles.ts) ──
    // FORM_LABELS has { label, color }; we derive bg/text/border from the single color
    form_proto_form: { bg: 'rgba(148, 163, 184, 0.12)', text: '#94a3b8', border: '#cbd5e1', label: 'Proto-form' },
    form_full_form: { bg: 'rgba(34, 197, 94, 0.12)', text: '#22c55e', border: '#86efac', label: 'Full Form' },
    form_contradictory_form: { bg: 'rgba(239, 68, 68, 0.12)', text: '#ef4444', border: '#fca5a5', label: 'Contradictory' },
    form_absent_but_implied: { bg: 'rgba(245, 158, 11, 0.12)', text: '#f59e0b', border: '#fde68a', label: 'Absent (Implied)' },
    form_different_framing: { bg: 'rgba(139, 92, 246, 0.12)', text: '#8b5cf6', border: '#c4b5fd', label: 'Different Framing' },

    // ── Idea types (from IDEA_FORM_COLORS in genealogyStyles.ts) ──
    idea_central_thesis: { bg: '#fef2f2', text: '#991b1b', border: '#f87171', label: 'Central Thesis' },
    idea_supporting_argument: { bg: '#eff6ff', text: '#1e40af', border: '#60a5fa', label: 'Supporting Argument' },
    idea_supporting_framework: { bg: '#eff6ff', text: '#1e40af', border: '#60a5fa', label: 'Supporting Framework' },
    idea_methodological_tool: { bg: '#f0fdf4', text: '#166534', border: '#4ade80', label: 'Methodological Tool' },
    idea_conceptual_framework: { bg: '#faf5ff', text: '#6b21a8', border: '#a78bfa', label: 'Conceptual Framework' },
    idea_empirical_finding: { bg: '#fffbeb', text: '#92400e', border: '#fbbf24', label: 'Empirical Finding' },
    idea_normative_claim: { bg: '#fff1f2', text: '#9f1239', border: '#fb7185', label: 'Normative Claim' },
    idea_analytical_distinction: { bg: '#ecfeff', text: '#155e75', border: '#22d3ee', label: 'Analytical Distinction' },
    idea_rhetorical_strategy: { bg: '#fff7ed', text: '#9a3412', border: '#fb923c', label: 'Rhetorical Strategy' },
    idea_rhetorical_device: { bg: '#fff7ed', text: '#9a3412', border: '#fb923c', label: 'Rhetorical Device' },
    idea_historical_analysis: { bg: '#eef2ff', text: '#3730a3', border: '#a5b4fc', label: 'Historical Analysis' },

    // ── Condition types (from CONDITION_TYPE_COLORS in genealogyStyles.ts) ──
    // CONDITION_TYPE_COLORS has a single color; we derive bg (lighten) and text (as-is) and border (as-is)
    condition_conceptual_foundation: { bg: 'rgba(59, 130, 246, 0.12)', text: '#3b82f6', border: '#93c5fd', label: 'Conceptual Foundation' },
    condition_audience_preparation: { bg: 'rgba(139, 92, 246, 0.12)', text: '#8b5cf6', border: '#c4b5fd', label: 'Audience Preparation' },
    condition_authority_establishment: { bg: 'rgba(239, 68, 68, 0.12)', text: '#ef4444', border: '#fca5a5', label: 'Authority Establishment' },
    condition_framework_provision: { bg: 'rgba(34, 197, 94, 0.12)', text: '#22c55e', border: '#86efac', label: 'Framework Provision' },
    condition_problem_definition: { bg: 'rgba(245, 158, 11, 0.12)', text: '#f59e0b', border: '#fde68a', label: 'Problem Definition' },
    condition_methodological_precedent: { bg: 'rgba(6, 182, 212, 0.12)', text: '#06b6d4', border: '#67e8f9', label: 'Methodological Precedent' },
    condition_intellectual_toolkit: { bg: 'rgba(236, 72, 153, 0.12)', text: '#ec4899', border: '#f9a8d4', label: 'Intellectual Toolkit' },
    condition_cross_domain_transfer: { bg: 'rgba(20, 184, 166, 0.12)', text: '#14b8a6', border: '#5eead4', label: 'Cross-Domain Transfer' },

    // ── Relationship types (from RELATIONSHIP_TYPE_STYLES in genealogyStyles.ts) ──
    relationship_direct_precursor: { bg: '#eff6ff', text: '#1e40af', border: '#93c5fd', label: 'Direct Precursor' },
    relationship_methodological_ancestor: { bg: '#f0fdf4', text: '#166534', border: '#86efac', label: 'Methodological Ancestor' },
    relationship_counter_position: { bg: '#fff1f2', text: '#9f1239', border: '#fda4af', label: 'Counter-Position' },
    relationship_indirect_contextualizer: { bg: '#fdf4ff', text: '#86198f', border: '#e879f9', label: 'Indirect Contextualizer' },
    relationship_stylistic_influence: { bg: '#fffbeb', text: '#92400e', border: '#fde68a', label: 'Stylistic Influence' },
    relationship_conceptual_sibling: { bg: '#ecfeff', text: '#155e75', border: '#a5f3fc', label: 'Conceptual Sibling' },
    relationship_different_field_relevant: { bg: '#f0fdfa', text: '#115e59', border: '#5eead4', label: 'Different Field' },
    relationship_tangential: { bg: '#f8fafc', text: '#64748b', border: '#cbd5e1', label: 'Tangential' },

    // ── Strength (from RELATIONSHIP_STRENGTH_STYLES in genealogyStyles.ts) ──
    strength_strong: { bg: 'rgba(34, 197, 94, 0.12)', text: '#16a34a', border: '#86efac', label: 'Strong' },
    strength_moderate: { bg: 'rgba(234, 179, 8, 0.12)', text: '#ca8a04', border: '#fde68a', label: 'Moderate' },
    strength_weak: { bg: 'rgba(148, 163, 184, 0.12)', text: '#64748b', border: '#cbd5e1', label: 'Weak' },

    // ── Awareness (from AWARENESS_LABELS in genealogyStyles.ts) ──
    awareness_explicit: { bg: 'rgba(34, 197, 94, 0.12)', text: '#22c55e', border: '#86efac', label: 'Explicit' },
    awareness_implicit: { bg: 'rgba(245, 158, 11, 0.12)', text: '#f59e0b', border: '#fde68a', label: 'Implicit' },
    awareness_unconscious: { bg: 'rgba(239, 68, 68, 0.12)', text: '#ef4444', border: '#fca5a5', label: 'Unconscious' },

    // ── Pattern types (from PATTERN_TYPE_LABELS in genealogyStyles.ts) ──
    // PATTERN_TYPE_LABELS only has labels, no colors; use neutral styling
    pattern_analytical_method: { bg: '#eff6ff', text: '#1e40af', border: '#bfdbfe', label: 'Analytical Method' },
    pattern_cognitive_habit: { bg: '#faf5ff', text: '#6b21a8', border: '#e9d5ff', label: 'Cognitive Habit' },
    pattern_recurring_metaphor: { bg: '#fff7ed', text: '#9a3412', border: '#fed7aa', label: 'Recurring Metaphor' },
    pattern_problem_solving_approach: { bg: '#f0fdf4', text: '#166534', border: '#bbf7d0', label: 'Problem-Solving' },
    pattern_theoretical_framework: { bg: '#ecfeff', text: '#155e75', border: '#a5f3fc', label: 'Theoretical Framework' },
    pattern_argumentative_structure: { bg: '#fef2f2', text: '#991b1b', border: '#fecaca', label: 'Argumentative Structure' },
    pattern_epistemic_commitment: { bg: '#eef2ff', text: '#3730a3', border: '#c7d2fe', label: 'Epistemic Commitment' },
  },

  components: {
    // ── Page accent (from GenealogyPage.css: #b5343a used throughout) ──
    page_accent: '#b5343a',
    page_accent_hover: '#9a2c32',
    page_accent_bg: 'rgba(181, 52, 58, 0.08)',
    // ── Section headers ──
    section_header_bg: '#f8f9fa',
    section_header_border: '#e2e5e9',
    section_header_text: '#1a1d23',
    // ── Cards (from GenealogyPage.css gen-config-card and --bg-surface/--border-color) ──
    card_bg: '#ffffff',
    card_border: '#e2e5e9',
    card_border_accent: '#b5343a',
    card_header_bg: '#f5f3f0',
    card_header_text: '#1a1a1a',
    // ── Chip weight stops (gradient from neutral to accent) ──
    chip_weight_0_bg: '#f8fafc',
    chip_weight_0_text: '#94a3b8',
    chip_weight_0_border: '#e2e8f0',
    chip_weight_25_bg: '#eff6ff',
    chip_weight_25_text: '#3b82f6',
    chip_weight_25_border: '#bfdbfe',
    chip_weight_50_bg: '#fef3c7',
    chip_weight_50_text: '#d97706',
    chip_weight_50_border: '#fde68a',
    chip_weight_75_bg: '#fee2e2',
    chip_weight_75_text: '#dc2626',
    chip_weight_75_border: '#fecaca',
    chip_weight_100_bg: 'rgba(181, 52, 58, 0.15)',
    chip_weight_100_text: '#b5343a',
    chip_weight_100_border: '#b5343a',
    chip_header_bg: '#f5f3f0',
    chip_header_text: '#1a1a1a',
    // ── Prose styling ──
    prose_lede_color: '#1a1d23',
    prose_lede_weight: '500',
    prose_blockquote_border: '#b5343a',
    prose_blockquote_bg: 'rgba(181, 52, 58, 0.04)',
    // ── Timeline components ──
    timeline_connector: '#e2e5e9',
    timeline_connector_width: '2px',
    timeline_node_bg: '#ffffff',
    timeline_node_border: '#b5343a',
    // ── Evidence markers ──
    evidence_dot_bg: '#b5343a',
    evidence_connector: '#e2e5e9',
    // ── Stats ──
    stat_number_color: '#b5343a',
    stat_label_color: '#6b7280',
    stat_card_bg: '#f8f9fa',
  },
};

// ── Context types ───────────────────────────────────────────────

interface DesignTokenContextValue {
  tokens: DesignTokenSet;
  loading: boolean;
  schoolKey: string;
  getCategoryColor: (category: string, key: string) => CategoricalItem | null;
  getSemanticColor: (scale: string, level: string) => SemanticTriple | null;
  getLabel: (category: string, key: string) => string;
  getChipWeight: (weight: number) => { bg: string; text: string; border: string };
}

interface DesignTokenProviderProps {
  schoolKey: string;
  jobId?: string;
  children: React.ReactNode;
}

// ── Context ─────────────────────────────────────────────────────

const defaultContextValue: DesignTokenContextValue = {
  tokens: FALLBACK_TOKENS,
  loading: false,
  schoolKey: 'humanist_craft',
  getCategoryColor: () => null,
  getSemanticColor: () => null,
  getLabel: () => '',
  getChipWeight: () => ({ bg: '#f8fafc', text: '#94a3b8', border: '#e2e8f0' }),
};

const DesignTokenContext = createContext<DesignTokenContextValue>(defaultContextValue);

// ── Provider component ──────────────────────────────────────────

export function DesignTokenProvider({ schoolKey, jobId, children }: DesignTokenProviderProps) {
  const [tokens, setTokens] = useState<DesignTokenSet>(FALLBACK_TOKENS);
  const [loading, setLoading] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Track previous CSS vars so we can clean them up on token change
  const appliedVarsRef = useRef<string[]>([]);

  // Fetch tokens when schoolKey changes
  useEffect(() => {
    if (!schoolKey) return;

    // If it's the fallback school and we already have fallback tokens, skip fetch
    // (still try the API, but don't block on it)
    let cancelled = false;
    setLoading(true);

    async function fetchTokens() {
      try {
        const resp = await fetch(
          `${ANALYZER_V2_URL}/v1/styles/tokens/${encodeURIComponent(schoolKey)}`
        );
        if (cancelled) return;

        if (resp.ok) {
          const data: DesignTokenSet = await resp.json();
          setTokens(data);

          // Persist school choice if jobId provided
          if (jobId) {
            try {
              localStorage.setItem(`style_school_${jobId}`, schoolKey);
            } catch {
              // localStorage may be unavailable
            }
          }
        } else {
          console.warn(
            `[DesignTokens] Failed to fetch tokens for "${schoolKey}" (${resp.status}), using fallback`
          );
          setTokens(FALLBACK_TOKENS);
        }
      } catch (err) {
        if (cancelled) return;
        console.warn(
          `[DesignTokens] Network error fetching tokens for "${schoolKey}", using fallback:`,
          err
        );
        setTokens(FALLBACK_TOKENS);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchTokens();
    return () => {
      cancelled = true;
    };
  }, [schoolKey, jobId]);

  // Apply CSS vars when tokens change
  useEffect(() => {
    const vars = flattenTokens(tokens);
    const el = wrapperRef.current;
    if (!el) return;

    // Remove previously applied vars that are no longer in the new set
    for (const oldVar of appliedVarsRef.current) {
      if (!(oldVar in vars)) {
        el.style.removeProperty(oldVar);
      }
    }

    // Apply new vars
    for (const [prop, value] of Object.entries(vars)) {
      el.style.setProperty(prop, value);
    }

    appliedVarsRef.current = Object.keys(vars);
  }, [tokens]);

  // ── Helper: getCategoryColor ──────────────────────────────────
  const getCategoryColor = useCallback(
    (category: string, key: string): CategoricalItem | null => {
      const lookupKey = `${category}_${key}` as keyof CategoricalTokens;
      const item = tokens.categorical[lookupKey];
      return item || null;
    },
    [tokens]
  );

  // ── Helper: getSemanticColor ──────────────────────────────────
  const getSemanticColor = useCallback(
    (scale: string, level: string): SemanticTriple | null => {
      const lookupKey = `${scale}_${level}` as keyof SemanticTokens;
      const item = tokens.semantic[lookupKey];
      return item || null;
    },
    [tokens]
  );

  // ── Helper: getLabel ──────────────────────────────────────────
  const getLabel = useCallback(
    (category: string, key: string): string => {
      const lookupKey = `${category}_${key}` as keyof CategoricalTokens;
      const item = tokens.categorical[lookupKey];
      return item?.label || key.replace(/_/g, ' ');
    },
    [tokens]
  );

  // ── Helper: getChipWeight ─────────────────────────────────────
  // Maps a 0-1 weight to the nearest chip weight stop (0, 25, 50, 75, 100)
  const getChipWeight = useCallback(
    (weight: number): { bg: string; text: string; border: string } => {
      const pct = Math.round(weight * 100);
      const stops = [0, 25, 50, 75, 100];
      let nearest = 0;
      let minDist = Infinity;
      for (const stop of stops) {
        const dist = Math.abs(pct - stop);
        if (dist < minDist) {
          minDist = dist;
          nearest = stop;
        }
      }

      const comp = tokens.components;
      switch (nearest) {
        case 0:
          return { bg: comp.chip_weight_0_bg, text: comp.chip_weight_0_text, border: comp.chip_weight_0_border };
        case 25:
          return { bg: comp.chip_weight_25_bg, text: comp.chip_weight_25_text, border: comp.chip_weight_25_border };
        case 50:
          return { bg: comp.chip_weight_50_bg, text: comp.chip_weight_50_text, border: comp.chip_weight_50_border };
        case 75:
          return { bg: comp.chip_weight_75_bg, text: comp.chip_weight_75_text, border: comp.chip_weight_75_border };
        case 100:
          return { bg: comp.chip_weight_100_bg, text: comp.chip_weight_100_text, border: comp.chip_weight_100_border };
        default:
          return { bg: comp.chip_weight_0_bg, text: comp.chip_weight_0_text, border: comp.chip_weight_0_border };
      }
    },
    [tokens]
  );

  // ── Memoize context value ─────────────────────────────────────
  const contextValue = useMemo<DesignTokenContextValue>(
    () => ({
      tokens,
      loading,
      schoolKey,
      getCategoryColor,
      getSemanticColor,
      getLabel,
      getChipWeight,
    }),
    [tokens, loading, schoolKey, getCategoryColor, getSemanticColor, getLabel, getChipWeight]
  );

  return (
    <DesignTokenContext.Provider value={contextValue}>
      <div ref={wrapperRef} className="design-token-wrapper" style={{ display: 'contents' }}>
        {children}
      </div>
    </DesignTokenContext.Provider>
  );
}

// ── Hook ────────────────────────────────────────────────────────

export function useDesignTokens(): DesignTokenContextValue {
  return useContext(DesignTokenContext);
}

// ── Export fallback for testing / direct use ────────────────────
export { FALLBACK_TOKENS };
