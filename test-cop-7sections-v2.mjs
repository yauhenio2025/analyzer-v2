import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

  try {
    // Step 1: Navigate
    console.log('=== Step 1: Navigate ===');
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });
    console.log('Page loaded');

    // Step 2: Click the "Comprehensive 2/16/2026" analysis card (15 ideas, 4 prior works)
    console.log('\n=== Step 2: Select Comprehensive 2/16/2026 analysis ===');

    // Find and click the comprehensive card with 15 ideas, 4 prior works, 11 tactics
    const compCard = page.locator('button.gen-result-card').filter({ hasText: '15 ideas' }).filter({ hasText: '4 prior works' });
    const compCardCount = await compCard.count();
    console.log(`Found ${compCardCount} matching comprehensive cards`);

    if (compCardCount > 0) {
      await compCard.first().click();
      console.log('Clicked comprehensive card');
      await page.waitForTimeout(3000);
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop2-01-analysis-selected.png`, fullPage: false });

    // Step 3: Check what tabs are visible now
    console.log('\n=== Step 3: Check tabs ===');

    // Get all buttons/tabs visible
    const allButtons = await page.locator('button').evaluateAll(
      els => els.map(el => ({
        text: el.textContent?.trim()?.substring(0, 80),
        classes: el.className,
        visible: el.offsetParent !== null
      })).filter(e => e.text && e.visible)
    );
    console.log('Visible buttons:');
    for (const b of allButtons) {
      if (b.text.length > 2) {
        console.log(`  "${b.text}" (${b.classes})`);
      }
    }

    // Step 4: Click on Conditions of Possibility tab
    console.log('\n=== Step 4: Click Conditions of Possibility tab ===');
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    const copTabCount = await copTab.count();
    console.log(`CoP tab found: ${copTabCount > 0}`);

    if (copTabCount > 0) {
      // Check if it's already active
      const isActive = await copTab.getAttribute('class');
      console.log(`CoP tab classes: ${isActive}`);
      await copTab.click();
      console.log('Clicked CoP tab');
      await page.waitForTimeout(2000);
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop2-02-cop-tab-clicked.png`, fullPage: false });

    // Step 5: Analyze the content area after clicking CoP
    console.log('\n=== Step 5: Analyze CoP content ===');

    // Get the full text content of the visible area
    const visibleText = await page.evaluate(() => {
      // Find the main content area
      const main = document.querySelector('main, [class*="content"], [class*="panel"]');
      if (main) return main.textContent?.substring(0, 3000);
      return document.body.textContent?.substring(0, 3000);
    });
    console.log('Content area text (first 2000 chars):');
    console.log(visibleText?.substring(0, 2000));

    // Look for ALL section headers in the content
    console.log('\n=== Step 5b: Find section headers ===');
    const headers = await page.evaluate(() => {
      const results = [];
      const elements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, button, summary, [role="button"], [class*="header"], [class*="title"], [class*="section"], [class*="accordion"]');
      for (const el of elements) {
        if (el.offsetParent === null) continue; // not visible
        const text = el.textContent?.trim();
        if (!text || text.length > 200) continue;
        results.push({
          tag: el.tagName,
          text: text.substring(0, 120),
          classes: el.className?.substring(0, 120) || '',
          ariaExpanded: el.getAttribute('aria-expanded')
        });
      }
      return results;
    });

    console.log('All visible headers/buttons:');
    for (const h of headers) {
      console.log(`  [${h.tag}] "${h.text}" expanded=${h.ariaExpanded} class="${h.classes}"`);
    }

    // Step 6: Look specifically for the expected section names
    console.log('\n=== Step 6: Search for expected sections ===');
    const expectedSections = [
      'Enabling Conditions',
      'Constraining Conditions',
      'Path Dependencies',
      'Unacknowledged Debts',
      'Alternative Paths',
      'Counterfactual Analysis',
      'Synthetic Judgment'
    ];

    // Also check for variations
    const alternateNames = [
      'enabling', 'constraining', 'path depend', 'unacknowledged', 'alternative',
      'counterfactual', 'synthetic', 'debts', 'possibilities', 'conditions'
    ];

    const bodyText = await page.textContent('body');
    console.log('\nSearching for exact section names:');
    for (const section of expectedSections) {
      const found = bodyText.includes(section);
      console.log(`  ${found ? 'FOUND' : 'MISSING'}: "${section}"`);
    }

    console.log('\nSearching for partial matches (case-insensitive):');
    const bodyTextLower = bodyText.toLowerCase();
    for (const name of alternateNames) {
      const found = bodyTextLower.includes(name);
      if (found) {
        // Find context around it
        const idx = bodyTextLower.indexOf(name);
        const context = bodyText.substring(Math.max(0, idx - 30), idx + name.length + 30);
        console.log(`  FOUND "${name}": ...${context}...`);
      } else {
        console.log(`  MISSING: "${name}"`);
      }
    }

    // Step 7: Take a full page screenshot of everything
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop2-03-fullpage.png`, fullPage: true });

    // Step 8: Try scrolling the content and take another screenshot
    console.log('\n=== Step 7: Scroll content area ===');
    await page.evaluate(() => {
      // Scroll the main content area or body
      const scrollable = document.querySelector('[class*="content"], [class*="panel"], main, [class*="scroll"]');
      if (scrollable) {
        scrollable.scrollTop = scrollable.scrollHeight;
      } else {
        window.scrollTo(0, document.body.scrollHeight);
      }
    });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop2-04-scrolled.png`, fullPage: false });

    // Console errors
    const errors = consoleMsgs.filter(m => m.startsWith('[error]'));
    if (errors.length > 0) {
      console.log('\n=== Console Errors ===');
      for (const e of errors.slice(0, 15)) {
        console.log(e);
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop2-error.png`, fullPage: true });
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
