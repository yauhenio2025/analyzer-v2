/**
 * CardRenderer — Expandable detail cards with subsections.
 *
 * Unlike CardGridRenderer (many small cards in a grid), this renders a smaller
 * number of detailed cards with rich subsection content. Each card can be
 * expanded/collapsed.
 *
 * Supports the same sub-renderer dispatch chain as AccordionRenderer:
 *   1. Check section_renderers[key] for a configured sub-renderer
 *   2. Pre-render compatibility check: skip if data type mismatches renderer
 *   3. SubRendererFallback wrapper: catch null output via useLayoutEffect
 *   4. nested_sections → GenericSectionRenderer with sub_renderers
 *   5. Auto-detect sub-renderer from data shape
 *   6. GenericSectionRenderer as final fallback (handles any data)
 *
 * renderer_config keys:
 *   card_title_field: string                         — field for card header (default: "title")
 *   subsections: (string | {key, title})[]           — named sections within each card
 *   section_renderers: Record<string, {renderer_type, config?, sub_renderers?}>
 *   show_relationship_badge: boolean                 — show relationship_type badge
 *   expandable: boolean                              — collapse/expand on click (default: true)
 *   items_path: string                               — dotted path to extract items
 *   prose_endpoint: string                           — for useProseExtraction
 */

import React, { useState, useMemo } from 'react';
import { RendererProps } from '../types';
import { useProseExtraction } from '../hooks/useProseExtraction';
import { resolveSubRenderer, autoDetectSubRenderer } from '../sub-renderers/SubRenderers';
import { isRendererCompatible, SubRendererFallback, GenericSectionRenderer } from '../dispatch/SubRendererDispatch';
// CSS: import '@caii/analysis-renderers/styles'; // shared CSS classes (gen-subsection-heading, gen-keyword-tag, etc.)

interface SubsectionDef {
  key: string;
  title: string;
}

function normalizeToArray(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    return Object.entries(data as Record<string, unknown>).map(([key, value]) => {
      if (value && typeof value === 'object') {
        return { _itemKey: key, ...(value as Record<string, unknown>) };
      }
      return { _itemKey: key, value };
    });
  }
  return [];
}

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

/**
 * Render inline markdown: **bold**, *italic*, `code`.
 * Returns React nodes for use inside JSX.
 */
