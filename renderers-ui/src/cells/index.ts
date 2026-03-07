/**
 * Cell Renderer Registry — Domain-specific card content components.
 */

import React from 'react';
import { TacticCardCell } from './TacticCardCell';
import { RelationshipCardCell } from './RelationshipCardCell';
import { TemplateCardCell } from './TemplateCardCell';
import type { CellRendererProps, CellRendererComponent } from '../types';

export type { CellRendererProps, CellRendererComponent };

/** Registry of cell renderers keyed by config.cell_renderer string */
export const cellRenderers: Record<string, CellRendererComponent> = {
  tactic_card: TacticCardCell,
  relationship_card: RelationshipCardCell,
  template_card: TemplateCardCell,
};

// Field classification for intelligent rendering
const TITLE_FIELDS = ['name', 'title', 'finding', 'tactic_name', 'concept', 'idea', 'theme'];
const BODY_FIELDS = ['condition', 'description', 'analysis', 'significance', 'explanation', 'mechanism', 'details', 'summary', 'how_it_enables', 'how_it_constrains', 'effect'];
const EVIDENCE_FIELDS = ['evidence', 'reasoning', 'supporting_evidence', 'rationale', 'justification'];
const META_FIELDS = new Set(['_category', 'docKey', 'tactic_id', 'condition_id', 'id', 'index', 'order']);

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
 */
export function DefaultCardCell({ item, config }: CellRendererProps) {
  const titleFieldOverride = config.card_title_field as string | undefined;
  const bodyFieldOverride = config.card_body_field as string | undefined;

  let titleText = '';
  let bodyText = '';
  let evidenceText = '';
  const tags: Array<[string, string]> = [];

  for (const [key, value] of Object.entries(item)) {
    if (value == null || value === '') continue;
    if (typeof value === 'object') continue;

    const strVal = String(value);

    if (titleFieldOverride && key === titleFieldOverride) {
      titleText = strVal;
      continue;
    }
    if (bodyFieldOverride && key === bodyFieldOverride) {
      bodyText = strVal;
      continue;
    }

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
