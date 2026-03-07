/**
 * CardGridRenderer — Generic card grid with pluggable cell renderers.
 *
 * Layout shell that handles:
 * - Data normalization (arrays stay as-is, Records are flattened)
 * - Grouping by a configurable field
 * - Summary bar with distribution counts
 * - Variable card sizing with hero card pattern
 * - Hover elevation and card type indicators
 * - Style override consumption for polish integration
 * - Expandable cards (optional)
 *
 * renderer_config keys:
 *   cell_renderer: string       — key into cellRenderers registry
 *   group_by: string            — field to group items by (optional)
 *   group_style_map: string     — key into STYLE_MAPS for group colors
 *   columns: number             — grid columns (default: 2)
 *   expandable: boolean         — cards expand on click (default: false)
 *   summary_fields: string[]    — fields for summary bar above grid
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { RendererProps } from '../types';
import { cellRenderers, DefaultCardCell } from '../cells';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import { useProseExtraction } from '../hooks/useProseExtraction';
import { StyleOverrides, getSO } from '../types/styles';
type CaptureSelection = Record<string, unknown>;
import { DistributionSummary } from '../sub-renderers/SubRenderers';

/** Tactic descriptions — domain metadata, not theming */
const TACTIC_DESCRIPTIONS: Record<string, string> = {
  conceptual_recycling: 'Repurposing earlier concepts under new theoretical guises',
  silent_revision: 'Revising positions without acknowledging the change',
  selective_continuity: 'Maintaining some threads while quietly dropping others',
  retroactive_framing: 'Reinterpreting past work through a later lens',
  escalation: 'Progressively intensifying a claim or position over time',
  narrative_bootstrapping: 'Building authority by narrating one\'s own trajectory',
  framework_migration: 'Moving core ideas into a different theoretical home',
  condition_shift: 'Redefining what counts as a precondition for one\'s argument',
  biographical_teleology: 'Treating an intellectual career as if it always aimed at the present',
  strategic_amnesia: 'Selectively forgetting earlier commitments that conflict with current ones',
  vocabulary_migration: 'Shifting key terms to new semantic fields',
  position_reversal: 'Adopting a stance previously argued against',
  strategic_ambiguity: 'Deliberately maintaining interpretive flexibility',
};

// ── Content length estimation ─────────────────────────────

/** Estimate the text content length of an item for hero detection */
function estimateContentLength(item: Record<string, unknown>): number {
  let total = 0;
  for (const value of Object.values(item)) {
    if (typeof value === 'string') total += value.length;
  }
  return total;
}

// ── Prose mode rendering helpers ─────────────────────────

function ProseLoadingState() {
  return (
    <div style={{ padding: '2rem', textAlign: 'center' as const }}>
      <div className="gen-extracting-spinner" />
      <p>Preparing structured view from analytical prose...</p>
    </div>
  );
}

function ProseErrorState({ error }: { error: string }) {
  return (
    <div className="gen-extraction-error" style={{ padding: '1rem' }}>
      <p>Could not extract structured data: {error}</p>
    </div>
  );
}

// ── Data normalization ───────────────────────────────────

function normalizeToArray(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) return data;

  if (data && typeof data === 'object' && !Array.isArray(data)) {
    const obj = data as Record<string, unknown>;
    const entries = Object.entries(obj);

    // Detect pattern: object whose values are arrays of objects
    // e.g. { enabling_conditions: [{...}], constraining_conditions: [{...}] }
    // Flatten into a single array with _category tag for grouping
    const arrayOfObjectEntries = entries.filter(
      ([, v]) => Array.isArray(v) && v.length > 0 && v[0] != null && typeof v[0] === 'object'
    );

    if (arrayOfObjectEntries.length > 0) {
      return arrayOfObjectEntries.flatMap(([key, arr]) =>
        (arr as Record<string, unknown>[]).map(item => ({
          _category: key,
          ...item,
        }))
      );
    }

    // Fallback: Record<string, T> → flatten to array with docKey field
    return entries.map(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        return { docKey: key, ...value as Record<string, unknown> };
      }
      return { docKey: key, value };
    });
  }

  return [];
}

// ── Grouping ─────────────────────────────────────────────

