/**
 * SubRendererDispatch — Shared dispatch utilities for sub-renderer resolution.
 *
 * Extracted from AccordionRenderer to be shared by both AccordionRenderer
 * and CardRenderer. Provides:
 *   - Pre-render compatibility checking (data type vs renderer expectations)
 *   - Defense-in-depth fallback wrapper (catches empty output at layout time)
 *   - Generic recursive renderer for arbitrary data shapes
 *   - Enum color resolution via design tokens
 */

import React, { useState, useLayoutEffect, useRef } from 'react';
import { resolveSubRenderer, autoDetectSubRenderer } from '../sub-renderers/SubRenderers';
import type { SubRendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import type { SemanticTriple } from '../types/designTokens';

// ── Pre-render compatibility check ──────────────────────
// Sub-renderers silently return null when data doesn't match their
// expectations (e.g. chip_grid given a string). This check prevents
// blank sections by falling through to auto-detection on mismatch.

export const REQUIRES_ARRAY = new Set([
  'chip_grid', 'mini_card_list', 'timeline_strip',
  'comparison_panel', 'definition_list',
  'intensity_matrix', 'move_repertoire', 'rich_description_list',
]);
export const REQUIRES_OBJECT = new Set(['stat_row', 'phase_timeline', 'distribution_summary']);

export function isRendererCompatible(
  rendererType: string,
  data: unknown,
  rendererConfig?: Record<string, unknown>,
): boolean {
  if (REQUIRES_ARRAY.has(rendererType) && !Array.isArray(data)) return false;
  if (REQUIRES_OBJECT.has(rendererType) && (typeof data !== 'object' || Array.isArray(data) || data === null)) return false;
  // evidence_trail requires config.steps array — without it, always returns null
  if (rendererType === 'evidence_trail' && (!rendererConfig?.steps || !Array.isArray(rendererConfig.steps))) return false;
  return true;
}

// ── Defense-in-depth fallback wrapper ────────────────────
// Even after the pre-render compatibility check, a sub-renderer might
// return null for reasons we can't predict (e.g. data is an array but
// items are wrong shape). This wrapper detects empty output via
// useLayoutEffect (before browser paint) and swaps in auto-detection.

export function SubRendererFallback({ Renderer, data, config, sectionKey }: {
  Renderer: React.FC<SubRendererProps>;
  data: unknown;
  config: Record<string, unknown>;
  sectionKey: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [fallback, setFallback] = useState(false);

  useLayoutEffect(() => {
    if (ref.current && ref.current.innerHTML.trim() === '') {
      console.warn(
        `[SubRendererDispatch] Renderer produced empty output for section '${sectionKey}' — falling back to auto-detection`
      );
      setFallback(true);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (fallback) {
    const autoType = autoDetectSubRenderer(data);
    const AutoComp = autoType ? resolveSubRenderer(autoType) : null;
    if (AutoComp) {
      return <AutoComp data={data} config={config} />;
    }
    return <GenericSectionRenderer data={data} />;
  }

  return <div ref={ref}><Renderer data={data} config={config} /></div>;
}

// ── Enum color resolution ───────────────────────────────
// Resolve enum-like string values to semantic token colors.
// Tries each semantic scale in order; returns first match or null.
const SEMANTIC_SCALES = ['severity', 'visibility', 'change', 'modality'];

export function resolveEnumColor(
  getSemanticColor: (scale: string, level: string) => SemanticTriple | null,
  value: string,
): { bg: string; text: string } | null {
  for (const scale of SEMANTIC_SCALES) {
    const result = getSemanticColor(scale, value);
    if (result) return result;
  }
  return null;
}

// ── Generic Section Renderer ────────────────────────────
// Recursively renders arbitrary structured data shapes:
// - string → paragraphs (with enum badge detection)
// - string[] → chip grid
// - object[] → mini-cards with key-value rendering
// - object → recursive render with indentation (with sub-renderer dispatch)
// - primitive → inline display

export function GenericSectionRenderer({ data, depth = 0, subRenderers }: {
  data: unknown;
  depth?: number;
  subRenderers?: Record<string, { renderer_type: string; config?: Record<string, unknown> }>;
}) {
  const { getSemanticColor } = useDesignTokens();

  if (data === null || data === undefined) return null;

  // String → paragraphs
  if (typeof data === 'string') {
    // Check if it looks like an enum value via semantic token lookup
    if (data.length < 30) {
      const enumStyle = resolveEnumColor(getSemanticColor, data);
      if (enumStyle) {
        return (
          <span className="gen-enum-badge" style={{ backgroundColor: enumStyle.bg, color: enumStyle.text }}>
            {data.replace(/_/g, ' ')}
          </span>
        );
      }
    }
    return (
      <div className="gen-field-text" style={{ marginBottom: 'var(--space-xs, 0.25rem)' }}>
        {data.split('\n').map((p, i) => (
          <p key={i}>{p}</p>
        ))}
      </div>
    );
  }

  // Number/boolean → inline
  if (typeof data === 'number') {
    return <span className="gen-number-value">{String(data)}</span>;
  }
  if (typeof data === 'boolean') {
    const boolColor = getSemanticColor('severity', data ? 'low' : 'high');
    return (
      <span className="gen-enum-badge" style={{
        backgroundColor: boolColor?.bg || 'rgba(34, 197, 94, 0.12)',
        color: boolColor?.text || '#16a34a',
      }}>
        {String(data)}
      </span>
    );
  }

  // Array of strings → chip grid
  if (Array.isArray(data) && data.length > 0 && data.every(d => typeof d === 'string')) {
    return (
      <div className="gen-chip-grid">
        {data.map((item, i) => (
          <span key={i} className="gen-chip-inline">
            {item}
          </span>
        ))}
      </div>
    );
  }

  // Array of objects → mini-cards
  if (Array.isArray(data) && data.length > 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm, 0.5rem)', margin: 'var(--space-xs, 0.25rem) 0' }}>
        {data.map((item, i) => (
          <GenericMiniCard key={i} data={item} depth={depth} />
        ))}
      </div>
    );
  }

  // Empty array
  if (Array.isArray(data) && data.length === 0) {
    return <p className="gen-empty-list">None</p>;
  }

  // Object → key-value pairs (with optional sub-renderer dispatch)
  if (typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    const entries = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== '');
    if (entries.length === 0) return null;

    return (
      <div className={depth > 0 ? 'gen-nested-content' : undefined}>
        {entries.map(([key, value]) => {
          // Check if a sub-renderer is configured for this key
          const subHint = subRenderers?.[key];
          if (subHint) {
            const SubComp = resolveSubRenderer(subHint.renderer_type);
            if (SubComp) {
              return (
                <div key={key} className="gen-field-row">
                  <div className="gen-field-label">
                    {key.replace(/_/g, ' ')}:
                  </div>
                  <SubComp data={value} config={subHint.config || {}} />
                </div>
              );
            }
          }

          return (
            <div key={key} className="gen-field-row">
              <span className="gen-field-label">
                {key.replace(/_/g, ' ')}:
              </span>
              {typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? (
                <span className="gen-field-value-inline">
                  <GenericSectionRenderer data={value} depth={depth + 1} />
                </span>
              ) : (
                <div className="gen-field-value-block">
                  <GenericSectionRenderer data={value} depth={depth + 1} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // Fallback
  return <span style={{ fontSize: 'var(--type-body, 0.9375rem)' }}>{String(data)}</span>;
}

export function GenericMiniCard({ data, depth }: { data: unknown; depth: number }) {
  const { getSemanticColor } = useDesignTokens();

  if (typeof data !== 'object' || data === null) {
    return <GenericSectionRenderer data={data} depth={depth + 1} />;
  }

  const obj = data as Record<string, unknown>;
  const entries = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== '');
  if (entries.length === 0) return null;

  // Heuristic: find a "name" or "title" field for the card header
  const nameKey = entries.find(([k]) => ['name', 'term', 'title', 'commitment', 'cluster_name', 'channel', 'evidence_type'].includes(k));
  const typeKey = entries.find(([k]) => ['type', 'centrality', 'drift_type', 'explicitness'].includes(k));

  return (
    <div className="gen-mini-card">
      {/* Header: name + type badge */}
      {nameKey && (
        <div className="gen-mini-card-header">
          <span className="gen-mini-card-name">
            {String(nameKey[1])}
          </span>
          {typeKey && (
            <GenericSectionRenderer data={typeKey[1]} depth={depth + 1} />
          )}
        </div>
      )}

      {/* Remaining fields */}
      {entries
        .filter(([k]) => k !== nameKey?.[0] && k !== typeKey?.[0])
        .map(([key, value]) => (
          <div key={key} className="gen-mini-card-field">
            <span className="gen-mini-card-label">
              {key.replace(/_/g, ' ')}:
            </span>
            {typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean' ? (
              <span className="gen-mini-card-value" style={{ marginLeft: 'var(--space-xs, 0.25rem)' }}>
                {typeof value === 'string' && value.length < 30 && resolveEnumColor(getSemanticColor, value) ? (
                  <GenericSectionRenderer data={value} depth={depth + 1} />
                ) : (
                  String(value)
                )}
              </span>
            ) : (
              <div style={{ marginTop: 'var(--space-2xs, 0.125rem)' }}>
                <GenericSectionRenderer data={value} depth={depth + 1} />
              </div>
            )}
          </div>
        ))}
    </div>
  );
}
