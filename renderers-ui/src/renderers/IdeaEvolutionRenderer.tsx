/**
 * IdeaEvolutionRenderer — Multi-source timeline renderer for idea genealogies.
 *
 * Joins data from 4 passes:
 * - Pass 1 (pass1_ideas): Extracted ideas with narrative structure
 * - Pass 2 (pass2_scans): Per-work trace scans
 * - Pass 3 (pass3_syntheses): Cross-work evolution synthesis per idea
 * - Pass 4 (pass4_functional): Functional analysis per idea
 *
 * Registered by view_key 'genealogy_idea_evolution' because its multi-source
 * join logic is too complex for a generic renderer. Receives the full
 * GenealogyResult as data.
 */

import React, { useState, useEffect } from 'react';
import { RendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5555/api';

// ── Types (mirroring GenealogyPage types) ────────────────

interface IdeaEntry {
  idea_id: string;
  idea_name: string;
  description: string;
  type: string;
  centrality: string;
  related_ideas?: string[];
  textual_evidence?: Array<{ quote: string; location: string }>;
  analytical_function?: string;
}

interface FoundationalPattern {
  pattern_id: string;
  pattern_name: string;
  pattern_description: string;
  how_it_enables_current_work: string;
  textual_evidence_prior?: Array<{ quote: string; location?: string }>;
  manifestation_in_current_work?: string;
  pattern_type?: string;
  author_awareness?: string;
}

interface CrossDomainTransfer {
  transfer_id: string;
  source_domain: string;
  target_domain: string;
  what_transferred: string;
  how_transformed?: string;
  validity_of_transfer?: string;
  blind_spots_created?: string;
  unique_insights_enabled?: string;
}

interface Pass2Result {
  prior_work_info: {
    title: string;
    year?: string;
    context?: string;
    relationship_type?: string;
  };
  traces_found: TraceEntry[];
  foundational_patterns?: FoundationalPattern[];
  cross_domain_transfers?: CrossDomainTransfer[];
  meta?: {
    relationship_type?: string;
  };
}

interface TraceEntry {
  trace_id: string;
  target_idea_id: string;
  target_idea_name: string;
  form_in_prior_work: string;
  description: string;
  textual_evidence?: Array<{ quote: string; location: string }>;
  confidence: string;
  notable_differences?: string;
}

interface Pass3Result {
  idea_id: string;
  idea_name: string;
  evolution_timeline?: Array<{
    work_title: string;
    year?: string;
    form: string;
    key_quote?: string;
    transition_to_next?: string;
    _vocabulary_used?: string[];
  }>;
  current_form?: {
    description: string;
    key_quote?: string;
  };
  evolution_pattern?: string;
  evolution_narrative?: string;
  what_was_gained?: string;
  what_was_lost?: string;
}

interface Pass4Result {
  functional_analyses: Array<{
    idea_id: string;
    idea_name: string;
    functions_served: Array<{
      function_type: string;
      description: string;
    }>;
    conditions_of_possibility?: string;
    what_would_be_impossible_without?: string;
  }>;
}

interface GenealogyResult {
  pass1_ideas?: { ideas: IdeaEntry[]; narrative_structure?: { main_thesis?: string; key_bifurcations?: string[] } };
  pass2_scans?: Record<string, Pass2Result>;
  pass3_syntheses?: Record<string, Pass3Result>;
  pass4_functional?: Pass4Result;
  _job_id?: string;
}

// ── V2 Extraction Format (from idea_evolution_extraction template) ───

interface V2IdeaEvolution {
  narrative_summary: string;
  key_bifurcations?: Array<{ description: string; year: number; significance: string }>;
  ideas: Array<{
    idea_id: string;
    idea_name: string;
    description: string;
    form_in_current_work?: string;
    evolution_pattern?: string;
    evolution_narrative?: string;
    evolution_timeline?: Array<{
      work_title: string;
      year: number;
      phase_label?: string;
      form: string;
      key_change: string;
      vocabulary_used?: string[];
    }>;
    what_was_gained?: string;
    what_was_lost?: string;
    transition_drivers?: string[];
    traces_in_prior_works?: Array<{
      work_title: string;
      relationship: string;
      evidence: string;
    }>;
  }>;
  cross_cutting_patterns?: {
    dominant_evolution_pattern?: string;
    audience_calibration?: string;
    prescription_diagnosis_gap?: string;
    overall_trajectory?: string;
  };
}

/** Detect if data is V2 extraction format (has top-level ideas array) */
function isV2Format(data: unknown): data is V2IdeaEvolution {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return Array.isArray(d.ideas) && d.ideas.length > 0 && typeof d.ideas[0]?.idea_id === 'string';
}

/** Adapt V2 extraction to GenealogyResult so the renderer can use shared rendering logic */
function adaptV2ToGenealogyResult(v2: V2IdeaEvolution): GenealogyResult {
  return {
    pass1_ideas: {
      ideas: v2.ideas.map(i => ({
        idea_id: i.idea_id,
        idea_name: i.idea_name,
        description: i.description,
        type: i.form_in_current_work || 'central_thesis',
        centrality: 'core',
      })),
      narrative_structure: {
        main_thesis: v2.narrative_summary,
        key_bifurcations: v2.key_bifurcations?.map(b =>
          `${b.description} (${b.year}) — ${b.significance}`
        ),
      },
    },
    pass3_syntheses: v2.ideas.reduce((acc, i) => {
      acc[i.idea_id] = {
        idea_id: i.idea_id,
        idea_name: i.idea_name,
        evolution_timeline: i.evolution_timeline?.map(e => ({
          work_title: e.work_title,
          year: String(e.year),
          form: e.phase_label || e.form,
          key_quote: e.key_change,
          _vocabulary_used: e.vocabulary_used,
        })),
        evolution_pattern: i.evolution_pattern,
        evolution_narrative: i.evolution_narrative,
        what_was_gained: i.what_was_gained,
        what_was_lost: i.what_was_lost,
      };
      return acc;
    }, {} as Record<string, Pass3Result>),
    pass2_scans: {},
  };
}

// ── Component ────────────────────────────────────────────

export function IdeaEvolutionRenderer({ data, config }: RendererProps) {
  const { getCategoryColor, getLabel } = useDesignTokens();

  // Detect V2 extraction format and adapt
  const isV2 = isV2Format(data);
  const v2Data = isV2 ? data as V2IdeaEvolution : null;
  const result = isV2 ? adaptV2ToGenealogyResult(data as V2IdeaEvolution) : data as GenealogyResult;

  // Capture mode
  const captureMode = config._captureMode as boolean | undefined;
  const onCapture = config._onCapture as
    | ((sel: Record<string, unknown>) => void)
    | undefined;
  const captureJobId = config._captureJobId as string | undefined;
  const captureViewKey = config._captureViewKey as string | undefined;

  const [expandedIdea, setExpandedIdea] = useState<string | null>(null);
  const [extractedFunctional, setExtractedFunctional] = useState<Pass4Result | null>(null);

  const ideas = result?.pass1_ideas?.ideas || [];
  const scans = result?.pass2_scans || {};
  const syntheses = result?.pass3_syntheses || {};
  const rawFunctional = result?.pass4_functional;

  // Handle prose mode for functional analysis (V1 only)
  const functionalIsProse = !isV2 && rawFunctional && '_prose_output' in rawFunctional;
  const jobId = result?._job_id || (config._jobId as string | undefined);

  useEffect(() => {
    if (!functionalIsProse || !jobId || extractedFunctional) return;
    const fetchPresentation = async () => {
      try {
        const wk = (config._workflowKey as string) || 'intellectual_genealogy';
        const response = await fetch(`${API_BASE}/analysis/${encodeURIComponent(wk)}/${jobId}/present/functional`, { method: 'POST' });
        if (response.ok) {
          const data = await response.json();
          setExtractedFunctional(data.data as Pass4Result);
        }
      } catch (e) {
        console.warn('Failed to extract functional analysis:', e);
      }
    };
    fetchPresentation();
  }, [functionalIsProse, jobId, extractedFunctional]);

  const functional = functionalIsProse ? extractedFunctional : rawFunctional;

  if (ideas.length === 0) {
    // Check for prose fallback
    if (data && typeof data === 'object' && '_prose_output' in (data as Record<string, unknown>)) {
      const prose = (data as Record<string, unknown>)._prose_output as string;
      return (
        <div className="gen-genealogies-tab">
          <div className="gen-prose-fallback">
            <p className="gen-prose-badge">Showing raw analysis output (structured extraction pending)</p>
            <div className="gen-narrative-text">
              {prose.split('\n').filter(Boolean).map((p, i) => (
                <p key={i}>{p}</p>
              ))}
            </div>
          </div>
        </div>
      );
    }
    return <p className="gen-empty">No ideas extracted yet.</p>;
  }

  return (
    <div className="gen-genealogies-tab">
      {/* Hero / Narrative Structure */}
      {result?.pass1_ideas?.narrative_structure && (
        <div className="gen-evo-hero">
          <div className="gen-evo-hero-label">Narrative Structure</div>
          {result.pass1_ideas.narrative_structure.main_thesis && (
            <blockquote className="gen-evo-thesis">
              {result.pass1_ideas.narrative_structure.main_thesis}
            </blockquote>
          )}
          {/* V2: structured bifurcations with year/description/significance */}
          {isV2 && v2Data?.key_bifurcations?.length ? (
            <div className="gen-evo-bifurcations">
              <div className="gen-evo-bifurcations-label">Key Bifurcations</div>
              <div className="gen-evo-bif-timeline">
                {v2Data.key_bifurcations.map((b, i) => (
                  <div key={i} className="gen-evo-bif-node">
                    <div className="gen-evo-bif-year">{b.year}</div>
                    <p className="gen-evo-bif-desc">{b.description}</p>
                    <p className="gen-evo-bif-sig">{b.significance}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* V1 fallback: flat string bifurcations */
            result.pass1_ideas.narrative_structure.key_bifurcations?.length ? (
              <div className="gen-evo-bifurcations">
                <div className="gen-evo-bifurcations-label">Key Bifurcations</div>
                <div className="gen-evo-bif-timeline">
                  {result.pass1_ideas.narrative_structure.key_bifurcations.map((b, i) => (
                    <div key={i} className="gen-evo-bif-node">
                      <p className="gen-evo-bif-desc">{b}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null
          )}
        </div>
      )}

      {/* Ideas */}
      <div className="gen-evo-cards">
        {ideas.map(idea => {
          const isExpanded = expandedIdea === idea.idea_id;
          const synthesis = syntheses[idea.idea_id];
          const funcAnalysis = functional?.functional_analyses?.find(
            fa => fa.idea_id === idea.idea_id
          );
          const formColors = getCategoryColor('idea', idea.type) || { bg: 'var(--dt-surface-alt, #f8fafc)', text: 'var(--dt-text-default, #334155)', border: 'var(--dt-border-default, #94a3b8)', label: idea.type?.replace(/_/g, ' ') };

          // Collect traces for this idea across all scans
          const tracesAcrossWorks: Array<{ workKey: string; scan: Pass2Result; traces: TraceEntry[] }> = [];
          Object.entries(scans).forEach(([workKey, scan]) => {
            const matching = scan.traces_found?.filter(t => t.target_idea_id === idea.idea_id) || [];
            if (matching.length > 0) {
              tracesAcrossWorks.push({ workKey, scan, traces: matching });
            }
          });

          // Collect indirect enablers
          const indirectEnablers: Array<{ workKey: string; scan: Pass2Result }> = [];
          Object.entries(scans).forEach(([workKey, scan]) => {
            const relType = scan.prior_work_info?.relationship_type || scan.meta?.relationship_type;
            if (relType === 'indirect_contextualizer' || relType === 'different_field_relevant') {
              const hasPatterns = (scan.foundational_patterns?.length || 0) > 0;
              const hasTransfers = (scan.cross_domain_transfers?.length || 0) > 0;
              if (hasPatterns || hasTransfers) {
                indirectEnablers.push({ workKey, scan });
              }
            }
          });

          return (
            <div
              key={idea.idea_id}
              className={`gen-evo-card ${isExpanded ? 'gen-evo-card--expanded' : ''}`}
              style={{ borderLeftColor: formColors.border }}
            >
              <button
                className="gen-evo-card-header"
                onClick={() => setExpandedIdea(isExpanded ? null : idea.idea_id)}
              >
                <div className="gen-evo-card-top">
                  <span className="gen-evo-card-id">{idea.idea_id}</span>
                  <span
                    className="gen-evo-card-form-badge"
                    style={{ background: formColors.bg, color: formColors.text }}
                  >
                    {formColors.label || idea.type?.replace(/_/g, ' ')}
                  </span>
                  <span className={`gen-evo-centrality gen-evo-centrality--${idea.centrality}`}>
                    {idea.centrality}
                  </span>
                  <span className="gen-evo-expand-icon">{isExpanded ? '\u25BC' : '\u25B6'}</span>
                </div>
                <h4 className="gen-evo-card-name">{idea.idea_name}</h4>
                <p className="gen-evo-card-desc">{idea.description}</p>
                <div className="gen-evo-card-footer">
                  {tracesAcrossWorks.length > 0 && (
                    <span className="gen-evo-trace-count">
                      {tracesAcrossWorks.length} prior work{tracesAcrossWorks.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  {indirectEnablers.length > 0 && (
                    <span className="gen-evo-trace-count gen-evo-indirect-count">
                      {indirectEnablers.length} indirect enabler{indirectEnablers.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  {synthesis?.evolution_pattern && (
                    <span className="gen-pattern-badge">
                      {synthesis.evolution_pattern.replace(/_/g, ' ')}
                    </span>
                  )}
                  {captureMode && onCapture && (
                    <span
                      title="Capture this idea"
                      onClick={e => {
                        e.stopPropagation();
                        onCapture({
                          source_view_key: captureViewKey || '',
                          source_section_key: idea.idea_id,
                          source_renderer_type: 'idea_evolution',
                          content_type: 'item',
                          selected_text: `${idea.idea_name}: ${idea.description || ''}`.slice(0, 500),
                          structured_data: { idea, synthesis, traces: tracesAcrossWorks.length },
                          context_title: `${captureViewKey || 'Ideas'} > ${idea.idea_name}`,
                          source_type: 'genealogy' as const,
                          genealogy_job_id: captureJobId || '',
                          depth_level: 'L2_element',
                        });
                      }}
                      style={{
                        marginLeft: 'auto',
                        cursor: 'pointer',
                        fontSize: '0.72rem',
                        padding: '1px 5px',
                        border: '1px solid var(--color-border, #ccc)',
                        borderRadius: '3px',
                        color: 'var(--dt-text-faint)',
                      }}
                    >
                      &#x1F4CC;
                    </span>
                  )}
                </div>
              </button>

              {isExpanded && (
                <div className="gen-evo-detail">
                  {/* Evolution Timeline */}
                  {synthesis?.evolution_timeline && synthesis.evolution_timeline.length > 0 && (
                    <div className="gen-timeline-section">
                      <h5>Evolution Timeline</h5>
                      <div className="gen-timeline">
                        {synthesis.evolution_timeline.map((entry, i) => (
                          <div key={i} className="gen-timeline-node">
                            <div className="gen-timeline-marker" />
                            <div className="gen-timeline-content">
                              <div className="gen-timeline-header">
                                <strong>{entry.work_title}</strong>
                                {entry.year && <span className="gen-timeline-year">{entry.year}</span>}
                              </div>
                              <p className="gen-timeline-form">{entry.form}</p>
                              {entry.key_quote && (
                                <blockquote className="gen-timeline-quote">"{entry.key_quote}"</blockquote>
                              )}
                              {entry.transition_to_next && (
                                <p className="gen-timeline-transition">{entry.transition_to_next}</p>
                              )}
                              {entry._vocabulary_used?.length ? (
                                <div className="gen-evo-vocab-chips">
                                  {entry._vocabulary_used.map((v, vi) => (
                                    <span key={vi} className="gen-evo-vocab-chip">{v}</span>
                                  ))}
                                </div>
                              ) : null}
                            </div>
                          </div>
                        ))}
                        {/* Current form */}
                        {synthesis.current_form && (
                          <div className="gen-timeline-node current">
                            <div className="gen-timeline-marker current" />
                            <div className="gen-timeline-content">
                              <strong>Current Work</strong>
                              <p className="gen-timeline-form">{synthesis.current_form.description}</p>
                              {synthesis.current_form.key_quote && (
                                <blockquote className="gen-timeline-quote">
                                  "{synthesis.current_form.key_quote}"
                                </blockquote>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {synthesis.evolution_pattern && (
                        <div className="gen-evolution-pattern">
                          <strong>Pattern:</strong>{' '}
                          <span className="gen-pattern-badge">
                            {synthesis.evolution_pattern.replace(/_/g, ' ')}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Evolution Narrative */}
                  {synthesis?.evolution_narrative && (
                    <div className="gen-narrative-section">
                      <h5>Evolution Narrative</h5>
                      <div className="gen-narrative-text">
                        {synthesis.evolution_narrative.split('\n').map((p, i) => (
                          <p key={i}>{p}</p>
                        ))}
                      </div>
                      {synthesis.what_was_gained && (
                        <div className="gen-gained-lost">
                          <div className="gen-gained">
                            <strong>What was gained:</strong> {synthesis.what_was_gained}
                          </div>
                          {synthesis.what_was_lost && (
                            <div className="gen-lost">
                              <strong>What was lost:</strong> {synthesis.what_was_lost}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Traces in Prior Works */}
                  {tracesAcrossWorks.length > 0 && (
                    <div className="gen-traces-section">
                      <h5>Traces in Prior Works</h5>
                      {tracesAcrossWorks.map(({ scan, traces }) => {
                        const relType = scan.prior_work_info?.relationship_type || scan.meta?.relationship_type || 'direct_precursor';
                        const relStyle = getCategoryColor('relationship', relType) || getCategoryColor('relationship', 'direct_precursor') || { bg: '#eff6ff', text: '#1e40af', border: '#93c5fd', label: 'Direct Precursor' };
                        return (
                          <div key={scan.prior_work_info.title} className="gen-trace-work">
                            <div className="gen-trace-work-header">
                              <strong>{scan.prior_work_info.title}</strong>
                              {scan.prior_work_info.year && (
                                <span className="gen-work-year">{scan.prior_work_info.year}</span>
                              )}
                              <span
                                className="gen-relationship-badge"
                                style={{ background: relStyle.bg, color: relStyle.text, borderColor: relStyle.border }}
                              >
                                {relStyle.label}
                              </span>
                            </div>
                            {traces.map(trace => (
                              <div key={trace.trace_id} className="gen-trace-item">
                                <div className="gen-trace-form-row">
                                  <span
                                    className="gen-form-badge"
                                    style={{
                                      color: getCategoryColor('form', trace.form_in_prior_work)?.text || '#94a3b8',
                                    }}
                                  >
                                    {getLabel('form', trace.form_in_prior_work) ||
                                      trace.form_in_prior_work.replace(/_/g, ' ')}
                                  </span>
                                  <span className={`gen-confidence confidence-${trace.confidence}`}>
                                    {trace.confidence}
                                  </span>
                                </div>
                                <p>{trace.description}</p>
                                {trace.notable_differences && (
                                  <p className="gen-trace-diff">
                                    <strong>Differences:</strong> {trace.notable_differences}
                                  </p>
                                )}
                                {trace.textual_evidence?.map((ev, i) => (
                                  <blockquote key={i} className="gen-trace-quote">
                                    "{ev.quote}"
                                    {ev.location && <cite>{ev.location}</cite>}
                                  </blockquote>
                                ))}
                              </div>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Indirect Enablers */}
                  {indirectEnablers.length > 0 && (
                    <div className="gen-indirect-section">
                      <h5>Indirect Enablers</h5>
                      <p className="gen-indirect-intro">
                        These works don't directly discuss this idea but provide foundational thinking that enables it.
                      </p>
                      {indirectEnablers.map(({ workKey, scan }) => {
                        const relType = scan.prior_work_info?.relationship_type || scan.meta?.relationship_type || 'indirect_contextualizer';
                        const relStyle = getCategoryColor('relationship', relType) || getCategoryColor('relationship', 'indirect_contextualizer') || { bg: '#fdf4ff', text: '#86198f', border: '#e879f9', label: 'Indirect Contextualizer' };
                        return (
                          <div key={workKey} className="gen-indirect-work">
                            <div className="gen-trace-work-header">
                              <strong>{scan.prior_work_info.title}</strong>
                              {scan.prior_work_info.year && (
                                <span className="gen-work-year">{scan.prior_work_info.year}</span>
                              )}
                              <span
                                className="gen-relationship-badge"
                                style={{ background: relStyle.bg, color: relStyle.text, borderColor: relStyle.border }}
                              >
                                {relStyle.label}
                              </span>
                            </div>

                            {/* Foundational Patterns */}
                            {scan.foundational_patterns?.map(pattern => (
                              <div key={pattern.pattern_id} className="gen-pattern-item">
                                <div className="gen-pattern-header">
                                  <strong className="gen-pattern-name">{pattern.pattern_name}</strong>
                                  {pattern.pattern_type && (
                                    <span className="gen-pattern-type-badge">
                                      {getLabel('pattern', pattern.pattern_type) || pattern.pattern_type.replace(/_/g, ' ')}
                                    </span>
                                  )}
                                  {pattern.author_awareness && (
                                    <span
                                      className="gen-awareness-badge"
                                      style={{ color: getCategoryColor('awareness', pattern.author_awareness)?.text || '#94a3b8' }}
                                    >
                                      {getLabel('awareness', pattern.author_awareness) || pattern.author_awareness}
                                    </span>
                                  )}
                                </div>
                                <p className="gen-pattern-desc">{pattern.pattern_description}</p>
                                <p className="gen-pattern-enables">
                                  <strong>How it enables current work:</strong> {pattern.how_it_enables_current_work}
                                </p>
                                {pattern.manifestation_in_current_work && (
                                  <p className="gen-pattern-manifestation">
                                    <strong>Manifests as:</strong> {pattern.manifestation_in_current_work}
                                  </p>
                                )}
                                {pattern.textual_evidence_prior?.map((ev, i) => (
                                  <blockquote key={i} className="gen-trace-quote">
                                    "{ev.quote}"
                                    {ev.location && <cite>{ev.location}</cite>}
                                  </blockquote>
                                ))}
                              </div>
                            ))}

                            {/* Cross-Domain Transfers */}
                            {scan.cross_domain_transfers?.map(transfer => (
                              <div key={transfer.transfer_id} className="gen-transfer-item">
                                <div className="gen-transfer-header">
                                  <span className="gen-transfer-domains">
                                    {transfer.source_domain} → {transfer.target_domain}
                                  </span>
                                </div>
                                <p><strong>What transferred:</strong> {transfer.what_transferred}</p>
                                {transfer.how_transformed && (
                                  <p><strong>How transformed:</strong> {transfer.how_transformed}</p>
                                )}
                                {transfer.validity_of_transfer && (
                                  <p><strong>Validity:</strong> {transfer.validity_of_transfer}</p>
                                )}
                                {transfer.blind_spots_created && (
                                  <p className="gen-transfer-blindspot">
                                    <strong>Blind spots:</strong> {transfer.blind_spots_created}
                                  </p>
                                )}
                                {transfer.unique_insights_enabled && (
                                  <p className="gen-transfer-insight">
                                    <strong>Unique insights:</strong> {transfer.unique_insights_enabled}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* V2: Traces in prior works */}
                  {isV2 && (() => {
                    const v2Idea = v2Data?.ideas.find(i => i.idea_id === idea.idea_id);
                    const v2Traces = v2Idea?.traces_in_prior_works;
                    if (!v2Traces?.length) return null;
                    return (
                      <div className="gen-traces-section">
                        <h5>Traces in Prior Works</h5>
                        {v2Traces.map((trace, ti) => {
                          const relStyle = getCategoryColor('relationship', trace.relationship) || getCategoryColor('relationship', 'direct_precursor') || { bg: '#eff6ff', text: '#1e40af', border: '#93c5fd', label: 'Direct Precursor' };
                          return (
                            <div key={ti} className="gen-trace-work">
                              <div className="gen-trace-work-header">
                                <strong>{trace.work_title}</strong>
                                <span
                                  className="gen-relationship-badge"
                                  style={{ background: relStyle.bg, color: relStyle.text, borderColor: relStyle.border }}
                                >
                                  {relStyle.label || trace.relationship.replace(/_/g, ' ')}
                                </span>
                              </div>
                              <p>{trace.evidence}</p>
                            </div>
                          );
                        })}
                      </div>
                    );
                  })()}

                  {/* V2: Transition Drivers */}
                  {isV2 && (() => {
                    const v2Idea = v2Data?.ideas.find(i => i.idea_id === idea.idea_id);
                    if (!v2Idea?.transition_drivers?.length) return null;
                    return (
                      <div className="gen-evo-drivers">
                        <h5>Transition Drivers</h5>
                        <div className="gen-evo-driver-chips">
                          {v2Idea.transition_drivers.map((d, i) => (
                            <span key={i} className="gen-evo-driver-chip">{d}</span>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  {/* Functional Analysis */}
                  {funcAnalysis && (
                    <div className="gen-functional-section">
                      <h5>Functional Analysis</h5>
                      {funcAnalysis.functions_served?.map((fn, i) => (
                        <div key={i} className="gen-function-item">
                          <span className="gen-function-type">
                            {fn.function_type.replace(/_/g, ' ')}
                          </span>
                          <p>{fn.description}</p>
                        </div>
                      ))}
                      {funcAnalysis.conditions_of_possibility && (
                        <div className="gen-func-conditions">
                          <strong>Conditions of Possibility:</strong>
                          <p>{funcAnalysis.conditions_of_possibility}</p>
                        </div>
                      )}
                      {funcAnalysis.what_would_be_impossible_without && (
                        <div className="gen-func-impossible">
                          <strong>What would be impossible without prior work:</strong>
                          <p>{funcAnalysis.what_would_be_impossible_without}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* V2: Cross-cutting patterns — synthesis panel */}
      {isV2 && v2Data?.cross_cutting_patterns && (
        <div className="gen-evo-synthesis-panel">
          <div className="gen-evo-synthesis-label">Cross-Cutting Patterns</div>

          {v2Data.cross_cutting_patterns.overall_trajectory && (
            <div className="gen-evo-trajectory">
              <div className="gen-evo-trajectory-icon">{'\u2192'}</div>
              <div className="gen-evo-trajectory-text">
                {v2Data.cross_cutting_patterns.overall_trajectory}
              </div>
            </div>
          )}

          <div className="gen-evo-patterns-grid">
            {v2Data.cross_cutting_patterns.dominant_evolution_pattern && (
              <div className="gen-evo-pattern-cell">
                <div className="gen-evo-pattern-cell-label">Dominant Pattern</div>
                <span className="gen-pattern-badge">
                  {v2Data.cross_cutting_patterns.dominant_evolution_pattern.replace(/_/g, ' ')}
                </span>
              </div>
            )}
            {v2Data.cross_cutting_patterns.audience_calibration && (
              <div className="gen-evo-pattern-cell">
                <div className="gen-evo-pattern-cell-label">Audience Calibration</div>
                <p>{v2Data.cross_cutting_patterns.audience_calibration}</p>
              </div>
            )}
            {v2Data.cross_cutting_patterns.prescription_diagnosis_gap && (
              <div className="gen-evo-pattern-cell">
                <div className="gen-evo-pattern-cell-label">Prescription-Diagnosis Gap</div>
                <p>{v2Data.cross_cutting_patterns.prescription_diagnosis_gap}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
