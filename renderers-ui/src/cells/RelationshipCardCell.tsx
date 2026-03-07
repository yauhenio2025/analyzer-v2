/**
 * RelationshipCardCell — Domain-specific cell renderer for relationship
 * classification items (prior work -> relationship type analysis).
 *
 * Supports both v2 extraction schema (flat fields from relationship_extraction
 * template) and legacy schema (classification.primary_type, prior_work_info).
 */

import React, { useState } from 'react';
import { CellRendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';

export function RelationshipCardCell({ item }: CellRendererProps) {
  const { getCategoryColor } = useDesignTokens();
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);

  // --- Resolve fields: v2 flat schema with fallback to legacy ---
  const classification = item.classification as Record<string, unknown> | undefined;
  const priorWorkInfo = item.prior_work_info as { title?: string; year?: string } | undefined;

  // Title: v2 work_title > _display_title > legacy prior_work_info.title > item.title
  const title = String(
    item.work_title || item._display_title || priorWorkInfo?.title || item.title || item.docKey || ''
  );

  // Year
  const year = item.work_year || priorWorkInfo?.year || item.year;

  // Relationship type: v2 relationship_type > legacy classification.primary_type
  const relationshipType = String(
    item.relationship_type || classification?.primary_type || ''
  );

  // Relationship strength (v2 only)
  const relationshipStrength = String(item.relationship_strength || '');

  // Summary: v2 summary > legacy classification.reasoning
  const summary = String(item.summary || classification?.reasoning || '');

  // Influence channels (v2)
  const influenceChannels = (item.influence_channels || []) as Array<{
    channel: string;
    description: string;
  }>;

  // Key evidence (v2)
  const keyEvidence = (item.key_evidence || []) as Array<{
    evidence_type: string;
    description: string;
    quote: string;
  }>;

  // Vocabulary contributed (v2)
  const vocabularyContributed = (item.vocabulary_contributed || []) as string[];

  // Centrality assessment (v2)
  const centralityAssessment = String(item.centrality_assessment || '');

  // What would be lost (v2)
  const whatWouldBeLost = String(item.what_would_be_lost || '');

  // Legacy fields
  const analysisFocus = classification?.recommended_analysis_focus as string | undefined;
  const aspectsToProbe = classification?.key_aspects_to_probe as string[] | undefined;

  // Style lookups
  const typeStyle = getCategoryColor('relationship', relationshipType);
  const strengthStyle = relationshipStrength
    ? getCategoryColor('strength', relationshipStrength)
    : null;

  return (
    <div
      className="gen-rel-card"
      style={{ borderLeftColor: typeStyle?.border || 'var(--dt-border-light)' }}
    >
      {/* Header: title + year + badges */}
      <div className="gen-rel-card-header">
        <strong>{title}</strong>
        {year ? <span className="gen-work-year">{String(year)}</span> : null}
      </div>

      {/* Badges row: type + strength */}
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
        {relationshipType && (
          <span
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              fontWeight: 600,
              backgroundColor: typeStyle?.bg || 'var(--dt-surface-alt)',
              color: typeStyle?.text || 'var(--dt-text-muted)',
              border: `1px solid ${typeStyle?.border || 'var(--dt-border-light)'}`,
            }}
          >
            {typeStyle?.label || relationshipType.replace(/_/g, ' ')}
          </span>
        )}
        {strengthStyle && (
          <span
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              fontWeight: 600,
              backgroundColor: strengthStyle.bg,
              color: strengthStyle.text,
              border: `1px solid ${strengthStyle.border}`,
            }}
          >
            {strengthStyle.label}
          </span>
        )}
      </div>

      {/* Summary */}
      {summary && <p className="gen-rel-reasoning">{summary}</p>}

      {/* Influence channels as chips */}
      {influenceChannels.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          <strong style={{ fontSize: '0.8rem', color: 'var(--dt-text-muted)' }}>Influence channels:</strong>
          <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
            {influenceChannels.map((ch, i) => (
              <span
                key={i}
                title={ch.description}
                style={{
                  display: 'inline-block',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  backgroundColor: 'var(--dt-surface-alt)',
                  color: 'var(--dt-text-default)',
                  border: '1px solid var(--dt-border-light)',
                  cursor: 'default',
                }}
              >
                {ch.channel.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Vocabulary contributed as word tags */}
      {vocabularyContributed.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          <strong style={{ fontSize: '0.8rem', color: 'var(--dt-text-muted)' }}>Vocabulary contributed:</strong>
          <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
            {vocabularyContributed.map((term, i) => (
              <span
                key={i}
                style={{
                  display: 'inline-block',
                  padding: '1px 5px',
                  borderRadius: '3px',
                  fontSize: '0.72rem',
                  fontStyle: 'italic',
                  backgroundColor: 'var(--dt-surface-alt, #eff6ff)',
                  color: 'var(--dt-text-accent, #1e40af)',
                  border: '1px solid var(--dt-border-light, #bfdbfe)',
                }}
              >
                {term}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Key evidence (expandable) */}
      {keyEvidence.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          <strong
            style={{ fontSize: '0.8rem', color: 'var(--dt-text-muted)', cursor: 'pointer', userSelect: 'none' }}
            onClick={() => setEvidenceExpanded(!evidenceExpanded)}
          >
            {evidenceExpanded ? '\u25BC' : '\u25B6'} Key evidence ({keyEvidence.length})
          </strong>
          {evidenceExpanded && (
            <div style={{ marginTop: '0.25rem' }}>
              {keyEvidence.map((ev, i) => (
                <div key={i} style={{ marginBottom: '0.375rem', paddingLeft: '0.5rem', borderLeft: '2px solid var(--dt-border-light)' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--dt-text-muted)', fontWeight: 600 }}>
                    {ev.evidence_type.replace(/_/g, ' ')}:
                  </span>
                  <span style={{ fontSize: '0.8rem', marginLeft: '0.25rem' }}>{ev.description}</span>
                  {ev.quote && (
                    <blockquote
                      style={{
                        margin: '0.25rem 0 0 0',
                        padding: '0.25rem 0.5rem',
                        fontSize: '0.75rem',
                        fontStyle: 'italic',
                        color: 'var(--dt-text-muted)',
                        borderLeft: '3px solid var(--dt-border-light)',
                        backgroundColor: 'var(--dt-surface-alt)',
                      }}
                    >
                      {ev.quote}
                    </blockquote>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Centrality + What would be lost */}
      {centralityAssessment && (
        <p style={{ fontSize: '0.8rem', color: 'var(--dt-text-muted)', marginTop: '0.5rem' }}>
          <strong>Centrality:</strong> {centralityAssessment}
        </p>
      )}
      {whatWouldBeLost && (
        <p style={{ fontSize: '0.8rem', color: 'var(--dt-text-muted)', fontStyle: 'italic', marginTop: '0.25rem' }}>
          <strong>Without this work:</strong> {whatWouldBeLost}
        </p>
      )}

      {/* Legacy fields fallback */}
      {analysisFocus && !summary && (
        <p className="gen-rel-focus">
          <strong>Analysis focus:</strong> {analysisFocus}
        </p>
      )}
      {aspectsToProbe && aspectsToProbe.length > 0 && !influenceChannels.length && (
        <div className="gen-rel-aspects">
          <strong>Key aspects to probe:</strong>
          <ul>
            {aspectsToProbe.map((aspect, i) => (
              <li key={i}>{aspect}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
