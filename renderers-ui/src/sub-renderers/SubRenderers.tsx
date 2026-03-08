/**
 * SubRenderers — Section-level rendering components for accordion sections.
 *
 * These are small, focused renderers that handle one section's data within
 * an accordion. The AccordionRenderer dispatches to these based on
 * config.section_renderers[sectionKey].renderer_type.
 *
 * Available sub-renderers:
 *   chip_grid        — Array of strings/objects → weighted chip cloud
 *   definition_list  — Array of "Term: Definition" strings or objects → glossary layout
 *   mini_card_list   — Array of objects → hero + grid insight cards
 *   key_value_table  — Object or [{key, value}] → styled two-column table
 *   prose_block      — String → formatted analysis with lede, blockquotes
 *   stat_row         — Object → monospace stat cards
 *   comparison_panel — Array of objects → side-by-side comparison with headers
 *   timeline_strip   — Array of objects with stages → evolution arc with progression
 *   evidence_trail   — Vertical chain of evidence steps with dot markers and connectors
 *   ordered_flow     — Ordered sequence of content units with connecting line and category badges
 *   intensity_matrix      — Dashboard rows with horizontal intensity bars for quantitative dimensions
 *   move_repertoire       — Grouped card list with collapsible category headers and count badges
 *   dialectical_pair      — Two-panel tension visualization for thesis/antithesis contrasts
 *   rich_description_list — Stacked items with colored borders for paragraph-length descriptions
 *   phase_timeline        — Connected timeline with prominent phase nodes for temporal data
 *   dependency_matrix     — Adjacency matrix / heatmap for directed chapter dependencies
 *   distribution_summary  — Visual bar chart with dominant highlight, counts, and optional narrative
 */

import React, { useState } from 'react';
import { EvidenceTrailSubRenderer } from '../components/EvidenceTrail';
import { EnableConditionsSubRenderer, ConstrainConditionsSubRenderer } from '../components/ConditionCards';
import { StyleOverrides, getSO } from '../types/styles';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import type { SubRendererProps } from '../types';
// CaptureSelection is passed via config._onCapture — no direct type import needed
type CaptureSelection = Record<string, unknown>;

// Re-export SubRendererProps for backward compat
export type { SubRendererProps } from '../types';

// ── Registry ─────────────────────────────────────────────

const SUB_RENDERER_MAP: Record<string, React.FC<SubRendererProps>> = {
  chip_grid: ChipGrid,
  definition_list: DefinitionList,
  mini_card_list: MiniCardList,
  key_value_table: KeyValueTable,
  prose_block: ProseBlock,
  stat_row: StatRow,
  comparison_panel: ComparisonPanel,
  timeline_strip: TimelineStrip,
  evidence_trail: EvidenceTrailSubRenderer,
  enabling_conditions: EnableConditionsSubRenderer,
  constraining_conditions: ConstrainConditionsSubRenderer,
  ordered_flow: OrderedFlow,
  intensity_matrix: IntensityMatrix,
  move_repertoire: MoveRepertoire,
  grouped_card_list: MoveRepertoire,  // alias for generic usage
  dialectical_pair: DialecticalPair,
  rich_description_list: RichDescriptionList,
  phase_timeline: PhaseTimeline,
  dependency_matrix: DependencyMatrix,
  distribution_summary: DistributionSummary,
};

export function resolveSubRenderer(rendererType: string): React.FC<SubRendererProps> | null {
  return SUB_RENDERER_MAP[rendererType] || null;
}

/**
 * Auto-detect the best sub-renderer for a data shape.
 * Used by AccordionRenderer when no section_renderer is explicitly configured.
 *
 * Decision tree:
 *   string → prose_block
 *   string[] → chip_grid
 *   object[] with nested array fields → timeline_strip (concept evolution, stage progressions)
 *   object[] with title+description → mini_card_list
 *   object[] short items (≤3 fields, all short) → chip_grid
 *   flat object (no nested arrays) → key_value_table
 *   object with only numeric values → stat_row
 */
