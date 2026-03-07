/**
 * TableRenderer — Multi-table display with LLM-driven table design.
 *
 * When receiving prose-mode data, requests table-format extraction from the LLM.
 * The LLM decides how many tables to create, what dimensions/columns to use,
 * and what data to put in rows — producing 3-5 meaningful analytical tables.
 *
 * Also supports config-driven single-table mode for structured data.
 *
 * renderer_config keys:
 *   columns: (string | {key, label, width?})[]  — column definitions (single-table mode)
 *   sortable: boolean                            — click column headers to sort (default: true)
 *   filterable: boolean                          — text filter input above tables
 *   items_path: string                           — dotted path to extract array from data
 *   prose_endpoint: string                       — base section name (auto-appends _table)
 */

import React, { useState, useMemo } from 'react';
import { RendererProps } from '../types';
import { useProseExtraction } from '../hooks/useProseExtraction';

interface ColumnDef {
  key: string;
  label: string;
  width?: string;
}

interface TableDef {
  title: string;
  description?: string;
  columns: ColumnDef[];
  rows: Record<string, unknown>[];
}

interface MultiTableData {
  tables: TableDef[];
  summary_note?: string;
}

function isMultiTableData(data: unknown): data is MultiTableData {
  return (
    data != null &&
    typeof data === 'object' &&
    Array.isArray((data as MultiTableData).tables) &&
    (data as MultiTableData).tables.length > 0
  );
}

function normalizeToArray(data: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object' && !Array.isArray(data)) {
    return Object.entries(data as Record<string, unknown>).map(([key, value]) => {
      if (value && typeof value === 'object') {
        return { _key: key, ...(value as Record<string, unknown>) };
      }
      return { _key: key, value };
    });
  }
  return [];
}

function getPath(obj: unknown, path: string): unknown {
  if (!path) return obj;
  const parts = path.split('.');
  let current: unknown = obj;
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

function formatCellValue(value: unknown): string {
  if (value == null) return '\u2014';
  if (typeof value === 'number') return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value)) return value.map(String).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

