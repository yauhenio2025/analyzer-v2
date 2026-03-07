import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/diagnosis';
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
    // STEP 1: Navigate + import
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
        if (i % 6 === 0) console.log(`  ${(i + 1) * 5}s: ${state}`);
        if (state === 'READY') { ready = true; break; }
        if (state === 'FAILED') break;
      }
    } else {
      console.log('Already imported');
    }
    if (!ready) { console.log('FAIL: import'); await browser.close(); process.exit(1); }

    // =========================================================================
    // STEP 2: Intercept API calls to see what config the presentation returns
    // =========================================================================
    console.log('\n=== STEP 2: Check what data the frontend has ===');

    // Inject diagnostic code to check the v2Presentation state
    // Since React state isn't directly accessible, we'll check the DOM and
    // also intercept network responses

    // First, click Target Work Profile
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(3000);

    // Check the accordion sections and their data via DOM inspection
    const accordionInfo = await page.evaluate(() => {
      // Find all h3 elements (accordion headers)
      const h3s = Array.from(document.querySelectorAll('h3'));
      const accordionHeaders = h3s.filter(h => h.textContent.includes('▼') || h.textContent.includes('▶'));

      return accordionHeaders.map(h => {
        const text = h.textContent.trim().replace(/[▼▶]\s*/, '');
        const isExpanded = h.textContent.includes('▼');
        const contentEl = h.nextElementSibling;

        let contentInfo = { html: '', classes: '', childTags: [] };
        if (contentEl && isExpanded) {
          contentInfo = {
            html: contentEl.innerHTML.substring(0, 1000),
            classes: contentEl.className,
            childTags: Array.from(contentEl.children).map(c => c.tagName + '.' + (c.className || '').substring(0, 40))
          };
        }

        return { text, isExpanded, contentInfo };
      });
    });

    console.log(`Accordion sections: ${accordionInfo.length}`);
    for (const section of accordionInfo) {
      console.log(`  ${section.isExpanded ? '▼' : '▶'} ${section.text}`);
      if (section.isExpanded) {
        console.log(`    HTML sample: ${section.contentInfo.html.substring(0, 300)}`);
        console.log(`    Child tags: ${JSON.stringify(section.contentInfo.childTags)}`);
      }
    }

    // =========================================================================
    // STEP 3: Expand all sections and check for sub-renderer specific patterns
    // =========================================================================
    console.log('\n=== STEP 3: Expand all sections + check sub-renderer dispatch ===');

    // Click each collapsed section
    const h3Elements = await page.$$('h3');
    for (const h3 of h3Elements) {
      const text = await h3.textContent();
      if (!text.includes('▶')) continue;
      await h3.click();
      await page.waitForTimeout(1000);
    }
    await page.waitForTimeout(1000);

    // Now check for sub-renderer visual indicators
    const subRendererCheck = await page.evaluate(() => {
      const results = {};

      // Find each accordion section's content
      const h3s = Array.from(document.querySelectorAll('h3'));
      const accordionHeaders = h3s.filter(h => h.textContent.includes('▼'));

      for (const h of accordionHeaders) {
        const sectionName = h.textContent.trim().replace(/[▼▶]\s*/, '');
        const contentEl = h.nextElementSibling;
        if (!contentEl) continue;

        // Check for specific sub-renderer patterns:
        // ChipGrid: inline-flex with borderRadius:12px rounded pills
        const pills = contentEl.querySelectorAll('span[style*="border-radius: 12px"]');
        // MiniCardList: cards with specific styling (from SubRenderers.tsx)
        const cards = contentEl.querySelectorAll('div[style*="border: 1px solid #e8ecf0"]');
        // KeyValueTable: <table> elements
        const tables = contentEl.querySelectorAll('table');
        // ProseBlock: div with line-height: 1.6
        const proseBlocks = contentEl.querySelectorAll('div[style*="line-height: 1.6"]');
        // ComparisonPanel: grid-template-columns: 1fr 1fr
        const comparisons = contentEl.querySelectorAll('div[style*="1fr 1fr"]');
        // StatRow: grid with text-align: center
        const statRows = contentEl.querySelectorAll('div[style*="text-align: center"]');

        // Also check for the OLD GenericSectionRenderer pattern:
        // borderLeft: 2px solid #e2e8f0 (the key-value indentation)
        const genericKV = contentEl.querySelectorAll('div[style*="border-left: 2px solid"]');
        // Old chip grid: border-radius: 4px (vs SubRenderer's 12px)
        const oldChips = contentEl.querySelectorAll('span[style*="border-radius: 4px"]');

        // Check if sub-renderer header labels exist (textTransform: capitalize + fontWeight: 600)
        const subHeaders = contentEl.querySelectorAll('div[style*="text-transform: capitalize"]');

        results[sectionName] = {
          pills_12px: pills.length,
          cards_e8ecf0: cards.length,
          tables: tables.length,
          proseBlocks: proseBlocks.length,
          comparisons: comparisons.length,
          statRows: statRows.length,
          genericKV: genericKV.length,
          oldChips_4px: oldChips.length,
          subHeaders: subHeaders.length,
          htmlLength: contentEl.innerHTML.length,
        };
      }

      return results;
    });

    console.log('\nSub-renderer dispatch analysis:');
    for (const [section, info] of Object.entries(subRendererCheck)) {
      console.log(`\n  ${section} (${info.htmlLength} chars HTML):`);
      console.log(`    New pills (12px radius): ${info.pills_12px}`);
      console.log(`    New cards (#e8ecf0):     ${info.cards_e8ecf0}`);
      console.log(`    Tables:                  ${info.tables}`);
      console.log(`    Prose blocks:            ${info.proseBlocks}`);
      console.log(`    Comparison panels:       ${info.comparisons}`);
      console.log(`    Stat rows:               ${info.statRows}`);
      console.log(`    OLD generic KV borders:  ${info.genericKV}`);
      console.log(`    OLD chips (4px radius):  ${info.oldChips_4px}`);
      console.log(`    Sub-section headers:     ${info.subHeaders}`);
    }

    // =========================================================================
    // STEP 4: Check what data keys exist in each section
    // =========================================================================
    console.log('\n=== STEP 4: Inspect data structure ===');

    // We need to check the actual data that was passed to the renderer.
    // Let me add console.log statements temporarily... but we can't modify deployed code.
    // Instead, let's check the API directly.

    const presentationCheck = await page.evaluate(async () => {
      // Try the compose endpoint to see what renderer_config is returned
      try {
        const resp = await fetch('https://analyzer-v2.onrender.com/v1/views/genealogy_target_profile');
        const viewDef = await resp.json();
        return {
          api_available: true,
          has_section_renderers: !!viewDef?.renderer_config?.section_renderers,
          section_renderer_keys: viewDef?.renderer_config?.section_renderers
            ? Object.keys(viewDef.renderer_config.section_renderers)
            : [],
          renderer_type: viewDef?.renderer_type,
          first_section_hint: viewDef?.renderer_config?.section_renderers?.conceptual_framework
            ? JSON.stringify(viewDef.renderer_config.section_renderers.conceptual_framework).substring(0, 300)
            : null,
        };
      } catch (e) {
        return { api_available: false, error: e.message };
      }
    });

    console.log('\nView definition API check:');
    console.log(JSON.stringify(presentationCheck, null, 2));

    // =========================================================================
    // STEP 5: Screenshot each section
    // =========================================================================
    console.log('\n=== STEP 5: Screenshots ===');

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: screenshotPath('full-page'), fullPage: true });

    // Scroll through and capture
    for (let y = 700; y <= 4000; y += 500) {
      await page.evaluate(scrollY => window.scrollTo(0, scrollY), y);
      await page.waitForTimeout(200);
      await page.screenshot({ path: screenshotPath(`scroll-${y}`), fullPage: false });
    }

    // =========================================================================
    // STEP 6: Check for React component tree issues
    // =========================================================================
    console.log('\n=== STEP 6: Debug sub-renderer dispatch ===');

    // Add a runtime diagnostic: monkey-patch resolveSubRenderer to log calls
    // Actually, since the code is bundled, let's just verify the config is present
    // by checking for the section_renderers in the rendered output
    const debugCheck = await page.evaluate(() => {
      // Check if any element has text "nested_sections" in the DOM (shouldn't appear visually)
      const allText = document.body.innerText;
      return {
        hasNestedSectionsText: allText.includes('nested_sections'),
        hasSubRenderersText: allText.includes('sub_renderers'),
        // Check specific patterns that would only appear if sub-renderers dispatch
        // ChipGrid uses borderRadius: 12px (not 4px like generic)
        // MiniCardList uses specific card styling
        // KeyValueTable uses <table>
        // ProseBlock uses lineHeight: 1.6
      };
    });
    console.log('Debug check:', JSON.stringify(debugCheck));

    // =========================================================================
    // Summary
    // =========================================================================
    console.log('\n=== CONSOLE ERRORS ===');
    const relevant = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('net::ERR') && !e.includes('Failed to load resource'));
    if (relevant.length === 0) console.log('No relevant console errors');
    else for (const err of relevant) console.log(`  ERROR: ${err}`);

    console.log('\n=== RELEVANT CONSOLE LOGS ===');
    const subRendLogs = consoleLogs.filter(l =>
      l.includes('sub-render') || l.includes('section_renderer') ||
      l.includes('SubRenderer') || l.includes('subRenderer') ||
      l.includes('nested_sections') || l.includes('resolveSubRenderer')
    );
    if (subRendLogs.length > 0) {
      for (const l of subRendLogs) console.log(`  ${l}`);
    } else {
      console.log('No sub-renderer related console logs');
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
