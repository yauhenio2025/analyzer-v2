/**
 * Shared style override types for the renderer system.
 *
 * StyleOverrides is the contract between the polish system (analyzer-v2)
 * and the frontend renderers. The polisher generates CSS property maps
 * for each injection point; renderers apply them as inline styles.
 *
 * 24 injection points total: 10 existing + 14 fine-grained.
 */

export interface StyleOverrides {
  // === Existing injection points ===
  section_header?: Record<string, string>;
  section_content?: Record<string, string>;
  card?: Record<string, string>;
  chip?: Record<string, string>;
  badge?: Record<string, string>;
  timeline_node?: Record<string, string>;
  prose?: Record<string, string>;
  accent_color?: string;
  view_wrapper?: Record<string, string>;
  items_container?: Record<string, string>;

  // === Fine-grained injection points ===
  section_title?: Record<string, string>;
  section_description?: Record<string, string>;
  card_header?: Record<string, string>;
  card_body?: Record<string, string>;
  chip_label?: Record<string, string>;
  chip_expanded?: Record<string, string>;
  prose_lede?: Record<string, string>;
  prose_body?: Record<string, string>;
  prose_quote?: Record<string, string>;
  timeline_connector?: Record<string, string>;
  stat_number?: Record<string, string>;
  stat_label?: Record<string, string>;
  hero_card?: Record<string, string>;
  view_header?: Record<string, string>;
}

/** Helper to extract StyleOverrides from a renderer config object. */
export function getSO(config: Record<string, unknown>): StyleOverrides | undefined {
  return config._style_overrides as StyleOverrides | undefined;
}
