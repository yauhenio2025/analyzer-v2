import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/subrenderers-final';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

let screenshotCount = 0;
function screenshotPath(name) {
  screenshotCount++;
  return `${SCREENSHOT_DIR}/${String(screenshotCount).padStart(2, '0')}-${name}.png`;
}

const BASE_URL = 'https://the-critic-1.onrender.com';
const JOB_ID = 'job-7d32be316d06';

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  const consoleErrors = [];
  const consoleLogs = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
    else consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
  });

  try {
    // =========================================================================
    // STEP 1: Import job
    // =========================================================================
    console.log('\n=== STEP 1: Navigate + import ===');
    await page.goto(`${BASE_URL}/genealogy`, { waitUntil: 'networkidle', timeout: 90000 });
    await page.waitForTimeout(3000);

    let ready = await page.evaluate(() => document.body.innerText.includes('Target Work Profile'));
    if (!ready) {
      const jobInput = await page.$('input[placeholder*="job"]');
      if (jobInput) {
        await jobInput.fill(JOB_ID);
        await page.click('button:has-text("Import")');
      }
      for (let i = 0; i < 84; i++) {
        await page.waitForTimeout(5000);
        const state = await page.evaluate(() => {
          if (document.body.innerText.includes('Import failed')) return 'FAILED';
          if (document.body.innerText.includes('Target Work Profile')) return 'READY';
          return 'IMPORTING';
        });
        if (i % 6 === 0) console.log(`  ${(i+1)*5}s: ${state}`);
        if (state === 'READY') { ready = true; break; }
        if (state === 'FAILED') break;
      }
    } else {
      console.log('Already imported');
    }
    if (!ready) { console.log('FAIL: import'); await browser.close(); process.exit(1); }

    // =========================================================================
    // STEP 2: Click Target Work Profile and analyze
    // =========================================================================
    console.log('\n=== STEP 2: Target Work Profile ===');
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(3000);

    // Inject diagnostic JS to check if sub-renderers were used
    // The AccordionRenderer sets section_renderers hints via config
    // We need to look at React internals or just inspect DOM output

    // First, get the presentation data to understand what sections exist
    const v2Presentation = await page.evaluate(() => {
      // Try to access React state
      const app = document.getElementById('root');
      if (!app?._reactRootContainer) return null;
      // Can't easily access React internals; check window state instead
      return window.__v2Presentation || null;
    });
    console.log(`  v2Presentation accessible: ${!!v2Presentation}`);

    // =========================================================================
    // STEP 3: Find the accordion sections by h3 markers
    // =========================================================================
    console.log('\n=== STEP 3: Find accordion h3 sections ===');

    // The accordion uses h3 with ▼/▶ markers
    const accordionHeaders = await page.evaluate(() => {
      const h3s = Array.from(document.querySelectorAll('h3'));
      return h3s
        .filter(h => h.textContent.includes('▼') || h.textContent.includes('▶'))
        .map(h => ({
          text: h.textContent.trim().replace(/[▼▶]\s*/, ''),
          expanded: h.textContent.includes('▼'),
          // Check what's in the next sibling (the expanded content)
          nextSiblingTag: h.nextElementSibling?.tagName,
          nextSiblingClass: h.nextElementSibling?.className?.substring(0, 80)
        }));
    });

    console.log(`  Accordion sections found: ${accordionHeaders.length}`);
    for (const h of accordionHeaders) {
      console.log(`    ${h.expanded ? '▼' : '▶'} ${h.text} (next: ${h.nextSiblingTag} .${h.nextSiblingClass})`);
    }

    // =========================================================================
    // STEP 4: Expand each section and screenshot
    // =========================================================================
    console.log('\n=== STEP 4: Expand and inspect each section ===');

    // Click each collapsed section to expand it
    const h3Elements = await page.$$('h3');
    for (const h3 of h3Elements) {
      const text = await h3.textContent();
      if (!text.includes('▶') && !text.includes('▼')) continue;

      const sectionName = text.replace(/[▼▶]\s*/, '').trim();
      const isExpanded = text.includes('▼');

      if (!isExpanded) {
        console.log(`\n  Expanding: "${sectionName}"`);
        await h3.scrollIntoViewIfNeeded();
        await h3.click();
        await page.waitForTimeout(1500);
      } else {
        console.log(`\n  Already expanded: "${sectionName}"`);
      }

      // Screenshot the section
      await h3.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
      await page.screenshot({ path: screenshotPath(`section-${sectionName.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`), fullPage: false });

      // Analyze the rendered content
      const sectionAnalysis = await h3.evaluate(el => {
        // The content is the sibling after the h3 (the expanded section div)
        let contentEl = el.nextElementSibling;
        // Sometimes there's an intermediate wrapper
        if (!contentEl || contentEl.tagName === 'H3') return { empty: true };

        const html = contentEl.innerHTML || '';

        // Check for specific sub-renderer patterns by looking at inline styles
        // ChipGrid: inline-flex items with rounded-full or border-radius on spans
        const chipLikeElements = contentEl.querySelectorAll('span[style*="border-radius"]');

        // MiniCardList: divs with border and padding for each card
        const cardLikeElements = contentEl.querySelectorAll('div[style*="border: 1px"]');

        // KeyValueTable: actual <table> elements
        const tables = contentEl.querySelectorAll('table');

        // ProseBlock: paragraphs with specific font sizing
        const proseBlocks = contentEl.querySelectorAll('div[style*="line-height: 1.6"]');

        // StatRow: grid layouts
        const gridLayouts = contentEl.querySelectorAll('div[style*="grid-template"]');

        // ComparisonPanel: 2-col grids
        const twoColGrids = contentEl.querySelectorAll('div[style*="grid-cols-2"], div[style*="1fr 1fr"]');

        // Generic section renderer uses specific class patterns
        const genericSections = contentEl.querySelectorAll('.gen-kv-row, .gen-array-items, .gen-mini-card');

        // Also check for the sub-renderer wrapper patterns
        const anyStyledDivs = contentEl.querySelectorAll('div[style]');

        return {
          empty: false,
          htmlLength: html.length,
          chipLike: chipLikeElements.length,
          cardLike: cardLikeElements.length,
          tables: tables.length,
          proseBlocks: proseBlocks.length,
          gridLayouts: gridLayouts.length,
          twoColGrids: twoColGrids.length,
          genericSections: genericSections.length,
          styledDivs: anyStyledDivs.length,
          // Get a content sample
          textSample: contentEl.textContent?.trim().substring(0, 200)
        };
      });

      if (sectionAnalysis.empty) {
        console.log(`  Content: EMPTY`);
      } else {
        console.log(`  HTML length: ${sectionAnalysis.htmlLength}`);
        console.log(`  Chip-like elements: ${sectionAnalysis.chipLike}`);
        console.log(`  Card-like elements: ${sectionAnalysis.cardLike}`);
        console.log(`  Tables: ${sectionAnalysis.tables}`);
        console.log(`  Prose blocks: ${sectionAnalysis.proseBlocks}`);
        console.log(`  Grid layouts: ${sectionAnalysis.gridLayouts}`);
        console.log(`  Generic sections (.gen-*): ${sectionAnalysis.genericSections}`);
        console.log(`  Styled divs: ${sectionAnalysis.styledDivs}`);
        console.log(`  Text sample: "${sectionAnalysis.textSample?.substring(0, 120)}..."`);
      }
    }

    // =========================================================================
    // STEP 5: Check what data keys actually exist vs config expectations
    // =========================================================================
    console.log('\n=== STEP 5: Check data vs config alignment ===');

    // The view definitions expect these section_renderers keys:
    const expectedKeys = {
      'Conceptual Framework': ['frameworks', 'vocabulary_map', 'methodological_signatures', 'metaphor_inventory', 'cross_domain_transfers', 'framework_relationships', 'architectural_summary'],
      'Semantic Constellation': ['core_concepts', 'concept_clusters', 'load_bearing_terms', 'boundary_tensions', 'semantic_architecture', 'vocabulary_signature'],
      'Inferential Commitments': ['key_ideas', 'commitments', 'backings', 'either_or_choices', 'hidden_premises', 'practical_implications', 'argumentative_structure'],
      'Concept Evolution': ['concepts', 'evolution_trajectories', 'definitional_variations', 'semantic_clusters', 'foundational_patterns', 'dimensional_comparisons']
    };

    // Try to access the actual data shape via the API
    // The job outputs are stored and served by the executor
    const jobDataCheck = await page.evaluate(async () => {
      try {
        // Check what the v2 presentation contains
        // The presentation API returns view payloads with data
        const res = await fetch('https://analyzer-v2.onrender.com/v1/executor/jobs/7d32be316d06/results');
        const data = await res.json();
        return { available: true, phases: data.length || Object.keys(data).length, sample: JSON.stringify(data).substring(0, 500) };
      } catch (e) {
        return { available: false, error: e.message };
      }
    });
    console.log(`  Job results API: ${JSON.stringify(jobDataCheck)}`);

    // =========================================================================
    // STEP 6: Full page screenshots with all sections expanded
    // =========================================================================
    console.log('\n=== STEP 6: Full page screenshots ===');

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: screenshotPath('full-page-top'), fullPage: true });

    // Scroll-based viewport captures
    for (let y = 700; y <= 5000; y += 600) {
      await page.evaluate(scrollY => window.scrollTo(0, scrollY), y);
      await page.waitForTimeout(300);
      await page.screenshot({ path: screenshotPath(`scroll-${y}`), fullPage: false });
    }

    console.log('Scroll screenshots taken');

    // =========================================================================
    // Summary
    // =========================================================================
    console.log('\n=== CONSOLE ERRORS ===');
    const relevant = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('net::ERR') && !e.includes('Failed to load resource'));
    if (relevant.length === 0) {
      console.log('No relevant console errors');
    } else {
      for (const err of relevant) console.log(`  ERROR: ${err}`);
    }

    // Check for sub-renderer related console logs
    const subRendLogs = consoleLogs.filter(l => l.includes('sub-render') || l.includes('section_renderer') || l.includes('SubRenderer'));
    if (subRendLogs.length > 0) {
      console.log('\nSub-renderer related logs:');
      for (const l of subRendLogs) console.log(`  ${l}`);
    }

    console.log(`\nScreenshots: ${screenshotCount} saved to ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    await page.screenshot({ path: screenshotPath('error'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
