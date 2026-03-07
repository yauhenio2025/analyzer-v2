/**
 * useProseExtraction — Detects prose-mode output and extracts structured data.
 *
 * Several workflow passes can produce output in "prose mode" (rich analytical
 * narrative) instead of structured JSON. When this happens the data contains
 * a `_prose_output` marker. This hook:
 *
 * 1. Detects the marker
 * 2. Calls the presentation extraction endpoint to get structured data
 * 3. Manages loading / error / extracted state
 *
 * Usage:
 *   const { data, loading, error, isProseMode } = useProseExtraction<Pass5Result>(
 *     result.pass5_tactics,
 *     result._job_id,
 *     'tactics'
 *   );
 */

import { useState, useEffect } from 'react';

// Consumer apps set this via env var. Supports CRA and Next.js conventions.
const API_BASE =
  (typeof process !== 'undefined' && process.env?.REACT_APP_API_URL) ||
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_URL) ||
  'http://localhost:5555/api';

interface ProseMarker {
  _prose_output: string;
  _output_mode: 'prose';
}

export interface ProseExtractionResult<T> {
  /** The structured data — either raw (if not prose) or extracted */
  data: T | null;
  /** Whether extraction is in progress */
  loading: boolean;
  /** Extraction error message, if any */
  error: string | null;
  /** Whether the source data was prose mode */
  isProseMode: boolean;
}

function isProseMarker(value: unknown): value is ProseMarker {
  return (
    value != null &&
    typeof value === 'object' &&
    '_prose_output' in (value as Record<string, unknown>)
  );
}

export function useProseExtraction<T>(
  rawData: T | ProseMarker | undefined,
  jobId: string | undefined,
  presentEndpoint: string // e.g. 'tactics', 'conditions', 'synthesis', 'functional'
): ProseExtractionResult<T> {
  const [extracted, setExtracted] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const proseMode = isProseMarker(rawData);

  useEffect(() => {
    // Not prose mode — nothing to extract
    if (!proseMode || !jobId) return;
    // Already extracted
    if (extracted) return;

    let cancelled = false;

    const fetchPresentation = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(
          `${API_BASE}/genealogy/${jobId}/present/${presentEndpoint}`,
          { method: 'POST' }
        );
        if (cancelled) return;

        if (response.ok) {
          const data = await response.json();
          setExtracted(data.data as T);
        } else {
          const errData = await response.json().catch(() => ({ detail: 'Unknown error' }));
          setError(errData.detail || `Extraction failed (${response.status})`);
        }
      } catch (e) {
        if (!cancelled) {
          setError(`Network error: ${e}`);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    fetchPresentation();

    return () => {
      cancelled = true;
    };
  }, [proseMode, jobId, presentEndpoint, extracted]);

  // Not prose mode — return raw data directly
  if (!proseMode) {
    return {
      data: (rawData as T) ?? null,
      loading: false,
      error: null,
      isProseMode: false,
    };
  }

  // Prose mode — return extracted data (or loading/error state)
  return {
    data: extracted,
    loading,
    error,
    isProseMode: true,
  };
}
