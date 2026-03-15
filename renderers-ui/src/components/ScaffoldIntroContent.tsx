import React from 'react';
import {
  asBlocks,
  asSectionIntros,
  hasScaffoldContent,
  humanizeSurfaceType,
  isNonEmptyString,
  ScaffoldItem,
} from './scaffoldUtils';

interface ScaffoldIntroContentProps {
  scaffold?: Record<string, unknown> | null;
}

const DEFAULT_VISIBLE_BLOCK_ITEMS = 2;
const DEFAULT_VISIBLE_SECTION_INTROS = 4;
const COLLAPSED_TEXT_LIMIT = 180;

function truncateText(value: string | undefined, maxChars = COLLAPSED_TEXT_LIMIT): string | undefined {
  if (!isNonEmptyString(value)) return value;
  if (value.length <= maxChars) return value;
  return `${value.slice(0, maxChars).trimEnd()}...`;
}

export function ScaffoldIntroContent({ scaffold }: ScaffoldIntroContentProps) {
  const [expandedBlocks, setExpandedBlocks] = React.useState<Record<string, boolean>>({});
  const [sectionGuideExpanded, setSectionGuideExpanded] = React.useState(false);
  const [guideCollapsed, setGuideCollapsed] = React.useState(false);
  const scaffoldValue = scaffold || {};
  const brief = isNonEmptyString(scaffoldValue.brief) ? scaffoldValue.brief : undefined;
  const howToRead = isNonEmptyString(scaffoldValue.how_to_read) ? scaffoldValue.how_to_read : undefined;
  const blocks = asBlocks(scaffoldValue.blocks);
  const sectionIntros = asSectionIntros(scaffoldValue.section_intros);
  const surfaceType = isNonEmptyString(scaffoldValue.surface_type) ? scaffoldValue.surface_type : undefined;
  const totalBlockItems = blocks.reduce(
    (sum, block) => sum + (Array.isArray(block.items) ? block.items.length : 0),
    0,
  );
  const shouldStartCollapsed = (
    totalBlockItems > 3
    || sectionIntros.length > 2
    || String(brief || '').length + String(howToRead || '').length > 360
  );
  const scaffoldStateKey = [
    surfaceType || '',
    brief || '',
    howToRead || '',
    blocks.length,
    totalBlockItems,
    sectionIntros.length,
    Boolean(scaffold),
  ].join('::');

  React.useEffect(() => {
    if (!scaffold) return;
    setGuideCollapsed(shouldStartCollapsed);
    setExpandedBlocks({});
    setSectionGuideExpanded(false);
  }, [scaffold, scaffoldStateKey, shouldStartCollapsed]);

  if (!hasScaffoldContent(scaffold)) return null;

  return (
    <div data-testid="scaffold-intro-content">
      <div>
        <div className="gen-scaffold-header">
          <div className="gen-scaffold-header-left">
            <h3 className="gen-scaffold-label">Reading Guide</h3>
            {isNonEmptyString(surfaceType) && (
              <span className="gen-scaffold-surface-type">
                {humanizeSurfaceType(surfaceType)}
              </span>
            )}
          </div>
          <button
            type="button"
            aria-expanded={!guideCollapsed}
            onClick={() => setGuideCollapsed((current) => !current)}
            className="gen-scaffold-toggle"
          >
            {guideCollapsed ? 'Show guide' : 'Hide guide'}
          </button>
        </div>

        {isNonEmptyString(brief) && (
          <p className="gen-scaffold-brief">
            {brief}
          </p>
        )}

        {isNonEmptyString(howToRead) && (
          <p className="gen-scaffold-how-to-read">
            {guideCollapsed ? truncateText(howToRead, 140) : howToRead}
          </p>
        )}
      </div>

      {!guideCollapsed && blocks.length > 0 && (
        <div className="gen-scaffold-blocks">
          {blocks.map((block, blockIndex) => {
            const items = Array.isArray(block.items)
              ? block.items.filter((item): item is ScaffoldItem => Boolean(item && typeof item === 'object'))
              : [];
            if (!items.length) return null;

            const blockId = block.key || block.title || `block-${blockIndex}`;
            const isExpanded = Boolean(expandedBlocks[blockId]);
            const collapsedItems = items.slice(0, DEFAULT_VISIBLE_BLOCK_ITEMS);
            const visibleItems = isExpanded ? items : collapsedItems;
            const hiddenCount = items.length - visibleItems.length;
            const hasTruncatedText = !isExpanded && visibleItems.some(item => {
              const truncated = truncateText(item.text);
              return truncated !== item.text;
            });

            const ListTag = block.style === 'numbered_list' ? 'ol' : 'ul';

            return (
              <div key={blockId}>
                {isNonEmptyString(block.title) && (
                  <h4 className="gen-scaffold-block-title">
                    {block.title}
                  </h4>
                )}

                <ListTag className="gen-scaffold-list">
                  {visibleItems.map((item, itemIndex) => (
                    <li key={`${blockId}-${itemIndex}`} className="gen-scaffold-list-item">
                      {isNonEmptyString(item.label) && (
                        <strong>
                          {item.label}
                          {isNonEmptyString(item.text) ? ': ' : ''}
                        </strong>
                      )}
                      {isNonEmptyString(item.text)
                        ? (isExpanded ? item.text : truncateText(item.text))
                        : null}
                    </li>
                  ))}
                </ListTag>

                {(hiddenCount > 0 || hasTruncatedText) && (
                  <button
                    type="button"
                    onClick={() => {
                      setExpandedBlocks(prev => ({
                        ...prev,
                        [blockId]: !isExpanded,
                      }));
                    }}
                    className="gen-scaffold-expand-btn"
                  >
                    {isExpanded
                      ? 'Show less'
                      : `Show more${hiddenCount > 0 ? ` (${hiddenCount} more)` : ''}`}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!guideCollapsed && sectionIntros.length > 0 && (
        <div className="gen-scaffold-section-guide">
          <h4 className="gen-scaffold-section-guide-title">
            Section Guide
          </h4>

          <div className="gen-scaffold-section-intros">
            {(sectionGuideExpanded
              ? sectionIntros
              : sectionIntros.slice(0, DEFAULT_VISIBLE_SECTION_INTROS)
            ).map((section, index) => {
              if (!isNonEmptyString(section.intro)) return null;

              return (
                <div
                  key={section.section_key || section.title || `section-${index}`}
                  className="gen-scaffold-section-intro-card"
                >
                  {isNonEmptyString(section.title) && (
                    <div className="gen-scaffold-section-intro-title">
                      {section.title}
                    </div>
                  )}
                  <div className="gen-scaffold-section-intro-text">
                    {section.intro}
                  </div>
                </div>
              );
            })}
          </div>

          {sectionIntros.length > DEFAULT_VISIBLE_SECTION_INTROS && (
            <button
              type="button"
              onClick={() => setSectionGuideExpanded(prev => !prev)}
              className="gen-scaffold-expand-btn"
            >
              {sectionGuideExpanded
                ? 'Show fewer sections'
                : `Show all sections (${sectionIntros.length})`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
