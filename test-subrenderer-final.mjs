import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/final';
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
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  try {
    // STEP 1: Navigate + import
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

    // STEP 2: Click Target Work Profile
    console.log('\n=== STEP 2: Click Target Work Profile ===');
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(3000);

    // STEP 3: Expand all accordion sections
    console.log('\n=== STEP 3: Expand all sections ===');
    const h3Elements = await page.$$('h3');
    for (const h3 of h3Elements) {
      const text = await h3.textContent();
      if (text.includes('▶')) {
        await h3.click();
        await page.waitForTimeout(1000);
      }
    }
    await page.waitForTimeout(1000);

    // STEP 4: Check for sub-renderer patterns
    console.log('\n=== STEP 4: Sub-renderer dispatch check ===');
    const checkResult = await page.evaluate(() => {
      const results = {};
      const h3s = Array.from(document.querySelectorAll('h3'));
      const accordionHeaders = h3s.filter(h => h.textContent.includes('▼'));

      for (const h of accordionHeaders) {
        const sectionName = h.textContent.trim().replace(/[▼▶]\s*/, '');
        const contentEl = h.nextElementSibling;
        if (!contentEl) continue;

        // Sub-renderer specific patterns:
        // MiniCardList: cards with border 1px solid #e8ecf0 and background #fafbfc
        const miniCards = contentEl.querySelectorAll('div[style*="#e8ecf0"]');
        // ChipGrid: pills with borderRadius: 12px
        const chipPills = contentEl.querySelectorAll('span[style*="border-radius: 12px"]');
        // KeyValueTable: <table> elements
        const tables = contentEl.querySelectorAll('table');
        // ProseBlock: div with line-height: 1.6
        const proseBlocks = contentEl.querySelectorAll('div[style*="line-height: 1.6"]');
        // ComparisonPanel: grid 1fr 1fr
        const comparisons = contentEl.querySelectorAll('div[style*="1fr 1fr"]');

        // OLD GenericSectionRenderer patterns:
        // border-left: 2px solid (key-value nesting)
        const genericNesting = contentEl.querySelectorAll('div[style*="border-left: 2px"]');
        // Small chips: borderRadius: 4px
        const oldChips = contentEl.querySelectorAll('span[style*="border-radius: 4px"]');

        // Inline chip badges for array values (new MiniCardList improvement)
        const inlineChips = contentEl.querySelectorAll('span[style*="border-radius: 3px"]');

        results[sectionName] = {
          miniCards: miniCards.length,
          chipPills: chipPills.length,
          tables: tables.length,
          proseBlocks: proseBlocks.length,
          comparisons: comparisons.length,
          genericNesting: genericNesting.length,
          oldChips: oldChips.length,
          inlineChips: inlineChips.length,
          htmlLength: contentEl.innerHTML.length,
        };
      }
      return results;
    });

    let totalSubRendered = 0;
    let totalGeneric = 0;

    for (const [section, info] of Object.entries(checkResult)) {
      const subTotal = info.miniCards + info.chipPills + info.tables + info.proseBlocks + info.comparisons;
      totalSubRendered += subTotal;
      totalGeneric += info.genericNesting;

      console.log(`\n  ${section} (${info.htmlLength} chars):`);
      console.log(`    NEW sub-renderers:`);
      console.log(`      MiniCardList cards:  ${info.miniCards}`);
      console.log(`      ChipGrid pills:      ${info.chipPills}`);
      console.log(`      Tables:              ${info.tables}`);
      console.log(`      Prose blocks:        ${info.proseBlocks}`);
      console.log(`      Comparison panels:   ${info.comparisons}`);
      console.log(`      Inline chip badges:  ${info.inlineChips}`);
      console.log(`    OLD generic patterns:`);
      console.log(`      Generic nesting:     ${info.genericNesting}`);
      console.log(`      Old chips (4px):     ${info.oldChips}`);
      console.log(`    → Sub-rendered elements: ${subTotal}, Generic elements: ${info.genericNesting}`);
    }

    console.log(`\n  TOTAL: ${totalSubRendered} sub-rendered, ${totalGeneric} generic`);

    // STEP 5: Take screenshots of each section
    console.log('\n=== STEP 5: Screenshots ===');

    const sectionHeaders = await page.$$('h3');
    for (const h3 of sectionHeaders) {
      const text = await h3.textContent();
      if (!text.includes('▼')) continue;
      const name = text.trim().replace(/[▼▶]\s*/, '').toLowerCase().replace(/\s+/g, '-');
      await h3.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
      await page.screenshot({ path: screenshotPath(`section-${name}`), fullPage: false });
    }

    // Full page
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: screenshotPath('full-page'), fullPage: true });

    // Scroll captures
    for (let y = 700; y <= 5000; y += 500) {
      await page.evaluate(scrollY => window.scrollTo(0, scrollY), y);
      await page.waitForTimeout(200);
      await page.screenshot({ path: screenshotPath(`scroll-${y}`), fullPage: false });
    }

    // Summary
    console.log('\n=== CONSOLE ERRORS ===');
    const relevant = consoleErrors.filter(e => !e.includes('favicon') && !e.includes('net::ERR') && !e.includes('Failed to load resource'));
    if (relevant.length === 0) console.log('No relevant errors');
    else for (const err of relevant) console.log(`  ERROR: ${err}`);

    console.log(`\nScreenshots: ${screenshotCount} saved to ${SCREENSHOT_DIR}`);

    // VERDICT
    if (totalSubRendered > 0) {
      console.log(`\n✓ PASS: Sub-renderers are dispatching (${totalSubRendered} elements)`);
    } else {
      console.log(`\n✗ FAIL: No sub-rendered elements found — still using GenericSectionRenderer`);
    }

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    await page.screenshot({ path: screenshotPath('error'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