interface Group {
  key: string;
  label: string;
  style: { bg: string; text: string; border: string; label?: string };
  items: Array<Record<string, unknown>>;
}

/** Style map key → category mapping for getCategoryColor lookups */
const STYLE_MAP_CATEGORIES: Record<string, string> = {
  tactic_styles: 'tactic',
  relationship_styles: 'relationship',
};

function groupItems(
  items: Array<Record<string, unknown>>,
  groupBy: string | undefined,
  styleMapKey: string | undefined,
  getCategoryColor?: (category: string, key: string) => { bg: string; text: string; border: string; label?: string } | null,
): Group[] {
  if (!groupBy) {
    return [{
      key: '__all__',
      label: '',
      style: { bg: 'transparent', text: 'inherit', border: 'transparent' },
      items,
    }];
  }

  const category = styleMapKey ? STYLE_MAP_CATEGORIES[styleMapKey] : undefined;
  const defaultStyle = { bg: 'var(--dt-surface-alt)', text: 'var(--dt-text-muted)', border: 'var(--dt-border-light)', label: undefined as string | undefined };

  const grouped: Record<string, Array<Record<string, unknown>>> = {};
  for (const item of items) {
    const groupValue = String(item[groupBy] || 'unknown');
    if (!grouped[groupValue]) grouped[groupValue] = [];
    grouped[groupValue].push(item);
  }

  // Sort groups by count (most frequent first)
  return Object.entries(grouped)
    .sort((a, b) => b[1].length - a[1].length)
    .map(([key, groupItems]) => {
      const mapStyle = category && getCategoryColor ? getCategoryColor(category, key) : null;
      // Format label: "enabling_conditions" → "Enabling Conditions"
      const rawLabel = key.replace(/_/g, ' ');
      const titleLabel = rawLabel.replace(/\b\w/g, c => c.toUpperCase());
      return {
        key,
        label: mapStyle?.label || titleLabel,
        style: mapStyle || defaultStyle,
        items: groupItems,
      };
    });
}

// ── Main Component ───────────────────────────────────────

/**
 * Navigate a dotted path into an object.
 */
