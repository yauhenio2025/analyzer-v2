/**
 * ProseRenderer — Generic renderer for narrative/prose content.
 *
 * Renders text data as formatted prose with section anchors.
 * Used as the default fallback for unknown renderer_types.
 */

import React from 'react';
import { RendererProps } from '../types';

export function ProseRenderer({ data, config }: RendererProps) {
  if (!data) {
    return <p className="gen-empty">No data available for this view.</p>;
  }

  // If data is a string, render directly
  if (typeof data === 'string') {
    return (
      <div className="gen-prose-renderer">
        <div
          className="gen-prose-content"
          dangerouslySetInnerHTML={{ __html: formatProse(data) }}
        />
      </div>
    );
  }

  // If data is an object with text fields, render them
  if (typeof data === 'object') {
    const obj = data as Record<string, unknown>;

    // Handle _prose_output marker (prose-mode workflow output)
    if (typeof obj._prose_output === 'string') {
      return (
        <div className="gen-prose-renderer">
          <div
            className="gen-prose-content"
            dangerouslySetInnerHTML={{ __html: formatProse(obj._prose_output) }}
          />
        </div>
      );
    }

    // Try known prose field names
    const proseFields = ['text', 'content', 'prose', 'narrative', 'summary',
      'executive_summary', 'genealogical_portrait', 'description'];

    for (const field of proseFields) {
      if (typeof obj[field] === 'string') {
        return (
          <div className="gen-prose-renderer">
            <div
              className="gen-prose-content"
              dangerouslySetInnerHTML={{ __html: formatProse(obj[field] as string) }}
            />
          </div>
        );
      }
    }

    // Fallback: show JSON
    return (
      <div className="gen-prose-renderer">
        <pre className="gen-raw-json">
          {JSON.stringify(data, null, 2)}
        </pre>
      </div>
    );
  }

  return <p className="gen-empty">Unsupported data format.</p>;
}

export function formatProse(text: string): string {
  // Convert markdown-like headers and paragraphs to HTML
  return text
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}
