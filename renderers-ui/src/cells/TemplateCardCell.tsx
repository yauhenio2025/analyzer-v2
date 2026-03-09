/**
 * TemplateCardCell -- Schema-driven card renderer.
 *
 * Instead of hardcoding field→UI mapping in React, this cell renderer
 * interprets a `card_template` JSON structure from the view definition.
 * Each "slot" in the template maps to an atomic rendering block:
 *
 *   badge_row       -- Row of colored badges (category or semantic colors)
 *   heading         -- Title text, optionally hidden when it matches a label
 *   prose           -- Paragraph text with optional subdued state
 *   chip_list       -- Array of string chips with optional link hints
 *   evidence_trail  -- Multi-step evidence chain (prior -> current -> assessment)
 *   key_value       -- Key-value pairs rendered as a compact table
 *   separator       -- Visual divider
 *
 * Template schema (in renderer_config.card_template):
 *   {
 *     wrapper_class?: string,           -- CSS class for outer div
 *     border_accent?: ColorRef,         -- Border-left color from design tokens
 *     border_weight_field?: string,     -- Field to read for border thickness
 *     border_weight_map?: Record<string, string>,  -- value -> CSS width
 *     slots: SlotConfig[]               -- Ordered list of content blocks
 *   }
 *
 * New renderers = new JSON. No React code needed.
 */

import React, { useState } from 'react';
import { CellRendererProps } from '../types';
import { useDesignTokens } from '../tokens/DesignTokenContext';
import { EvidenceTrail, EvidenceTrailStep, EvidenceTrailItem } from '../components/EvidenceTrail';

// ── Types ──────────────────────────────────────────────

interface ColorRef {
  category: string;
  key_field: string;
}

interface BadgeConfig {
  field: string;
  color_mode: 'category' | 'semantic';
  color_category?: string;
  color_scale?: string;
  transform?: 'lowercase' | 'uppercase' | 'titlecase';
  value_map?: Record<string, string>;
  default_value?: string;
}

interface EvidenceStepConfig {
  label: string;
  field: string;
  variant: 'prior' | 'current' | 'assessment';
  item_title_field?: string;
  item_quote_field?: string;
  item_cite_field?: string;
  is_text?: boolean;
}

interface SlotConfig {
  type: string;
  field?: string;
  label?: string;
  // badge_row
  badges?: BadgeConfig[];
  // heading
  hide_when_matches_label?: ColorRef;
  // prose
  subdued_when?: { field: string; equals: string };
  // chip_list
  link_title_pattern?: string;
  item_label_field?: string;
  item_tooltip_field?: string;
  // evidence_trail
  steps?: EvidenceStepConfig[];
  accent_from?: ColorRef;
  collapsed_by_default?: boolean;
  // key_value
  entries?: Array<{ field: string; label: string }>;
}

interface CardTemplate {
  wrapper_class?: string;
  border_accent?: ColorRef;
  border_weight_field?: string;
  border_weight_map?: Record<string, string>;
  slots: SlotConfig[];
}

type GetCategoryColor = (cat: string, key: string) => { bg: string; text: string; border: string; label?: string } | null;
type GetSemanticColor = (scale: string, level: string) => { bg: string; text: string; border: string } | null;
type GetLabel = (cat: string, key: string) => string;

// ── Block: badge_row ───────────────────────────────────

function BadgeRowBlock({ badges, item, getCategoryColor, getSemanticColor, getLabel }: {
  badges: BadgeConfig[];
  item: Record<string, unknown>;
  getCategoryColor: GetCategoryColor;
  getSemanticColor: GetSemanticColor;
  getLabel: GetLabel;
}) {
  return (
    <div className="ar-card-badge-row">
      {badges.map((badge, idx) => {
        const rawValue = String(item[badge.field] || badge.default_value || '');
        if (!rawValue) return null;

        let displayValue = rawValue;
        let colors: { bg: string; text: string; border?: string } | null = null;

        if (badge.color_mode === 'category' && badge.color_category) {
          colors = getCategoryColor(badge.color_category, rawValue);
          displayValue = getLabel(badge.color_category, rawValue) || rawValue.replace(/_/g, ' ');
        } else if (badge.color_mode === 'semantic' && badge.color_scale) {
          const key = rawValue.toLowerCase();
          const tokenKey = badge.value_map?.[key] || key;
          colors = getSemanticColor(badge.color_scale, tokenKey);
          displayValue = key;
        }

        if (badge.transform === 'lowercase') displayValue = displayValue.toLowerCase();
        else if (badge.transform === 'uppercase') displayValue = displayValue.toUpperCase();
        else if (badge.transform === 'titlecase') displayValue = displayValue.replace(/\b\w/g, c => c.toUpperCase());

        const fallback = { bg: '#f8fafc', text: '#334155', border: '#e2e8f0' };
        const c = colors || fallback;

        const isSemantic = badge.color_mode === 'semantic';
        const className = isSemantic
          ? `ar-severity-badge ar-severity-badge--${rawValue.toLowerCase()}`
          : 'ar-card-type-badge';

        return (
          <span
            key={idx}
            className={className}
            style={{ background: c.bg, color: c.text, borderColor: c.border }}
          >
            {displayValue}
          </span>
        );
      })}
    </div>
  );
}

