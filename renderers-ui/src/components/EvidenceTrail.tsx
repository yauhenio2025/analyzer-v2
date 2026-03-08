/**
 * EvidenceTrail — Reusable vertical chain of evidence steps.
 *
 * Renders a narrative progression with dot markers, gradient connectors,
 * and quoted content. Each step can contain multiple items (with title,
 * quote, citation) or a single text block.
 *
 * Two usage modes:
 *   1. Direct — import EvidenceTrail and pass pre-built steps array
 *   2. Sub-renderer — use EvidenceTrailSubRenderer with config-driven
 *      field mapping (registered in SubRenderers.tsx)
 *
 * CSS classes used (from renderers.css):
 *   .gen-evidence-trail, .gen-trail-chain, .gen-trail-step,
 *   .gen-trail-marker, .gen-trail-dot, .gen-trail-label,
 *   .gen-trail-content, .gen-trail-connector, .gen-trail-quote,
 *   .gen-quote-mark, .gen-trail-cite, .ar-card-assessment
 */

import React from 'react';

// ── Public types ─────────────────────────────────────────

export interface EvidenceTrailItem {
  title?: string;
  quote?: string;
  cite?: string;
}

export interface EvidenceTrailStep {
  label: string;
  variant: 'prior' | 'current' | 'assessment';
  items?: EvidenceTrailItem[];
  text?: string;
}

export interface EvidenceTrailProps {
  steps: EvidenceTrailStep[];
  accentColor?: string;
  borderColor?: string;
}

// ── Core component ───────────────────────────────────────

export function EvidenceTrail({ steps, accentColor, borderColor }: EvidenceTrailProps) {
  if (steps.length === 0) return null;

  const accent = accentColor || 'var(--dt-text-muted)';
  const border = borderColor || 'var(--dt-border-light)';

  return (
    <div className="gen-trail-chain">
      {steps.map((step, idx) => {
        const prevStep = idx > 0 ? steps[idx - 1] : null;
        const showConnector = Boolean(prevStep);
        const isLast = step.variant === 'assessment';

        return (
          <React.Fragment key={idx}>
            {/* Connector between steps */}
            {showConnector && (
              <div
                className={`gen-trail-connector${isLast ? ' gen-trail-connector--final' : ''}`}
                style={{
                  background: isLast
                    ? border
                    : `linear-gradient(to bottom, ${border}, ${accent})`,
                }}
              />
            )}

            {/* Step */}
            <div className={`gen-trail-step gen-trail-step--${step.variant}`}>
              <div className="gen-trail-marker">
                <span
                  className={`gen-trail-dot gen-trail-dot--${step.variant}`}
                  style={step.variant === 'current' ? { background: accent } : undefined}
                />
                <span className="gen-trail-label">{step.label}</span>
              </div>
              <div className="gen-trail-content">
                {/* Multi-item steps (prior work, current evidence) */}
                {step.items && step.items.map((item, i) => {
                  if (step.variant === 'prior') {
                    return (
                      <div key={i} className="gen-trail-ref">
                        {item.title && <span className="gen-ref-title">{item.title}</span>}
                        {item.quote && (
                          <blockquote className="gen-trail-quote">
                            <span className="gen-quote-mark">&ldquo;</span>
                            {item.quote}
                            <span className="gen-quote-mark">&rdquo;</span>
                          </blockquote>
                        )}
                      </div>
                    );
                  }
                  // current and other variants with items
                  return (
                    <blockquote
                      key={i}
                      className="gen-trail-quote gen-trail-quote--current"
                      style={{ borderLeftColor: border }}
                    >
                      <span className="gen-quote-mark">&ldquo;</span>
                      {item.quote || item.title || ''}
                      <span className="gen-quote-mark">&rdquo;</span>
                      {item.cite && <cite className="gen-trail-cite">{item.cite}</cite>}
                    </blockquote>
                  );
                })}

                {/* Single-text step (assessment) */}
                {step.text && (
                  <p className="ar-card-assessment">{step.text}</p>
                )}
              </div>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Sub-renderer wrapper (config-driven) ─────────────────

/**
 * Config shape for sub-renderer usage:
 *   steps: Array<{
 *     label: string;           — display label ("Prior work")
 *     field: string;           — data field to read from
 *     variant: string;         — "prior" | "current" | "assessment"
 *     item_title_field?: string;   — field within each item for title
 *     item_quote_field?: string;   — field within each item for quote
 *     item_cite_field?: string;    — field within each item for citation
 *     is_text?: boolean;       — treat field as single text (not array)
 *   }>
 *   accent_color?: string;
 *   border_color?: string;
 */
export function EvidenceTrailSubRenderer({
  data,
  config,
}: {
  data: unknown;
  config: Record<string, unknown>;
}) {
  const obj = (data && typeof data === 'object' && !Array.isArray(data))
    ? data as Record<string, unknown>
    : {};

  const stepConfigs = config.steps as Array<{
    label: string;
    field: string;
    variant: string;
    item_title_field?: string;
    item_quote_field?: string;
    item_cite_field?: string;
    is_text?: boolean;
  }> | undefined;

  if (!stepConfigs || !Array.isArray(stepConfigs)) return null;

  const steps: EvidenceTrailStep[] = [];

  for (const sc of stepConfigs) {
    const raw = obj[sc.field];
    if (raw === undefined || raw === null || raw === '') continue;

    const variant = (sc.variant || 'prior') as EvidenceTrailStep['variant'];

    if (sc.is_text || typeof raw === 'string') {
      steps.push({ label: sc.label, variant, text: String(raw) });
    } else if (Array.isArray(raw)) {
      const items: EvidenceTrailItem[] = raw.map((entry: unknown) => {
        if (typeof entry === 'string') return { quote: entry };
        if (typeof entry === 'object' && entry !== null) {
          const e = entry as Record<string, unknown>;
          return {
            title: sc.item_title_field ? String(e[sc.item_title_field] || '') : undefined,
            quote: sc.item_quote_field ? String(e[sc.item_quote_field] || '') : undefined,
            cite: sc.item_cite_field ? String(e[sc.item_cite_field] || '') : undefined,
          };
        }
        return { quote: String(entry) };
      });
      if (items.length > 0) {
        steps.push({ label: sc.label, variant, items });
      }
    }
  }

  if (steps.length === 0) return null;

  return (
    <EvidenceTrail
      steps={steps}
      accentColor={config.accent_color as string | undefined}
      borderColor={config.border_color as string | undefined}
    />
  );
}