export function autoDetectSubRenderer(data: unknown): string | null {
  if (data === null || data === undefined) return null;

  if (typeof data === 'string') return 'prose_block';

  if (Array.isArray(data) && data.length > 0) {
    if (data.every(d => typeof d === 'string')) {
      // Check if strings look like "Term: Definition" → use definition_list
      const strs = data as string[];
      const defCount = strs.filter(s => {
        const colonIdx = s.indexOf(':');
        // Term before colon (1-60 chars), definition after colon (10+ chars)
        return colonIdx > 1 && colonIdx < 60 && s.length > colonIdx + 10;
      }).length;
      if (defCount >= strs.length * 0.5) return 'definition_list';
      return 'chip_grid';
    }

    const firstObj = data.find(d => typeof d === 'object' && d !== null) as Record<string, unknown> | undefined;
    if (firstObj) {
      const entries = Object.entries(firstObj);
      const hasArrayField = entries.some(([, v]) => Array.isArray(v) && (v as unknown[]).length > 0);
      const fieldCount = entries.length;
      const shortStringCount = entries.filter(([, v]) => typeof v === 'string' && (v as string).length < 60).length;
      const longStringCount = entries.filter(([, v]) => typeof v === 'string' && (v as string).length >= 60).length;

      if (hasArrayField) return 'timeline_strip';
      if (fieldCount <= 3 && shortStringCount >= fieldCount - 1 && longStringCount === 0) return 'chip_grid';
      if (longStringCount > 0) return 'mini_card_list';
      return 'mini_card_list';
    }
  }

  if (typeof data === 'object' && !Array.isArray(data)) {
    const obj = data as Record<string, unknown>;
    const entries = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined);
    if (entries.length > 0 && entries.every(([, v]) => typeof v === 'number')) return 'stat_row';
    const allScalar = entries.every(([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean');
    if (allScalar) return 'key_value_table';
  }

  return null;
}

// ── Helpers ──────────────────────────────────────────────

function getField(obj: Record<string, unknown>, field: string | undefined): string {
  if (!field) return '';
  const val = obj[field];
  if (val === null || val === undefined) return '';
  return String(val);
}

function getNumField(obj: Record<string, unknown>, field: string | undefined): number | null {
  if (!field) return null;
  const val = obj[field];
  if (typeof val === 'number') return val;
  if (typeof val === 'string') {
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
  }
  return null;
}

interface AutoFields {
  title?: string;
  subtitle?: string;
  description?: string;
  badge?: string;
  label?: string;
  count?: string;
  key?: string;
  value?: string;
}

const TITLE_HINTS = ['name', 'title', 'label', 'term', 'concept', 'framework_name', 'heading'];
const SUBTITLE_HINTS = ['type', 'category', 'kind', 'centrality', 'status', 'role', 'level'];
const DESC_HINTS = ['description', 'summary', 'definition', 'explanation', 'text', 'content', 'methodological_signature'];
const KEY_HINTS = ['key', 'term', 'concept', 'name', 'label'];
const VALUE_HINTS = ['value', 'definition', 'meaning', 'description', 'explanation'];

function autoDetectFields(sample: Record<string, unknown>): AutoFields {
  const result: AutoFields = {};
  const entries = Object.entries(sample);

  const shortStrings: string[] = [];
  const longStrings: string[] = [];
  const numericFields: string[] = [];

  for (const [k, v] of entries) {
    if (typeof v === 'string') {
      if (v.length > 80) longStrings.push(k);
      else shortStrings.push(k);
    } else if (typeof v === 'number') {
      numericFields.push(k);
    }
  }

  result.title = shortStrings.find(k => TITLE_HINTS.includes(k)) || shortStrings[0];
  result.label = result.title;

  const remaining = shortStrings.filter(k => k !== result.title);
  result.subtitle = remaining.find(k => SUBTITLE_HINTS.includes(k)) || remaining[0];

  result.description = longStrings.find(k => DESC_HINTS.includes(k)) || longStrings[0];

  result.badge = numericFields[0];
  result.count = numericFields[0];

  result.key = shortStrings.find(k => KEY_HINTS.includes(k)) || shortStrings[0];
  const valCandidates = [...longStrings, ...shortStrings.filter(k => k !== result.key)];
  result.value = valCandidates.find(k => VALUE_HINTS.includes(k)) || valCandidates[0];

  return result;
}

function resolveField(config: Record<string, unknown>, configKey: string, auto: AutoFields, autoKey: keyof AutoFields): string | undefined {
  return (config[configKey] as string | undefined) || auto[autoKey];
}

// ── Color Utilities ──────────────────────────────────────

function parseAccentHSL(hex: string | undefined): { h: number; s: number; l: number } {
  if (!hex || !hex.startsWith('#') || hex.length < 7) return { h: 220, s: 55, l: 45 };
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0, s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
    else if (max === g) h = ((b - r) / d + 2) / 6;
    else h = ((r - g) / d + 4) / 6;
  }
  return { h: Math.round(h * 360), s: Math.round(s * 100), l: Math.round(l * 100) };
}

/** Render inline markdown: **bold** → accent-underlined bold, *italic* → em */
function renderInlineMarkdown(text: string, accentColor: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  const regex = /(\*\*(.+?)\*\*|\*(.+?)\*)/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    if (match[2]) {
      parts.push(
        <strong key={match.index} style={{
          fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
          textDecoration: 'underline',
          textDecorationColor: accentColor,
          textUnderlineOffset: '3px',
          textDecorationThickness: '2px',
        }}>
          {match[2]}
        </strong>
      );
    } else if (match[3]) {
      parts.push(<em key={match.index}>{match[3]}</em>);
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length > 0 ? parts : [text];
}

// ── ChipGrid ─────────────────────────────────────────────

function ChipGrid({ data, config }: SubRendererProps) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);
  const { getChipWeight, tokens } = useDesignTokens();
  const so = getSO(config);

  if (!data || !Array.isArray(data)) return null;

  const firstObj = data.find(d => typeof d === 'object' && d !== null) as Record<string, unknown> | undefined;
  const auto = firstObj ? autoDetectFields(firstObj) : {};
  const labelField = resolveField(config, 'label_field', auto, 'label');
  const countField = resolveField(config, 'count_field', auto, 'count');
  const subtitleField = resolveField(config, 'subtitle_field', auto, 'subtitle');
  const descField = resolveField(config, 'description_field', auto, 'description');

  const hasDetails = firstObj && (
    (descField && getField(firstObj, descField).length > 0) ||
    Object.values(firstObj).some(v => Array.isArray(v))
  );

  // Collect numeric values for size variation
  const numericValues: number[] = [];
  if (countField) {
    data.forEach(item => {
      if (typeof item === 'object' && item !== null) {
        const n = getNumField(item as Record<string, unknown>, countField);
        if (n !== null) numericValues.push(n);
      }
    });
  }
  const hasNumeric = numericValues.length > 0;
  const minVal = hasNumeric ? Math.min(...numericValues) : 0;
  const maxVal = hasNumeric ? Math.max(...numericValues) : 1;
  const valRange = maxVal - minVal || 1;

  // Build chip items with weight for sorting
  const chipItems = data.map((item, i) => {
    const label = typeof item === 'string'
      ? item
      : typeof item === 'object' && item !== null
        ? getField(item as Record<string, unknown>, labelField)
          || String(Object.values(item as Record<string, unknown>).find(v => typeof v === 'string' && (v as string).length < 80) || `Item ${i + 1}`)
        : String(item);

    const subtitle = typeof item === 'object' && item !== null && subtitleField
      ? getField(item as Record<string, unknown>, subtitleField)
      : '';

    const count = typeof item === 'object' && item !== null && countField
      ? getNumField(item as Record<string, unknown>, countField)
      : null;

    const weight = hasNumeric && count !== null
      ? (count - minVal) / valRange
      : 0.5;

    return { item, label, subtitle, count, weight, originalIndex: i };
  });

  // Sort by weight descending for weighted cloud layout
  const sortedChips = [...chipItems].sort((a, b) => b.weight - a.weight);

  return (
    <div>
      <div style={{
        display: 'flex', gap: 'var(--space-sm, 0.5rem)', flexWrap: 'wrap',
        padding: 'var(--space-md, 0.75rem)',
        backgroundColor: 'var(--color-surface-alt, #f8f9fa)',
        borderRadius: 'var(--radius-lg, 12px)',
        border: '1px solid var(--color-border-light, #eef0f2)',
        ...so?.items_container,
      }}>
        {sortedChips.map(({ item, label, subtitle, count, weight, originalIndex }) => {
          const chipColors = getChipWeight(weight);
          const colors = { ...chipColors, headerBg: tokens.components.chip_header_bg, headerText: tokens.components.chip_header_text };
          const isExpanded = expandedIdx === originalIndex;
          const isClickable = hasDetails && typeof item === 'object' && item !== null;

          // Size variation: large chips (weight > 0.7) get bigger padding/font
          const sizeClass = weight > 0.7 ? 'large' : weight > 0.3 ? 'medium' : 'small';
          const padH = sizeClass === 'large' ? '18px' : sizeClass === 'medium' ? '14px' : '10px';
          const padV = sizeClass === 'large' ? '8px' : sizeClass === 'medium' ? '6px' : '5px';
          const fontSize = sizeClass === 'large'
            ? 'var(--type-body, 0.9375rem)'
            : sizeClass === 'medium'
              ? 'var(--type-caption, 0.8125rem)'
              : 'var(--type-label, 0.6875rem)';

          return (
            <span
              key={originalIndex}
              onClick={isClickable ? () => setExpandedIdx(isExpanded ? null : originalIndex) : undefined}
              title={isClickable ? 'Click to expand details' : undefined}
              style={{
                display: 'inline-flex', alignItems: 'center',
                gap: 'var(--space-xs, 0.25rem)',
                padding: `${padV} ${padH}`,
                borderRadius: 'var(--radius-pill, 9999px)',
                fontSize,
                fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
                backgroundColor: isExpanded ? colors.headerBg : colors.bg,
                color: isExpanded ? colors.headerText : colors.text,
                border: `1.5px solid ${isExpanded ? colors.headerBg : colors.border}`,
                boxShadow: isExpanded
                  ? 'var(--shadow-md, 0 4px 6px rgba(0,0,0,0.05))'
                  : 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
                cursor: isClickable ? 'pointer' : 'default',
                transition: `all var(--duration-fast, 150ms) var(--ease-out, ease)`,
                ...so?.chip,
              }}
            >
              <span style={so?.chip_label}>{label}</span>
              {subtitle && (
                <span style={{
                  fontSize: 'var(--type-label, 0.6875rem)',
                  fontWeight: 'var(--weight-medium, 500)' as unknown as number,
                  padding: '1px 7px', borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: isExpanded ? 'rgba(255,255,255,0.25)' : colors.headerBg,
                  color: colors.headerText,
                  letterSpacing: '0.02em',
                  ...so?.badge,
                }}>{subtitle}</span>
              )}
              {count !== null && (
                <span style={{
                  fontSize: 'var(--type-label, 0.6875rem)',
                  fontWeight: 'var(--weight-bold, 700)' as unknown as number,
                  backgroundColor: isExpanded ? 'rgba(255,255,255,0.25)' : colors.headerBg,
                  color: colors.headerText,
                  borderRadius: 'var(--radius-pill, 9999px)',
                  padding: '1px 6px',
                  ...so?.badge,
                }}>
                  {count}
                </span>
              )}
            </span>
          );
        })}
      </div>

      {/* Expanded detail — inline card */}
      {expandedIdx !== null && typeof data[expandedIdx] === 'object' && data[expandedIdx] !== null && (() => {
        const obj = data[expandedIdx] as Record<string, unknown>;
        const label = getField(obj, labelField);
        const subtitle = getField(obj, subtitleField);
        const desc = descField ? getField(obj, descField) : '';
        const expandChipColors = getChipWeight(0.6);
        const colors = { ...expandChipColors, headerBg: tokens.components.chip_header_bg, headerText: tokens.components.chip_header_text };

        const skipKeys = new Set([labelField, subtitleField, descField].filter(Boolean) as string[]);
        const remaining = Object.entries(obj).filter(([k, v]) => !skipKeys.has(k) && v !== null && v !== undefined && v !== '');
        const arrayFields = remaining.filter(([, v]) => Array.isArray(v));
        const scalarFields = remaining.filter(([, v]) => !Array.isArray(v) && typeof v === 'string' && (v as string).length > 40);
        const shortFields = remaining.filter(([, v]) => !Array.isArray(v) && (typeof v !== 'string' || (v as string).length <= 40));

        return (
          <div style={{
            margin: 'var(--space-sm, 0.5rem) 0',
            borderRadius: 'var(--radius-md, 8px)',
            overflow: 'hidden',
            border: `1.5px solid ${colors.border}`,
            boxShadow: 'var(--shadow-md, 0 4px 6px rgba(0,0,0,0.05))',
            ...so?.chip_expanded,
          }}>
            {/* Card header */}
            <div style={{
              padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
              backgroundColor: colors.headerBg,
              display: 'flex', alignItems: 'center', gap: 'var(--space-sm, 0.5rem)',
            }}>
              <strong style={{
                fontSize: 'var(--type-subheading, 1.125rem)',
                color: colors.headerText,
              }}>{label}</strong>
              {subtitle && (
                <span style={{
                  fontSize: 'var(--type-label, 0.6875rem)',
                  fontWeight: 'var(--weight-medium, 500)' as unknown as number,
                  padding: '2px 8px', borderRadius: 'var(--radius-pill, 9999px)',
                  backgroundColor: 'rgba(255,255,255,0.2)',
                  color: colors.headerText,
                  letterSpacing: '0.02em',
                }}>{subtitle}</span>
              )}
              <span
                onClick={() => setExpandedIdx(null)}
                style={{
                  marginLeft: 'auto', cursor: 'pointer',
                  fontSize: 'var(--type-label, 0.6875rem)',
                  color: 'rgba(255,255,255,0.7)',
                  padding: '2px 8px', borderRadius: 'var(--radius-sm, 4px)',
                  transition: `opacity var(--duration-fast, 150ms)`,
                }}
              >close</span>
            </div>

            {/* Card body */}
            <div style={{
              padding: 'var(--space-md, 1rem)',
              backgroundColor: colors.bg,
            }}>
              {desc && (
                <p style={{
                  margin: '0 0 var(--space-sm, 0.5rem) 0',
                  fontSize: 'var(--type-body, 0.9375rem)',
                  color: 'var(--color-text, #1a1d23)',
                  lineHeight: 'var(--leading-relaxed, 1.65)',
                }}>{desc}</p>
              )}

              {shortFields.length > 0 && (
                <div style={{
                  display: 'flex', gap: 'var(--space-md, 0.75rem)', flexWrap: 'wrap',
                  marginBottom: arrayFields.length > 0 || scalarFields.length > 0 ? 'var(--space-sm, 0.5rem)' : 0,
                }}>
                  {shortFields.map(([k, v]) => (
                    <span key={k} style={{ fontSize: 'var(--type-caption, 0.8125rem)', color: 'var(--color-text-muted, #6b7280)' }}>
                      <span className="gen-inline-label">
                        {k.replace(/_/g, ' ')}:
                      </span>{' '}
                      {String(v)}
                    </span>
                  ))}
                </div>
              )}

              {scalarFields.map(([k, v]) => (
                <div key={k} style={{ marginBottom: 'var(--space-xs, 0.375rem)' }}>
                  <span className="gen-inline-label" style={{ display: 'block', marginBottom: 'var(--space-2xs, 0.125rem)' }}>
                    {k.replace(/_/g, ' ')}
                  </span>
                  <span style={{
                    fontSize: 'var(--type-caption, 0.8125rem)',
                    color: 'var(--color-text-muted, #6b7280)',
                    lineHeight: 'var(--leading-normal, 1.5)',
                  }}>{String(v)}</span>
                </div>
              ))}

              {arrayFields.map(([k, v]) => (
                <div key={k} style={{ marginTop: 'var(--space-xs, 0.375rem)' }}>
                  <span className="gen-inline-label" style={{ marginRight: 'var(--space-xs, 0.375rem)' }}>
                    {k.replace(/_/g, ' ')}:
                  </span>
                  <span style={{ display: 'inline-flex', gap: 'var(--space-xs, 0.25rem)', flexWrap: 'wrap' }}>
                    {(v as unknown[]).map((chip, ci) => (
                      <span key={ci} className="gen-keyword-tag">{String(chip)}</span>
                    ))}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })()}
    </div>
  );
}

// ── DefinitionList → Glossary/Vocabulary ─────────────────

/**
 * Purpose-built renderer for glossary/vocabulary data.
 * Handles:
 *   - Array of "Term: Definition" strings (splits on first colon)
 *   - Array of objects with term/definition fields
 * Renders as a visually rich definition list with:
 *   - Prominent term styling with accent color
 *   - Clear definition text
 *   - Alternating subtle backgrounds
 *   - Compact, scannable layout
 */
function DefinitionList({ data, config }: SubRendererProps) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);
  const { tokens } = useDesignTokens();
  const so = getSO(config);

  // Capture mode support (threaded from AccordionRenderer)
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  if (!data || !Array.isArray(data) || data.length === 0) return null;

  // Parse items into {term, definition} pairs
  const termField = config.term_field as string | undefined;
  const defField = config.definition_field as string | undefined;

  const items = data.map((item, i) => {
    if (typeof item === 'string') {
      // Split "Term: Definition" on first colon
      const colonIdx = item.indexOf(':');
      if (colonIdx > 0 && colonIdx < 80) {
        return {
          term: item.slice(0, colonIdx).trim(),
          definition: item.slice(colonIdx + 1).trim(),
        };
      }
      return { term: `Entry ${i + 1}`, definition: item };
    }
    if (typeof item === 'object' && item !== null) {
      const obj = item as Record<string, unknown>;
      const t = getField(obj, termField) || getField(obj, 'term') || getField(obj, 'name') || getField(obj, 'concept') || getField(obj, 'label') || '';
      const d = getField(obj, defField) || getField(obj, 'definition') || getField(obj, 'description') || getField(obj, 'meaning') || '';
      return { term: t || `Entry ${i + 1}`, definition: d || JSON.stringify(obj) };
    }
    return { term: `Entry ${i + 1}`, definition: String(item) };
  });

  // Color rotation for visual variety using series palette
  const palette = tokens.primitives.series_palette;
  const termColor = (idx: number) => {
    const color = palette[idx % palette.length];
    return {
      termBg: color,
      termText: 'var(--dt-text-inverse)',
      dotColor: color,
      hoverBg: tokens.surfaces.surface_alt,
    };
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '2px',
      borderRadius: 'var(--radius-lg, 12px)',
      overflow: 'hidden',
      border: '1px solid var(--color-border-light, #eef0f2)',
      boxShadow: 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
      ...so?.items_container,
    }}>
      {items.map((item, i) => {
        const colors = termColor(i);
        const isExpanded = expandedIdx === i;
        const isLong = item.definition.length > 180;
        const displayDef = !isLong || isExpanded
          ? item.definition
          : item.definition.slice(0, 180) + '...';

        return (
          <div
            key={i}
            onClick={isLong ? () => setExpandedIdx(isExpanded ? null : i) : undefined}
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              gap: 0,
              backgroundColor: i % 2 === 0
                ? 'var(--color-surface, #ffffff)'
                : 'var(--color-surface-alt, #f8f9fa)',
              cursor: isLong ? 'pointer' : 'default',
              transition: 'background-color 150ms ease',
            }}
          >
            {/* Term column */}
            <div style={{
              padding: '10px 14px',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
              minWidth: '200px',
              maxWidth: '280px',
              borderRight: `3px solid ${colors.dotColor}`,
              backgroundColor: i % 2 === 0 ? tokens.surfaces.surface_alt : tokens.surfaces.surface_inset,
            }}>
              <span style={{
                display: 'inline-block',
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: colors.dotColor,
                marginTop: '6px',
                flexShrink: 0,
              }} />
              <span style={{
                fontSize: 'var(--type-caption, 0.8125rem)',
                fontWeight: 'var(--weight-bold, 700)' as unknown as number,
                color: tokens.surfaces.text_default,
                lineHeight: '1.3',
                letterSpacing: '0.01em',
                ...so?.stat_label,
              }}>
                {item.term}
              </span>
            </div>

            {/* Definition column */}
            <div style={{
              padding: '10px 16px',
              fontSize: 'var(--type-body, 0.9375rem)',
              fontWeight: 'var(--weight-normal, 400)' as unknown as number,
              color: 'var(--color-text, #1a1d23)',
              lineHeight: 'var(--leading-relaxed, 1.6)',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '8px',
            }}>
              <div style={{ flex: 1 }}>
                {renderInlineMarkdown(displayDef, colors.dotColor)}
                {isLong && (
                  <span className="gen-show-more-link" style={{ marginLeft: '6px' }}>
                    {isExpanded ? 'show less' : 'show more'}
                  </span>
                )}
              </div>
              {captureMode && onCapture && (
                <button
                  title="Capture this item"
                  onClick={e => {
                    e.stopPropagation();
                    onCapture({
                      source_view_key: captureViewKey || '',
                      source_section_key: parentSectionKey,
                      source_item_index: i,
                      source_renderer_type: 'definition_list',
                      content_type: 'item',
                      selected_text: `${item.term}: ${item.definition}`.slice(0, 500),
                      structured_data: data[i],
                      context_title: parentSectionKey
                        ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${item.term}`
                        : `${captureViewKey || 'Analysis'} > ${item.term}`,
                      source_type: (captureSourceType || 'analysis') as string,
                      entity_id: captureEntityId || captureJobId || '',
                      depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
                      parent_context: parentSectionKey ? {
                        section_key: parentSectionKey,
                        section_title: parentSectionTitle || '',
                      } : undefined,
                    });
                  }}
                  style={{
                    flexShrink: 0,
                    background: 'none',
                    border: '1px solid var(--color-border, #ccc)',
                    borderRadius: '4px',
                    color: 'var(--dt-text-faint, #94a3b8)',
                    cursor: 'pointer',
                    padding: '2px 6px',
                    fontSize: '0.7rem',
                    lineHeight: 1,
                    marginTop: '2px',
                  }}
                >
                  &#x1F4CC;
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── MiniCardList → Insight Cards ─────────────────────────

function MiniCardList({ data, config }: SubRendererProps) {
  const [expandedCards, setExpandedCards] = React.useState<Set<number>>(new Set());
  const [hoveredIdx, setHoveredIdx] = React.useState<number | null>(null);
  const { tokens } = useDesignTokens();

  // Capture mode support (threaded from AccordionRenderer)
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  if (!data || !Array.isArray(data)) return null;
  const so = getSO(config);

  const firstObj = data.find(d => typeof d === 'object' && d !== null) as Record<string, unknown> | undefined;
  const auto = firstObj ? autoDetectFields(firstObj) : {};
  const titleField = resolveField(config, 'title_field', auto, 'title');
  const subtitleField = resolveField(config, 'subtitle_field', auto, 'subtitle');
  const badgeField = resolveField(config, 'badge_field', auto, 'badge');
  const descriptionField = resolveField(config, 'description_field', auto, 'description');

  // Hero card is opt-in: set hero:true in config to enable the hero pattern
  const useHero = config.hero === true;

  // Determine hero card: highest significance/importance/priority, or first
  const SIGNIFICANCE_KEYS = ['significance', 'importance', 'priority', 'weight', 'relevance'];
  let heroIdx = useHero ? 0 : -1;
  if (useHero && data.length > 1 && firstObj) {
    const sigField = Object.keys(firstObj).find(k => SIGNIFICANCE_KEYS.includes(k));
    if (sigField) {
      let maxVal = -Infinity;
      data.forEach((item, i) => {
        if (typeof item === 'object' && item !== null) {
          const val = getNumField(item as Record<string, unknown>, sigField);
          if (val !== null && val > maxVal) { maxVal = val; heroIdx = i; }
        }
      });
    }
  }

  const toggleExpand = (idx: number) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const DESC_TRUNCATE_LEN = Infinity; // Show full text — no truncation

  const renderCard = (item: unknown, idx: number, isHero: boolean) => {
    if (typeof item !== 'object' || item === null) return null;
    const obj = item as Record<string, unknown>;

    const title = getField(obj, titleField);
    const subtitle = getField(obj, subtitleField);
    const badge = getField(obj, badgeField);
    const description = getField(obj, descriptionField);

    const shownFields = new Set([titleField, subtitleField, badgeField, descriptionField]);
    const remaining = Object.entries(obj).filter(
      ([k, v]) => !shownFields.has(k) && v !== null && v !== undefined && v !== ''
    );
    const chipFields = remaining.filter(([, v]) => Array.isArray(v) && (v as unknown[]).every(x => typeof x === 'string'));
    const scalarFields = remaining.filter(([, v]) => !Array.isArray(v) || !(v as unknown[]).every(x => typeof x === 'string'));

    const seriesColor = tokens.primitives.series_palette[idx % tokens.primitives.series_palette.length];
    const colors = {
      headerBg: seriesColor,
      headerText: tokens.surfaces.text_on_accent,
      accent: seriesColor,
      lightBg: tokens.surfaces.surface_alt,
      darkText: tokens.surfaces.text_default,
      border: tokens.surfaces.border_default,
    };
    const isHovered = hoveredIdx === idx;
    const isContentExpanded = expandedCards.has(idx);
    const needsTruncation = !isHero && description.length > DESC_TRUNCATE_LEN;

    return (
      <div
        key={idx}
        onMouseEnter={() => setHoveredIdx(idx)}
        onMouseLeave={() => setHoveredIdx(null)}
        style={{
          borderRadius: 'var(--radius-md, 8px)',
          overflow: 'hidden',
          borderLeft: `4px solid ${colors.accent}`,
          border: `1px solid var(--color-border, #e2e5e9)`,
          borderLeftWidth: '4px',
          borderLeftColor: colors.accent,
          boxShadow: isHovered
            ? 'var(--shadow-md, 0 4px 6px rgba(0,0,0,0.05))'
            : 'var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06))',
          transform: isHovered ? 'translateY(-2px)' : 'none',
          transition: `box-shadow var(--duration-fast, 150ms) var(--ease-out, ease), transform var(--duration-fast, 150ms) var(--ease-out, ease)`,
          backgroundColor: 'var(--color-surface, #ffffff)',
          ...(isHero ? so?.hero_card : {}),
          ...so?.card,
        }}
      >
        {/* Header bar */}
        <div style={{
          padding: isHero
            ? 'var(--space-md, 1rem) var(--space-lg, 1.5rem)'
            : 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
          display: 'flex', alignItems: 'center', gap: 'var(--space-sm, 0.5rem)', flexWrap: 'wrap',
          ...so?.card_header,
        }}>
          {title && (
            <strong style={{
              fontSize: isHero
                ? 'var(--type-heading, 1.375rem)'
                : 'var(--type-body, 0.9375rem)',
              fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
              color: 'var(--color-text, #1a1d23)',
              lineHeight: 'var(--leading-tight, 1.2)',
            }}>
              {title}
            </strong>
          )}
          {subtitle && (
            <span style={{
              fontSize: 'var(--type-label, 0.6875rem)',
              fontWeight: 'var(--weight-medium, 500)' as unknown as number,
              color: colors.headerBg,
              padding: '2px 10px',
              borderRadius: 'var(--radius-pill, 9999px)',
              backgroundColor: colors.lightBg,
              letterSpacing: '0.02em',
              ...so?.badge,
            }}>{subtitle}</span>
          )}
          {badge && (
            <span style={{
              fontSize: 'var(--type-label, 0.6875rem)',
              fontWeight: 'var(--weight-bold, 700)' as unknown as number,
              padding: '2px 8px',
              borderRadius: 'var(--radius-pill, 9999px)',
              backgroundColor: colors.lightBg,
              color: colors.darkText,
              marginLeft: 'auto',
              ...so?.badge,
            }}>
              {badge}
            </span>
          )}
          {captureMode && onCapture && (
            <button
              title="Capture this card"
              onClick={e => {
                e.stopPropagation();
                onCapture({
                  source_view_key: captureViewKey || '',
                  source_item_index: idx,
                  source_renderer_type: 'mini_card_list',
                  content_type: 'card',
                  selected_text: `${title}: ${description}`.slice(0, 500),
                  structured_data: obj,
                  context_title: parentSectionKey
                    ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${title || `Card ${idx + 1}`}`
                    : `${captureViewKey || 'Analysis'} > ${title || `Card ${idx + 1}`}`,
                  source_type: (captureSourceType || 'analysis') as string,
                  entity_id: captureEntityId || captureJobId || '',
                  depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
                  parent_context: parentSectionKey ? {
                    section_key: parentSectionKey,
                    section_title: parentSectionTitle || '',
                  } : undefined,
                });
              }}
              style={{
                background: 'none',
                border: '1px solid var(--color-border, #ccc)',
                borderRadius: '4px',
                color: 'var(--dt-text-faint, #94a3b8)',
                cursor: 'pointer',
                padding: '2px 6px',
                fontSize: '0.7rem',
                lineHeight: 1,
                marginLeft: badge ? '0' : 'auto',
              }}
            >
              &#x1F4CC;
            </button>
          )}
        </div>

        {/* Description body */}
        {description && (
          <div style={{
            padding: isHero
              ? '0 var(--space-lg, 1.5rem) var(--space-md, 1rem)'
              : '0 var(--space-md, 1rem) var(--space-sm, 0.5rem)',
            ...so?.card_body,
          }}>
            <p style={{
              fontSize: isHero
                ? 'var(--type-body, 0.9375rem)'
                : 'var(--type-caption, 0.8125rem)',
              color: 'var(--color-text, #1a1d23)',
              lineHeight: 'var(--leading-relaxed, 1.65)',
              margin: 0,
              ...so?.prose,
            }}>
              {needsTruncation && !isContentExpanded
                ? description.slice(0, DESC_TRUNCATE_LEN) + '...'
                : description}
            </p>
            {needsTruncation && (
              <button
                className="gen-show-more-link"
                onClick={(e) => { e.stopPropagation(); toggleExpand(idx); }}
                style={{
                  marginTop: 'var(--space-xs, 0.25rem)',
                }}
              >
                {isContentExpanded ? 'show less' : 'show more'}
              </button>
            )}
          </div>
        )}

        {/* Scalar fields */}
        {scalarFields.length > 0 && (
          <div style={{
            padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
            backgroundColor: 'var(--color-surface-alt, #f8f9fa)',
            borderTop: '1px solid var(--color-border-light, #eef0f2)',
          }}>
            {scalarFields.map(([key, value]) => (
              <div key={key} style={{ marginBottom: 'var(--space-2xs, 0.25rem)' }}>
                <span className="gen-inline-label">
                  {key.replace(/_/g, ' ')}:
                </span>
                <span style={{
                  marginLeft: 'var(--space-xs, 0.375rem)',
                  fontSize: 'var(--type-caption, 0.8125rem)',
                  color: 'var(--color-text-muted, #6b7280)',
                }}>
                  {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Chip fields */}
        {chipFields.length > 0 && (
          <div style={{
            padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
            backgroundColor: colors.lightBg,
            borderTop: '1px solid var(--color-border-light, #eef0f2)',
          }}>
            {chipFields.map(([key, value]) => (
              <div key={key} style={{ marginBottom: 'var(--space-xs, 0.375rem)' }}>
                <span className="gen-inline-label" style={{
                  display: 'block',
                  marginBottom: 'var(--space-2xs, 0.25rem)',
                }}>
                  {key.replace(/_/g, ' ')}
                </span>
                <div style={{ display: 'flex', gap: 'var(--space-xs, 0.25rem)', flexWrap: 'wrap' }}>
                  {(value as string[]).map((v, vi) => (
                    <span key={vi} className="gen-keyword-tag">{String(v)}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // Single card → render as hero only if hero mode enabled
  if (data.length === 1) {
    return (
      <div style={{ ...so?.items_container }}>
        {renderCard(data[0], 0, useHero)}
      </div>
    );
  }

  // Default: uniform grid layout
  if (!useHero) {
    return (
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 'var(--space-md, 1rem)',
        ...so?.items_container,
      }}>
        {data.map((item, i) => renderCard(item, i, false))}
      </div>
    );
  }

  // Multi-card layout: hero on top, rest in 2-column grid
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      gap: 'var(--space-md, 1rem)',
      ...so?.items_container,
    }}>
      {renderCard(data[heroIdx], heroIdx, true)}

      {data.length > 1 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 'var(--space-md, 1rem)',
        }}>
          {data.map((item, i) => {
            if (i === heroIdx) return null;
            return renderCard(item, i, false);
          })}
        </div>
      )}
    </div>
  );
}

// ── KeyValueTable ────────────────────────────────────────

function KeyValueTable({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  const so = getSO(config);

  const firstObj = Array.isArray(data)
    ? data.find(d => typeof d === 'object' && d !== null) as Record<string, unknown> | undefined
    : undefined;
  const auto = firstObj ? autoDetectFields(firstObj) : {};
  const keyField = resolveField(config, 'key_field', auto, 'key');
  const valueField = resolveField(config, 'value_field', auto, 'value');

  let rows: Array<{ key: string; value: string }> = [];

  if (Array.isArray(data)) {
    rows = data.map(item => {
      if (typeof item !== 'object' || item === null) return { key: '', value: String(item) };
      const obj = item as Record<string, unknown>;
      return {
        key: getField(obj, keyField) || Object.keys(obj)[0] || '',
        value: getField(obj, valueField) || String(Object.values(obj).find(v => typeof v === 'string' && v.length > 20) ?? Object.values(obj)[1] ?? ''),
      };
    });
  } else if (typeof data === 'object' && data !== null) {
    rows = Object.entries(data as Record<string, unknown>).map(([k, v]) => ({
      key: k,
      value: typeof v === 'object' ? JSON.stringify(v) : String(v ?? ''),
    }));
  }

  if (rows.length === 0) return null;

  const isNumeric = (val: string) => /^[\d,.]+%?$/.test(val.trim());

  return (
    <div style={{
      borderRadius: 'var(--radius-md, 8px)',
      overflow: 'hidden',
      border: '1px solid var(--color-border, #e2e5e9)',
      boxShadow: 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
      ...so?.card,
    }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} style={{
              backgroundColor: i % 2 === 0
                ? 'var(--color-surface, #ffffff)'
                : 'var(--color-surface-alt, #f8f9fa)',
            }}>
              <td style={{
                padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
                fontSize: 'var(--type-label, 0.6875rem)',
                fontWeight: 'var(--weight-medium, 500)' as unknown as number,
                color: tokens.surfaces.text_default,
                width: '30%', verticalAlign: 'top',
                textTransform: 'capitalize' as const,
                letterSpacing: '0.02em',
                borderRight: `2px solid ${tokens.surfaces.border_accent}`,
                backgroundColor: i % 2 === 0
                  ? tokens.surfaces.surface_alt
                  : tokens.surfaces.surface_inset,
                ...so?.stat_label,
              }}>
                {row.key.replace(/_/g, ' ')}
              </td>
              <td style={{
                padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
                fontSize: 'var(--type-body, 0.9375rem)',
                fontWeight: isNumeric(row.value)
                  ? ('var(--weight-semibold, 600)' as unknown as number)
                  : ('var(--weight-normal, 400)' as unknown as number),
                fontFamily: isNumeric(row.value) ? 'var(--font-mono, monospace)' : 'inherit',
                color: 'var(--color-text, #1a1d23)',
                lineHeight: 'var(--leading-normal, 1.5)',
                ...(isNumeric(row.value) ? so?.stat_number : {}),
              }}>
                {row.value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── ProseBlock → Formatted Analysis ─────────────────────

interface ProseSegment {
  type: 'paragraph' | 'blockquote' | 'hr' | 'heading';
  content: string;
  level?: number;
}

function parseProseContent(text: string): ProseSegment[] {
  const lines = text.split('\n');
  const segments: ProseSegment[] = [];
  let currentParagraph: string[] = [];
  let currentBlockquote: string[] = [];

  function flushParagraph() {
    if (currentParagraph.length > 0) {
      const joined = currentParagraph.join(' ').trim();
      if (joined) segments.push({ type: 'paragraph', content: joined });
      currentParagraph = [];
    }
  }

  function flushBlockquote() {
    if (currentBlockquote.length > 0) {
      const joined = currentBlockquote.join(' ').trim();
      if (joined) segments.push({ type: 'blockquote', content: joined });
      currentBlockquote = [];
    }
  }

  for (const line of lines) {
    const trimmed = line.trim();

    if (/^(---+|\*\*\*+)$/.test(trimmed)) {
      flushParagraph();
      flushBlockquote();
      segments.push({ type: 'hr', content: '' });
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)/);
    if (headingMatch) {
      flushParagraph();
      flushBlockquote();
      segments.push({ type: 'heading', content: headingMatch[2], level: headingMatch[1].length });
      continue;
    }

    if (trimmed.startsWith('>')) {
      flushParagraph();
      currentBlockquote.push(trimmed.replace(/^>\s*/, ''));
      continue;
    }

    if (!trimmed) {
      flushBlockquote();
      flushParagraph();
      continue;
    }

    flushBlockquote();
    currentParagraph.push(trimmed);
  }

  flushParagraph();
  flushBlockquote();

  return segments;
}

function ProseBlock({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  const so = getSO(config);
  if (!data) return null;

  const text = typeof data === 'string'
    ? data
    : typeof data === 'object' && data !== null
      ? Object.values(data).filter(v => typeof v === 'string').join('\n\n')
      : String(data);

  if (!text.trim()) return null;

  const accentHex = so?.accent_color || tokens.components.page_accent;
  const segments = parseProseContent(text);

  let paragraphIndex = 0;

  return (
    <div style={{
      fontSize: 'var(--type-body, 0.9375rem)',
      lineHeight: 'var(--leading-relaxed, 1.65)',
      color: 'var(--color-text, #1a1d23)',
      ...so?.prose,
    }}>
      {segments.map((segment, i) => {
        if (segment.type === 'hr') {
          return (
            <hr key={i} style={{
              border: 'none',
              height: '1px',
              backgroundColor: 'var(--color-border, #e2e5e9)',
              margin: 'var(--space-lg, 1.5rem) var(--space-xl, 2rem)',
            }} />
          );
        }

        if (segment.type === 'heading') {
          const headingSizes: Record<number, string> = {
            1: 'var(--type-heading, 1.375rem)',
            2: 'var(--type-subheading, 1.125rem)',
            3: 'var(--type-body, 0.9375rem)',
          };
          return (
            <p key={i} style={{
              fontSize: headingSizes[segment.level || 3],
              fontWeight: 'var(--weight-bold, 700)' as unknown as number,
              color: tokens.surfaces.text_default,
              marginTop: 'var(--space-lg, 1.5rem)',
              marginBottom: 'var(--space-sm, 0.5rem)',
              lineHeight: 'var(--leading-tight, 1.2)',
            }}>
              {segment.content}
            </p>
          );
        }

        if (segment.type === 'blockquote') {
          return (
            <blockquote key={i} style={{
              margin: 'var(--space-md, 1rem) 0',
              padding: 'var(--space-md, 1rem) var(--space-lg, 1.5rem)',
              borderLeft: `4px solid ${accentHex}`,
              backgroundColor: tokens.components.prose_blockquote_bg,
              borderRadius: '0 var(--radius-md, 8px) var(--radius-md, 8px) 0',
              fontStyle: 'italic',
              color: 'var(--color-text-muted, #6b7280)',
              lineHeight: 'var(--leading-loose, 1.8)',
              ...so?.prose_quote,
            }}>
              {renderInlineMarkdown(segment.content, accentHex)}
            </blockquote>
          );
        }

        // Paragraph: first paragraph is lede
        const isLede = paragraphIndex === 0;
        paragraphIndex++;

        if (isLede) {
          return (
            <p key={i} style={{
              fontSize: 'var(--type-subheading, 1.125rem)',
              fontWeight: 'var(--weight-medium, 500)' as unknown as number,
              lineHeight: 'var(--leading-snug, 1.35)',
              color: 'var(--color-text, #1a1d23)',
              marginTop: 0,
              marginBottom: 'var(--space-md, 1rem)',
              ...so?.prose_lede,
            }}>
              {renderInlineMarkdown(segment.content, accentHex)}
            </p>
          );
        }

        return (
          <p key={i} style={{
            fontSize: 'var(--type-body, 0.9375rem)',
            fontWeight: 'var(--weight-normal, 400)' as unknown as number,
            lineHeight: 'var(--leading-relaxed, 1.65)',
            color: 'var(--color-text, #1a1d23)',
            marginTop: 0,
            marginBottom: 'var(--space-md, 1rem)',
            ...so?.prose_body,
          }}>
            {renderInlineMarkdown(segment.content, accentHex)}
          </p>
        );
      })}
    </div>
  );
}

// ── StatRow ──────────────────────────────────────────────

function StatRow({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  if (!data || typeof data !== 'object') return null;
  const so = getSO(config);

  const obj = data as Record<string, unknown>;
  const entries = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined);

  if (entries.length === 0) return null;

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: `repeat(${Math.min(entries.length, 4)}, 1fr)`,
      gap: 'var(--space-md, 0.75rem)',
      ...so?.items_container,
    }}>
      {entries.map(([key, value]) => (
        <div key={key} style={{
          padding: 'var(--space-md, 1rem)',
          borderRadius: 'var(--radius-md, 8px)',
          backgroundColor: 'var(--color-surface, #ffffff)',
          border: '1px solid var(--color-border-light, #eef0f2)',
          boxShadow: 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
          textAlign: 'center' as const,
          ...so?.card,
        }}>
          <div style={{
            fontSize: 'var(--type-number, 1.25rem)',
            fontFamily: 'var(--font-mono, monospace)',
            fontWeight: 'var(--weight-bold, 700)' as unknown as number,
            color: tokens.components.stat_number_color,
            lineHeight: 'var(--leading-tight, 1.2)',
            ...so?.stat_number,
          }}>
            {typeof value === 'number' ? value.toLocaleString() : String(value)}
          </div>
          <div className="gen-inline-label" style={{
            marginTop: 'var(--space-xs, 0.25rem)',
            ...so?.stat_label,
          }}>
            {key.replace(/_/g, ' ')}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── ComparisonPanel ──────────────────────────────────────

function ComparisonPanel({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  if (!data || !Array.isArray(data)) return null;
  const so = getSO(config);

  // Capture mode support (threaded from AccordionRenderer)
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  const firstObj = data.find(d => typeof d === 'object' && d !== null) as Record<string, unknown> | undefined;
  const longStrings = firstObj
    ? Object.entries(firstObj).filter(([, v]) => typeof v === 'string' && (v as string).length > 20).map(([k]) => k)
    : [];
  const leftField = (config.left_field as string | undefined) || longStrings[0];
  const rightField = (config.right_field as string | undefined) || longStrings[1];

  const leftLabel = leftField ? leftField.replace(/_/g, ' ') : 'Left';
  const rightLabel = rightField ? rightField.replace(/_/g, ' ') : 'Right';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      gap: 'var(--space-md, 0.75rem)',
      ...so?.items_container,
    }}>
      {/* Column headers */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1px' }}>
        <div style={{
          padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
          backgroundColor: tokens.primitives.series_palette[0],
          color: tokens.surfaces.text_on_accent,
          fontSize: 'var(--type-caption, 0.8125rem)',
          fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
          borderRadius: 'var(--radius-md, 8px) 0 0 0',
          ...so?.card_header,
        }}>
          {leftLabel}
        </div>
        <div style={{
          padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
          backgroundColor: tokens.primitives.series_palette[1],
          color: 'var(--dt-text-inverse)',
          fontSize: 'var(--type-caption, 0.8125rem)',
          fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
          textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
          borderRadius: '0 var(--radius-md, 8px) 0 0',
          ...so?.card_header,
        }}>
          {rightLabel}
        </div>
      </div>

      {data.map((item, i) => {
        if (typeof item !== 'object' || item === null) return null;
        const obj = item as Record<string, unknown>;

        const left = getField(obj, leftField);
        const right = getField(obj, rightField);

        const otherFields = Object.entries(obj).filter(
          ([k, v]) => k !== leftField && k !== rightField && v !== null && v !== undefined && v !== ''
        );

        // Build a label for this comparison row
        const rowLabel = otherFields.length > 0
          ? otherFields.map(([k, v]) => `${k.replace(/_/g, ' ')}: ${String(v)}`).join(', ')
          : `Row ${i + 1}`;

        return (
          <div key={i} style={{
            borderRadius: 'var(--radius-md, 8px)',
            border: '1px solid var(--color-border, #e2e5e9)',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
          }}>
            {/* Header bar with other fields + capture button */}
            {(otherFields.length > 0 || (captureMode && onCapture)) && (
              <div style={{
                padding: 'var(--space-xs, 0.375rem) var(--space-md, 0.75rem)',
                backgroundColor: 'var(--color-surface-alt, #f8f9fa)',
                fontSize: 'var(--type-label, 0.6875rem)',
                color: 'var(--color-text-muted, #6b7280)',
                borderBottom: '1px solid var(--color-border-light, #eef0f2)',
                display: 'flex', gap: 'var(--space-sm, 0.5rem)', flexWrap: 'wrap',
                alignItems: 'center',
              }}>
                {otherFields.map(([k, v]) => (
                  <span key={k}>
                    <strong style={{ textTransform: 'capitalize' as const }}>{k.replace(/_/g, ' ')}</strong>: {String(v)}
                  </span>
                ))}
                {captureMode && onCapture && (
                  <button
                    title="Capture this comparison"
                    onClick={e => {
                      e.stopPropagation();
                      onCapture({
                        source_view_key: captureViewKey || '',
                        source_section_key: parentSectionKey,
                        source_item_index: i,
                        source_renderer_type: 'comparison_panel',
                        content_type: 'item',
                        selected_text: `${leftLabel}: ${left || '—'} vs ${rightLabel}: ${right || '—'}`.slice(0, 500),
                        structured_data: obj,
                        context_title: parentSectionKey
                          ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${rowLabel}`
                          : `${captureViewKey || 'Analysis'} > ${rowLabel}`,
                        source_type: (captureSourceType || 'analysis') as string,
                      entity_id: captureEntityId || captureJobId || '',
                        depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
                        parent_context: parentSectionKey ? {
                          section_key: parentSectionKey,
                          section_title: parentSectionTitle || '',
                        } : undefined,
                      });
                    }}
                    style={{
                      marginLeft: 'auto',
                      flexShrink: 0,
                      background: 'none',
                      border: '1px solid var(--color-border, #ccc)',
                      borderRadius: '4px',
                      color: 'var(--dt-text-faint, #94a3b8)',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.7rem',
                      lineHeight: 1,
                    }}
                  >
                    &#x1F4CC;
                  </button>
                )}
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr' }}>
              <div style={{
                padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
                fontSize: 'var(--type-body, 0.9375rem)',
                color: 'var(--color-text, #1a1d23)',
                lineHeight: 'var(--leading-normal, 1.5)',
                ...so?.card_body,
              }}>
                {left || <span style={{ color: 'var(--color-text-faint, #9ca3af)', fontStyle: 'italic' }}>—</span>}
              </div>
              {/* Vertical divider */}
              <div style={{
                width: '2px',
                background: `linear-gradient(to bottom, ${tokens.surfaces.border_light}, ${tokens.surfaces.border_accent}, ${tokens.surfaces.border_light})`,
              }} />
              <div style={{
                padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
                fontSize: 'var(--type-body, 0.9375rem)',
                color: 'var(--color-text, #1a1d23)',
                lineHeight: 'var(--leading-normal, 1.5)',
                ...so?.card_body,
              }}>
                {right || <span style={{ color: 'var(--color-text-faint, #9ca3af)', fontStyle: 'italic' }}>—</span>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── TimelineStrip → Evolution Arc ────────────────────────

function TimelineStrip({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  const so = getSO(config);
  const [expandedCard, setExpandedCard] = React.useState<string | null>(null);
  if (!data || !Array.isArray(data)) return null;

  // TimelineStrip uses HSL-derived progressive coloring for evolution arcs.
  // Derive accent HSL from the token system's accent color.
  const accent = parseAccentHSL(so?.accent_color || tokens.components.page_accent);

  const firstObj = data.find(d => typeof d === 'object' && d !== null) as Record<string, unknown> | undefined;
  const auto = firstObj ? autoDetectFields(firstObj) : {};
  const labelField = resolveField(config, 'label_field', auto, 'label');
  const stagesField = (config.stages_field as string | undefined)
    || (firstObj ? Object.entries(firstObj).find(([, v]) => Array.isArray(v))?.[0] : undefined);

  function renderStageNode(stage: unknown, j: number, totalStages: number) {
    // Visual progression: size and saturation increase from left to right
    const progress = totalStages > 1 ? j / (totalStages - 1) : 0.5;
    const saturation = Math.max(accent.s * 0.3, 12) + progress * 30;
    const bgLightness = 96 - progress * 8;
    const textLightness = 30 - progress * 10;
    const borderSat = Math.max(accent.s * 0.4, 15) + progress * 20;

    // Size increases with progress
    const padV = `${0.4 + progress * 0.3}rem`;
    const padH = `${0.6 + progress * 0.4}rem`;
    const fontSize = progress > 0.6
      ? 'var(--type-caption, 0.8125rem)'
      : 'var(--type-label, 0.6875rem)';

    if (typeof stage === 'string') {
      return (
        <div style={{
          padding: `${padV} ${padH}`,
          borderRadius: 'var(--radius-md, 8px)',
          backgroundColor: `hsl(${accent.h}, ${saturation}%, ${bgLightness}%)`,
          border: `1.5px solid hsl(${accent.h}, ${borderSat}%, ${78 - progress * 10}%)`,
          fontSize,
          fontWeight: 'var(--weight-medium, 500)' as unknown as number,
          lineHeight: 'var(--leading-snug, 1.35)',
          color: `hsl(${accent.h}, ${Math.min(accent.s + 10, 75)}%, ${textLightness}%)`,
          minWidth: `${130 + progress * 40}px`,
          maxWidth: '280px',
          flexShrink: 0,
          boxShadow: 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
          ...so?.timeline_node,
        }}>
          {stage}
        </div>
      );
    }

    if (typeof stage === 'object' && stage !== null) {
      const obj = stage as Record<string, unknown>;
      const stageAuto = autoDetectFields(obj);
      const primaryLabel = getField(obj, 'form') || getField(obj, stageAuto.title)
        || getField(obj, 'label') || getField(obj, 'name');
      const periodLabel = getField(obj, 'period') || getField(obj, 'era') || getField(obj, 'date') || getField(obj, 'year');
      const secondaryFields = Object.entries(obj).filter(
        ([k, v]) => !['form', 'name', 'title', 'label', 'period', 'era', 'date', 'year'].includes(k)
          && typeof v === 'string' && (v as string).length > 0
      );

      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
          {/* Temporal marker above */}
          {periodLabel && (
            <div style={{
              fontSize: 'var(--type-label, 0.6875rem)',
              fontFamily: 'var(--font-mono, monospace)',
              fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
              color: `hsl(${accent.h}, ${Math.min(accent.s + 10, 70)}%, 45%)`,
              letterSpacing: '0.04em',
              marginBottom: 'var(--space-xs, 0.25rem)',
              textAlign: 'center' as const,
            }}>
              {periodLabel}
            </div>
          )}
          {/* Stage card */}
          <div style={{
            padding: `${padV} ${padH}`,
            borderRadius: 'var(--radius-md, 8px)',
            backgroundColor: `hsl(${accent.h}, ${saturation}%, ${bgLightness}%)`,
            border: `1.5px solid hsl(${accent.h}, ${borderSat}%, ${78 - progress * 10}%)`,
            fontSize,
            lineHeight: 'var(--leading-snug, 1.35)',
            color: `hsl(${accent.h}, ${Math.min(accent.s + 10, 75)}%, ${textLightness}%)`,
            minWidth: `${130 + progress * 40}px`,
            maxWidth: '280px',
            boxShadow: 'var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04))',
            ...so?.timeline_node,
          }}>
            <div style={{
              fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
              marginBottom: secondaryFields.length > 0 ? 'var(--space-2xs, 0.25rem)' : 0,
            }}>
              {primaryLabel || 'Stage ' + (j + 1)}
            </div>
            {secondaryFields.slice(0, 2).map(([k, v]) => (
              <div key={k} style={{
                fontSize: 'var(--type-label, 0.6875rem)',
                color: `hsl(${accent.h}, ${Math.max(accent.s * 0.5, 15)}%, ${40 - progress * 5}%)`,
                marginTop: 'var(--space-2xs, 0.15rem)',
              }}>
                <span className="gen-inline-label">
                  {k.replace(/_/g, ' ')}:
                </span>{' '}
                {String(v).length > 80 ? String(v).slice(0, 77) + '...' : String(v)}
              </div>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div style={{
        padding: `${padV} ${padH}`,
        borderRadius: 'var(--radius-md, 8px)',
        backgroundColor: `hsl(${accent.h}, ${saturation}%, ${bgLightness}%)`,
        border: `1px solid hsl(${accent.h}, ${borderSat}%, ${80 - progress * 8}%)`,
        fontSize: 'var(--type-label, 0.6875rem)',
        color: `hsl(${accent.h}, ${Math.min(accent.s + 10, 70)}%, ${textLightness}%)`,
        flexShrink: 0,
        ...so?.timeline_node,
      }}>
        {String(stage)}
      </div>
    );
  }

  /** Render the connecting arrow between stages with gradient */
  function renderConnector(j: number, totalStages: number) {
    const progress = totalStages > 1 ? j / (totalStages - 1) : 0;
    const nextProgress = totalStages > 1 ? (j + 1) / (totalStages - 1) : 1;
    const startLight = 82 - progress * 25;
    const endLight = 82 - nextProgress * 25;
    const startSat = Math.max(accent.s * 0.3, 12) + progress * 25;
    const endSat = Math.max(accent.s * 0.3, 12) + nextProgress * 25;

    return (
      <div style={{
        display: 'flex', alignItems: 'center',
        flexShrink: 0, padding: '0 2px',
        alignSelf: 'center',
        ...so?.timeline_connector,
      }}>
        <div style={{
          width: '24px', height: '3px',
          background: `linear-gradient(to right, hsl(${accent.h}, ${startSat}%, ${startLight}%), hsl(${accent.h}, ${endSat}%, ${endLight}%))`,
          borderRadius: '2px',
          position: 'relative' as const,
        }}>
          <div style={{
            position: 'absolute' as const, right: '-5px', top: '-4px',
            width: 0, height: 0,
            borderTop: '5.5px solid transparent',
            borderBottom: '5.5px solid transparent',
            borderLeft: `8px solid hsl(${accent.h}, ${endSat}%, ${endLight}%)`,
          }} />
        </div>
      </div>
    );
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      gap: 'var(--space-lg, 1.25rem)',
      ...so?.items_container,
    }}>
      {data.map((item, i) => {
        if (typeof item !== 'object' || item === null) return null;
        const obj = item as Record<string, unknown>;
        const label = getField(obj, labelField);
        const stages = stagesField ? obj[stagesField] : null;
        const cardId = `${label || i}`;
        const isExpanded = expandedCard === cardId;

        const metaFields = Object.entries(obj).filter(
          ([k, v]) => k !== labelField && k !== stagesField && v !== null && v !== undefined && v !== ''
        );

        return (
          <div key={i} style={{
            minWidth: 0, overflow: 'hidden',
            borderRadius: 'var(--radius-lg, 12px)',
            border: '1px solid var(--color-border, #e2e5e9)',
            backgroundColor: 'var(--color-surface, #ffffff)',
            boxShadow: 'var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.06))',
            ...so?.card,
          }}>
            {/* Header */}
            {label && (
              <div
                onClick={() => setExpandedCard(isExpanded ? null : cardId)}
                style={{
                  fontSize: 'var(--type-body, 0.9375rem)',
                  fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
                  color: 'var(--color-text, #1a1d23)',
                  padding: 'var(--space-sm, 0.625rem) var(--space-md, 1rem)',
                  backgroundColor: 'var(--color-surface-alt, #f8f9fa)',
                  borderBottom: '1px solid var(--color-border-light, #eef0f2)',
                  cursor: metaFields.length > 0 ? 'pointer' : 'default',
                  display: 'flex', alignItems: 'center',
                  gap: 'var(--space-sm, 0.5rem)',
                  ...so?.card_header,
                }}>
                {label}
                {Array.isArray(stages) && (
                  <span style={{
                    fontSize: 'var(--type-label, 0.6875rem)',
                    fontWeight: 'var(--weight-medium, 500)' as unknown as number,
                    color: 'var(--color-text-faint, #9ca3af)',
                    backgroundColor: tokens.surfaces.surface_inset,
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    ...so?.badge,
                  }}>
                    {stages.length} stages
                  </span>
                )}
              </div>
            )}

            {/* Timeline strip */}
            {Array.isArray(stages) && stages.length > 0 && (
              <div style={{
                padding: 'var(--space-md, 0.75rem)',
                overflowX: 'auto' as const,
              }}>
                <div style={{
                  display: 'flex', alignItems: 'flex-end',
                  gap: 0,
                  minWidth: 'min-content',
                }}>
                  {stages.map((stage, j) => (
                    <React.Fragment key={j}>
                      {renderStageNode(stage, j, stages.length)}
                      {j < stages.length - 1 && renderConnector(j, stages.length)}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}

            {/* Expanded metadata */}
            {isExpanded && metaFields.length > 0 && (
              <div style={{
                padding: 'var(--space-sm, 0.625rem) var(--space-md, 1rem)',
                borderTop: '1px solid var(--color-border-light, #eef0f2)',
                backgroundColor: 'var(--color-surface, #ffffff)',
              }}>
                {metaFields.map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 'var(--space-2xs, 0.25rem)' }}>
                    <span className="gen-inline-label">
                      {k.replace(/_/g, ' ')}:
                    </span>
                    <span style={{
                      marginLeft: 'var(--space-xs, 0.375rem)',
                      fontSize: 'var(--type-caption, 0.8125rem)',
                      color: 'var(--color-text, #1a1d23)',
                    }}>
                      {typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Non-stage fallback */}
            {(!stages || !Array.isArray(stages) || stages.length === 0) && metaFields.length > 0 && (
              <div style={{
                padding: 'var(--space-sm, 0.625rem) var(--space-md, 1rem)',
                fontSize: 'var(--type-caption, 0.8125rem)',
                color: 'var(--color-text-muted, #6b7280)',
              }}>
                {metaFields.map(([k, v]) => (
                  <div key={k} style={{ marginBottom: 'var(--space-2xs, 0.25rem)' }}>
                    <strong style={{
                      textTransform: 'capitalize' as const,
                      fontSize: 'var(--type-label, 0.6875rem)',
                      color: 'var(--color-text-muted, #6b7280)',
                    }}>
                      {k.replace(/_/g, ' ')}:
                    </strong>{' '}
                    {typeof v === 'string' ? v : JSON.stringify(v)}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── IntensityMatrix → Dashboard-style Intensity Bars ────────
//
// Each row: title + category badge + horizontal bar + expandable description.
// Bars width proportional to ordinal intensity level. Sorted by intensity (highest first).
//
// Config:
//   title_field       — row title
//   subtitle_field    — category badge
//   intensity_field   — ordinal intensity value
//   intensity_scale   — ordered levels, e.g. ['low', 'medium', 'high']
//   description_field — expandable text
//   sort_by_intensity — sort by intensity descending (default true)

function IntensityMatrix({ data, config }: SubRendererProps) {
  const [expandedIdx, setExpandedIdx] = React.useState<Set<number>>(new Set());
  const { tokens, getSemanticColor } = useDesignTokens();

  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  if (!data || !Array.isArray(data) || data.length === 0) return null;

  const titleField = (config.title_field as string) || 'name';
  const subtitleField = (config.subtitle_field as string) || undefined;
  const intensityField = (config.intensity_field as string) || 'intensity';
  const descField = (config.description_field as string) || 'description';
  const sortByIntensity = config.sort_by_intensity !== false;

  // Build intensity scale from config or infer from data
  const configScale = config.intensity_scale as string[] | undefined;
  const intensityScale: string[] = configScale
    || (() => {
      const vals = new Set<string>();
      data.forEach(item => {
        if (typeof item === 'object' && item !== null) {
          const v = (item as Record<string, unknown>)[intensityField];
          if (typeof v === 'string') vals.add(v.toLowerCase());
        }
      });
      // Default ordering heuristic
      const ordered = ['rare', 'low', 'minimal', 'occasional', 'moderate', 'medium', 'frequent', 'significant', 'high', 'very_high', 'critical'];
      const found = ordered.filter(l => vals.has(l));
      return found.length > 0 ? found : Array.from(vals);
    })();

  // Map intensity value to 0–1 fraction
  const getIntensityFraction = (val: string): number => {
    const lower = val.toLowerCase().replace(/\s+/g, '_');
    const idx = intensityScale.findIndex(s => s.toLowerCase().replace(/\s+/g, '_') === lower);
    if (idx === -1) return 0.5;
    if (intensityScale.length <= 1) return 1;
    return (idx + 1) / intensityScale.length;
  };

  // Color for intensity bar — use semantic severity or series palette
  const getBarColor = (fraction: number): string => {
    const palette = tokens.primitives.series_palette;
    if (fraction >= 0.8) {
      const sem = getSemanticColor('severity', 'high');
      return sem?.bg || palette[0];
    }
    if (fraction >= 0.5) {
      const sem = getSemanticColor('severity', 'medium');
      return sem?.bg || palette[4];
    }
    const sem = getSemanticColor('severity', 'low');
    return sem?.bg || palette[2];
  };

  const getBarTextColor = (fraction: number): string => {
    if (fraction >= 0.8) {
      const sem = getSemanticColor('severity', 'high');
      return sem?.text || tokens.surfaces.text_default;
    }
    if (fraction >= 0.5) {
      const sem = getSemanticColor('severity', 'medium');
      return sem?.text || tokens.surfaces.text_default;
    }
    const sem = getSemanticColor('severity', 'low');
    return sem?.text || tokens.surfaces.text_default;
  };

  // Prepare and optionally sort items
  const items = data
    .map((item, origIdx) => {
      if (typeof item !== 'object' || item === null) return null;
      const obj = item as Record<string, unknown>;
      const intensityVal = getField(obj, intensityField);
      const fraction = getIntensityFraction(intensityVal);
      return { obj, origIdx, intensityVal, fraction };
    })
    .filter(Boolean) as Array<{
      obj: Record<string, unknown>;
      origIdx: number;
      intensityVal: string;
      fraction: number;
    }>;

  if (sortByIntensity) {
    items.sort((a, b) => b.fraction - a.fraction);
  }

  const toggleExpand = (idx: number) => {
    setExpandedIdx(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const DESC_LIMIT = Infinity; // Show full text — no truncation

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
      {items.map((item, displayIdx) => {
        const { obj, origIdx, intensityVal, fraction } = item;
        const title = getField(obj, titleField);
        const subtitle = subtitleField ? getField(obj, subtitleField) : '';
        const desc = getField(obj, descField);
        const isExpanded = expandedIdx.has(displayIdx);
        const needsTruncation = desc.length > DESC_LIMIT;
        const barColor = getBarColor(fraction);
        const barTextColor = getBarTextColor(fraction);
        const barWidth = Math.max(fraction * 100, 8); // minimum 8% for visibility

        return (
          <div
            key={origIdx}
            style={{
              backgroundColor: 'var(--color-surface, #ffffff)',
              borderLeft: `3px solid ${barColor}`,
              padding: '0',
              borderRadius: '0 var(--radius-sm, 4px) var(--radius-sm, 4px) 0',
            }}
          >
            {/* Main row */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr auto minmax(80px, 160px)',
                gap: 'var(--space-sm, 0.5rem)',
                alignItems: 'center',
                padding: 'var(--space-xs, 0.375rem) var(--space-md, 1rem)',
                cursor: desc ? 'pointer' : 'default',
              }}
              onClick={() => desc && toggleExpand(displayIdx)}
            >
              {/* Title + subtitle */}
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-sm, 0.5rem)', flexWrap: 'wrap', minWidth: 0 }}>
                <span style={{
                  fontWeight: 600,
                  fontSize: 'var(--type-body, 0.9375rem)',
                  color: 'var(--color-text, #1a1d23)',
                  lineHeight: 'var(--leading-snug, 1.4)',
                }}>
                  {title}
                </span>
                {subtitle && (
                  <span style={{
                    fontSize: 'var(--type-label, 0.6875rem)',
                    fontWeight: 500,
                    color: 'var(--color-text-muted, #6b7280)',
                    padding: '1px 8px',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    backgroundColor: 'var(--color-surface-alt, #f8f9fa)',
                    whiteSpace: 'nowrap',
                  }}>
                    {subtitle}
                  </span>
                )}
                {captureMode && onCapture && (
                  <button
                    title="Capture this item"
                    onClick={e => {
                      e.stopPropagation();
                      onCapture({
                        source_view_key: captureViewKey || '',
                        source_item_index: origIdx,
                        source_renderer_type: 'intensity_matrix',
                        content_type: 'item',
                        selected_text: `${title} [${intensityVal}]: ${desc}`.slice(0, 500),
                        structured_data: obj,
                        context_title: parentSectionKey
                          ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${title}`
                          : `${captureViewKey || 'Analysis'} > ${title}`,
                        source_type: (captureSourceType || 'analysis') as string,
                        entity_id: captureEntityId || captureJobId || '',
                        depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
                        parent_context: parentSectionKey ? {
                          section_key: parentSectionKey,
                          section_title: parentSectionTitle || '',
                        } : undefined,
                      });
                    }}
                    style={{
                      background: 'none',
                      border: '1px solid var(--color-border, #ccc)',
                      borderRadius: '4px',
                      color: 'var(--dt-text-faint, #94a3b8)',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.7rem',
                      lineHeight: 1,
                    }}
                  >
                    &#x1F4CC;
                  </button>
                )}
              </div>

              {/* Intensity label */}
              <span style={{
                fontSize: 'var(--type-label, 0.6875rem)',
                fontWeight: 700,
                color: barTextColor,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
                whiteSpace: 'nowrap',
              }}>
                {intensityVal.replace(/_/g, ' ')}
              </span>

              {/* Intensity bar */}
              <div style={{
                height: '8px',
                backgroundColor: 'var(--color-surface-alt, #f0f1f3)',
                borderRadius: '4px',
                overflow: 'hidden',
              }}>
                <div style={{
                  width: `${barWidth}%`,
                  height: '100%',
                  backgroundColor: barColor,
                  borderRadius: '4px',
                  transition: 'width 300ms ease',
                }} />
              </div>
            </div>

            {/* Expandable description */}
            {desc && isExpanded && (
              <div style={{
                padding: '0 var(--space-md, 1rem) var(--space-sm, 0.5rem)',
                fontSize: 'var(--type-caption, 0.8125rem)',
                color: 'var(--color-text-muted, #6b7280)',
                lineHeight: 'var(--leading-relaxed, 1.65)',
                borderTop: '1px solid var(--color-border-light, #eef0f2)',
                marginTop: '2px',
                paddingTop: 'var(--space-xs, 0.375rem)',
              }}>
                {desc}
              </div>
            )}
            {desc && !isExpanded && needsTruncation && (
              <div style={{
                padding: '0 var(--space-md, 1rem) var(--space-xs, 0.25rem)',
                fontSize: 'var(--type-label, 0.6875rem)',
                color: 'var(--color-text-faint, #9ca3af)',
              }}>
                {desc.slice(0, DESC_LIMIT)}...
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── MoveRepertoire → Grouped Intellectual Gestures ──────────
//
// Items grouped by a category field. Each group has a colored header with
// count badge. Items within groups are compact rows. Groups are collapsible.
//
// Config:
//   title_field       — item title
//   group_field       — field to group by
//   description_field — item description
//   badge_field       — optional extra badge per item
//   collapse_groups   — start collapsed (default false)

function MoveRepertoire({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  const [collapsedGroups, setCollapsedGroups] = React.useState<Set<string>>(new Set());
  const [expandedDescs, setExpandedDescs] = React.useState<Set<string>>(new Set());
  const [initialized, setInitialized] = React.useState(false);

  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  if (!data || !Array.isArray(data) || data.length === 0) return null;

  const titleField = (config.title_field as string) || 'name';
  const groupField = (config.group_field as string) || 'type';
  const descField = (config.description_field as string) || 'description';
  const badgeField = (config.badge_field as string) || undefined;
  const startCollapsed = config.collapse_groups === true;

  // Group items
  const groups = new Map<string, Array<{ obj: Record<string, unknown>; origIdx: number }>>();
  data.forEach((item, idx) => {
    if (typeof item !== 'object' || item === null) return;
    const obj = item as Record<string, unknown>;
    const groupVal = getField(obj, groupField) || 'Other';
    if (!groups.has(groupVal)) groups.set(groupVal, []);
    groups.get(groupVal)!.push({ obj, origIdx: idx });
  });

  // Initialize collapsed state on first render with data
  if (!initialized && startCollapsed && groups.size > 0) {
    setCollapsedGroups(new Set(groups.keys()));
    setInitialized(true);
  }

  const toggleGroup = (group: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  const toggleDesc = (key: string) => {
    setExpandedDescs(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const palette = tokens.primitives.series_palette;
  const DESC_LIMIT = Infinity; // Show full text — no truncation

  const groupEntries = Array.from(groups.entries());

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md, 1rem)' }}>
      {groupEntries.map(([groupName, items], groupIdx) => {
        const isCollapsed = collapsedGroups.has(groupName);
        const groupColor = palette[groupIdx % palette.length];

        return (
          <div key={groupName} style={{
            borderRadius: 'var(--radius-md, 8px)',
            border: '1px solid var(--color-border, #e2e5e9)',
            overflow: 'hidden',
          }}>
            {/* Group header */}
            <div
              onClick={() => toggleGroup(groupName)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-sm, 0.5rem)',
                padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
                backgroundColor: groupColor,
                color: tokens.surfaces.text_on_accent,
                cursor: 'pointer',
                userSelect: 'none',
              }}
            >
              <span style={{
                fontSize: '11px',
                transition: 'transform 150ms ease',
                transform: isCollapsed ? 'rotate(-90deg)' : 'rotate(0deg)',
                display: 'inline-block',
              }}>
                &#9662;
              </span>
              <span style={{
                fontWeight: 600,
                fontSize: 'var(--type-body, 0.9375rem)',
                textTransform: 'capitalize',
              }}>
                {groupName.replace(/_/g, ' ')}
              </span>
              <span style={{
                marginLeft: 'auto',
                fontSize: 'var(--type-label, 0.6875rem)',
                fontWeight: 700,
                backgroundColor: 'rgba(255,255,255,0.25)',
                padding: '1px 8px',
                borderRadius: 'var(--radius-pill, 9999px)',
              }}>
                {items.length}
              </span>
            </div>

            {/* Group items */}
            {!isCollapsed && (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {items.map(({ obj, origIdx }, itemIdx) => {
                  const title = getField(obj, titleField);
                  const desc = getField(obj, descField);
                  const badge = badgeField ? getField(obj, badgeField) : '';
                  const descKey = `${groupName}-${itemIdx}`;
                  const isDescExpanded = expandedDescs.has(descKey);
                  const needsTruncation = desc.length > DESC_LIMIT;

                  return (
                    <div
                      key={itemIdx}
                      style={{
                        padding: 'var(--space-xs, 0.375rem) var(--space-md, 1rem)',
                        borderBottom: itemIdx < items.length - 1 ? '1px solid var(--color-border-light, #eef0f2)' : 'none',
                        backgroundColor: itemIdx % 2 === 0 ? 'var(--color-surface, #ffffff)' : 'var(--color-surface-alt, #fafbfc)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-sm, 0.5rem)', flexWrap: 'wrap' }}>
                        <span style={{
                          fontWeight: 600,
                          fontSize: 'var(--type-body, 0.9375rem)',
                          color: 'var(--color-text, #1a1d23)',
                          lineHeight: 'var(--leading-snug, 1.4)',
                        }}>
                          {title}
                        </span>
                        {badge && (
                          <span style={{
                            fontSize: 'var(--type-label, 0.6875rem)',
                            fontWeight: 500,
                            color: groupColor,
                            padding: '1px 8px',
                            borderRadius: 'var(--radius-pill, 9999px)',
                            backgroundColor: 'var(--color-surface-alt, #f8f9fa)',
                          }}>
                            {badge}
                          </span>
                        )}
                        {captureMode && onCapture && (
                          <button
                            title="Capture this item"
                            onClick={e => {
                              e.stopPropagation();
                              onCapture({
                                source_view_key: captureViewKey || '',
                                source_item_index: origIdx,
                                source_renderer_type: 'move_repertoire',
                                content_type: 'item',
                                selected_text: `[${groupName}] ${title}: ${desc}`.slice(0, 500),
                                structured_data: obj,
                                context_title: parentSectionKey
                                  ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${groupName} > ${title}`
                                  : `${captureViewKey || 'Analysis'} > ${groupName} > ${title}`,
                                source_type: (captureSourceType || 'analysis') as string,
                                entity_id: captureEntityId || captureJobId || '',
                                depth_level: 'L2_element',
                                parent_context: parentSectionKey ? {
                                  section_key: parentSectionKey,
                                  section_title: parentSectionTitle || '',
                                } : undefined,
                              });
                            }}
                            style={{
                              background: 'none',
                              border: '1px solid var(--color-border, #ccc)',
                              borderRadius: '4px',
                              color: 'var(--dt-text-faint, #94a3b8)',
                              cursor: 'pointer',
                              padding: '2px 6px',
                              fontSize: '0.7rem',
                              lineHeight: 1,
                              marginLeft: 'auto',
                            }}
                          >
                            &#x1F4CC;
                          </button>
                        )}
                      </div>
                      {desc && (
                        <div
                          style={{
                            marginTop: '2px',
                            fontSize: 'var(--type-caption, 0.8125rem)',
                            color: 'var(--color-text-muted, #6b7280)',
                            lineHeight: 'var(--leading-relaxed, 1.6)',
                            cursor: needsTruncation ? 'pointer' : 'default',
                          }}
                          onClick={() => needsTruncation && toggleDesc(descKey)}
                        >
                          {needsTruncation && !isDescExpanded
                            ? desc.slice(0, DESC_LIMIT) + '...'
                            : desc}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── DialecticalPair → Tension/Contrast Visualization ────────
//
// Two panels with a central tension indicator. Left = thesis/foregrounded,
// right = antithesis/suppressed. Central node shows relationship type.
//
// Config:
//   left_key, right_key         — field names or sub-section keys for left/right
//   left_label, right_label     — panel headers
//   relationship_label          — central node text (default "vs")
//   left_title_field, right_title_field — title fields within items
//   left_description_field, right_description_field — description fields

function DialecticalPair({ data, config }: SubRendererProps) {
  const { tokens } = useDesignTokens();
  const [expandedLeft, setExpandedLeft] = React.useState<Set<number>>(new Set());
  const [expandedRight, setExpandedRight] = React.useState<Set<number>>(new Set());

  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  const leftKey = (config.left_key as string) || 'left';
  const rightKey = (config.right_key as string) || 'right';
  const leftLabel = (config.left_label as string) || leftKey.replace(/_/g, ' ');
  const rightLabel = (config.right_label as string) || rightKey.replace(/_/g, ' ');
  const relationshipLabel = (config.relationship_label as string) || 'vs';

  const leftTitleField = (config.left_title_field as string) || undefined;
  const rightTitleField = (config.right_title_field as string) || undefined;
  const leftDescField = (config.left_description_field as string) || undefined;
  const rightDescField = (config.right_description_field as string) || undefined;

  // Resolve data shape: could be {left_key: [...], right_key: [...]} or [{left_field, right_field}, ...]
  let leftItems: Array<Record<string, unknown>> = [];
  let rightItems: Array<Record<string, unknown>> = [];

  if (data && typeof data === 'object' && !Array.isArray(data)) {
    // Object with left/right sub-arrays
    const obj = data as Record<string, unknown>;
    const rawLeft = obj[leftKey];
    const rawRight = obj[rightKey];
    if (Array.isArray(rawLeft)) leftItems = rawLeft.filter(x => typeof x === 'object' && x !== null) as Array<Record<string, unknown>>;
    if (Array.isArray(rawRight)) rightItems = rawRight.filter(x => typeof x === 'object' && x !== null) as Array<Record<string, unknown>>;
  } else if (Array.isArray(data)) {
    // Array of paired objects — split using left_key/right_key as field names
    data.forEach(item => {
      if (typeof item !== 'object' || item === null) return;
      const obj = item as Record<string, unknown>;
      // If fields exist, treat as paired data
      const leftVal = obj[leftKey];
      const rightVal = obj[rightKey];
      if (leftVal !== undefined || rightVal !== undefined) {
        leftItems.push({ text: leftVal, ...obj });
        rightItems.push({ text: rightVal, ...obj });
      }
    });
  }

  if (leftItems.length === 0 && rightItems.length === 0) return null;

  const palette = tokens.primitives.series_palette;
  const leftColor = palette[0];
  const rightColor = palette[1];
  const DESC_LIMIT = Infinity; // Show full text — no truncation

  const autoFindTitle = (obj: Record<string, unknown>, explicitField?: string): string => {
    if (explicitField && obj[explicitField]) return String(obj[explicitField]);
    for (const k of TITLE_HINTS) {
      if (obj[k] && typeof obj[k] === 'string') return String(obj[k]);
    }
    // Fallback: first short string
    const firstShort = Object.entries(obj).find(([, v]) => typeof v === 'string' && (v as string).length < 80);
    return firstShort ? String(firstShort[1]) : '';
  };

  const autoFindDesc = (obj: Record<string, unknown>, explicitField?: string): string => {
    if (explicitField && obj[explicitField]) return String(obj[explicitField]);
    for (const k of DESC_HINTS) {
      if (obj[k] && typeof obj[k] === 'string') return String(obj[k]);
    }
    // Fallback: longest string
    let longest = '';
    Object.values(obj).forEach(v => {
      if (typeof v === 'string' && v.length > longest.length) longest = v;
    });
    return longest;
  };

  const toggleLeft = (idx: number) => {
    setExpandedLeft(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };
  const toggleRight = (idx: number) => {
    setExpandedRight(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  const renderPanel = (
    items: Array<Record<string, unknown>>,
    side: 'left' | 'right',
    color: string,
    titleFieldOverride: string | undefined,
    descFieldOverride: string | undefined,
    expandedSet: Set<number>,
    toggleFn: (idx: number) => void,
  ) => (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      maxHeight: '400px',
      overflowY: 'auto',
    }}>
      {items.map((obj, idx) => {
        const title = autoFindTitle(obj, titleFieldOverride);
        const desc = autoFindDesc(obj, descFieldOverride);
        const isExpanded = expandedSet.has(idx);
        const needsTruncation = desc.length > DESC_LIMIT;

        return (
          <div
            key={idx}
            style={{
              padding: 'var(--space-xs, 0.375rem) var(--space-sm, 0.5rem)',
              borderBottom: idx < items.length - 1 ? '1px solid var(--color-border-light, #eef0f2)' : 'none',
              cursor: needsTruncation ? 'pointer' : 'default',
            }}
            onClick={() => needsTruncation && toggleFn(idx)}
          >
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 'var(--space-xs, 0.25rem)' }}>
              <span style={{
                fontWeight: 600,
                fontSize: 'var(--type-caption, 0.8125rem)',
                color: 'var(--color-text, #1a1d23)',
                lineHeight: 'var(--leading-snug, 1.4)',
              }}>
                {title}
              </span>
              {captureMode && onCapture && (
                <button
                  title={`Capture ${side} item`}
                  onClick={e => {
                    e.stopPropagation();
                    onCapture({
                      source_view_key: captureViewKey || '',
                      source_item_index: idx,
                      source_renderer_type: 'dialectical_pair',
                      content_type: 'item',
                      selected_text: `[${side === 'left' ? leftLabel : rightLabel}] ${title}: ${desc}`.slice(0, 500),
                      structured_data: obj,
                      context_title: parentSectionKey
                        ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${side === 'left' ? leftLabel : rightLabel} > ${title}`
                        : `${captureViewKey || 'Analysis'} > ${side === 'left' ? leftLabel : rightLabel} > ${title}`,
                      source_type: (captureSourceType || 'analysis') as string,
                      entity_id: captureEntityId || captureJobId || '',
                      depth_level: 'L2_element',
                      parent_context: parentSectionKey ? {
                        section_key: parentSectionKey,
                        section_title: parentSectionTitle || '',
                      } : undefined,
                    });
                  }}
                  style={{
                    background: 'none',
                    border: '1px solid var(--color-border, #ccc)',
                    borderRadius: '4px',
                    color: 'var(--dt-text-faint, #94a3b8)',
                    cursor: 'pointer',
                    padding: '2px 6px',
                    fontSize: '0.7rem',
                    lineHeight: 1,
                    marginLeft: 'auto',
                    flexShrink: 0,
                  }}
                >
                  &#x1F4CC;
                </button>
              )}
            </div>
            {desc && (
              <div style={{
                marginTop: '2px',
                fontSize: 'var(--type-label, 0.6875rem)',
                color: 'var(--color-text-muted, #6b7280)',
                lineHeight: 'var(--leading-relaxed, 1.6)',
              }}>
                {needsTruncation && !isExpanded
                  ? desc.slice(0, DESC_LIMIT) + '...'
                  : desc}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  return (
    <div style={{
      borderRadius: 'var(--radius-md, 8px)',
      border: '1px solid var(--color-border, #e2e5e9)',
      overflow: 'hidden',
    }}>
      {/* Column headers */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr' }}>
        <div style={{
          padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
          backgroundColor: leftColor,
          color: tokens.surfaces.text_on_accent,
          fontSize: 'var(--type-caption, 0.8125rem)',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          textAlign: 'center',
        }}>
          {leftLabel}
        </div>
        {/* Central tension node */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '0 var(--space-sm, 0.5rem)',
          backgroundColor: tokens.surfaces.surface_alt,
          position: 'relative',
        }}>
          <span style={{
            fontSize: 'var(--type-label, 0.6875rem)',
            fontWeight: 800,
            color: tokens.surfaces.text_muted,
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            padding: '2px 10px',
            borderRadius: 'var(--radius-pill, 9999px)',
            border: `2px solid ${tokens.surfaces.border_accent}`,
            backgroundColor: tokens.surfaces.surface_default,
            whiteSpace: 'nowrap',
          }}>
            {relationshipLabel}
          </span>
        </div>
        <div style={{
          padding: 'var(--space-sm, 0.5rem) var(--space-md, 1rem)',
          backgroundColor: rightColor,
          color: tokens.surfaces.text_on_accent,
          fontSize: 'var(--type-caption, 0.8125rem)',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          textAlign: 'center',
        }}>
          {rightLabel}
        </div>
      </div>

      {/* Panels */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr' }}>
        {renderPanel(leftItems, 'left', leftColor, leftTitleField, leftDescField, expandedLeft, toggleLeft)}
        {/* Vertical tension line */}
        <div style={{
          width: '3px',
          background: `linear-gradient(to bottom, ${leftColor}, ${tokens.surfaces.border_accent}, ${rightColor})`,
        }} />
        {renderPanel(rightItems, 'right', rightColor, rightTitleField, rightDescField, expandedRight, toggleRight)}
      </div>
    </div>
  );
}

// ── OrderedFlow → Sequential Content Units ───────────────
//
// Generic renderer for any ordered sequence of content units:
// chapters, argument steps, methodology phases, dialectical moves,
// policy stages, evidence links, etc.
//
// Config:
//   title_field       — primary label (auto-strips "Chapter N:" / "Step N:" prefixes)
//   subtitle_field    — category/role badge (colored by design token semantic lookup)
//   description_field — expandable detail text
//   number_field      — explicit numbering field (falls back to extracting from title or index)
//   strip_prefix      — regex to strip from title (default: /^(Chapter|Step|Phase|Stage)\s+\d+[.:]\s*/i)

function OrderedFlow({ data, config }: SubRendererProps) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);
  const { tokens, getCategoryColor } = useDesignTokens();

  if (!data || !Array.isArray(data) || data.length === 0) return null;

  const titleField = (config.title_field as string) || 'title';
  const subtitleField = (config.subtitle_field as string) || 'type';
  const descriptionField = (config.description_field as string) || 'description';
  const numberField = (config.number_field as string) || undefined;
  const stripPrefix = config.strip_prefix as string | undefined;

  const prefixRegex = stripPrefix
    ? new RegExp(stripPrefix, 'i')
    : /^(Chapter|Step|Phase|Stage|Part|Section|Move)\s+\d+[.:]\s*/i;

  const lineColor = tokens.surfaces?.border_default || '#e2e5e9';

  return (
    <div style={{ position: 'relative', paddingLeft: '36px' }}>
      {/* Vertical connecting line */}
      <div style={{
        position: 'absolute',
        left: '11px',
        top: '12px',
        bottom: '12px',
        width: '2px',
        backgroundColor: lineColor,
      }} />

      {data.map((item, idx) => {
        if (typeof item !== 'object' || item === null) return null;
        const obj = item as Record<string, unknown>;
        const title = getField(obj, titleField);
        const category = getField(obj, subtitleField);
        const categoryLower = category.toLowerCase();
        const desc = getField(obj, descriptionField);
        const isExpanded = expandedIdx === idx;
        const isLast = idx === data.length - 1;

        // Resolve step number: explicit field → extract from title → index
        let stepLabel: string;
        if (numberField && obj[numberField] !== undefined) {
          stepLabel = String(obj[numberField]);
        } else {
          const numMatch = title.match(/(\d+)/);
          stepLabel = numMatch ? numMatch[1] : String(idx + 1);
        }

        // Strip common prefixes for cleaner display
        const cleanTitle = title.replace(prefixRegex, '');

        // Color from design tokens: try categorical lookup, then series palette fallback
        const catColor = getCategoryColor?.(subtitleField, categoryLower);
        const dotColor = catColor?.text
          || tokens.primitives.series_palette[idx % tokens.primitives.series_palette.length];

        const DESC_LIMIT = Infinity; // Show full text — no truncation
        const needsTruncation = desc.length > DESC_LIMIT;
        const displayDesc = isExpanded || !needsTruncation
          ? desc
          : desc.slice(0, DESC_LIMIT) + '...';

        return (
          <div
            key={idx}
            onClick={() => needsTruncation && setExpandedIdx(isExpanded ? null : idx)}
            style={{
              position: 'relative',
              paddingBottom: isLast ? 0 : 'var(--space-xs, 0.375rem)',
              marginBottom: isLast ? 0 : 'var(--space-xs, 0.375rem)',
              cursor: needsTruncation ? 'pointer' : 'default',
            }}
          >
            {/* Step dot */}
            <div style={{
              position: 'absolute',
              left: '-36px',
              top: '2px',
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              backgroundColor: dotColor,
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '11px',
              fontWeight: 700,
              zIndex: 1,
              fontFamily: 'var(--font-mono, monospace)',
            }}>
              {stepLabel}
            </div>

            {/* Title + category */}
            <div style={{
              display: 'flex',
              alignItems: 'baseline',
              gap: 'var(--space-sm, 0.5rem)',
              flexWrap: 'wrap',
              lineHeight: 'var(--leading-snug, 1.4)',
            }}>
              <span style={{
                fontWeight: 600,
                fontSize: 'var(--type-body, 0.9375rem)',
                color: 'var(--color-text, #1a1d23)',
              }}>
                {cleanTitle}
              </span>

              {category && (
                <span style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                  color: dotColor,
                  opacity: 0.85,
                }}>
                  {category}
                </span>
              )}
            </div>

            {/* Description */}
            {desc && (
              <div style={{
                marginTop: '2px',
                fontSize: 'var(--type-caption, 0.8125rem)',
                color: 'var(--color-text-muted, #6b7280)',
                lineHeight: 'var(--leading-relaxed, 1.6)',
              }}>
                {displayDesc}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── RichDescriptionList → Readable Stacked Items ──────────
//
// Vertically-stacked list where each item gets room to breathe.
// Handles BOTH string arrays ("Label: description") and object arrays.
//
// Config:
//   title_field        — For object arrays: field name for label
//   description_field  — For object arrays: field name for description
//   separator          — For string arrays: split label from description (default ":")
//   max_visible_chars  — Auto-collapse longer descriptions (default 200)
//   badge_fields       — Optional extra fields to show as badges

function RichDescriptionList({ data, config }: SubRendererProps) {
  const [expandedIdx, setExpandedIdx] = React.useState<Set<number>>(new Set());
  const { tokens } = useDesignTokens();

  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  if (!data || !Array.isArray(data) || data.length === 0) return null;

  const titleField = config.title_field as string | undefined;
  const descriptionField = config.description_field as string | undefined;
  const separator = (config.separator as string) || ':';
  const maxChars = (config.max_visible_chars as number) || Infinity; // Show full text — no truncation
  const badgeFields = (config.badge_fields as string[]) || [];

  const palette = tokens.primitives.series_palette;

  // Parse items — handle string arrays and object arrays
  const items: Array<{ label: string; description: string; badges: string[]; raw: unknown }> = data.map(item => {
    if (typeof item === 'string') {
      // Parse "Label: description..." format
      const sepIdx = item.indexOf(separator);
      if (sepIdx > 0 && sepIdx < 60) {
        return {
          label: item.slice(0, sepIdx).trim(),
          description: item.slice(sepIdx + separator.length).trim(),
          badges: [],
          raw: item,
        };
      }
      // No separator found — use first ~40 chars as label
      const firstSpace = item.indexOf(' ', 30);
      if (firstSpace > 0) {
        return { label: item.slice(0, firstSpace), description: item.slice(firstSpace + 1), badges: [], raw: item };
      }
      return { label: item, description: '', badges: [], raw: item };
    }

    if (typeof item === 'object' && item !== null) {
      const obj = item as Record<string, unknown>;
      const label = titleField ? getField(obj, titleField) : '';
      const desc = descriptionField ? getField(obj, descriptionField) : '';
      const badges = badgeFields.map(f => getField(obj, f)).filter(Boolean);

      // If no explicit fields, auto-detect
      if (!label && !desc) {
        const auto = autoDetectFields(obj);
        return {
          label: auto.title ? getField(obj, auto.title) : '',
          description: auto.description ? getField(obj, auto.description) : '',
          badges,
          raw: item,
        };
      }
      return { label, description: desc, badges, raw: item };
    }

    return { label: String(item), description: '', badges: [], raw: item };
  });

  const toggleExpand = (idx: number) => {
    setExpandedIdx(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 0,
      borderRadius: 'var(--radius-md, 8px)',
      border: '1px solid var(--color-border, #e2e5e9)',
      overflow: 'hidden',
    }}>
      {items.map((item, idx) => {
        const color = palette[idx % palette.length];
        const isExpanded = expandedIdx.has(idx);
        const needsTruncation = item.description.length > maxChars;
        const isLast = idx === items.length - 1;

        return (
          <div
            key={idx}
            style={{
              display: 'flex',
              borderBottom: isLast ? 'none' : '1px solid var(--color-border-light, #eef0f2)',
            }}
          >
            {/* Colored left border */}
            <div style={{
              width: '4px',
              backgroundColor: color,
              flexShrink: 0,
            }} />

            {/* Content */}
            <div style={{
              flex: 1,
              padding: 'var(--space-sm, 0.75rem) var(--space-md, 1rem)',
            }}>
              {/* Header row: dot + label + count + capture */}
              <div style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 'var(--space-xs, 0.25rem)',
              }}>
                <span style={{
                  color,
                  fontSize: '14px',
                  lineHeight: 1,
                  flexShrink: 0,
                }}>●</span>
                <span style={{
                  fontWeight: 700,
                  fontSize: 'var(--type-caption, 0.8125rem)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.04em',
                  color: 'var(--color-text, #1a1d23)',
                  lineHeight: 'var(--leading-snug, 1.4)',
                }}>
                  {item.label || `Item ${idx + 1}`}
                </span>

                {/* Badges */}
                {item.badges.map((badge, bi) => (
                  <span key={bi} style={{
                    fontSize: '10px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.05em',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-pill, 9999px)',
                    backgroundColor: `${palette[(idx + bi + 1) % palette.length]}22`,
                    color: palette[(idx + bi + 1) % palette.length],
                  }}>
                    {badge}
                  </span>
                ))}

                {/* Count badge */}
                <span style={{
                  marginLeft: 'auto',
                  fontSize: '10px',
                  fontWeight: 500,
                  color: 'var(--dt-text-faint, #94a3b8)',
                  flexShrink: 0,
                }}>
                  [{idx + 1}/{items.length}]
                </span>

                {/* Capture button */}
                {captureMode && onCapture && (
                  <button
                    title="Capture this item"
                    onClick={e => {
                      e.stopPropagation();
                      onCapture({
                        source_view_key: captureViewKey || '',
                        source_item_index: idx,
                        source_renderer_type: 'rich_description_list',
                        content_type: 'item',
                        selected_text: `${item.label}: ${item.description}`.slice(0, 500),
                        structured_data: item.raw,
                        context_title: parentSectionKey
                          ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > ${item.label}`
                          : `${captureViewKey || 'Analysis'} > ${item.label}`,
                        source_type: (captureSourceType || 'analysis') as string,
                        entity_id: captureEntityId || captureJobId || '',
                        depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
                        parent_context: parentSectionKey ? {
                          section_key: parentSectionKey,
                          section_title: parentSectionTitle || '',
                        } : undefined,
                      });
                    }}
                    style={{
                      background: 'none',
                      border: '1px solid var(--color-border, #ccc)',
                      borderRadius: '4px',
                      color: 'var(--dt-text-faint, #94a3b8)',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.7rem',
                      lineHeight: 1,
                      flexShrink: 0,
                    }}
                  >
                    &#x1F4CC;
                  </button>
                )}
              </div>

              {/* Description */}
              {item.description && (
                <div style={{
                  marginTop: 'var(--space-2xs, 0.25rem)',
                  fontSize: 'var(--type-caption, 0.8125rem)',
                  color: 'var(--color-text-muted, #6b7280)',
                  lineHeight: 'var(--leading-relaxed, 1.6)',
                }}>
                  {needsTruncation && !isExpanded
                    ? item.description.slice(0, maxChars) + '...'
                    : item.description
                  }
                  {needsTruncation && (
                    <button
                      onClick={(e) => { e.stopPropagation(); toggleExpand(idx); }}
                      className="gen-show-more-link"
                      style={{
                        background: 'none',
                        border: 'none',
                        color,
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                        padding: '0 4px',
                        marginLeft: '4px',
                        fontWeight: 600,
                      }}
                    >
                      {isExpanded ? 'collapse ▴' : 'expand ▾'}
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── PhaseTimeline → Connected Phase Nodes ──────────────────
//
// Horizontal connected timeline with prominent phase nodes. Designed for
// temporal/sequential data stored as an OBJECT with a phases array and
// optional mode badge.
//
// Config:
//   phases_field      — key containing the phases array (default "phases")
//   label_field       — field within each phase for the label (default "label")
//   description_field — field within each phase for the description (default "description")
//   mode_field        — optional top-level field for a mode badge (default "mode")

function PhaseTimeline({ data, config }: SubRendererProps) {
  const [expandedIdx, setExpandedIdx] = React.useState<Set<number>>(new Set());
  const { tokens } = useDesignTokens();

  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as ((sel: CaptureSelection) => void) | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureSourceType = config._captureSourceType as string | undefined;
  const captureEntityId = config._captureEntityId as string | undefined;
  const parentSectionKey = config._parentSectionKey as string | undefined;
  const parentSectionTitle = config._parentSectionTitle as string | undefined;

  if (!data || typeof data !== 'object' || Array.isArray(data)) return null;

  const obj = data as Record<string, unknown>;
  const phasesField = (config.phases_field as string) || 'phases';
  const labelField = (config.label_field as string) || 'label';
  const descField = (config.description_field as string) || 'description';
  const modeField = (config.mode_field as string) || 'mode';

  const rawPhases = obj[phasesField];
  if (!Array.isArray(rawPhases) || rawPhases.length === 0) return null;

  const mode = obj[modeField] as string | undefined;
  const palette = tokens.primitives.series_palette;
  const DESC_LIMIT = Infinity; // Show full text — no truncation

  const phases = rawPhases
    .filter(p => typeof p === 'object' && p !== null)
    .map(p => p as Record<string, unknown>);

  const toggleExpand = (idx: number) => {
    setExpandedIdx(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  };

  return (
    <div>
      {/* Mode badge */}
      {mode && (
        <div style={{
          marginBottom: 'var(--space-sm, 0.75rem)',
          display: 'flex',
          justifyContent: 'center',
        }}>
          <span style={{
            fontSize: '10px',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            padding: '3px 12px',
            borderRadius: 'var(--radius-pill, 9999px)',
            backgroundColor: `${palette[0]}18`,
            color: palette[0],
            border: `1px solid ${palette[0]}40`,
          }}>
            {mode} temporality
          </span>
        </div>
      )}

      {/* Timeline — horizontal layout */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 0,
        overflow: 'hidden',
      }}>
        {phases.map((phase, idx) => {
          const label = getField(phase, labelField);
          const desc = getField(phase, descField);
          const color = palette[idx % palette.length];
          const isExpanded = expandedIdx.has(idx);
          const needsTruncation = desc.length > DESC_LIMIT;
          const isLast = idx === phases.length - 1;

          return (
            <React.Fragment key={idx}>
              {/* Phase node */}
              <div style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                minWidth: 0,
              }}>
                {/* Node circle */}
                <div style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  backgroundColor: color,
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  fontWeight: 700,
                  flexShrink: 0,
                  zIndex: 1,
                  fontFamily: 'var(--font-mono, monospace)',
                  boxShadow: `0 0 0 3px ${color}30`,
                }}>
                  {idx + 1}
                </div>

                {/* Label card */}
                <div style={{
                  marginTop: 'var(--space-xs, 0.375rem)',
                  textAlign: 'center',
                  padding: 'var(--space-xs, 0.375rem) var(--space-sm, 0.5rem)',
                  borderRadius: 'var(--radius-md, 8px)',
                  border: `1px solid ${color}40`,
                  backgroundColor: `${color}08`,
                  width: '100%',
                  minHeight: '44px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <span style={{
                    fontWeight: 700,
                    fontSize: 'var(--type-label, 0.6875rem)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    color: 'var(--color-text, #1a1d23)',
                    lineHeight: 'var(--leading-snug, 1.3)',
                  }}>
                    {label || `Phase ${idx + 1}`}
                  </span>
                </div>

                {/* Description below node */}
                {desc && (
                  <div
                    onClick={() => needsTruncation && toggleExpand(idx)}
                    style={{
                      marginTop: 'var(--space-2xs, 0.25rem)',
                      fontSize: 'var(--type-label, 0.6875rem)',
                      color: 'var(--color-text-muted, #6b7280)',
                      lineHeight: 'var(--leading-relaxed, 1.6)',
                      textAlign: 'center',
                      padding: '0 var(--space-2xs, 0.125rem)',
                      cursor: needsTruncation ? 'pointer' : 'default',
                    }}
                  >
                    {needsTruncation && !isExpanded
                      ? desc.slice(0, DESC_LIMIT) + '...'
                      : desc
                    }
                    {needsTruncation && (
                      <button
                        onClick={e => { e.stopPropagation(); toggleExpand(idx); }}
                        style={{
                          background: 'none',
                          border: 'none',
                          color,
                          cursor: 'pointer',
                          fontSize: '0.7rem',
                          padding: '0 3px',
                          marginLeft: '2px',
                          fontWeight: 600,
                        }}
                      >
                        {isExpanded ? '▴' : '▾'}
                      </button>
                    )}
                  </div>
                )}

                {/* Capture button */}
                {captureMode && onCapture && (
                  <button
                    title="Capture this phase"
                    onClick={e => {
                      e.stopPropagation();
                      onCapture({
                        source_view_key: captureViewKey || '',
                        source_item_index: idx,
                        source_renderer_type: 'phase_timeline',
                        content_type: 'item',
                        selected_text: `[Phase ${idx + 1}] ${label}: ${desc}`.slice(0, 500),
                        structured_data: phase,
                        context_title: parentSectionKey
                          ? `${captureViewKey || 'Analysis'} > ${parentSectionTitle || ''} > Phase: ${label}`
                          : `${captureViewKey || 'Analysis'} > Phase: ${label}`,
                        source_type: (captureSourceType || 'analysis') as string,
                        entity_id: captureEntityId || captureJobId || '',
                        depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
                        parent_context: parentSectionKey ? {
                          section_key: parentSectionKey,
                          section_title: parentSectionTitle || '',
                        } : undefined,
                      });
                    }}
                    style={{
                      marginTop: 'var(--space-2xs, 0.25rem)',
                      background: 'none',
                      border: '1px solid var(--color-border, #ccc)',
                      borderRadius: '4px',
                      color: 'var(--dt-text-faint, #94a3b8)',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.7rem',
                      lineHeight: 1,
                    }}
                  >
                    &#x1F4CC;
                  </button>
                )}
              </div>

              {/* Connector line between nodes */}
              {!isLast && (
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  paddingTop: '18px',
                  flexShrink: 0,
                }}>
                  <div style={{
                    width: '28px',
                    height: '2px',
                    background: `linear-gradient(to right, ${color}, ${palette[(idx + 1) % palette.length]})`,
                  }} />
                  <div style={{
                    width: 0,
                    height: 0,
                    borderTop: '4px solid transparent',
                    borderBottom: '4px solid transparent',
                    borderLeft: `6px solid ${palette[(idx + 1) % palette.length]}`,
                  }} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}


// ── Distribution Summary ────────────────────────────────
/**
 * Visual distribution bar chart with optional dominant pattern highlight
 * and collapsible narrative. Configurable via JSON view definitions.
 *
 * Data shape (object):
 *   {
 *     distribution: Record<string, number> | Array<{ key: string; count: number; major_count?: number }>
 *     dominant?: string
 *     narrative?: string
 *   }
 *
 * Field mapping config (for data that doesn't use these exact field names):
 *   distribution_field?: string   -- field name for distribution data (default: "distribution")
 *   dominant_field?: string       -- field name for dominant item (default: "dominant")
 *   narrative_field?: string      -- field name for narrative text (default: "narrative")
 *
 * Display config:
 *   category?: string            -- design token category for colors (e.g., "tactic", "relationship")
 *   dominant_label?: string       -- label above dominant value (default: "Dominant")
 *   count_noun?: string           -- noun for total count (default: "items")
 *   type_noun?: string            -- noun for type count (default: "types")
 *   severity_value?: string       -- label for severity badges (default: "major")
 *
 * Interactive mode (passed by CardGridRenderer via _ prefix):
 *   _onFilterClick?: (key: string) => void   -- makes bars clickable
 *   _activeFilter?: string | null            -- highlights active bar
 *   _groups?: Group[]                        -- live groups (overrides distribution field)
 */

// ── dependency_matrix ─────────────────────────────────────────
// Adjacency matrix / heatmap for directed relationships.
// Data: array of {source, target, type} objects.
// Config:
//   source_field — field name for row source (default "chapter")
//   target_field — field name for column target (default "depends_on")
//   type_field   — field name for relationship type (default "dependency_type")
//   abbreviate_labels — shorten labels (default true)

function DependencyMatrix({ data, config }: SubRendererProps) {
  const [hoveredCell, setHoveredCell] = React.useState<{ row: number; col: number } | null>(null);
  const { tokens } = useDesignTokens();

  if (!data || !Array.isArray(data) || data.length === 0) return null;

  const sourceField = (config.source_field as string) || 'chapter';
  const targetField = (config.target_field as string) || 'depends_on';
  const typeField = (config.type_field as string) || 'dependency_type';
  const abbreviate = config.abbreviate_labels !== false;

  const palette = tokens.primitives.series_palette;

  // Extract unique labels (preserving order of first appearance)
  const labelSet = new Set<string>();
  for (const item of data) {
    const obj = item as Record<string, unknown>;
    const src = String(obj[sourceField] || '');
    const tgt = String(obj[targetField] || '');
    if (src) labelSet.add(src);
    if (tgt) labelSet.add(tgt);
  }
  const labels = Array.from(labelSet);

  // Extract unique types for legend
  const typeSet = new Set<string>();
  for (const item of data) {
    const obj = item as Record<string, unknown>;
    const t = String(obj[typeField] || '');
    if (t) typeSet.add(t);
  }
  const types = Array.from(typeSet);
  const typeColorMap: Record<string, string> = {};
  types.forEach((t, i) => { typeColorMap[t] = palette[i % palette.length]; });

  // Build adjacency map: [rowIdx][colIdx] = type
  const adjacency: Record<string, Record<string, string>> = {};
  for (const item of data) {
    const obj = item as Record<string, unknown>;
    const src = String(obj[sourceField] || '');
    const tgt = String(obj[targetField] || '');
    const typ = String(obj[typeField] || '');
    if (src && tgt) {
      if (!adjacency[src]) adjacency[src] = {};
      adjacency[src][tgt] = typ;
    }
  }

  // Abbreviation helper
  const abbrev = (label: string): string => {
    if (!abbreviate) return label;
    // "Chapter 1" → "Ch1", "Appendix 1" → "App1", or first 4 chars
    return label
      .replace(/^Chapter\s*/i, 'Ch')
      .replace(/^Appendix\s*/i, 'App')
      .replace(/^Part\s*/i, 'P')
      .slice(0, 6);
  };

  const cellSize = 32;
  const labelWidth = 80;
  const hovered = hoveredCell ? {
    src: labels[hoveredCell.row],
    tgt: labels[hoveredCell.col],
    type: adjacency[labels[hoveredCell.row]]?.[labels[hoveredCell.col]],
  } : null;

  return (
    <div style={{ overflowX: 'auto' }}>
      {/* Tooltip */}
      {hovered?.type && (
        <div style={{
          padding: '6px 10px',
          marginBottom: '8px',
          fontSize: '0.82rem',
          background: 'var(--dt-surface-card, #f8f6f3)',
          border: '1px solid var(--color-border, #e2e5e9)',
          borderRadius: 'var(--radius-sm, 4px)',
          color: 'var(--dt-ink-primary, #1a1a2e)',
        }}>
          <strong>{hovered.src}</strong> → <strong>{hovered.tgt}</strong>: {hovered.type.replace(/_/g, ' ')}
        </div>
      )}

      <table style={{
        borderCollapse: 'collapse',
        fontSize: '0.75rem',
        fontFamily: 'var(--font-mono, monospace)',
      }}>
        {/* Column headers */}
        <thead>
          <tr>
            <th style={{ width: labelWidth, minWidth: labelWidth }} />
            {labels.map((label, ci) => (
              <th key={ci} style={{
                width: cellSize,
                minWidth: cellSize,
                textAlign: 'center',
                padding: '2px',
                fontWeight: 500,
                color: 'var(--dt-ink-secondary, #6b7280)',
                writingMode: labels.length > 6 ? 'vertical-rl' : undefined,
                transform: labels.length > 6 ? 'rotate(180deg)' : undefined,
                height: labels.length > 6 ? 60 : undefined,
              }}>
                {abbrev(label)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((rowLabel, ri) => (
            <tr key={ri}>
              <td style={{
                padding: '2px 6px',
                textAlign: 'right',
                fontWeight: 500,
                color: 'var(--dt-ink-secondary, #6b7280)',
                whiteSpace: 'nowrap',
              }}>
                {abbrev(rowLabel)}
              </td>
              {labels.map((colLabel, ci) => {
                const cellType = adjacency[rowLabel]?.[colLabel];
                const isDiagonal = ri === ci;
                const isHovered = hoveredCell?.row === ri && hoveredCell?.col === ci;

                return (
                  <td
                    key={ci}
                    onMouseEnter={() => setHoveredCell({ row: ri, col: ci })}
                    onMouseLeave={() => setHoveredCell(null)}
                    style={{
                      width: cellSize,
                      height: cellSize,
                      textAlign: 'center',
                      border: '1px solid var(--color-border-light, #eef0f2)',
                      background: isDiagonal
                        ? 'var(--dt-surface-bg, #f0ede6)'
                        : cellType
                          ? typeColorMap[cellType]
                          : 'transparent',
                      opacity: cellType ? (isHovered ? 1 : 0.75) : 1,
                      cursor: cellType ? 'pointer' : 'default',
                      transition: 'opacity 0.15s',
                      borderRadius: isHovered ? '2px' : undefined,
                      boxShadow: isHovered && cellType ? '0 0 0 2px var(--dt-ink-primary, #1a1a2e)' : undefined,
                    }}
                  >
                    {cellType && (
                      <span style={{
                        display: 'inline-block',
                        width: 10,
                        height: 10,
                        borderRadius: 2,
                        background: '#fff',
                        opacity: 0.6,
                      }} />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Legend */}
      <div style={{
        display: 'flex',
        gap: '12px',
        marginTop: '10px',
        flexWrap: 'wrap',
        fontSize: '0.78rem',
        color: 'var(--dt-ink-secondary, #6b7280)',
      }}>
        {types.map((type, i) => (
          <span key={type} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <span style={{
              display: 'inline-block',
              width: 12,
              height: 12,
              borderRadius: 2,
              background: typeColorMap[type],
            }} />
            {type.replace(/_/g, ' ')}
          </span>
        ))}
      </div>
    </div>
  );
}

export function DistributionSummary({ data, config }: SubRendererProps) {
  const { getCategoryColor, getLabel } = useDesignTokens();
  const [narrativeExpanded, setNarrativeExpanded] = useState(false);

  const obj = (data && typeof data === 'object' && !Array.isArray(data))
    ? data as Record<string, unknown>
    : null;
  if (!obj) return null;

  // Config
  const category = config.category as string | undefined;
  const dominantLabel = (config.dominant_label as string) || 'Dominant';
  const countNoun = (config.count_noun as string) || 'items';
  const typeNoun = (config.type_noun as string) || 'types';
  const severityValue = (config.severity_value as string) || 'major';

  // Field mapping (allows data to use different field names)
  const distField = (config.distribution_field as string) || 'distribution';
  const domField = (config.dominant_field as string) || 'dominant';
  const narrField = (config.narrative_field as string) || 'narrative';

  // Interactive mode (injected by CardGridRenderer)
  const onFilterClick = config._onFilterClick as ((key: string) => void) | undefined;
  const activeFilter = config._activeFilter as string | null | undefined;
  const liveGroups = config._groups as Array<{
    key: string; label: string;
    style: { bg: string; text: string; border: string };
    items: Array<Record<string, unknown>>;
  }> | undefined;

  // Build entries — prefer live groups (interactive) over static distribution
  const formatName = (key: string) =>
    (category ? getLabel(category, key) : null) || key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

  let entries: Array<{ key: string; label: string; count: number; majorCount: number;
    colors: { bg: string; text: string; border: string } }> = [];

  const fallbackColors = { bg: '#f1f5f9', text: '#64748b', border: '#e2e8f0' };

  if (liveGroups && liveGroups.length > 0) {
    entries = liveGroups.map(g => ({
      key: g.key,
      label: g.label,
      count: g.items.length,
      majorCount: g.items.filter(i => String(i.severity || '').toLowerCase() === severityValue).length,
      colors: (category ? getCategoryColor(category, g.key) : null) || g.style || fallbackColors,
    }));
  } else {
    const rawDist = obj[distField];
    if (rawDist && typeof rawDist === 'object' && !Array.isArray(rawDist)) {
      entries = Object.entries(rawDist as Record<string, number>)
        .map(([key, count]) => ({
          key, count: Number(count) || 0, majorCount: 0,
          label: formatName(key),
          colors: (category ? getCategoryColor(category, key) : null) || fallbackColors,
        }))
        .sort((a, b) => b.count - a.count);
    } else if (Array.isArray(rawDist)) {
      entries = (rawDist as Array<Record<string, unknown>>).map(item => {
        const key = String(item.key || '');
        return {
          key, count: Number(item.count || 0), majorCount: Number(item.major_count || 0),
          label: String(item.label || '') || formatName(key),
          colors: (category ? getCategoryColor(category, key) : null) || fallbackColors,
        };
      }).sort((a, b) => b.count - a.count);
    }
  }

  if (entries.length === 0) return null;

  const totalCount = entries.reduce((sum, e) => sum + e.count, 0);
  const maxCount = Math.max(...entries.map(e => e.count));
  const dominant = obj[domField] as string | undefined;
  const narrative = obj[narrField] as string | undefined;
  const isInteractive = Boolean(onFilterClick);

  return (
    <div className="ar-dist-summary">
      {/* Header: dominant + total count */}
      <div className="gen-summary-header">
        {dominant && (
          <div className="gen-summary-stat">
            <span className="gen-stat-label">{dominantLabel}</span>
            <span className="gen-stat-value">{formatName(dominant)}</span>
          </div>
        )}
        <div className="gen-summary-counts">
          <span className="gen-summary-count-big">{totalCount}</span>
          <span className="gen-summary-count-label">{countNoun} across {entries.length} {typeNoun}</span>
        </div>
      </div>

      {/* Distribution bars */}
      <div className="gen-dist-bars">
        {entries.map(entry => {
          const pct = Math.max(8, (entry.count / maxCount) * 100);
          const isActive = activeFilter === entry.key;
          const BarTag = isInteractive ? 'button' : 'div';

          return (
            <BarTag
              key={entry.key}
              type={isInteractive ? 'button' : undefined}
              className={`gen-dist-bar-row ${isActive ? 'gen-dist-bar-row--active' : ''}`}
              onClick={isInteractive ? () => onFilterClick!(entry.key) : undefined}
            >
              <span className="gen-dist-bar-label">{entry.label}</span>
              <span className="gen-dist-bar-track">
                <span
                  className="gen-dist-bar-fill"
                  style={{
                    width: `${pct}%`,
                    backgroundColor: entry.colors.text,
                    opacity: isActive ? 1 : 0.7,
                  }}
                />
              </span>
              <span className="gen-dist-bar-count" style={{ color: entry.colors.text }}>
                {entry.count}
              </span>
              {entry.majorCount > 0 && (
                <span className="gen-dist-bar-severity">{entry.majorCount} {severityValue}</span>
              )}
            </BarTag>
          );
        })}
        {isInteractive && activeFilter && (
          <button type="button" className="gen-dist-bar-clear" onClick={() => onFilterClick!('')}>
            Clear filter
          </button>
        )}
      </div>

      {/* Narrative */}
      {narrative && (
        <>
          <div className={`gen-pattern-narrative-wrap ${narrativeExpanded ? 'gen-pattern-narrative-wrap--expanded' : ''}`}>
            <p className="gen-pattern-narrative">{narrative}</p>
          </div>
          <button
            type="button"
            className="gen-narrative-toggle"
            onClick={() => setNarrativeExpanded(!narrativeExpanded)}
          >
            {narrativeExpanded ? 'Show less' : 'Read full analysis'}
          </button>
        </>
      )}
    </div>
  );
}