function getPath(obj: unknown, path: string): unknown {
  if (!path) return obj;
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

export function CardGridRenderer({ data, config }: RendererProps) {
  const { getCategoryColor, getSemanticColor, getLabel } = useDesignTokens();

  const cellRendererKey = config.cell_renderer as string | undefined;
  const groupBy = config.group_by as string | undefined;
  const groupStyleMap = config.group_style_map as string | undefined;
  const expandable = config.expandable as boolean | undefined;
  const itemsPath = config.items_path as string | undefined;
  const proseEndpoint = config.prose_endpoint as string | undefined;

  // Group scroll-to targeting (from URL ?group= param)
  const targetGroup = config._targetGroup as string | undefined;
  const onGroupConsumed = config._onGroupConsumed as (() => void) | undefined;

  // Capture mode
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as
    | ((sel: Record<string, unknown>) => void)
    | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;

  const so = getSO(config);

  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  // Prose extraction — detect if the data has _prose_output marker
  const { data: extractedData, loading, error, isProseMode } = useProseExtraction<unknown>(
    data as unknown,
    config._jobId as string | undefined,
    proseEndpoint || 'data'
  );

  const workingData = isProseMode ? extractedData : data;
  const workingObj = workingData as Record<string, unknown> | undefined;

  // Resolve cell renderer
  const CellRenderer = cellRendererKey
    ? cellRenderers[cellRendererKey] || DefaultCardCell
    : DefaultCardCell;

  // Extract items array from the data using items_path
  const rawItems = useMemo(() => {
    if (!workingData) return [];
    const extracted = itemsPath ? getPath(workingData, itemsPath) : workingData;
    return normalizeToArray(extracted);
  }, [workingData, itemsPath]);

  // Auto-detect group_by: if items have _category (from flattening), group by it
  const effectiveGroupBy = groupBy || (
    rawItems.length > 0 && rawItems[0]._category ? '_category' : undefined
  );

  // Group items
  const groups = useMemo(
    () => groupItems(rawItems, effectiveGroupBy, groupStyleMap, getCategoryColor),
    [rawItems, effectiveGroupBy, groupStyleMap, getCategoryColor]
  );

  // Apply active filter
  const visibleGroups = activeFilter
    ? groups.filter(g => g.key === activeFilter)
    : groups;

  if (loading) return <ProseLoadingState />;
  if (error) return <ProseErrorState error={error} />;

  if (!workingData) {
    return <p className="gen-empty">No data available yet.</p>;
  }

  if (rawItems.length === 0) {
    return <p className="gen-empty">No items found.</p>;
  }

  const hasGroups = groups.length > 1 || groups[0]?.key !== '__all__';

  // Summary panel config — either from view definition or legacy tactic_patterns fallback
  const summaryConfig = config.summary as {
    data_path?: string;
    renderer_config?: Record<string, unknown>;
  } | undefined;
  const summaryDataPath = summaryConfig?.data_path || 'tactic_patterns';
  const summaryData = workingObj?.[summaryDataPath] as Record<string, unknown> | undefined;
  const hasSummary = Boolean(summaryData);

  const handleFilterClick = (groupKey: string) => {
    if (!groupKey) { setActiveFilter(null); return; }
    setActiveFilter(prev => prev === groupKey ? null : groupKey);
  };

  return (
    <div className="gen-card-grid-renderer" style={so?.view_wrapper || undefined}>
      {/* Prose mode badge */}
      {isProseMode && (
        <div className="gen-prose-badge">
          <span className="gen-prose-indicator">Extracted from analytical prose</span>
        </div>
      )}

      {/* Distribution summary with integrated bar chart */}
      {hasSummary && (
        <DistributionSummary
          data={summaryData}
          config={{
            ...summaryConfig?.renderer_config,
            _onFilterClick: handleFilterClick,
            _activeFilter: activeFilter,
            _groups: hasGroups ? groups : undefined,
          }}
        />
      )}

      {/* Flat filter chips — only when no distribution summary (non-tactic views) */}
      {hasGroups && !hasSummary && (
        <div className="gen-rel-summary">
          <span className="gen-rel-total">
            {rawItems.length} item{rawItems.length !== 1 ? 's' : ''}
          </span>
          <div className="gen-rel-dist">
            {groups.map(group => (
              <button
                key={group.key}
                type="button"
                className={`gen-rel-dist-tag ${activeFilter === group.key ? 'gen-rel-dist-tag--active' : ''}`}
                style={{
                  background: activeFilter === group.key ? group.style.text : group.style.bg,
                  color: activeFilter === group.key ? 'var(--dt-text-inverse)' : group.style.text,
                  borderColor: group.style.border,
                }}
                onClick={() => handleFilterClick(group.key)}
              >
                {group.label}: {group.items.length}
              </button>
            ))}
            {activeFilter && (
              <button
                type="button"
                className="gen-rel-dist-clear"
                onClick={() => setActiveFilter(null)}
              >
                Show all
              </button>
            )}
          </div>
        </div>
      )}

      {/* Grouped card grid */}
      {visibleGroups.map(group => {
        // Sort items within group: major first, then moderate, then minor
        const severityWeight: Record<string, number> = { major: 3, moderate: 2, minor: 1 };
        const sortedItems = [...group.items].sort((a, b) => {
          const wa = severityWeight[String(a.severity || 'minor').toLowerCase()] || 0;
          const wb = severityWeight[String(b.severity || 'minor').toLowerCase()] || 0;
          return wb - wa;
        });
        const majorCount = sortedItems.filter(i => String(i.severity || '').toLowerCase() === 'major').length;
        const description = TACTIC_DESCRIPTIONS[group.key];

        return (
          <GroupSection
            key={group.key}
            group={group}
            sortedItems={sortedItems}
            majorCount={majorCount}
            description={description}
            hasGroups={hasGroups}
            config={config}
            expandable={expandable}
            CellRenderer={CellRenderer}
            so={so}
            isTarget={targetGroup === group.key}
            onTargetConsumed={targetGroup === group.key ? onGroupConsumed : undefined}
          />
        );
      })}
    </div>
  );
}

// ── Group Section ─────────────────────────────────────────

function GroupSection({
  group,
  sortedItems,
  majorCount,
  description,
  hasGroups,
  config,
  expandable,
  CellRenderer,
  so,
  isTarget,
  onTargetConsumed,
}: {
  group: Group;
  sortedItems: Array<Record<string, unknown>>;
  majorCount: number;
  description: string | undefined;
  hasGroups: boolean;
  config: Record<string, unknown>;
  expandable?: boolean;
  CellRenderer: React.ComponentType<{ item: Record<string, unknown>; config: Record<string, unknown> }>;
  so: StyleOverrides | undefined;
  isTarget?: boolean;
  onTargetConsumed?: () => void;
}) {
  const groupRef = useRef<HTMLDivElement>(null);
  const [highlight, setHighlight] = useState(false);

  // Scroll-to + highlight when this is the target group
  useEffect(() => {
    if (!isTarget || !groupRef.current) return;
    const el = groupRef.current;
    // Small delay to ensure layout is settled
    const timer = setTimeout(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setHighlight(true);
      // Remove highlight after animation
      const fadeTimer = setTimeout(() => {
        setHighlight(false);
        onTargetConsumed?.();
      }, 2000);
      return () => clearTimeout(fadeTimer);
    }, 300);
    return () => clearTimeout(timer);
  }, [isTarget, onTargetConsumed]);

  // Derive subtle background tint from group color
  const groupTintBg = hasGroups && group.style.text !== 'inherit'
    ? `${group.style.text}06`
    : undefined;

  const groupStyle: React.CSSProperties | undefined = groupTintBg
    ? {
        background: groupTintBg,
        borderRadius: 'var(--radius-lg, 12px)',
        padding: 'var(--space-lg, 1.5rem)',
        ...(highlight ? { outline: '2px solid var(--dt-accent, #6366f1)', outlineOffset: '2px', transition: 'outline-color 0.5s' } : {}),
      }
    : (highlight ? { outline: '2px solid var(--dt-accent, #6366f1)', outlineOffset: '2px', transition: 'outline-color 0.5s' } : undefined);

  return (
    <div
      ref={groupRef}
      id={`group-${group.key}`}
      className={hasGroups ? 'gen-rel-group gen-rel-group--enhanced' : ''}
      style={groupStyle}
    >
      {hasGroups && (
        <div
          className="gen-rel-group-header gen-rel-group-header--enhanced"
          style={{ '--group-accent': group.style.text, '--group-border': group.style.border } as React.CSSProperties}
        >
          <div className="gen-rel-group-rule" style={{ background: `linear-gradient(to right, ${group.style.text}, ${group.style.border}40)` }} />
          <h3 style={so?.section_title || undefined}>
            <span
              className="gen-rel-group-badge"
              style={{ background: group.style.bg, color: group.style.text, borderColor: group.style.border }}
            >
              {group.label}
            </span>
            <span className="gen-rel-group-count">
              {group.items.length} item{group.items.length !== 1 ? 's' : ''}
            </span>
            {majorCount > 0 && (
              <span className="gen-rel-major-pill">{majorCount} major</span>
            )}
          </h3>
          {description && (
            <p className="gen-rel-group-desc" style={so?.section_description || undefined}>{description}</p>
          )}
        </div>
      )}
      <div className="gen-rel-cards gen-rel-cards--variable" style={so?.items_container || undefined}>
        {sortedItems.map((item, idx) => {
          const isHero = idx === 0 && sortedItems.length > 1;
          const isLongContent = estimateContentLength(item) > 200;
          const spanFull = isHero || isLongContent;
          const isSingleCard = sortedItems.length === 1;

          return (
            <CardWrapper
              key={String(item.tactic_id || item.docKey || idx)}
              item={item}
              config={config}
              expandable={expandable}
              CellRenderer={CellRenderer}
              groupStyle={group.style}
              isHero={spanFull}
              isSingleCard={isSingleCard}
              so={so}
            />
          );
        })}
      </div>
    </div>
  );
}

