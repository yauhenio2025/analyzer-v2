/**
 * StatSummaryRenderer — Key statistics display with optional prose section.
 *
 * renderer_config keys:
 *   stats: (string | {key, label, format?})[]  — fields to show as stat cards
 *   prose_section: string                       — key of a longer narrative field
 *   layout: "stats_above_prose" | "prose_above_stats"  (default: stats_above_prose)
 *   prose_endpoint: string                      — for useProseExtraction
 */

import React, { useMemo } from 'react';
import { RendererProps } from '../types';
import { useProseExtraction } from '../hooks/useProseExtraction';

interface StatDef {
  key: string;
  label: string;
  format?: 'text' | 'list' | 'number' | 'badge';
}

function renderStatValue(value: unknown): React.ReactNode {
  if (value == null) {
    return <span style={{ color: 'var(--dt-text-faint)', fontStyle: 'italic' }}>Not available</span>;
  }

  if (Array.isArray(value)) {
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: '4px', marginTop: '4px' }}>
        {value.map((item, i) => (
          <span
            key={i}
            style={{
              display: 'inline-block',
              padding: '2px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              fontWeight: 500,
              background: 'var(--dt-page-accent-bg, rgba(181, 52, 58, 0.08))',
              color: 'var(--dt-page-accent, #b5343a)',
              border: '1px solid var(--dt-page-accent-border, rgba(181, 52, 58, 0.2))',
            }}
          >
            {String(item).replace(/_/g, ' ')}
          </span>
        ))}
      </div>
    );
  }

  if (typeof value === 'number') {
    return <span style={{ fontSize: '18px', fontWeight: 600, color: 'var(--dt-text-default)' }}>{value}</span>;
  }

  return (
    <div style={{ fontSize: '13px', color: 'var(--dt-text-default)', lineHeight: '1.5', marginTop: '2px' }}>
      {String(value)}
    </div>
  );
}

export function StatSummaryRenderer({ data, config }: RendererProps) {
  const rawStats = config.stats as (string | StatDef)[] | undefined;
  const proseSection = config.prose_section as string | undefined;
  const layout = (config.layout as string) || 'stats_above_prose';
  const proseEndpoint = config.prose_endpoint as string | undefined;

  const { data: extractedData, loading, error, isProseMode } = useProseExtraction<unknown>(
    data as unknown,
    config._jobId as string | undefined,
    proseEndpoint || 'data'
  );

  const workingData = (isProseMode ? extractedData : data) as Record<string, unknown> | null;

  const stats: StatDef[] = useMemo(() => {
    if (!rawStats) return [];
    return rawStats.map(s =>
      typeof s === 'string' ? { key: s, label: s.replace(/_/g, ' ') } : s
    );
  }, [rawStats]);

  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' as const }}>
        <div className="gen-extracting-spinner" />
        <p>Loading summary data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gen-extraction-error" style={{ padding: '1rem' }}>
        <p>Could not load summary: {error}</p>
      </div>
    );
  }

  if (!workingData) {
    return <p className="gen-empty">No summary data available.</p>;
  }

  // Auto-detect stats from data keys if none configured
  const effectiveStats = stats.length > 0
    ? stats
    : Object.keys(workingData)
        .filter(k => !k.startsWith('_') && k !== proseSection)
        .map(k => ({ key: k, label: k.replace(/_/g, ' ') }));

  const proseText = proseSection ? (workingData[proseSection] as string | undefined) : undefined;

  const statsBlock = effectiveStats.length > 0 ? (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
      gap: '12px',
      marginBottom: proseText ? '16px' : '0',
    }}>
      {effectiveStats.map(stat => {
        const value = workingData[stat.key];
        if (value == null) return null;
        return (
          <div
            key={stat.key}
            style={{
              background: 'var(--color-surface-elev, #f5f3f0)',
              border: '1px solid var(--color-border, #e2e5e9)',
              borderRadius: '8px',
              padding: '12px 14px',
            }}
          >
            <div style={{
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--dt-text-faint)',
              textTransform: 'uppercase' as const,
              letterSpacing: '0.05em',
              marginBottom: '4px',
            }}>
              {stat.label}
            </div>
            {renderStatValue(value)}
          </div>
        );
      })}
    </div>
  ) : null;

  const proseBlock = proseText ? (
    <div style={{
      background: 'var(--color-surface-elev, #f5f3f0)',
      border: '1px solid var(--color-border, #e2e5e9)',
      borderRadius: '8px',
      padding: '16px',
    }}>
      {String(proseText).split('\n').map((p, i) =>
        p.trim() ? (
          <p key={i} style={{ fontSize: '13px', color: 'var(--dt-text-muted)', lineHeight: '1.6', margin: '0 0 8px 0' }}>
            {p}
          </p>
        ) : null
      )}
    </div>
  ) : null;

  return (
    <div className="gen-stat-summary-renderer">
      {isProseMode ? (
        <div className="gen-prose-badge">
          <span className="gen-prose-indicator">Extracted from analytical prose</span>
        </div>
      ) : null}

      {layout === 'prose_above_stats' ? (
        <>{proseBlock}{statsBlock}</>
      ) : (
        <>{statsBlock}{proseBlock}</>
      )}
    </div>
  );
}