function renderInlineMarkdown(text: string): React.ReactNode {
  // Split on bold (**...**), italic (*...*), and code (`...`) patterns
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    // Find the earliest inline pattern
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/);
    const italicMatch = remaining.match(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/);
    const codeMatch = remaining.match(/`([^`]+)`/);

    // Find which match comes first
    const matches = [
      boldMatch ? { type: 'bold', match: boldMatch, index: boldMatch.index! } : null,
      italicMatch ? { type: 'italic', match: italicMatch, index: italicMatch.index! } : null,
      codeMatch ? { type: 'code', match: codeMatch, index: codeMatch.index! } : null,
    ].filter(Boolean).sort((a, b) => a!.index - b!.index);

    if (matches.length === 0) {
      parts.push(remaining);
      break;
    }

    const first = matches[0]!;
    // Push text before the match
    if (first.index > 0) {
      parts.push(remaining.substring(0, first.index));
    }

    if (first.type === 'bold') {
      parts.push(
        <strong key={key++} style={{ fontWeight: 700, color: 'var(--dt-text-default)' }}>
          {first.match[1]}
        </strong>
      );
    } else if (first.type === 'italic') {
      parts.push(
        <em key={key++} style={{ fontStyle: 'italic' }}>
          {first.match[1]}
        </em>
      );
    } else if (first.type === 'code') {
      parts.push(
        <code key={key++} style={{
          fontFamily: 'var(--font-mono, monospace)',
          fontSize: '0.9em',
          padding: '1px 4px',
          borderRadius: '3px',
          background: 'var(--dt-surface-alt, rgba(0,0,0,0.05))',
        }}>
          {first.match[1]}
        </code>
      );
    }

    remaining = remaining.substring(first.index + first.match[0].length);
  }

  return parts.length === 1 && typeof parts[0] === 'string' ? parts[0] : <>{parts}</>;
}

function resolveTitle(item: Record<string, unknown>, titleField: string): string {
  if (item[titleField]) return String(item[titleField]);
  if (item._display_title) return String(item._display_title);
  const pwi = item.prior_work_info as Record<string, unknown> | undefined;
  if (pwi?.title) return String(pwi.title);
  return String(item._itemKey || item.name || item.title || 'Untitled');
}

export function CardRenderer({ data, config }: RendererProps) {
  const cardTitleField = (config.card_title_field as string) || 'title';
  const rawSubsections = config.subsections as (string | SubsectionDef)[] | undefined;
  const showRelBadge = (config.show_relationship_badge as boolean) ?? false;
  const expandable = (config.expandable as boolean) ?? true;
  const itemsPath = config.items_path as string | undefined;
  const proseEndpoint = config.prose_endpoint as string | undefined;
  const sectionRenderers = config.section_renderers as Record<string, {
    renderer_type: string;
    config?: Record<string, unknown>;
    sub_renderers?: Record<string, { renderer_type: string; config?: Record<string, unknown> }>;
  }> | undefined;

  // Capture mode
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as
    | ((sel: Record<string, unknown>) => void)
    | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;

  const subsections: SubsectionDef[] = useMemo(() => {
    if (!rawSubsections) return [];
    return rawSubsections.map(s =>
      typeof s === 'string' ? { key: s, title: s.replace(/_/g, ' ') } : s
    );
  }, [rawSubsections]);

  const { data: extractedData, loading, error, isProseMode } = useProseExtraction<unknown>(
    data as unknown,
    config._jobId as string | undefined,
    proseEndpoint || 'data'
  );

  const workingData = isProseMode ? extractedData : data;

  const items = useMemo(() => {
    if (!workingData) return [];
    const extracted = itemsPath ? getPath(workingData, itemsPath) : workingData;
    return normalizeToArray(extracted);
  }, [workingData, itemsPath]);

  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set());

  const toggleCard = (idx: number) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        next.add(idx);
      }
      return next;
    });
  };

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' as const }}>
        <div className="gen-extracting-spinner" />
        <p>Preparing card data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gen-extraction-error" style={{ padding: '1rem' }}>
        <p>Could not load card data: {error}</p>
      </div>
    );
  }

  if (!workingData || items.length === 0) {
    return <p className="gen-empty">No items to display.</p>;
  }

  return (
    <div className="gen-card-renderer">
      {isProseMode ? (
        <div className="gen-prose-badge">
          <span className="gen-prose-indicator">Extracted from analytical prose</span>
        </div>
      ) : null}

      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '10px' }}>
        {items.map((item, idx) => {
          const isExpanded = !expandable || expandedCards.has(idx);
          const title = resolveTitle(item, cardTitleField);
          const relType = (item.prior_work_info as Record<string, unknown> | undefined)?.relationship_type
            || item.relationship_type
            || (item.meta as Record<string, unknown> | undefined)?.relationship_type;

          return (
            <div
              key={String(item._itemKey || idx)}
              style={{
                background: 'var(--color-surface-elev, #f5f3f0)',
                border: `1px solid ${isExpanded ? 'var(--dt-page-accent-border, rgba(181, 52, 58, 0.3))' : 'var(--color-border, #e2e5e9)'}`,
                borderRadius: '8px',
                overflow: 'hidden',
                transition: 'border-color 0.2s',
              }}
            >
              {/* Card header */}
              <div
                onClick={expandable ? () => toggleCard(idx) : undefined}
                style={{
                  padding: 'var(--space-sm, 0.75rem) var(--space-md, 1rem)',
                  cursor: expandable ? 'pointer' : 'default',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-sm, 0.5rem)',
                }}
              >
                {expandable ? (
                  <span style={{ color: 'var(--dt-text-faint)', fontSize: '0.625rem', flexShrink: 0, transition: 'transform 150ms ease' }}>
                    {isExpanded ? '\u25BC' : '\u25B6'}
                  </span>
                ) : null}
                <strong style={{
                  flex: 1,
                  fontSize: 'var(--type-body, 0.9375rem)',
                  fontFamily: "'Source Serif 4', 'Source Serif Pro', Georgia, serif",
                  fontWeight: 'var(--weight-semibold, 600)' as unknown as number,
                  color: 'var(--dt-text-default)',
                  lineHeight: 'var(--leading-snug, 1.35)',
                }}>
                  {title}
                </strong>
                {showRelBadge && relType ? (
                  <span className="gen-keyword-tag">
                    {String(relType).replace(/_/g, ' ')}
                  </span>
                ) : null}
                {captureMode && onCapture && (
                  <button
                    title="Capture this card"
                    onClick={e => {
                      e.stopPropagation();
                      const parentSectionKey = config._parentSectionKey as string | undefined;
                      const parentSectionTitle = config._parentSectionTitle as string | undefined;
                      onCapture({
                        source_view_key: captureViewKey || '',
                        source_item_index: idx,
                        source_renderer_type: 'card',
                        content_type: 'card',
                        selected_text: typeof item === 'object'
                          ? (item.summary || item.analysis || JSON.stringify(item)).toString().slice(0, 500)
                          : String(item).slice(0, 500),
                        structured_data: item,
                        context_title: parentSectionKey
                          ? `${captureViewKey || 'Genealogy'} > ${parentSectionTitle || ''} > ${title}`
                          : `${captureViewKey || 'Genealogy'} > ${title}`,
                        source_type: 'genealogy' as const,
                        genealogy_job_id: captureJobId || '',
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
                      color: 'var(--dt-text-faint)',
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

              {/* Card body with subsections */}
              {isExpanded ? (
                <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--color-border, #e2e5e9)' }}>
                  {(() => {
                    // Check if item is prose-only (from per_item views without structured data).
                    // When _prose_output or _raw_prose exists, always prefer prose rendering
                    // over subsection rendering — subsection keys won't exist in prose items.
                    const hasProse = Boolean(item._raw_prose || item._prose_output);
                    const isProseOnlyItem = hasProse && item._output_mode === 'prose';

                    // Even if subsections are configured, check whether ANY actually exist in the item.
                    // If none match, fall through to prose/fallback rendering.
                    const matchingSubsections = subsections.filter(sub => item[sub.key] != null);
                    const useSubsections = !isProseOnlyItem && matchingSubsections.length > 0;

                    return useSubsections ? (
                    matchingSubsections.map(sub => {
                      const sectionData = item[sub.key];
                      return (
                        <div key={sub.key} style={{ marginTop: '12px' }}>
                          <h5 className="gen-subsection-heading">
                            {sub.title}
                          </h5>
                          {/* Sub-renderer dispatch chain (same as AccordionRenderer):
                              1. Configured renderer → compatibility check → SubRendererFallback
                              2. nested_sections → GenericSectionRenderer with sub_renderers
                              3. Auto-detect from data shape
                              4. GenericSectionRenderer as final fallback */}
                          {(() => {
                            const hint = sectionRenderers?.[sub.key];
                            if (hint) {
                              const SectionRenderer = resolveSubRenderer(hint.renderer_type);
                              const subConfig = { ...(hint.config || {}) };

                              if (SectionRenderer) {
                                if (!isRendererCompatible(hint.renderer_type, sectionData, hint.config)) {
                                  console.warn(
                                    `[CardRenderer] Configured '${hint.renderer_type}' incompatible with ${Array.isArray(sectionData) ? 'array' : typeof sectionData} data for section '${sub.key}' — falling through to auto-detection`
                                  );
                                } else {
                                  return (
                                    <SubRendererFallback
                                      Renderer={SectionRenderer}
                                      data={sectionData}
                                      config={subConfig}
                                      sectionKey={sub.key}
                                    />
                                  );
                                }
                              }

                              // nested_sections: pass sub_renderers to GenericSectionRenderer
                              if (hint.sub_renderers) {
                                return <GenericSectionRenderer data={sectionData} subRenderers={hint.sub_renderers} />;
                              }
                            }

                            // Auto-detect the best sub-renderer from data shape
                            const autoRenderer = autoDetectSubRenderer(sectionData);
                            if (autoRenderer) {
                              const AutoComp = resolveSubRenderer(autoRenderer);
                              if (AutoComp) {
                                return <AutoComp data={sectionData} config={{}} />;
                              }
                            }

                            // Final fallback: GenericSectionRenderer handles any data shape
                            return <GenericSectionRenderer data={sectionData} />;
                          })()}
                        </div>
                      );
                    })
                  ) : (
                    /* No subsections: render prose content or all non-meta fields */
                    <div style={{ marginTop: '12px' }}>
                      {/* Render _raw_prose or _prose_output if present (per-item prose cards) */}
                      {(item._raw_prose || item._prose_output) ? (
                        <div style={{
                          fontSize: '13px',
                          color: 'var(--dt-text-muted)',
                          lineHeight: '1.6',
                        }}>
                          {String(item._raw_prose || item._prose_output).split('\n').map((line, i) => {
                            const trimmed = line.trim();
                            if (!trimmed) return <br key={i} />;
                            // Order matters: check longer prefixes first
                            if (trimmed.startsWith('#### ')) {
                              return (
                                <h6 key={i} style={{
                                  fontSize: '0.75rem',
                                  fontWeight: 600,
                                  color: 'var(--dt-text-muted)',
                                  margin: '12px 0 4px 0',
                                  letterSpacing: '0.02em',
                                }}>
                                  {renderInlineMarkdown(trimmed.replace(/^####\s*/, ''))}
                                </h6>
                              );
                            }
                            if (trimmed.startsWith('### ')) {
                              return (
                                <h5 key={i} style={{
                                  fontSize: '0.8125rem',
                                  fontWeight: 600,
                                  color: 'var(--dt-text-default)',
                                  margin: '14px 0 6px 0',
                                  borderBottom: '1px solid var(--dt-border-light, #eef0f2)',
                                  paddingBottom: '4px',
                                }}>
                                  {renderInlineMarkdown(trimmed.replace(/^###\s*/, ''))}
                                </h5>
                              );
                            }
                            if (trimmed.startsWith('## ')) {
                              const heading = trimmed.replace(/^##\s*/, '');
                              if (/^\[[\w_]+\]$/.test(heading)) {
                                return (
                                  <div key={i} className="gen-inline-label" style={{
                                    margin: '16px 0 4px 0',
                                  }}>
                                    {heading.replace(/^\[|\]$/g, '').replace(/_/g, ' ')}
                                  </div>
                                );
                              }
                              return (
                                <h4 key={i} style={{
                                  fontSize: '0.875rem',
                                  fontWeight: 600,
                                  color: 'var(--dt-text-default)',
                                  margin: '16px 0 6px 0',
                                  borderBottom: '1px solid var(--dt-border-light, #eef0f2)',
                                  paddingBottom: '4px',
                                }}>
                                  {renderInlineMarkdown(heading)}
                                </h4>
                              );
                            }
                            if (trimmed.startsWith('# ')) {
                              return (
                                <h3 key={i} style={{
                                  fontSize: '0.9375rem',
                                  fontWeight: 600,
                                  fontFamily: "'Source Serif 4', 'Source Serif Pro', Georgia, serif",
                                  color: 'var(--dt-text-default)',
                                  margin: '20px 0 8px 0',
                                }}>
                                  {renderInlineMarkdown(trimmed.replace(/^#\s*/, ''))}
                                </h3>
                              );
                            }
                            if (trimmed.startsWith('---')) {
                              return <hr key={i} style={{ border: 'none', borderTop: '1px solid var(--color-border, #e2e5e9)', margin: '12px 0' }} />;
                            }
                            if (/^\[[\w_]+\]$/.test(trimmed)) {
                              return (
                                <div key={i} className="gen-inline-label" style={{
                                  margin: '8px 0 4px 0',
                                }}>
                                  {trimmed.replace(/^\[|\]$/g, '').replace(/_/g, ' ')}
                                </div>
                              );
                            }
                            return (
                              <p key={i} style={{ margin: '0 0 6px 0' }}>
                                {renderInlineMarkdown(trimmed)}
                              </p>
                            );
                          })}
                        </div>
                      ) : (
                        /* Fallback: render all non-meta fields via GenericSectionRenderer */
                        Object.entries(item).map(([key, val]) => {
                          if (key === cardTitleField || key.startsWith('_') || key === 'prior_work_info' || val == null) return null;
                          return (
                            <div key={key} style={{ marginBottom: '10px' }}>
                              <h5 className="gen-subsection-heading">
                                {key.replace(/_/g, ' ')}
                              </h5>
                              <GenericSectionRenderer data={val} />
                            </div>
                          );
                        })
                      )}
                    </div>
                  );
                  })()}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: 'var(--space-sm, 0.5rem)', fontSize: 'var(--type-label, 0.6875rem)', color: 'var(--dt-text-faint)' }}>
        {items.length} item{items.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
