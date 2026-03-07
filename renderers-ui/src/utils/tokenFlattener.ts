/**
 * Token Flattener - Converts nested DesignTokenSet to flat CSS custom properties.
 *
 * Transforms the structured token hierarchy into a flat Record<string, string>
 * where keys are CSS custom property names (--dt-*) and values are token values.
 * This is injected into the DOM via element.style.setProperty() by DesignTokenContext.
 */

import { DesignTokenSet, SemanticTriple, CategoricalItem } from '../types/designTokens';

/**
 * Flattens a nested DesignTokenSet into a flat Record<string, string>
 * where keys are CSS custom property names (--dt-*) and values are the token values.
 */
export function flattenTokens(tokens: DesignTokenSet): Record<string, string> {
  const result: Record<string, string> = {};

  // Tier 1: Primitives (skip non-CSS values like series_palette array)
  const primitives = tokens.primitives;
  for (const [key, value] of Object.entries(primitives)) {
    if (key === 'series_palette') {
      // Store each series color individually
      (value as string[]).forEach((color, i) => {
        result[`--dt-series-${i}`] = color;
      });
    } else {
      result[`--dt-${key.replace(/_/g, '-')}`] = value as string;
    }
  }

  // Tier 2: Surfaces
  for (const [key, value] of Object.entries(tokens.surfaces)) {
    result[`--dt-${key.replace(/_/g, '-')}`] = value as string;
  }

  // Tier 3: Scales
  for (const [key, value] of Object.entries(tokens.scales)) {
    result[`--dt-${key.replace(/_/g, '-')}`] = value as string;
  }

  // Tier 4: Semantic (each is a SemanticTriple with bg, text, border)
  for (const [key, triple] of Object.entries(tokens.semantic)) {
    const t = triple as SemanticTriple;
    result[`--dt-${key.replace(/_/g, '-')}-bg`] = t.bg;
    result[`--dt-${key.replace(/_/g, '-')}-text`] = t.text;
    result[`--dt-${key.replace(/_/g, '-')}-border`] = t.border;
  }

  // Tier 5: Categorical (each is a CategoricalItem with bg, text, border, label)
  for (const [key, item] of Object.entries(tokens.categorical)) {
    const c = item as CategoricalItem;
    result[`--dt-${key.replace(/_/g, '-')}-bg`] = c.bg;
    result[`--dt-${key.replace(/_/g, '-')}-text`] = c.text;
    result[`--dt-${key.replace(/_/g, '-')}-border`] = c.border;
    // Labels are not CSS properties - they're accessed via JS context
  }

  // Tier 6: Components
  for (const [key, value] of Object.entries(tokens.components)) {
    result[`--dt-${key.replace(/_/g, '-')}`] = value as string;
  }

  return result;
}
