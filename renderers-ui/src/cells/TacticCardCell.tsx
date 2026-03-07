/**
 * TacticCardCell — Editorial-quality cell renderer for evolution tactic items.
 *
 * Renders tactic cards with:
 * - Severity-scaled visual weight (major → dominant, minor → subdued)
 * - Evidence trail via reusable EvidenceTrail component
 * - Cross-reference idea chips with color accents
 * - Type-coded header with descriptive context
 */

import React, { useState } from 'react';
import { CellRendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import { EvidenceTrail, EvidenceTrailStep } from '../components/EvidenceTrail';

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

export function TacticCardCell({ item, config }: CellRendererProps) {
  const { getCategoryColor, getSemanticColor, getLabel } = useDesignTokens();
  const [evidenceCollapsed, setEvidenceCollapsed] = useState(true);

  const tacticType = String(item.tactic_type || '');
  const colors = getCategoryColor('tactic', tacticType) || { bg: '#f8fafc', text: '#334155', border: '#e2e8f0' };
  const severityKey = String(item.severity || 'minor').toLowerCase();
  const severity = getSemanticColor('severity', severityKey) || { bg: 'rgba(34, 197, 94, 0.15)', text: '#16a34a', border: '#bbf7d0' };
  const isMajor = severityKey === 'major';
  const isMinor = severityKey === 'minor';

  const ideaIds = item.idea_ids_involved as string[] | undefined;
  const priorRefs = item.prior_work_references as Array<{
    work_title: string;
    relevant_quote?: string;
  }> | undefined;
  const currentEvidence = item.current_work_evidence as Array<{
    quote: string;
    location?: string;
  }> | undefined;

  const tacticName = item.tactic_name ? String(item.tactic_name) : '';
  const tacticLabel = getLabel('tactic', tacticType);
  const showName = Boolean(tacticName && tacticName !== tacticLabel);
  const hasPrior = Boolean(priorRefs && priorRefs.length > 0);
  const hasCurrent = Boolean(currentEvidence && currentEvidence.length > 0);
  const hasAssessment = Boolean(item.assessment);

  // Build evidence trail steps from tactic fields
  const evidenceSteps: EvidenceTrailStep[] = [];
  if (hasPrior) {
    evidenceSteps.push({
      label: 'Prior work',
      variant: 'prior',
      items: priorRefs!.map(r => ({ title: r.work_title, quote: r.relevant_quote })),
    });
  }
  if (hasCurrent) {
    evidenceSteps.push({
      label: 'Current work',
      variant: 'current',
      items: currentEvidence!.map(e => ({ quote: e.quote, cite: e.location })),
    });
  }
  if (hasAssessment) {
    evidenceSteps.push({
      label: 'Assessment',
      variant: 'assessment',
      text: String(item.assessment),
    });
  }

  const pieceCount = evidenceSteps.reduce((n, s) => n + (s.items?.length || (s.text ? 1 : 0)), 0);

  return (
    <div
      className={`gen-tactic-card gen-tactic-card--${severityKey}`}
      style={{
        borderLeftColor: colors.text,
        borderLeftWidth: isMajor ? '5px' : '3px',
      }}
    >
      {/* ── Header: type badge + severity ── */}
      <div className="gen-tactic-header">
        <span
          className="gen-tactic-type-badge"
          style={{ background: colors.bg, color: colors.text, borderColor: colors.border }}
        >
          {tacticLabel || tacticType.replace(/_/g, ' ')}
        </span>
        <span
          className={`gen-severity-badge gen-severity-badge--${severityKey}`}
          style={{ background: severity.bg, color: severity.text }}
        >
          {severityKey}
        </span>
      </div>

      {/* ── Tactic name (if different from type label) ── */}
      {showName && (
        <h4 className="gen-tactic-name">{tacticName}</h4>
      )}

      {/* ── Description ── */}
      <p className={`gen-tactic-desc ${isMinor ? 'gen-tactic-desc--subdued' : ''}`}>
        {String(item.description || '')}
      </p>

      {/* ── Cross-reference idea chips ── */}
      {ideaIds && ideaIds.length > 0 ? (
        <div className="gen-tactic-ideas">
          <span className="gen-tactic-section-label">Ideas involved</span>
          <div className="gen-idea-tags">
            {ideaIds.map(id => (
              <span
                key={id}
                className="gen-idea-tag gen-idea-tag--linked"
                title={`See idea ${id} in Idea Evolution Map`}
              >
                {id}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {/* ── Evidence Trail (collapsible) ── */}
      {evidenceSteps.length > 0 ? (
        <div className="gen-evidence-trail">
          <button
            type="button"
            className={`gen-evidence-toggle${evidenceCollapsed ? ' gen-evidence-toggle--collapsed' : ''}`}
            onClick={(e) => { e.stopPropagation(); setEvidenceCollapsed(!evidenceCollapsed); }}
          >
            <span className="gen-evidence-toggle-icon">{'\u25B6'}</span>
            <span className="gen-evidence-toggle-label">Evidence Trail</span>
            <span className="gen-evidence-count">{pieceCount}</span>
          </button>
          {!evidenceCollapsed && (
            <EvidenceTrail
              steps={evidenceSteps}
              accentColor={colors.text}
              borderColor={colors.border}
            />
          )}
        </div>
      ) : null}
    </div>
  );
}
