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
    // STEP 1: Navigate to /genealogy — job should already be imported
    // =========================================================================
    console.log('\n=== STEP 1: Navigate to /genealogy ===');
    await page.goto(`${BASE_URL}/genealogy`, { waitUntil: 'networkidle', timeout: 90000 });
    await page.waitForTimeout(3000);

    // Verify results are present
    const hasResults = await page.evaluate(() => {
      return document.body.innerText.includes('Analysis Results') &&
             document.body.innerText.includes('Target Work Profile');
    });

    if (!hasResults) {
      console.log('FAIL: Results not present — job may not be cached. Previous test should have imported it.');
      await page.screenshot({ path: screenshotPath('no-results'), fullPage: true });
      await browser.close();
      process.exit(1);
    }
    console.log('Results are present');

    // =========================================================================
    // STEP 2: Click Target Work Profile tab
    // =========================================================================
    console.log('\n=== STEP 2: Click Target Work Profile tab ===');
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(3000);

    // Scroll to the content area
    await page.evaluate(() => window.scrollTo(0, 700));
    await page.waitForTimeout(500);
    await page.screenshot({ path: screenshotPath('twp-overview'), fullPage: false });
    console.log('Screenshot: twp-overview');

    // =========================================================================
    // STEP 3: Explore the Target Work Profile content structure
    // =========================================================================
    console.log('\n=== STEP 3: Analyze TWP content structure ===');

    const structure = await page.evaluate(() => {
      // Look for sub-view sections — they could be:
      // 1. Child tab buttons
      // 2. Accordion details/summary elements
      // 3. Nested sections with headers

      const details = document.querySelectorAll('details');
      const summaries = Array.from(document.querySelectorAll('summary')).map(s => s.textContent.trim());

      // Look for sub-tab buttons within the results area
      const resultsArea = document.querySelector('.gen-results-area') ||
                          document.querySelector('[class*="result"]') ||
                          document.querySelector('[class*="content"]');

      // Find any buttons that look like child view tabs
      const buttons = Array.from(document.querySelectorAll('button'));
      const tabLikeButtons = buttons
        .filter(b => {
          const text = b.textContent.trim();
          return ['Conceptual', 'Semantic', 'Inferential', 'Concept Evolution', 'Framework', 'Constellation', 'Commitments'].some(k => text.includes(k));
        })
        .map(b => b.textContent.trim());

      // Find h2, h3 headers in the view area
      const headers = Array.from(document.querySelectorAll('h2, h3, h4'))
        .map(h => ({ tag: h.tagName, text: h.textContent.trim() }))
        .filter(h => h.text.length > 0 && h.text.length < 100);

      return {
        detailsCount: details.length,
        summaries,
        tabLikeButtons,
        headers: headers.slice(0, 30)
      };
    });

    console.log(`  <details> elements: ${structure.detailsCount}`);
    console.log(`  <summary> texts: ${JSON.stringify(structure.summaries.slice(0, 15))}`);
    console.log(`  Tab-like buttons: ${JSON.stringify(structure.tabLikeButtons)}`);
    console.log(`  Headers: ${JSON.stringify(structure.headers.slice(0, 15))}`);

    // =========================================================================
    // STEP 4: Click into each sub-view accordion section and check rendering
    // =========================================================================
    const subViewNames = ['Conceptual Framework', 'Semantic Constellation', 'Inferential Commitments', 'Concept Evolution'];

    for (const name of subViewNames) {
      console.log(`\n=== STEP 4: Expand "${name}" ===`);

      // Try clicking the summary/details element
      const summaryEl = await page.$(`summary:has-text("${name}")`);
      const detailsEl = await page.$(`details:has-text("${name}")`);
      const buttonEl = await page.$(`button:has-text("${name}")`);

      let clicked = false;
      if (summaryEl) {
        await summaryEl.click();
        clicked = true;
        console.log(`  Clicked summary element`);
      } else if (buttonEl) {
        await buttonEl.click();
        clicked = true;
        console.log(`  Clicked button element`);
      } else {
        // Try clicking any element containing the text
        const textEl = await page.$(`text="${name}"`);
        if (textEl) {
          await textEl.click();
          clicked = true;
          console.log(`  Clicked text element`);
        } else {
          console.log(`  WARN: Could not find clickable element for "${name}"`);
        }
      }

      if (clicked) {
        await page.waitForTimeout(2000);

        // Scroll to the expanded section
        const sectionEl = await page.$(`text="${name}"`);
        if (sectionEl) {
          await sectionEl.scrollIntoViewIfNeeded();
          await page.waitForTimeout(500);
        }

        await page.screenshot({ path: screenshotPath(`expanded-${name.toLowerCase().replace(/ /g, '-')}`), fullPage: false });
        console.log(`  Screenshot taken`);

        // Analyze what's rendered inside this section
        const sectionContent = await page.evaluate((sectionName) => {
          // Find the section by name and look at what's rendered after it
          const allElements = document.querySelectorAll('*');
          let foundSection = false;
          let sectionHTML = '';

          for (const el of allElements) {
            if (el.textContent?.trim() === sectionName && (el.tagName === 'SUMMARY' || el.tagName === 'H3' || el.tagName === 'H4' || el.tagName === 'BUTTON')) {
              foundSection = true;
              // Get the parent's innerHTML (first 3000 chars)
              const parent = el.closest('details') || el.closest('section') || el.parentElement;
              if (parent) {
                sectionHTML = parent.innerHTML.substring(0, 3000);
              }
              break;
            }
          }

          // Look for sub-renderer class indicators globally in visible area
          const visibleChips = document.querySelectorAll('.inline-flex.items-center.rounded-full, [class*="chip"], [class*="pill"]');
          const visibleCards = document.querySelectorAll('[class*="shadow"][class*="rounded"], [class*="mini-card"]');
          const visibleTables = document.querySelectorAll('table');

          return {
            foundSection,
            htmlSnippetLength: sectionHTML.length,
            hasSubRendererHints: sectionHTML.includes('chip') || sectionHTML.includes('card') || sectionHTML.includes('timeline') || sectionHTML.includes('comparison'),
            chipElements: visibleChips.length,
            cardElements: visibleCards.length,
            tableElements: visibleTables.length
          };
        }, name);

        console.log(`  Found section: ${sectionContent.foundSection}`);
        console.log(`  HTML snippet length: ${sectionContent.htmlSnippetLength}`);
        console.log(`  Sub-renderer class hints: ${sectionContent.hasSubRendererHints}`);
        console.log(`  Visible chips: ${sectionContent.chipElements}, cards: ${sectionContent.cardElements}, tables: ${sectionContent.tableElements}`);
      }
    }

    // =========================================================================
    // STEP 5: Full page scroll capture
    // =========================================================================
    console.log('\n=== STEP 5: Full page capture of TWP ===');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);

    // Click Target Work Profile again to make sure we're on it
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(2000);

    // Take a full page screenshot
    await page.screenshot({ path: screenshotPath('twp-full-page'), fullPage: true });
    console.log('Full page screenshot taken');

    // Also scroll through and capture at different positions
    for (let scrollY = 700; scrollY <= 3000; scrollY += 600) {
      await page.evaluate((y) => window.scrollTo(0, y), scrollY);
      await page.waitForTimeout(300);
      await page.screenshot({ path: screenshotPath(`twp-scroll-${scrollY}`), fullPage: false });
    }
    console.log('Scroll screenshots taken');

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
