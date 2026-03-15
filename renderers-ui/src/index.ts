/**
 * @the-syllabus/analysis-renderers — Shared renderer components for analyzer-v2 view definitions.
 *
 * This package provides the complete rendering pipeline:
 * - Container renderers (accordion, card_grid, prose, table, etc.)
 * - Sub-renderers (chip_grid, mini_card_list, distribution_summary, etc.)
 * - Cell renderers (template_card, default auto-classify, etc.)
 * - Design token system (DesignTokenProvider + useDesignTokens hook)
 * - Renderer registry (view_key → component resolution)
 *
 * CSS: import '@the-syllabus/analysis-renderers/styles' for all renderer styles.
 */

// ── Types ────────────────────────────────────────────────
export type {
  RendererProps,
  RendererComponent,
  CellRendererProps,
  CellRendererComponent,
  SubRendererProps,
  SubRendererComponent,
  StyleOverrides,
  DesignTokenSet,
  SemanticTriple,
  CategoricalItem,
  PrimitiveTokens,
  SurfaceTokens,
  ScaleTokens,
  SemanticTokens,
  CategoricalTokens,
  ComponentTokens,
} from './types';
export { getSO } from './types';

// ── Design Tokens ────────────────────────────────────────
export {
  DesignTokenProvider,
  useDesignTokens,
  FALLBACK_TOKENS,
} from './tokens/DesignTokenContext';

// ── Utilities ────────────────────────────────────────────
export { flattenTokens } from './utils/tokenFlattener';

// ── Container Renderers ──────────────────────────────────
export { AccordionRenderer } from './renderers/AccordionRenderer';
export { CardGridRenderer } from './renderers/CardGridRenderer';
export { CardRenderer } from './renderers/CardRenderer';
export { ProseRenderer, formatProse } from './renderers/ProseRenderer';
export { TableRenderer } from './renderers/TableRenderer';
export { StatSummaryRenderer } from './renderers/StatSummaryRenderer';
export { RawJsonRenderer } from './renderers/RawJsonRenderer';

// ── Sub-Renderers ────────────────────────────────────────
export {
  resolveSubRenderer,
  autoDetectSubRenderer,
  DistributionSummary,
} from './sub-renderers/SubRenderers';

// ── Sub-Renderer Dispatch ────────────────────────────────
export {
  isRendererCompatible,
  SubRendererFallback,
  GenericSectionRenderer,
  GenericMiniCard,
  resolveEnumColor,
  REQUIRES_ARRAY,
  REQUIRES_OBJECT,
} from './dispatch/SubRendererDispatch';

// ── Cell Renderers ───────────────────────────────────────
export { cellRenderers, DefaultCardCell } from './cells';
export { TemplateCardCell } from './cells/TemplateCardCell';

// ── Shared Components ────────────────────────────────────
export { EvidenceTrail, EvidenceTrailSubRenderer } from './components/EvidenceTrail';
export type { EvidenceTrailStep, EvidenceTrailItem } from './components/EvidenceTrail';
export { EnableConditionsSubRenderer, ConstrainConditionsSubRenderer } from './components/ConditionCards';
export { ViewShell } from './components/ViewShell';
export { ScaffoldIntroContent } from './components/ScaffoldIntroContent';

// ── Hooks ────────────────────────────────────────────────
export { useProseExtraction } from './hooks/useProseExtraction';
