/**
 * SynthesisRenderer — Rich narrative renderer for final synthesis output.
 *
 * Renders Pass 7 synthesis data: executive summary, genealogical portrait,
 * key findings, idea genealogy summaries, author intellectual profile,
 * and methodological notes.
 *
 * Registered by view_key 'genealogy_portrait' since its structure is
 * specific to the genealogy final synthesis output.
 *
 * Supports prose mode via useProseExtraction.
 */

import React from 'react';
import { RendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import { useProseExtraction } from '../hooks/useProseExtraction';

interface Pass7Result {
  executive_summary?: string;
  genealogical_portrait?: string;
  key_findings?: Array<{
    finding: string;
    significance?: string;
    evidence_strength?: string;
  }>;
  idea_genealogies?: Array<{
    idea_id: string;
    idea_name: string;
    genealogy_summary?: string;
    evolution_pattern?: string;
    tactics_involved?: string[];
    functional_role?: string;
  }>;
  author_intellectual_profile?: {
    evolution_style?: string;
    dominant_tactics?: string[];
    intellectual_honesty_assessment?: string;
    biographical_interpretation?: string;
  };
  methodological_notes?: {
    limitations?: string[];
    areas_requiring_further_investigation?: string[];
    confidence_assessment?: string;
  };
}

export function SynthesisRenderer({ data, config }: RendererProps) {
  const { getCategoryColor, getLabel } = useDesignTokens();

  const { data: extractedData, loading, error, isProseMode } = useProseExtraction<Pass7Result>(
    data as Pass7Result | undefined,
    config._jobId as string | undefined,
    'synthesis'
  );

  // Capture mode
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as
    | ((sel: Record<string, unknown>) => void)
    | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;

  const synthesis = isProseMode ? extractedData : (data as Pass7Result | null);

  if (loading) {
    return (
      <div className="gen-synthesis-tab">
        <div className="gen-extracting-notice">
          <div className="gen-extracting-spinner" />
          <p>Preparing structured view from analytical prose...</p>
          <p className="gen-extracting-detail">
            The final synthesis was produced as rich analytical prose.
            Extracting structured data for display.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gen-synthesis-tab">
        <div className="gen-extraction-error">
          <p>Could not extract structured synthesis: {error}</p>
        </div>
      </div>
    );
  }

  if (!synthesis) {
    return <p className="gen-empty">Final synthesis not yet available.</p>;
  }

  const renderCaptureBtn = (sectionKey: string, title: string, text: string, sectionData?: unknown) => {
    if (!captureMode || !onCapture) return null;
    return (
      <button
        title="Capture this section"
        onClick={() => onCapture({
          source_view_key: captureViewKey || '',
          source_section_key: sectionKey,
          source_renderer_type: 'synthesis',
          content_type: 'section',
          selected_text: text.slice(0, 500),
          structured_data: sectionData,
          context_title: `Synthesis > ${title}`,
          source_type: 'genealogy' as const,
          genealogy_job_id: captureJobId || '',
          depth_level: 'L1_section',
        })}
        style={{
          background: 'none',
          border: '1px solid var(--color-border, #ccc)',
          borderRadius: '4px',
          color: 'var(--dt-text-faint)',
          cursor: 'pointer',
          padding: '2px 6px',
          fontSize: '0.7rem',
          lineHeight: 1,
          marginLeft: '8px',
          verticalAlign: 'middle',
        }}
      >
        &#x1F4CC;
      </button>
    );
  };

  return (
    <div className="gen-synthesis-tab">
      {isProseMode && (
        <div className="gen-prose-badge">
          <span className="gen-prose-indicator">Extracted from analytical prose</span>
        </div>
      )}

      {/* Executive Summary */}
      {synthesis.executive_summary && (
        <div className="gen-exec-summary">
          <h3>Executive Summary{renderCaptureBtn('exec_summary', 'Executive Summary', synthesis.executive_summary)}</h3>
          <p>{synthesis.executive_summary}</p>
        </div>
      )}

      {/* Genealogical Portrait */}
      {synthesis.genealogical_portrait && (
        <div className="gen-portrait">
          <h3>Genealogical Portrait{renderCaptureBtn('portrait', 'Genealogical Portrait', synthesis.genealogical_portrait)}</h3>
          <div className="gen-portrait-text">
            {synthesis.genealogical_portrait.split('\n').map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </div>
      )}

      {/* Key Findings */}
      {synthesis.key_findings && synthesis.key_findings.length > 0 && (
        <div className="gen-key-findings">
          <h3>Key Findings{renderCaptureBtn('key_findings', 'Key Findings', JSON.stringify(synthesis.key_findings).slice(0, 500), synthesis.key_findings)}</h3>
          <div className="gen-findings-list">
            {synthesis.key_findings.map((f, i) => (
              <div key={i} className="gen-finding-card">
                <p className="gen-finding-text">{f.finding}</p>
                {f.significance && (
                  <p className="gen-finding-sig">{f.significance}</p>
                )}
                {f.evidence_strength && (
                  <span className={`gen-evidence-badge strength-${f.evidence_strength}`}>
                    {f.evidence_strength}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Idea Genealogies Summary */}
      {synthesis.idea_genealogies && synthesis.idea_genealogies.length > 0 && (
        <div className="gen-idea-summaries">
          <h3>Idea Genealogy Summaries</h3>
          {synthesis.idea_genealogies.map((ig, i) => (
            <div key={i} className="gen-idea-summary-card">
              <div className="gen-idea-summary-header">
                <span className="gen-idea-id">{ig.idea_id}</span>
                <strong>{ig.idea_name}</strong>
                {ig.evolution_pattern && (
                  <span className="gen-pattern-badge">
                    {ig.evolution_pattern.replace(/_/g, ' ')}
                  </span>
                )}
              </div>
              {ig.genealogy_summary && <p>{ig.genealogy_summary}</p>}
              {ig.tactics_involved && ig.tactics_involved.length > 0 && (
                <div className="gen-tactics-tags">
                  {ig.tactics_involved.map((t, j) => {
                    const colors = getCategoryColor('tactic', t) || { bg: '#f8fafc', text: '#334155', border: '#e2e8f0' };
                    return (
                      <span
                        key={j}
                        className="gen-tactic-mini-tag"
                        style={{ background: colors.bg, color: colors.text }}
                      >
                        {getLabel('tactic', t) || t}
                      </span>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Author Intellectual Profile */}
      {synthesis.author_intellectual_profile && (
        <div className="gen-author-profile">
          <h3>Author Intellectual Profile</h3>
          {synthesis.author_intellectual_profile.evolution_style && (
            <div className="gen-profile-field">
              <strong>Evolution Style:</strong>
              <p>{synthesis.author_intellectual_profile.evolution_style}</p>
            </div>
          )}
          {synthesis.author_intellectual_profile.dominant_tactics &&
            synthesis.author_intellectual_profile.dominant_tactics.length > 0 && (
            <div className="gen-profile-field">
              <strong>Dominant Tactics:</strong>
              <div className="gen-tactics-tags">
                {synthesis.author_intellectual_profile.dominant_tactics.map((t, i) => {
                  const colors = getCategoryColor('tactic', t) || { bg: '#f8fafc', text: '#334155', border: '#e2e8f0' };
                  return (
                    <span
                      key={i}
                      className="gen-tactic-mini-tag"
                      style={{ background: colors.bg, color: colors.text }}
                    >
                      {getLabel('tactic', t) || t}
                    </span>
                  );
                })}
              </div>
            </div>
          )}
          {synthesis.author_intellectual_profile.intellectual_honesty_assessment && (
            <div className="gen-profile-field">
              <strong>Intellectual Honesty Assessment:</strong>
              <p>{synthesis.author_intellectual_profile.intellectual_honesty_assessment}</p>
            </div>
          )}
          {synthesis.author_intellectual_profile.biographical_interpretation && (
            <div className="gen-profile-field">
              <strong>Biographical Interpretation:</strong>
              <p>{synthesis.author_intellectual_profile.biographical_interpretation}</p>
            </div>
          )}
        </div>
      )}

      {/* Methodological Notes */}
      {synthesis.methodological_notes && (
        <div className="gen-method-notes">
          <h3>Methodological Notes</h3>
          {synthesis.methodological_notes.confidence_assessment && (
            <p className="gen-confidence-text">
              <strong>Confidence:</strong> {synthesis.methodological_notes.confidence_assessment}
            </p>
          )}
          {synthesis.methodological_notes.limitations &&
            synthesis.methodological_notes.limitations.length > 0 && (
            <div className="gen-limitations">
              <strong>Limitations:</strong>
              <ul>
                {synthesis.methodological_notes.limitations.map((l, i) => (
                  <li key={i}>{l}</li>
                ))}
              </ul>
            </div>
          )}
          {synthesis.methodological_notes.areas_requiring_further_investigation &&
            synthesis.methodological_notes.areas_requiring_further_investigation.length > 0 && (
            <div className="gen-further-investigation">
              <strong>Areas Requiring Further Investigation:</strong>
              <ul>
                {synthesis.methodological_notes.areas_requiring_further_investigation.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
