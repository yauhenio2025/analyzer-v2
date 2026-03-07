import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/subrenderers';
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
    // =========================================================================
    // STEP 1: Navigate and import
    // =========================================================================
    console.log('\n=== STEP 1: Navigate to /genealogy and import ===');
    await page.goto(`${BASE_URL}/genealogy`, { waitUntil: 'networkidle', timeout: 90000 });
    await page.waitForTimeout(3000);

    // Check if already imported
    let hasResults = await page.evaluate(() =>
      document.body.innerText.includes('Target Work Profile')
    );

    if (!hasResults) {
      console.log(`Importing job: ${JOB_ID}`);
      const jobInput = await page.$('input[placeholder*="job"]');
      if (jobInput) {
        await jobInput.fill(JOB_ID);
        await page.click('button:has-text("Import")');
      }

      // Wait for import (up to 7 minutes)
      for (let i = 0; i < 84; i++) {
        await page.waitForTimeout(5000);
        const state = await page.evaluate(() => {
          if (document.body.innerText.includes('Import failed')) return 'FAILED';
          if (document.body.innerText.includes('Target Work Profile')) return 'READY';
          return 'IMPORTING';
        });
        if (i % 6 === 0) console.log(`  ${(i + 1) * 5}s: ${state}`);
        if (state === 'READY') { hasResults = true; break; }
        if (state === 'FAILED') break;
      }
    } else {
      console.log('Results already present');
    }

    if (!hasResults) {
      console.log('FAIL: Import did not complete');
      await page.screenshot({ path: screenshotPath('import-fail'), fullPage: true });
      await browser.close();
      process.exit(1);
    }

    console.log('Import complete');
    await page.waitForTimeout(2000);

    // =========================================================================
    // STEP 2: Click Target Work Profile
    // =========================================================================
    console.log('\n=== STEP 2: Click Target Work Profile ===');
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(3000);

    // Scroll down to content
    await page.evaluate(() => window.scrollTo(0, 700));
    await page.waitForTimeout(500);
    await page.screenshot({ path: screenshotPath('twp-initial'), fullPage: false });

    // =========================================================================
    // STEP 3: Understand the DOM structure
    // =========================================================================
    console.log('\n=== STEP 3: Analyze DOM structure ===');
    const domInfo = await page.evaluate(() => {
      const resultsArea = document.querySelector('.gen-results-area');
      if (!resultsArea) return { found: false };

      // What's inside the results area?
      const children = Array.from(resultsArea.children);
      const childInfo = children.map(c => ({
        tag: c.tagName,
        class: c.className?.substring(0, 80),
        text: c.textContent?.substring(0, 100)
      }));

      // Look for view-level containers
      const viewContainers = resultsArea.querySelectorAll('[class*="view-"], [data-view], [class*="accordion"]');

      // Look for all details/summary pairs
      const details = resultsArea.querySelectorAll('details');
      const detailsInfo = Array.from(details).map(d => ({
        open: d.open,
        summary: d.querySelector('summary')?.textContent?.trim()?.substring(0, 60)
      }));

      // Look for tab-like navigation within TWP
      const tabBtns = Array.from(resultsArea.querySelectorAll('button')).map(b => b.textContent.trim()).filter(t => t.length < 50);

      return {
        found: true,
        childCount: children.length,
        firstChildren: childInfo.slice(0, 5),
        viewContainers: viewContainers.length,
        details: detailsInfo,
        buttons: tabBtns.slice(0, 20)
      };
    });

    console.log(`Results area found: ${domInfo.found}`);
    if (domInfo.found) {
      console.log(`  Children: ${domInfo.childCount}`);
      console.log(`  First children: ${JSON.stringify(domInfo.firstChildren, null, 2)}`);
      console.log(`  View containers: ${domInfo.viewContainers}`);
      console.log(`  Details/accordions: ${JSON.stringify(domInfo.details)}`);
      console.log(`  Buttons: ${JSON.stringify(domInfo.buttons)}`);
    }

    // Also check the broader page structure
    const pageStructure = await page.evaluate(() => {
      // Find all text that looks like section headers near the results
      const allH = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5'));
      const headerTexts = allH.map(h => ({
        tag: h.tagName,
        text: h.textContent.trim().substring(0, 80)
      }));

      // Check for child view tabs (the presentation system uses these)
      const childTabContainer = document.querySelector('[class*="child-tab"], [class*="sub-tab"], [class*="child-view"]');

      // Find all "sections" in the current view
      const sections = document.querySelectorAll('section, [class*="section"]');

      return {
        headers: headerTexts.slice(0, 20),
        childTabContainer: !!childTabContainer,
        sectionCount: sections.length
      };
    });

    console.log(`\n  Page headers: ${JSON.stringify(pageStructure.headers.slice(0, 15))}`);
    console.log(`  Child tab container: ${pageStructure.childTabContainer}`);
    console.log(`  Section elements: ${pageStructure.sectionCount}`);

    // =========================================================================
    // STEP 4: Try to find and expand Conceptual Framework
    // =========================================================================
    console.log('\n=== STEP 4: Find Conceptual Framework section ===');

    // The accordion renderer uses details/summary elements
    // Try various selectors
    const cfFound = await page.evaluate(() => {
      const el = document.querySelector('summary');
      if (!el) return { found: false, totalSummaries: 0 };

      const summaries = Array.from(document.querySelectorAll('summary'));
      return {
        found: true,
        totalSummaries: summaries.length,
        summaryTexts: summaries.map(s => s.textContent.trim().substring(0, 80))
      };
    });

    console.log(`  Summary elements: ${cfFound.totalSummaries}`);
    if (cfFound.summaryTexts) {
      console.log(`  Summary texts: ${JSON.stringify(cfFound.summaryTexts)}`);
    }

    // Try expanding each accordion section and taking screenshots
    if (cfFound.totalSummaries > 0) {
      const summaries = await page.$$('summary');
      for (let i = 0; i < Math.min(summaries.length, 8); i++) {
        const text = await summaries[i].textContent();
        const trimmed = text.trim().substring(0, 50);
        console.log(`\n  Expanding summary[${i}]: "${trimmed}"`);

        await summaries[i].scrollIntoViewIfNeeded();
        await summaries[i].click();
        await page.waitForTimeout(1000);

        await page.screenshot({ path: screenshotPath(`accordion-section-${i}`), fullPage: false });
        console.log(`  Screenshot taken`);

        // Check what rendered inside
        const parent = await summaries[i].evaluateHandle(el => el.closest('details'));
        const innerContent = await parent.evaluate(el => {
          const inner = el.innerHTML;
          // Check for sub-renderer class patterns
          return {
            length: inner.length,
            hasChipGrid: inner.includes('rounded-full') || inner.includes('chip'),
            hasMiniCards: inner.includes('shadow') && inner.includes('rounded'),
            hasTable: inner.includes('<table'),
            hasTimeline: inner.includes('timeline'),
            hasComparison: inner.includes('grid-cols-2') || inner.includes('comparison'),
            hasProse: inner.includes('<p>'),
            // Sample first 200 chars of actual content (skip summary)
            contentSample: inner.replace(/<summary>.*?<\/summary>/s, '').replace(/<[^>]+>/g, ' ').trim().substring(0, 200)
          };
        });

        console.log(`  Inner HTML length: ${innerContent.length}`);
        console.log(`  Has chip-like: ${innerContent.hasChipGrid}`);
        console.log(`  Has card-like: ${innerContent.hasMiniCards}`);
        console.log(`  Has table: ${innerContent.hasTable}`);
        console.log(`  Has prose: ${innerContent.hasProse}`);
        console.log(`  Content sample: "${innerContent.contentSample.substring(0, 120)}..."`);
      }
    }

    // =========================================================================
    // STEP 5: Full page screenshot
    // =========================================================================
    console.log('\n=== STEP 5: Full-page screenshot of TWP ===');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: screenshotPath('twp-full'), fullPage: true });
    console.log('Full page screenshot taken');

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
    console.log(`\nScreenshots: ${screenshotCount} saved to ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    await page.screenshot({ path: screenshotPath('error'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
