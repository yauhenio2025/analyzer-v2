/**
 * Renderer type definitions — shared across all consumer apps.
 */

import React from 'react';

/** The props every top-level renderer receives. */
export interface RendererProps {
  /** The full analysis result data — renderers pick what they need */
  data: unknown;
  /** Renderer-specific configuration from the view definition */
  config: Record<string, unknown>;
  /** Children views (for container renderers like tabs) */
  children?: React.ReactNode;
}

export type RendererComponent = React.ComponentType<RendererProps>;

/** The props every cell renderer receives (inside card grids). */
export interface CellRendererProps {
  /** The individual item to render inside a card */
  item: Record<string, unknown>;
  /** The full renderer_config from the view definition */
  config: Record<string, unknown>;
}

export type CellRendererComponent = React.ComponentType<CellRendererProps>;

/** The props every sub-renderer receives (inside accordion sections). */
export interface SubRendererProps {
  data: unknown;
  config: Record<string, unknown>;
}

export type SubRendererComponent = React.FC<SubRendererProps>;

// Re-export from sibling type files
export type {
  StyleOverrides,
} from './styles';
export { getSO } from './styles';

export type {
  DesignTokenSet,
  SemanticTriple,
  CategoricalItem,
  PrimitiveTokens,
  SurfaceTokens,
  ScaleTokens,
  SemanticTokens,
  CategoricalTokens,
  ComponentTokens,
} from './designTokens';
