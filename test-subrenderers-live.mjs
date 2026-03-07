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
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // =========================================================================
    // STEP 1: Navigate to /genealogy and import job
    // =========================================================================
    console.log('\n=== STEP 1: Navigate to /genealogy ===');
    await page.goto(`${BASE_URL}/genealogy`, { waitUntil: 'networkidle', timeout: 90000 });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: screenshotPath('genealogy-initial'), fullPage: false });
    console.log('Screenshot: genealogy-initial');

    // Check if job is already imported (look for tabs)
    const alreadyImported = await page.evaluate(() => {
      return document.body.innerText.includes('Target Work Profile') ||
             document.body.innerText.includes('Relationship Landscape');
    });

    if (alreadyImported) {
      console.log('Job already imported, skipping import step');
    } else {
      console.log(`Importing job: ${JOB_ID}`);
      // Clear and fill the job ID input
      const jobInput = await page.$('input[placeholder*="job"]');
      if (jobInput) {
        await jobInput.fill('');
        await jobInput.fill(JOB_ID);
        await page.click('button:has-text("Import")');
        console.log('Import clicked, waiting...');
      } else {
        console.log('WARN: Job input not found, trying alternative selectors');
        // Try other input selectors
        const inputs = await page.$$('input');
        console.log(`Found ${inputs.length} inputs`);
        for (const input of inputs) {
          const placeholder = await input.getAttribute('placeholder');
          console.log(`  placeholder: "${placeholder}"`);
        }
      }

      // Wait for import to complete (up to 6 minutes)
      let ready = false;
      for (let i = 0; i < 72; i++) {
        await page.waitForTimeout(5000);
        const state = await page.evaluate(() => {
          if (document.body.innerText.includes('Import failed')) return 'FAILED';
          if (document.body.innerText.includes('Target Work Profile')) return 'READY';
          if (document.body.innerText.includes('Relationship Landscape')) return 'READY';
          return 'IMPORTING';
        });
        if (i % 6 === 0) console.log(`  ${(i + 1) * 5}s: ${state}`);
        if (state === 'READY') { ready = true; break; }
        if (state === 'FAILED') {
          console.log('FAIL: Import failed');
          await page.screenshot({ path: screenshotPath('import-failed'), fullPage: true });
          break;
        }
      }

      if (!ready) {
        console.log('Import did not complete within 6 minutes');
        await page.screenshot({ path: screenshotPath('import-timeout'), fullPage: true });
        await browser.close();
        process.exit(1);
      }
    }

    console.log('Job imported successfully');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: screenshotPath('after-import'), fullPage: false });
    console.log('Screenshot: after-import');

    // =========================================================================
    // STEP 2: Click Target Work Profile tab
    // =========================================================================
    console.log('\n=== STEP 2: Click Target Work Profile tab ===');

    const twpTab = await page.$('button:has-text("Target Work Profile")');
    if (twpTab) {
      await twpTab.click();
      await page.waitForTimeout(3000);
      await page.screenshot({ path: screenshotPath('target-work-profile'), fullPage: false });
      console.log('Screenshot: target-work-profile');

      // Check for sub-tabs
      const subTabs = await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        return buttons
          .filter(b => ['Conceptual Framework', 'Semantic Constellation', 'Inferential Commitments', 'Concept Evolution']
            .some(name => b.textContent.includes(name)))
          .map(b => b.textContent.trim());
      });
      console.log(`Sub-tabs found: ${JSON.stringify(subTabs)}`);
    } else {
      console.log('WARN: Target Work Profile tab not found');
      // List all visible tab buttons
      const allButtons = await page.$$eval('button', els => els.map(e => e.textContent.trim()).filter(t => t.length > 0 && t.length < 50));
      console.log(`Available buttons: ${JSON.stringify(allButtons.slice(0, 20))}`);
    }

    // =========================================================================
    // STEP 3: Test each sub-tab
    // =========================================================================
    const subTabNames = [
      'Conceptual Framework',
      'Semantic Constellation',
      'Inferential Commitments',
      'Concept Evolution'
    ];

    for (const tabName of subTabNames) {
      console.log(`\n=== STEP 3: Sub-tab: ${tabName} ===`);

      const tab = await page.$(`button:has-text("${tabName}")`);
      if (tab) {
        await tab.click();
        await page.waitForTimeout(3000);

        // Scroll down to see results
        await page.evaluate(() => window.scrollTo(0, 400));
        await page.waitForTimeout(500);
        await page.screenshot({ path: screenshotPath(`subtab-${tabName.toLowerCase().replace(/ /g, '-')}-top`), fullPage: false });

        // Scroll further to see more content
        await page.evaluate(() => window.scrollTo(0, 900));
        await page.waitForTimeout(500);
        await page.screenshot({ path: screenshotPath(`subtab-${tabName.toLowerCase().replace(/ /g, '-')}-mid`), fullPage: false });

        // Check for sub-renderer indicators
        const renderInfo = await page.evaluate(() => {
          // Look for specific sub-renderer CSS patterns
          const chips = document.querySelectorAll('[class*="chip"], [class*="badge"], [class*="pill"]');
          const cards = document.querySelectorAll('[class*="mini-card"], [class*="card-list"]');
          const tables = document.querySelectorAll('table');
          const timelines = document.querySelectorAll('[class*="timeline"]');
          const comparisons = document.querySelectorAll('[class*="comparison"]');

          // Check accordion sections
          const accordionSections = document.querySelectorAll('[class*="accordion"], details, summary');

          // Get text content of sections to identify what data is showing
          const sectionHeaders = Array.from(document.querySelectorAll('h3, h4, summary, [class*="section-title"]'))
            .map(el => el.textContent.trim())
            .filter(t => t.length > 0 && t.length < 100);

          return {
            chips: chips.length,
            cards: cards.length,
            tables: tables.length,
            timelines: timelines.length,
            comparisons: comparisons.length,
            accordionSections: accordionSections.length,
            sectionHeaders: sectionHeaders.slice(0, 15)
          };
        });

        console.log(`  Render elements found:`);
        console.log(`    Chips/badges: ${renderInfo.chips}`);
        console.log(`    Cards: ${renderInfo.cards}`);
        console.log(`    Tables: ${renderInfo.tables}`);
        console.log(`    Timelines: ${renderInfo.timelines}`);
        console.log(`    Comparisons: ${renderInfo.comparisons}`);
        console.log(`    Accordion sections: ${renderInfo.accordionSections}`);
        console.log(`    Section headers: ${JSON.stringify(renderInfo.sectionHeaders)}`);

        // Check for any error states
        const hasError = await page.evaluate(() => {
          return document.body.innerText.includes('Error') ||
                 document.body.innerText.includes('No data') ||
                 document.body.innerText.includes('undefined');
        });
        if (hasError) {
          console.log('  WARN: Possible error or no-data state detected');
        }

      } else {
        console.log(`  WARN: "${tabName}" tab button not found`);
      }
    }

    // =========================================================================
    // STEP 4: Full page screenshot of each sub-tab
    // =========================================================================
    console.log('\n=== STEP 4: Full-page screenshots ===');

    for (const tabName of subTabNames) {
      const tab = await page.$(`button:has-text("${tabName}")`);
      if (tab) {
        await tab.click();
        await page.waitForTimeout(2000);
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(300);
        await page.screenshot({ path: screenshotPath(`fullpage-${tabName.toLowerCase().replace(/ /g, '-')}`), fullPage: true });
        console.log(`Full-page screenshot: ${tabName}`);
      }
    }

    // =========================================================================
    // STEP 5: Check the view config that was actually sent to the renderer
    // =========================================================================
    console.log('\n=== STEP 5: Check rendered view configs ===');

    // Navigate to the raw output tab to see what the renderer received
    const rawTab = await page.$('button:has-text("Raw Engine Output")');
    if (rawTab) {
      await rawTab.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: screenshotPath('raw-output-tab'), fullPage: false });
      console.log('Screenshot: raw-output-tab');
    }

    // =========================================================================
    // Final summary
    // =========================================================================
    console.log('\n=== CONSOLE ERRORS ===');
    const relevantErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('net::ERR') &&
      !e.includes('Failed to load resource')
    );
    if (relevantErrors.length === 0) {
      console.log('No relevant console errors detected');
    } else {
      for (const err of relevantErrors) {
        console.log(`  ERROR: ${err}`);
      }
    }

    console.log(`\nTotal screenshots taken: ${screenshotCount}`);
    console.log(`Screenshots saved to: ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    await page.screenshot({ path: screenshotPath('error-state'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