// ── Card Wrapper (handles expansion, hero sizing, type indicators) ──

function CardWrapper({
  item,
  config,
  expandable,
  CellRenderer,
  groupStyle,
  isHero,
  isSingleCard,
  so,
}: {
  item: Record<string, unknown>;
  config: Record<string, unknown>;
  expandable?: boolean;
  CellRenderer: React.ComponentType<{ item: Record<string, unknown>; config: Record<string, unknown> }>;
  groupStyle: { text: string; bg?: string; border?: string };
  isHero: boolean;
  isSingleCard: boolean;
  so: StyleOverrides | undefined;
}) {
  const { getSemanticColor, getLabel } = useDesignTokens();
  const [expanded, setExpanded] = useState(false);

  // Default cell renderer always gets expand/collapse (text is clamped by CSS)
  const isDefaultCell = CellRenderer === DefaultCardCell;
  const canExpand = expandable || isDefaultCell;

  // Determine severity for type indicator dot
  const severityKey = String(item.severity || '').toLowerCase();
  const severityStyle = getSemanticColor('severity', severityKey);

  // Card type from _category or tactic_type
  const cardType = String(item._category || item.tactic_type || '');

  // Build card class names
  const cardClasses = [
    'gen-rel-card',
    'gen-rel-card--enhanced',
    expanded ? 'expanded' : '',
    isHero ? 'gen-rel-card--hero' : '',
    isSingleCard ? 'gen-rel-card--single' : '',
  ].filter(Boolean).join(' ');

  // Build inline styles: merge base with style overrides
  const baseCardStyle: Record<string, string> = {
    borderLeftColor: groupStyle.text,
    cursor: canExpand ? 'pointer' : 'default',
  };
  const cardStyle = isHero
    ? { ...baseCardStyle, ...so?.hero_card, ...so?.card }
    : { ...baseCardStyle, ...so?.card };

  // Capture button (rendered outside JSX to avoid TS2746)
  const captureBtn = config._captureMode && config._onCapture ? (
    <button
      key="capture-btn"
      title="Capture this card"
      onClick={e => {
        e.stopPropagation();
        const onCap = config._onCapture as (sel: CaptureSelection) => void;
        const title = String(item.title || item.name || item.tactic_id || '');
        const parentSectionKey = config._parentSectionKey as string | undefined;
        const parentSectionTitle = config._parentSectionTitle as string | undefined;
        onCap({
          source_view_key: String(config._captureViewKey || ''),
          source_item_index: undefined,
          source_renderer_type: 'card_grid',
          content_type: 'card',
          selected_text: (item.summary || item.analysis || item.description || JSON.stringify(item)).toString().slice(0, 500),
          structured_data: item,
          context_title: parentSectionKey
            ? `${config._captureViewKey || 'Genealogy'} > ${parentSectionTitle || ''} > ${title}`
            : `${config._captureViewKey || 'Genealogy'} > ${title}`,
          source_type: 'genealogy' as const,
          genealogy_job_id: String(config._captureJobId || ''),
          depth_level: parentSectionKey ? 'L2_element' : 'L1_section',
          parent_context: parentSectionKey ? {
            section_key: parentSectionKey,
            section_title: parentSectionTitle || '',
          } : undefined,
        });
      }}
      style={{
        position: 'absolute' as const,
        top: '6px',
        right: '6px',
        background: 'rgba(255,255,255,0.9)',
        border: '1px solid #ccc',
        borderRadius: '4px',
        cursor: 'pointer',
        padding: '2px 5px',
        fontSize: '0.7rem',
        lineHeight: 1,
        zIndex: 2,
      }}
    >
      &#x1F4CC;
    </button>
  ) : null;

  return (
    <div
      className={cardClasses}
      style={cardStyle}
      onClick={canExpand ? () => setExpanded(!expanded) : undefined}
    >
      {captureBtn}
      {/* Type indicator dot */}
      {(severityStyle || cardType) && (
        <div className="gen-card-type-indicator">
          {severityStyle && (
            <span
              className="gen-card-type-dot"
              style={{ background: severityStyle.text }}
              title={`Severity: ${severityKey}`}
            />
          )}
          {cardType && (
            <span className="gen-card-type-label" style={so?.badge || undefined}>
              {getLabel('tactic', cardType) || cardType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </span>
          )}
        </div>
      )}

      {/* Card content from cell renderer */}
      <div className="gen-card-content" style={so?.card_body || undefined}>
        <CellRenderer item={item} config={config} />
      </div>

      {canExpand && (
        <div className="card-cell-expand-hint">
          {expanded ? 'click to collapse' : 'click to expand'}
        </div>
      )}
    </div>
  );
}