// ── Single Table Component ──────────────────────────────
function SingleTable({
  table,
  sortable,
  tableIndex,
}: {
  table: TableDef;
  sortable: boolean;
  tableIndex: number;
}) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  const columns: ColumnDef[] = useMemo(() => {
    if (table.columns && table.columns.length > 0) {
      return table.columns.map(col =>
        typeof col === 'string'
          ? { key: col, label: (col as string).replace(/_/g, ' ') }
          : col
      );
    }
    if (table.rows.length === 0) return [];
    return Object.keys(table.rows[0])
      .filter(k => !k.startsWith('_'))
      .map(k => ({ key: k, label: k.replace(/_/g, ' ') }));
  }, [table.columns, table.rows]);

  const sortedRows = useMemo(() => {
    if (!sortable || !sortCol) return table.rows;
    return [...table.rows].sort((a, b) => {
      const aVal = a[sortCol] ?? '';
      const bVal = b[sortCol] ?? '';
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortAsc ? aVal - bVal : bVal - aVal;
      }
      const cmp = String(aVal).localeCompare(String(bVal));
      return sortAsc ? cmp : -cmp;
    });
  }, [table.rows, sortCol, sortAsc, sortable]);

  const handleSort = (colKey: string) => {
    if (!sortable) return;
    if (sortCol === colKey) {
      setSortAsc(!sortAsc);
    } else {
      setSortCol(colKey);
      setSortAsc(true);
    }
  };

  if (columns.length === 0 || table.rows.length === 0) return null;

  // Alternate subtle row tints per table
  const accentHues = [0, 210, 35, 280, 150]; // red, blue, amber, purple, teal
  const hue = accentHues[tableIndex % accentHues.length];

  return (
    <div style={{
      background: 'var(--color-surface-elev, #f5f3f0)',
      border: '1px solid var(--color-border, #e2e5e9)',
      borderRadius: '10px',
      overflow: 'hidden',
    }}>
      {/* Table header */}
      <div style={{
        padding: '14px 18px 10px',
        borderBottom: '1px solid var(--color-border, #e2e5e9)',
      }}>
        <h4 style={{
          margin: '0 0 2px 0',
          fontSize: '14px',
          fontWeight: 700,
          color: 'var(--dt-text-default)',
          letterSpacing: '-0.01em',
        }}>
          {table.title}
        </h4>
        {table.description ? (
          <p style={{
            margin: 0,
            fontSize: '12px',
            color: 'var(--dt-text-muted)',
            lineHeight: '1.4',
          }}>
            {table.description}
          </p>
        ) : null}
      </div>

      {/* Table content */}
      <div style={{ overflowX: 'auto' as const }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse' as const,
          fontSize: '13px',
        }}>
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{
                    textAlign: 'left' as const,
                    padding: '10px 14px',
                    borderBottom: `2px solid hsla(${hue}, 40%, 50%, 0.25)`,
                    color: 'var(--dt-text-muted)',
                    fontSize: '11px',
                    fontWeight: 700,
                    textTransform: 'uppercase' as const,
                    letterSpacing: '0.06em',
                    cursor: sortable ? 'pointer' : 'default',
                    userSelect: 'none' as const,
                    whiteSpace: 'nowrap' as const,
                    width: col.width || 'auto',
                    background: `hsla(${hue}, 30%, 50%, 0.04)`,
                    transition: 'background 0.15s',
                  }}
                >
                  {col.label}
                  {sortable && sortCol === col.key ? (
                    <span style={{ marginLeft: '4px', fontSize: '9px' }}>
                      {sortAsc ? '\u25B2' : '\u25BC'}
                    </span>
                  ) : sortable ? (
                    <span style={{ marginLeft: '4px', fontSize: '9px', opacity: 0.3 }}>
                      {'\u25B2'}
                    </span>
                  ) : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, idx) => (
              <tr
                key={idx}
                style={{
                  borderBottom: idx < sortedRows.length - 1
                    ? '1px solid var(--color-border, #e2e5e9)'
                    : 'none',
                  background: idx % 2 === 1
                    ? `hsla(${hue}, 20%, 50%, 0.03)`
                    : 'transparent',
                }}
              >
                {columns.map((col, colIdx) => (
                  <td
                    key={col.key}
                    style={{
                      padding: '10px 14px',
                      color: colIdx === 0 ? 'var(--dt-text-default)' : 'var(--dt-text-muted)',
                      fontWeight: colIdx === 0 ? 600 : 400,
                      lineHeight: '1.45',
                      verticalAlign: 'top' as const,
                      maxWidth: '400px',
                    }}
                  >
                    {formatCellValue(row[col.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Row count */}
      <div style={{
        padding: '6px 14px',
        fontSize: '11px',
        color: 'var(--dt-text-faint)',
        textAlign: 'right' as const,
        borderTop: '1px solid var(--color-border, #e2e5e9)',
        background: `hsla(${hue}, 20%, 50%, 0.02)`,
      }}>
        {table.rows.length} row{table.rows.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}

// ── Main TableRenderer ──────────────────────────────────
export function TableRenderer({ data, config }: RendererProps) {
  const rawColumns = config.columns as (string | ColumnDef)[] | undefined;
  const sortable = (config.sortable as boolean) ?? true;
  const filterable = (config.filterable as boolean) ?? false;
  const itemsPath = config.items_path as string | undefined;
  const proseEndpoint = config.prose_endpoint as string | undefined;

  // For table rendering, use the _table variant of the prose endpoint
  // so the LLM produces multi-table structured output
  const tableEndpoint = proseEndpoint ? `${proseEndpoint}_table` : 'data';

  const { data: extractedData, loading, error, isProseMode } = useProseExtraction<unknown>(
    data as unknown,
    config._jobId as string | undefined,
    tableEndpoint
  );

  const workingData = isProseMode ? extractedData : data;

  const [filterText, setFilterText] = useState('');

  // ── Multi-table mode (LLM-generated tables) ──
  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' as const }}>
        <div className="gen-extracting-spinner" />
        <p style={{ color: 'var(--dt-text-muted)', fontSize: '13px' }}>
          Designing analytical tables...
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gen-extraction-error" style={{ padding: '1rem' }}>
        <p>Could not load table data: {error}</p>
      </div>
    );
  }

  if (!workingData) {
    return <p className="gen-empty">No data available for table display.</p>;
  }

  // Check if we got multi-table format from the LLM
  if (isMultiTableData(workingData)) {
    const { tables, summary_note } = workingData;

    // Filter across all tables if filterable
    const filteredTables = filterable && filterText.trim()
      ? tables.map(t => ({
          ...t,
          rows: t.rows.filter(row =>
            t.columns.some(col => {
              const val = row[col.key];
              return val != null && String(val).toLowerCase().includes(filterText.toLowerCase());
            })
          ),
        })).filter(t => t.rows.length > 0)
      : tables;

    return (
      <div className="gen-table-renderer">
        {isProseMode ? (
          <div className="gen-prose-badge">
            <span className="gen-prose-indicator">Extracted from analytical prose</span>
          </div>
        ) : null}

        {filterable ? (
          <div style={{ marginBottom: '16px' }}>
            <input
              type="text"
              placeholder="Filter across all tables..."
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                border: '1px solid var(--color-border, #e2e5e9)',
                borderRadius: '6px',
                fontSize: '13px',
                background: 'var(--color-surface-elev, #f5f3f0)',
                color: 'var(--dt-text-default)',
                boxSizing: 'border-box' as const,
              }}
            />
          </div>
        ) : null}

        <div style={{ display: 'flex', flexDirection: 'column' as const, gap: '20px' }}>
          {filteredTables.map((table, idx) => (
            <SingleTable
              key={idx}
              table={table}
              sortable={sortable}
              tableIndex={idx}
            />
          ))}
        </div>

        {summary_note ? (
          <div style={{
            marginTop: '16px',
            padding: '12px 16px',
            background: 'var(--dt-surface-alt, rgba(100, 116, 139, 0.06))',
            borderRadius: '8px',
            borderLeft: '3px solid var(--dt-border-light, rgba(100, 116, 139, 0.25))',
          }}>
            <p style={{
              margin: 0,
              fontSize: '13px',
              color: 'var(--dt-text-muted)',
              lineHeight: '1.55',
              fontStyle: 'italic' as const,
            }}>
              {summary_note}
            </p>
          </div>
        ) : null}

        <div style={{
          marginTop: '8px',
          fontSize: '11px',
          color: 'var(--dt-text-faint)',
          textAlign: 'right' as const,
        }}>
          {filteredTables.length} table{filteredTables.length !== 1 ? 's' : ''}
          {' \u00B7 '}
          {filteredTables.reduce((sum, t) => sum + t.rows.length, 0)} total rows
        </div>
      </div>
    );
  }

  // ── Single-table fallback (config-driven for structured data) ──
  const columns: ColumnDef[] = rawColumns
    ? rawColumns.map(col =>
        typeof col === 'string' ? { key: col, label: col.replace(/_/g, ' ') } : col
      )
    : [];

  const extracted = itemsPath ? getPath(workingData, itemsPath) : workingData;
  const rows = normalizeToArray(extracted);

  if (rows.length === 0) {
    return <p className="gen-empty">No data available for this table.</p>;
  }

  // Build a single TableDef and delegate to SingleTable
  const autoColumns: ColumnDef[] = columns.length > 0
    ? columns
    : Object.keys(rows[0])
        .filter(k => !k.startsWith('_'))
        .map(k => ({ key: k, label: k.replace(/_/g, ' ') }));

  const singleTable: TableDef = {
    title: '',
    columns: autoColumns,
    rows,
  };

  return (
    <div className="gen-table-renderer">
      {filterable ? (
        <div style={{ marginBottom: '12px' }}>
          <input
            type="text"
            placeholder="Filter rows..."
            value={filterText}
            onChange={e => setFilterText(e.target.value)}
            style={{
              width: '100%',
              padding: '6px 10px',
              border: '1px solid var(--color-border, #e2e5e9)',
              borderRadius: '4px',
              fontSize: '13px',
              background: 'var(--color-surface-elev, #f5f3f0)',
              color: 'var(--dt-text-default)',
              boxSizing: 'border-box' as const,
            }}
          />
        </div>
      ) : null}

      <SingleTable
        table={filterable && filterText.trim()
          ? {
              ...singleTable,
              rows: singleTable.rows.filter(row =>
                autoColumns.some(col => {
                  const val = row[col.key];
                  return val != null && String(val).toLowerCase().includes(filterText.toLowerCase());
                })
              ),
            }
          : singleTable
        }
        sortable={sortable}
        tableIndex={0}
      />
    </div>
  );
}
