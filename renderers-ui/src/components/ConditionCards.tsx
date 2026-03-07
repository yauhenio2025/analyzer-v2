/**
 * ConditionCards — Domain-specific sub-renderers for Conditions of Possibility sections.
 *
 * Extracted from AccordionRenderer to follow the data-driven sub-renderer pattern.
 * These preserve the rich visual treatment for enabling/constraining conditions:
 *   - Condition type colored chips
 *   - How-managed semantic badges
 *   - Prior works tags
 *   - Evidence blockquotes
 *
 * Registered as named sub-renderers in SubRenderers.tsx:
 *   enabling_conditions  → EnableConditionsSubRenderer
 *   constraining_conditions → ConstrainConditionsSubRenderer
 */

import React from 'react';
import type { SubRendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import type { StyleOverrides } from '../types/styles';

// ── Enabling Conditions Sub-Renderer ─────────────────────

export function EnableConditionsSubRenderer({ data, config }: SubRendererProps) {
  const { getCategoryColor } = useDesignTokens();

  if (!data || !Array.isArray(data) || data.length === 0) return null;
  const conditions = data as Array<Record<string, unknown>>;
  const sectionDesc = (config.section_description as string) ||
    'How the author\'s prior work makes the current argument possible';
  const so = config._style_overrides as StyleOverrides | undefined;

  return (
    <>
      <p className="gen-section-desc" style={so?.prose || undefined}>{sectionDesc}</p>
      <div className="gen-conditions-grid">
        {conditions.map(cond => (
          <div key={String(cond.condition_id)} className="gen-condition-card enabling" style={so?.card || undefined}>
            <div className="gen-condition-header">
              <span
                className="gen-condition-type"
                style={{
                  borderColor: getCategoryColor('condition', String(cond.condition_type))?.text || 'var(--dt-text-muted, #64748b)',
                  color: getCategoryColor('condition', String(cond.condition_type))?.text || 'var(--dt-text-muted, #64748b)',
                  ...so?.chip,
                }}
              >
                {String(cond.condition_type || '').replace(/_/g, ' ')}
              </span>
              {cond.how_managed ? (
                <span className={`gen-managed-badge managed-${cond.how_managed}`} style={so?.badge || undefined}>
                  {String(cond.how_managed)}
                </span>
              ) : null}
            </div>
            <p className="gen-condition-desc">{String(cond.description || '')}</p>
            {cond.how_it_enables ? (
              <p className="gen-condition-enables">
                <strong>How it enables:</strong> {String(cond.how_it_enables)}
              </p>
            ) : null}
            {Array.isArray(cond.prior_works_involved) && cond.prior_works_involved.length > 0 && (
              <div className="gen-condition-works">
                {(cond.prior_works_involved as string[]).map((w, i) => (
                  <span key={i} className="gen-work-tag">{w}</span>
                ))}
              </div>
            )}
            {cond.evidence ? (
              <blockquote className="gen-condition-evidence">{String(cond.evidence)}</blockquote>
            ) : null}
          </div>
        ))}
      </div>
    </>
  );
}

// ── Constraining Conditions Sub-Renderer ─────────────────

export function ConstrainConditionsSubRenderer({ data, config }: SubRendererProps) {
  if (!data || !Array.isArray(data) || data.length === 0) return null;
  const constraints = data as Array<Record<string, unknown>>;
  const sectionDesc = (config.section_description as string) ||
    'How prior work limits or constrains the current argument';
  const so = config._style_overrides as StyleOverrides | undefined;

  return (
    <>
      <p className="gen-section-desc" style={so?.prose || undefined}>{sectionDesc}</p>
      <div className="gen-constraints-list">
        {constraints.map((constraint, i) => (
          <div key={String(constraint.constraint_id || i)} className="gen-constraint-card" style={so?.card || undefined}>
            {constraint.type ? (
              <span className="gen-constraint-type" style={so?.chip || undefined}>
                {String(constraint.type).replace(/_/g, ' ')}
              </span>
            ) : null}
            <p>{String(constraint.description || '')}</p>
            {constraint.how_navigated ? (
              <p className="gen-constraint-nav">
                <strong>How navigated:</strong> {String(constraint.how_navigated)}
              </p>
            ) : null}
          </div>
        ))}
      </div>
    </>
  );
}
