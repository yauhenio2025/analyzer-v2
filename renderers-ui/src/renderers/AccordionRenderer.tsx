/**
 * AccordionRenderer — Generic collapsible sections renderer.
 *
 * Reads section definitions from renderer_config.sections, renders each
 * as a collapsible panel. Supports prose mode via useProseExtraction.
 *
 * All sections dispatch through a resilient fallback chain:
 *   1. Check section_renderers[key] for a configured sub-renderer
 *   2. Pre-render compatibility check: skip if data type mismatches renderer
 *   3. SubRendererFallback wrapper: catch null output via useLayoutEffect
 *   4. Auto-detect sub-renderer from data shape
 *   5. GenericSectionRenderer as final fallback (handles any data)
 *
 * renderer_config keys:
 *   sections: Array<{key, title}>  — sections to render
 *   expand_first: boolean          — auto-expand first section
 *   prose_endpoint: string         — endpoint key for prose extraction
 *   section_renderers: Record<string, {renderer_type, config?, sub_renderers?}>
 *
 * Per-section polish keys (threaded via config._*):
 *   _onPolishSection: (sectionKey, feedback) => void
 *   _onResetSection: (sectionKey) => void
 *   _sectionPolishState: Record<string, 'idle'|'polishing'|'polished'|'error'>
 *   _section_overrides: Record<string, {style_overrides, renderer_config_patch?}>
 *   _section_descriptions: Record<string, string> — section subtitle text from polish
 */

import React, { useState, useEffect, useRef } from 'react';
import { RendererProps } from '../types';
import { useProseExtraction } from '../hooks/useProseExtraction';
import { resolveSubRenderer, autoDetectSubRenderer } from '../sub-renderers/SubRenderers';
import { isRendererCompatible, SubRendererFallback, GenericSectionRenderer } from '../dispatch/SubRendererDispatch';
import { ProvenanceSectionIcon } from '../provenance/ProvenanceSectionIcon';
import { StyleOverrides } from '../types/styles';
import { useDesignTokens } from '../tokens/DesignTokenContext';
// CSS: import '@caii/analysis-renderers/styles';

interface SectionDef {
  key: string;
  title: string;
}

type SectionPolishState = 'idle' | 'polishing' | 'polished' | 'error';

/**
 * Extract a short preview string from various data shapes.
 * Used to show a hint of section content when collapsed.
 */
function extractPreviewText(data: unknown, maxLen = 80): string {
  if (typeof data === 'string') {
    const clean = data.replace(/\n/g, ' ').trim();
    return clean.length > maxLen ? clean.slice(0, maxLen) + '\u2026' : clean;
  }
  if (Array.isArray(data) && data.length > 0) {
    const first = data[0];
    if (typeof first === 'string') {
      const clean = first.replace(/\n/g, ' ').trim();
      return clean.length > maxLen ? clean.slice(0, maxLen) + '\u2026' : clean;
    }
    if (typeof first === 'object' && first !== null) {
      const obj = first as Record<string, unknown>;
      for (const key of ['name', 'title', 'term', 'summary', 'description', 'commitment']) {
        if (typeof obj[key] === 'string') {
          const val = (obj[key] as string).replace(/\n/g, ' ').trim();
          return val.length > maxLen ? val.slice(0, maxLen) + '\u2026' : val;
        }
      }
    }
  }
  if (typeof data === 'object' && data !== null && !Array.isArray(data)) {
    const obj = data as Record<string, unknown>;
    for (const key of ['summary', 'description', 'overview', 'analysis', 'assessment']) {
      if (typeof obj[key] === 'string') {
        const val = (obj[key] as string).replace(/\n/g, ' ').trim();
        return val.length > maxLen ? val.slice(0, maxLen) + '\u2026' : val;
      }
    }
  }
  return '';
}