// ── Block: heading ─────────────────────────────────────

function HeadingBlock({ field, item, hideWhenMatchesLabel, getLabel }: {
  field: string;
  item: Record<string, unknown>;
  hideWhenMatchesLabel?: ColorRef;
  getLabel: GetLabel;
}) {
  const text = String(item[field] || '');
  if (!text) return null;

  if (hideWhenMatchesLabel) {
    const keyValue = String(item[hideWhenMatchesLabel.key_field] || '');
    const label = getLabel(hideWhenMatchesLabel.category, keyValue);
    if (text === label) return null;
  }

  return <h4 className="ar-card-heading">{text}</h4>;
}

// ── Block: prose ───────────────────────────────────────

function ProseBlock({ field, item, subduedWhen }: {
  field: string;
  item: Record<string, unknown>;
  subduedWhen?: { field: string; equals: string };
}) {
  const text = String(item[field] || '');
  if (!text) return null;

  const isSubdued = subduedWhen
    && String(item[subduedWhen.field] || '').toLowerCase() === subduedWhen.equals;

  return (
    <p className={`ar-card-prose${isSubdued ? ' ar-card-prose--subdued' : ''}`}>
      {text}
    </p>
  );
}

// ── Block: chip_list ───────────────────────────────────

function ChipListBlock({ field, item, label, linkTitlePattern, itemLabelField, itemTooltipField }: {
  field: string;
  item: Record<string, unknown>;
  label?: string;
  linkTitlePattern?: string;
  itemLabelField?: string;
  itemTooltipField?: string;
}) {
  const raw = item[field];
  if (!raw || !Array.isArray(raw) || raw.length === 0) return null;

  // Normalize: support both string[] and {label_field, tooltip_field}[]
  const chips = raw.map((val, idx) => {
    if (typeof val === 'string') {
      return { key: val || String(idx), text: val, tooltip: linkTitlePattern ? linkTitlePattern.replace('{value}', val) : undefined };
    }
    if (val && typeof val === 'object') {
      const obj = val as Record<string, unknown>;
      const text = itemLabelField ? String(obj[itemLabelField] || '') : JSON.stringify(val);
      const tooltip = itemTooltipField ? String(obj[itemTooltipField] || '') : undefined;
      return { key: text || String(idx), text, tooltip };
    }
    return { key: String(idx), text: String(val), tooltip: undefined };
  }).filter(c => c.text);

  if (chips.length === 0) return null;

  return (
    <div className="ar-card-chip-list">
      {label && <span className="ar-card-section-label">{label}</span>}
      <div className="gen-idea-tags">
        {chips.map((chip, idx) => (
          <span
            key={`${chip.key}-${idx}`}
            className="gen-idea-tag gen-idea-tag--linked"
            title={chip.tooltip}
          >
            {chip.text}
          </span>
        ))}
      </div>
    </div>
  );
}

// ── Block: evidence_trail ──────────────────────────────

function EvidenceTrailBlock({ steps, item, label, accentFrom, collapsedByDefault, getCategoryColor }: {
  steps: EvidenceStepConfig[];
  item: Record<string, unknown>;
  label?: string;
  accentFrom?: ColorRef;
  collapsedByDefault?: boolean;
  getCategoryColor: GetCategoryColor;
}) {
  const [collapsed, setCollapsed] = useState(collapsedByDefault ?? false);

  const trailSteps: EvidenceTrailStep[] = [];

  for (const sc of steps) {
    const raw = item[sc.field];
    if (raw === undefined || raw === null || raw === '') continue;

    const variant = sc.variant as EvidenceTrailStep['variant'];

    if (sc.is_text || typeof raw === 'string') {
      trailSteps.push({ label: sc.label, variant, text: String(raw) });
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
        trailSteps.push({ label: sc.label, variant, items });
      }
    }
  }

  if (trailSteps.length === 0) return null;

  let accentColor: string | undefined;
  let borderColor: string | undefined;
  if (accentFrom) {
    const keyValue = String(item[accentFrom.key_field] || '');
    const colors = getCategoryColor(accentFrom.category, keyValue);
    if (colors) {
      accentColor = colors.text;
      borderColor = colors.border;
    }
  }

  // Count total evidence pieces for the summary
  const pieceCount = trailSteps.reduce((n, s) => n + (s.items?.length || (s.text ? 1 : 0)), 0);

  return (
    <div className="gen-evidence-trail">
      <button
        type="button"
        className={`gen-evidence-toggle${collapsed ? ' gen-evidence-toggle--collapsed' : ''}`}
        onClick={(e) => { e.stopPropagation(); setCollapsed(!collapsed); }}
      >
        <span className="gen-evidence-toggle-icon">{'\u25B6'}</span>
        <span className="gen-evidence-toggle-label">
          {label || 'Evidence Trail'}
        </span>
        <span className="gen-evidence-count">{pieceCount}</span>
      </button>
      {!collapsed && (
        <EvidenceTrail steps={trailSteps} accentColor={accentColor} borderColor={borderColor} />
      )}
    </div>
  );
}

