/**
 * Cell Renderer Registry — Domain-specific card content components.
 */

import React from 'react';
import { TemplateCardCell } from './TemplateCardCell';
import type { CellRendererProps, CellRendererComponent } from '../types';

export type { CellRendererProps, CellRendererComponent };

/** Registry of cell renderers keyed by config.cell_renderer string */
export const cellRenderers: Record<string, CellRendererComponent> = {
  template_card: TemplateCardCell,
};

// Field classification for intelligent rendering
const TITLE_FIELDS = ['name', 'title', 'finding', 'concept', 'idea', 'theme'];
const BODY_FIELDS = ['condition', 'description', 'analysis', 'significance', 'explanation', 'mechanism', 'details', 'summary', 'how_it_enables', 'how_it_constrains', 'effect'];
const EVIDENCE_FIELDS = ['evidence', 'reasoning', 'supporting_evidence', 'rationale', 'justification'];
const META_FIELDS = new Set(['_category', 'docKey', 'condition_id', 'id', 'index', 'order']);

function classifyField(key: string): 'title' | 'body' | 'evidence' | 'tag' | 'skip' {
  if (META_FIELDS.has(key)) return 'skip';
  if (TITLE_FIELDS.includes(key)) return 'title';
  if (BODY_FIELDS.includes(key)) return 'body';
  if (EVIDENCE_FIELDS.includes(key)) return 'evidence';
  return 'tag';
}

function formatLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

/**
 * Default cell renderer — auto-classifies item fields into visual tiers.
 *
 * When renderer_config declares explicit field mappings (title_field,
 * subtitle_field, description_field, badge_field), only those fields
 * are rendered. Unmapped fields are suppressed.
 */
export function DefaultCardCell({ item, config }: CellRendererProps) {
  const titleField = (config.title_field ?? config.card_title_field) as string | undefined;
  const subtitleField = config.subtitle_field as string | undefined;
  const descriptionField = (config.description_field ?? config.card_body_field) as string | undefined;
  const badgeField = config.badge_field as string | undefined;
  const hasExplicitMapping = !!(titleField || subtitleField || descriptionField || badgeField);

  const str = (key: string): string => {
    const v = item[key];
    return (v != null && v !== '' && typeof v !== 'object') ? String(v) : '';
  };

  // ── Explicit-mapping path: render only the declared fields ──
  if (hasExplicitMapping) {
    const titleText = titleField ? str(titleField) : '';
    const subtitleText = subtitleField ? str(subtitleField) : '';
    const descText = descriptionField ? str(descriptionField) : '';
    const badgeText = badgeField ? str(badgeField) : '';
    const badgeNorm = badgeText.toLowerCase().replace(/[^a-z]/g, '');
    const badgeClass = badgeText ? `card-cell-badge card-cell-badge--${badgeNorm}` : '';

    return React.createElement('div', { className: 'card-cell-default' },
      titleText
        ? React.createElement('div', { className: 'card-cell-title' },
            titleText.length > 200 ? titleText.slice(0, 200) + '\u2026' : titleText
          )
        : null,
      subtitleText
        ? React.createElement('div', { className: 'card-cell-subtitle' }, subtitleText)
        : null,
      descText
        ? React.createElement('p', { className: 'card-cell-body' }, descText)
        : null,
      badgeText
        ? React.createElement('span', { className: badgeClass }, badgeText.replace(/_/g, ' '))
        : null,
    );
  }

  // ── Auto-classification fallback (no explicit field mapping) ──
  let titleText = '';
  let bodyText = '';
  let evidenceText = '';
  const tags: Array<[string, string]> = [];

  for (const [key, value] of Object.entries(item)) {
    if (value == null || value === '') continue;
    if (typeof value === 'object') continue;
    const strVal = String(value);
    const cls = classifyField(key);
    if (cls === 'skip') continue;
    if (cls === 'title' && !titleText) { titleText = strVal; continue; }
    if (cls === 'body' && !bodyText) { bodyText = strVal; continue; }
    if (cls === 'evidence' && !evidenceText) { evidenceText = strVal; continue; }
    if (cls === 'tag') tags.push([key, strVal]);
  }

  if (!titleText && bodyText && bodyText.length < 120) {
    titleText = bodyText;
    bodyText = '';
  }

  return React.createElement('div', { className: 'card-cell-default' },
    titleText
      ? React.createElement('div', { className: 'card-cell-title' },
          titleText.length > 200 ? titleText.slice(0, 200) + '\u2026' : titleText
        )
      : null,
    bodyText
      ? React.createElement('p', { className: 'card-cell-body' }, bodyText)
      : null,
    evidenceText
      ? React.createElement('blockquote', { className: 'card-cell-evidence' }, evidenceText)
      : null,
    tags.length > 0
      ? React.createElement('div', { className: 'card-cell-tags' },
          ...tags.slice(0, 4).map(([k, v]) =>
            React.createElement('span', { key: k, className: 'card-cell-tag' },
              React.createElement('span', { className: 'card-cell-tag-label' }, formatLabel(k)),
              ' ',
              v.replace(/_/g, ' ')
            )
          )
        )
      : null
  );
}
