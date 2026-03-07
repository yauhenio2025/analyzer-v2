/**
 * ProvenanceSectionIcon — Stub for the provenance icon in accordion section headers.
 *
 * Consumer apps that support provenance tracking should override this component
 * by importing and registering their own implementation.
 */

import React from 'react';

interface ProvenanceSectionIconProps {
  sectionKey: string;
  config: unknown;
  children_payloads?: unknown;
}

/** Default no-op stub — renders nothing. Consumer apps override for provenance UI. */
export function ProvenanceSectionIcon(_props: ProvenanceSectionIconProps) {
  return null;
}
