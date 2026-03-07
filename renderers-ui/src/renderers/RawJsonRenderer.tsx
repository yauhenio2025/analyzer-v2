/**
 * RawJsonRenderer — Debug renderer showing raw JSON data.
 *
 * Used for on_demand debug views. Collapsible with syntax highlighting.
 */

import React, { useState } from 'react';
import { RendererProps } from '../types';

export function RawJsonRenderer({ data, config }: RendererProps) {
  const [collapsed, setCollapsed] = useState(true);

  if (!data) {
    return <p className="gen-empty">No raw data available.</p>;
  }

  const jsonString = JSON.stringify(data, null, 2);
  const lineCount = jsonString.split('\n').length;

  return (
    <div className="gen-raw-json-renderer">
      <div className="gen-raw-header">
        <button
          className="gen-raw-toggle"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? '\u25B6' : '\u25BC'} Raw JSON ({lineCount} lines)
        </button>
      </div>
      {!collapsed && (
        <pre className="gen-raw-json">
          {jsonString}
        </pre>
      )}
    </div>
  );
}
