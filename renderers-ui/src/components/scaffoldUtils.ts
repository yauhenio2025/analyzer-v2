export interface ScaffoldItem {
  label?: string;
  text?: string;
  view_key?: string;
}

export interface ScaffoldBlock {
  key?: string;
  title?: string;
  style?: string;
  items?: ScaffoldItem[];
}

export interface SectionIntro {
  section_key?: string;
  title?: string;
  intro?: string;
}

export function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0;
}

export function asBlocks(value: unknown): ScaffoldBlock[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is ScaffoldBlock => Boolean(item && typeof item === 'object'));
}

export function asSectionIntros(value: unknown): SectionIntro[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is SectionIntro => Boolean(item && typeof item === 'object'));
}

export function humanizeSurfaceType(value: string): string {
  return value.replace(/_/g, ' ');
}

export function hasScaffoldContent(scaffold?: Record<string, unknown> | null): boolean {
  if (!scaffold) return false;

  const blocks = asBlocks(scaffold.blocks);
  const sectionIntros = asSectionIntros(scaffold.section_intros);

  return isNonEmptyString(scaffold.brief)
    || isNonEmptyString(scaffold.how_to_read)
    || blocks.some(block => Array.isArray(block.items) && block.items.length > 0)
    || sectionIntros.some(section => isNonEmptyString(section.intro));
}