// ── Block: key_value ───────────────────────────────────

function KeyValueBlock({ entries, item }: {
  entries: Array<{ field: string; label: string }>;
  item: Record<string, unknown>;
}) {
  const pairs = entries
    .map(e => ({ label: e.label, value: item[e.field] }))
    .filter(p => p.value != null && p.value !== '');

  if (pairs.length === 0) return null;

  return (
    <div className="gen-template-kv">
      {pairs.map((p, idx) => (
        <div key={idx} className="gen-template-kv-row">
          <span className="gen-template-kv-label">{p.label}</span>
          <span className="gen-template-kv-value">{String(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Block: separator ───────────────────────────────────

function SeparatorBlock() {
  return <hr className="gen-template-separator" />;
}

// ── Slot dispatcher ────────────────────────────────────

function TemplateSlot({ slot, item, getCategoryColor, getSemanticColor, getLabel }: {
  slot: SlotConfig;
  item: Record<string, unknown>;
  getCategoryColor: GetCategoryColor;
  getSemanticColor: GetSemanticColor;
  getLabel: GetLabel;
}) {
  switch (slot.type) {
    case 'badge_row':
      return slot.badges ? (
        <BadgeRowBlock
          badges={slot.badges}
          item={item}
          getCategoryColor={getCategoryColor}
          getSemanticColor={getSemanticColor}
          getLabel={getLabel}
        />
      ) : null;

    case 'heading':
      return slot.field ? (
        <HeadingBlock
          field={slot.field}
          item={item}
          hideWhenMatchesLabel={slot.hide_when_matches_label}
          getLabel={getLabel}
        />
      ) : null;

    case 'prose':
      return slot.field ? (
        <ProseBlock field={slot.field} item={item} subduedWhen={slot.subdued_when} />
      ) : null;

    case 'chip_list':
      return slot.field ? (
        <ChipListBlock
          field={slot.field}
          item={item}
          label={slot.label}
          linkTitlePattern={slot.link_title_pattern}
          itemLabelField={slot.item_label_field}
          itemTooltipField={slot.item_tooltip_field}
        />
      ) : null;

    case 'evidence_trail':
      return slot.steps ? (
        <EvidenceTrailBlock
          steps={slot.steps}
          item={item}
          label={slot.label}
          accentFrom={slot.accent_from}
          collapsedByDefault={slot.collapsed_by_default}
          getCategoryColor={getCategoryColor}
        />
      ) : null;

    case 'key_value':
      return slot.entries ? (
        <KeyValueBlock entries={slot.entries} item={item} />
      ) : null;

    case 'separator':
      return <SeparatorBlock />;

    default:
      return null;
  }
}

// ── Main component ─────────────────────────────────────

export function TemplateCardCell({ item, config }: CellRendererProps) {
  const { getCategoryColor, getSemanticColor, getLabel } = useDesignTokens();

  const template = config.card_template as CardTemplate | undefined;
  if (!template || !template.slots) {
    return <p className="gen-empty">No card template configured.</p>;
  }

  // Compute wrapper styles from template config
  const wrapperClass = template.wrapper_class || '';
  const severityField = template.border_weight_field;
  const severityValue = severityField ? String(item[severityField] || '').toLowerCase() : '';
  const severityModifier = severityValue ? ` ${wrapperClass}--${severityValue}` : '';

  let borderStyle: React.CSSProperties | undefined;
  if (template.border_accent) {
    const keyValue = String(item[template.border_accent.key_field] || '');
    const colors = getCategoryColor(template.border_accent.category, keyValue);
    if (colors) {
      const width = template.border_weight_map?.[severityValue] || '4px';
      borderStyle = {
        borderTopColor: colors.text,
        borderTopWidth: width,
        borderTopStyle: 'solid',
      };
    }
  }

  const className = `${wrapperClass}${severityModifier}`.trim() || undefined;

  return (
    <div className={className} style={borderStyle}>
      {template.slots.map((slot, idx) => (
        <TemplateSlot
          key={idx}
          slot={slot}
          item={item}
          getCategoryColor={getCategoryColor}
          getSemanticColor={getSemanticColor}
          getLabel={getLabel}
        />
      ))}
    </div>
  );
}
