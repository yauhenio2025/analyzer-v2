import React from 'react';

import { getRendererCapabilities } from '../capabilities';

interface ViewShellProps {
  rendererType: string;
  scaffold?: Record<string, unknown> | null;
  fallbackScaffold?: React.ReactNode;
  children: (rendererScaffold: Record<string, unknown> | null) => React.ReactNode;
}

export function ViewShell({
  rendererType,
  scaffold = null,
  fallbackScaffold = null,
  children,
}: ViewShellProps) {
  const capabilities = getRendererCapabilities(rendererType);
  const rendererScaffold = capabilities.integratesScaffold ? scaffold : null;

  return (
    <>
      {!capabilities.integratesScaffold ? fallbackScaffold : null}
      {children(rendererScaffold)}
    </>
  );
}