export function AccordionRenderer({ data, config }: RendererProps) {
  const { getSemanticColor } = useDesignTokens();
  const sections = (config.sections as SectionDef[]) || [];
  const expandFirst = config.expand_first as boolean | undefined;
  const proseEndpoint = (config.prose_endpoint as string) || 'conditions';
  const styleOverrides = config._style_overrides as StyleOverrides | undefined;

  // Section descriptions from polish (threaded by Phase 1 or available directly)
  const sectionDescriptions = config._section_descriptions as Record<string, string> | undefined;

  // Per-section polish controls (threaded from GenealogyPage)
  const onPolishSection = config._onPolishSection as
    | ((sectionKey: string, feedback: string) => void)
    | undefined;
  const onResetSection = config._onResetSection as
    | ((sectionKey: string) => void)
    | undefined;
  const sectionPolishState = config._sectionPolishState as
    | Record<string, SectionPolishState>
    | undefined;
  const sectionOverrides = config._section_overrides as
    | Record<string, { style_overrides: StyleOverrides; renderer_config_patch?: Record<string, unknown> }>
    | undefined;
  // Capture mode support (threaded from CaptureContext → V2TabContent)
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as
    | ((sel: Record<string, unknown>) => void)
    | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;
  const captureStatusMap = config._captureStatusMap as Record<string, Array<{
    destination: string | null;
    research_status: string | null;
    has_answer: boolean;
  }>> | undefined;

  const provenanceEnabled = config._provenanceEnabled as boolean | undefined;
  const provenanceChildren = config._provenanceChildren as
    | Array<{ view_key: string; view_name: string; engine_key: string | null; renderer_type: string; [key: string]: unknown }>
    | undefined;

  // Prose extraction
  const { data: extractedData, loading, error, isProseMode } = useProseExtraction<unknown>(
    data as unknown,
    config._jobId as string | undefined,
    proseEndpoint
  );

  const workingData = (isProseMode ? extractedData : data) as Record<string, unknown> | null;

  // Track which sections are expanded
  const [expandedSections, setExpandedSections] = useState<Set<string>>(() => {
    if (expandFirst && sections.length > 0) {
      return new Set([sections[0].key]);
    }
    return new Set<string>();
  });

  // Track ever-expanded for animation (keep content in DOM after first expand)
  const [everExpanded, setEverExpanded] = useState<Set<string>>(() => {
    if (expandFirst && sections.length > 0) {
      return new Set([sections[0].key]);
    }
    return new Set<string>();
  });

  // Track which sections have the feedback row open
  const [feedbackOpen, setFeedbackOpen] = useState<Set<string>>(new Set());
  // Track feedback text per section
  const [feedbackText, setFeedbackText] = useState<Record<string, string>>({});

  // ── Deep-link support: auto-expand, scroll, highlight target section ──
  const deepLinkSection = config._deepLinkSection as string | null | undefined;
  const onDeepLinkConsumed = config._onDeepLinkConsumed as (() => void) | undefined;
  const deepLinkProcessedRef = useRef(false);

  useEffect(() => {
    if (!deepLinkSection || deepLinkProcessedRef.current) return;
    const targetSection = sections.find(s => s.key === deepLinkSection);
    if (!targetSection) {
      console.warn(`[DeepLink] section_key "${deepLinkSection}" not found in accordion sections`);
      onDeepLinkConsumed?.();
      return;
    }
    // Expand the target section
    setExpandedSections(prev => { const next = new Set(prev); next.add(deepLinkSection); return next; });
    setEverExpanded(prev => { const next = new Set(prev); next.add(deepLinkSection); return next; });
    deepLinkProcessedRef.current = true;

    // Wait for DOM to render the expanded section, then scroll + highlight
    requestAnimationFrame(() => {
      setTimeout(() => {
        const el = document.getElementById(`section-${deepLinkSection}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'start' });
          el.classList.add('gen-accordion-section--highlighted');
          setTimeout(() => el.classList.remove('gen-accordion-section--highlighted'), 2000);
        }
        onDeepLinkConsumed?.();
      }, 150);
    });
  }, [deepLinkSection, sections, onDeepLinkConsumed]);

  const toggleSection = (key: string) => {
    setExpandedSections(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
    // Track ever-expanded so content stays in DOM for animation
    setEverExpanded(prev => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
  };

  const toggleFeedback = (key: string) => {
    setFeedbackOpen(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handlePolishClick = (sectionKey: string) => {
    if (onPolishSection) {
      onPolishSection(sectionKey, feedbackText[sectionKey] || '');
      setFeedbackOpen(prev => {
        const next = new Set(prev);
        next.delete(sectionKey);
        return next;
      });
    }
  };

  if (loading) {
    return (
      <div className="gen-conditions-tab">
        <div className="gen-extracting-notice">
          <div className="gen-extracting-spinner" />
          <p>Preparing structured view from analytical prose...</p>
          <p className="gen-extracting-detail">
            Extracting structured data for display.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gen-conditions-tab">
        <div className="gen-extraction-error">
          <p>Could not extract structured data: {error}</p>
          <p className="gen-extraction-fallback">
            Try refreshing the page or running the analysis again.
          </p>
        </div>
      </div>
    );
  }

  if (!workingData) {
    return <p className="gen-empty">No data available yet.</p>;
  }

  // Check if synthetic_judgment is already included as an accordion section
  const hasSyntheticSection = sections.some(s => s.key === 'synthetic_judgment');
  // Check if counterfactual_analysis is handled (either as 'counterfactual_analysis' or legacy 'counterfactuals')
  const hasCounterfactualSection = sections.some(s => s.key === 'counterfactual_analysis' || s.key === 'counterfactuals');

  return (
    <div className="gen-conditions-tab">
      {isProseMode && (
        <div className="gen-prose-mode-badge">
          Schema-on-read: extracted from analytical prose
        </div>
      )}

      {sections.map(section => {
        // Resolve section data — with backward-compat fallback for renamed keys
        let sectionData = workingData[section.key];
        if (!sectionData && section.key === 'counterfactuals') {
          sectionData = workingData.counterfactual_analysis;
        }
        if (!sectionData) return null;

        const isExpanded = expandedSections.has(section.key);
        const hasEverExpanded = everExpanded.has(section.key);
        const polishState = sectionPolishState?.[section.key] || 'idle';
        const hasOverride = !!sectionOverrides?.[section.key];
        const isFeedbackOpen = feedbackOpen.has(section.key);

        // Per-section style overrides take precedence over view-level
        const effectiveSO = sectionOverrides?.[section.key]?.style_overrides || styleOverrides;

        // Section description from polish or config
        const description = sectionDescriptions?.[section.key];

        // Preview text for collapsed state
        const previewText = !isExpanded ? extractPreviewText(sectionData) : '';

        // Accent color for border and badge
        const accentColor = effectiveSO?.accent_color;

        return (
          <div
            key={section.key}
            id={`section-${section.key}`}
            className={`gen-accordion-section ${isExpanded ? 'gen-accordion-section--expanded' : ''}`}
          >
            {/* Section Header */}
            <div
              className="gen-accordion-header"
              onClick={() => toggleSection(section.key)}
              style={{
                ...(effectiveSO?.section_header || {}),
                borderLeftColor: accentColor || undefined,
              }}
            >
              <div className="gen-accordion-header-row">
                <span className={`gen-accordion-chevron ${isExpanded ? 'gen-accordion-chevron--open' : ''}`}>
                  &#x25B8;
                </span>

                <span
                  className="gen-accordion-title"
                  style={effectiveSO?.section_title || undefined}
                >
                  {section.title}
                </span>

                {/* Item count badge for arrays */}
                {Array.isArray(sectionData) && (
                  <span
                    className="gen-accordion-count"
                    style={accentColor ? { backgroundColor: accentColor, color: '#fff' } : undefined}
                  >
                    {sectionData.length}
                  </span>
                )}

                {/* Provenance section icon */}
                {provenanceEnabled && (
                  <ProvenanceSectionIcon
                    sectionKey={section.key}
                    config={(config.section_renderers as Record<string, unknown> | undefined)?.[section.key] as any}
                    children_payloads={provenanceChildren}
                  />
                )}

                {/* Capture status dots — always visible */}
                {(() => {
                  const statusKey = `${captureViewKey || ''}::${section.key}`;
                  const statuses = captureStatusMap?.[statusKey];
                  if (!statuses?.length) return null;
                  const hasArsenal = statuses.some(s => s.destination === 'arsenal');
                  const hasResearchAnswered = statuses.some(s => s.destination === 'research_todo' && s.has_answer);
                  const hasResearchPending = statuses.some(s => s.destination === 'research_todo' && !s.has_answer);
                  return (
                    <span className="capture-status-dots" onClick={e => e.stopPropagation()}>
                      {hasArsenal && <span className="capture-status-dot capture-status-dot--arsenal" title="Sent to Arsenal" />}
                      {hasResearchAnswered && <span className="capture-status-dot capture-status-dot--answered" title="Research answered" />}
                      {hasResearchPending && <span className="capture-status-dot capture-status-dot--research" title="Research question pending" />}
                    </span>
                  );
                })()}

                {/* Capture button — shown only in capture mode */}
                {captureMode && onCapture && (
                  <button
                    className="section-capture-btn"
                    title="Capture this section"
                    onClick={e => {
                      e.stopPropagation();
                      onCapture({
                        source_view_key: captureViewKey || '',
                        source_section_key: section.key,
                        source_renderer_type: 'accordion',
                        content_type: 'section',
                        selected_text: previewText || extractPreviewText(sectionData) || section.title || section.key,
                        structured_data: sectionData,
                        context_title: `${captureViewKey || 'Genealogy'} > ${section.title || section.key}`,
                        source_type: 'genealogy' as const,
                        genealogy_job_id: captureJobId || '',
                        depth_level: 'L1_section',
                      });
                    }}
                    style={{
                      marginLeft: onPolishSection ? '0' : 'auto',
                      background: 'none',
                      border: '1px solid #475569',
                      borderRadius: '4px',
                      color: '#94a3b8',
                      cursor: 'pointer',
                      padding: '2px 6px',
                      fontSize: '0.75rem',
                      lineHeight: 1,
                    }}
                  >
                    &#x1F4CC;
                  </button>
                )}

                {/* Per-section polish controls — right side of header */}
                {onPolishSection && (
                  <span
                    className="section-polish-controls"
                    onClick={e => e.stopPropagation()}
                    style={{
                      marginLeft: 'auto',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.375rem',
                    }}
                  >
                    {/* Polishing spinner */}
                    {polishState === 'polishing' && (
                      <span className="section-polish-spinner" title="Polishing..." />
                    )}

                    {/* Polished checkmark */}
                    {hasOverride && polishState !== 'polishing' && (
                      <span
                        style={{ color: getSemanticColor('severity', 'low')?.text || '#16a34a', fontSize: '0.85rem', cursor: 'default' }}
                        title="Section polished"
                      >
                        &#10003;
                      </span>
                    )}

                    {/* Reset link */}
                    {hasOverride && onResetSection && (
                      <button
                        className="section-polish-btn section-polish-reset"
                        onClick={() => onResetSection(section.key)}
                        title="Reset section polish"
                      >
                        Reset
                      </button>
                    )}

                    {/* Pencil button to open feedback row */}
                    {!hasOverride && polishState !== 'polishing' && (
                      <button
                        className="section-polish-btn section-polish-pencil"
                        onClick={() => toggleFeedback(section.key)}
                        title="Polish this section"
                      >
                        &#9998;
                      </button>
                    )}

                    {/* Error indicator */}
                    {polishState === 'error' && (
                      <span style={{ color: getSemanticColor('severity', 'high')?.text || '#dc2626', fontSize: '0.72rem' }}>failed</span>
                    )}
                  </span>
                )}
              </div>

              {/* Section description (from polish or config) */}
              {description && (
                <div
                  className="gen-accordion-description"
                  style={effectiveSO?.section_description || undefined}
                >
                  {description}
                </div>
              )}

              {/* Preview text when collapsed */}
              {!isExpanded && previewText && (
                <div className="gen-accordion-preview">
                  {previewText}
                </div>
              )}
            </div>

            {/* Feedback row — collapsible input below header */}
            {isFeedbackOpen && !hasOverride && polishState !== 'polishing' && (
              <div className="section-polish-feedback-row">
                <input
                  type="text"
                  className="section-polish-feedback-input"
                  placeholder="Optional: describe what to improve..."
                  value={feedbackText[section.key] || ''}
                  onChange={e =>
                    setFeedbackText(prev => ({ ...prev, [section.key]: e.target.value }))
                  }
                  onKeyDown={e => {
                    if (e.key === 'Enter') handlePolishClick(section.key);
                  }}
                />
                <button
                  className="section-polish-btn section-polish-go"
                  onClick={() => handlePolishClick(section.key)}
                >
                  Polish
                </button>
                <button
                  className="section-polish-btn section-polish-cancel"
                  onClick={() => toggleFeedback(section.key)}
                >
                  &times;
                </button>
              </div>
            )}

            {/* Collapsible content with smooth animation */}
            <div className={`gen-section-collapse ${isExpanded ? 'gen-section-expanded' : ''}`}>
              <div className="gen-section-collapse-inner">
                {hasEverExpanded && (
                  <div className="gen-section-content" style={effectiveSO?.section_content || undefined}>
                    {(() => {
                      // Sub-renderer dispatch with resilient fallback chain:
                      //   1. Try configured renderer (if compatible with data)
                      //   2. If incompatible or unresolved, try nested_sections
                      //   3. Auto-detect renderer based on data shape
                      //   4. GenericSectionRenderer as final fallback

                      // Forward capture config so sub-renderers (CardGrid, Card, etc.) show capture buttons
                      const captureForward = {
                        _captureMode: captureMode,
                        _onCapture: onCapture,
                        _captureJobId: captureJobId,
                        _captureViewKey: captureViewKey,
                        _parentSectionKey: section.key,
                        _parentSectionTitle: section.title,
                      };

                      const sectionHints = config.section_renderers as Record<string, { renderer_type: string; config?: Record<string, unknown>; sub_renderers?: Record<string, { renderer_type: string; config?: Record<string, unknown> }> }> | undefined;
                      const hint = sectionHints?.[section.key];
                      if (hint) {
                        const SectionRenderer = resolveSubRenderer(hint.renderer_type);
                        const subConfig = { ...(hint.config || {}), _style_overrides: effectiveSO, ...captureForward };

                        if (SectionRenderer) {
                          // Pre-render compatibility check: skip renderer if
                          // data type doesn't match (e.g. chip_grid given a string)
                          if (!isRendererCompatible(hint.renderer_type, sectionData, hint.config)) {
                            console.warn(
                              `[AccordionRenderer] Configured '${hint.renderer_type}' incompatible with ${Array.isArray(sectionData) ? 'array' : typeof sectionData} data for section '${section.key}' — falling through to auto-detection`
                            );
                          } else {
                            // Wrap in SubRendererFallback for defense-in-depth:
                            // catches cases where data type matches but content
                            // still causes null (e.g. empty array, wrong item shape)
                            return (
                              <SubRendererFallback
                                Renderer={SectionRenderer}
                                data={sectionData}
                                config={subConfig}
                                sectionKey={section.key}
                              />
                            );
                          }
                        }

                        // nested_sections: pass sub_renderers to generic
                        if (hint.sub_renderers) {
                          return <GenericSectionRenderer data={sectionData} subRenderers={hint.sub_renderers} />;
                        }
                      }

                      // Auto-detect the best sub-renderer based on data shape
                      const autoRenderer = autoDetectSubRenderer(sectionData);
                      if (autoRenderer) {
                        const AutoComp = resolveSubRenderer(autoRenderer);
                        if (AutoComp) {
                          return <AutoComp data={sectionData} config={{ _style_overrides: effectiveSO, ...captureForward }} />;
                        }
                      }

                      // Final fallback: generic renderer handles any data shape
                      return <GenericSectionRenderer data={sectionData} />;
                    })()}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {/* Synthetic judgment — always visible if present AND not already an accordion section */}
      {!hasSyntheticSection && workingData.synthetic_judgment ? (
        <div className="gen-synthetic-judgment">
          <h3>Synthetic Judgment</h3>
          <div className="gen-judgment-text">
            {String(workingData.synthetic_judgment).split('\n').map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </div>
      ) : null}

      {/* Counterfactual analysis — standalone if not already in sections config */}
      {!hasCounterfactualSection && workingData.counterfactual_analysis ? (
        <div className="gen-counterfactual">
          <h3>Counterfactual Analysis</h3>
          <p className="gen-section-desc">
            What the argument would look like without the author's prior work
          </p>
          <div className="gen-counterfactual-text">
            {String(workingData.counterfactual_analysis).split('\n').map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

