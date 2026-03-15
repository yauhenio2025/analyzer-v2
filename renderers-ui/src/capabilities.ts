export interface RendererCapabilities {
  integratesScaffold: boolean;
}

const DEFAULT_RENDERER_CAPABILITIES: RendererCapabilities = {
  integratesScaffold: false,
};

export const RENDERER_CAPABILITIES: Record<string, RendererCapabilities> = {
  accordion: { integratesScaffold: true },
};

export function getRendererCapabilities(rendererType: string): RendererCapabilities {
  return RENDERER_CAPABILITIES[rendererType] || DEFAULT_RENDERER_CAPABILITIES;
}
