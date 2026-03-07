import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console messages
  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

  try {
    // Step 1: Navigate to the genealogy page
    console.log('=== Step 1: Navigate to genealogy page ===');
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });
    console.log('Page loaded');
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-01-page-loaded.png`, fullPage: false });

    // Step 2: Select the "Comprehensive 2/16/2026" analysis
    console.log('\n=== Step 2: Select the Comprehensive analysis ===');

    // Look for the analysis selector
    const selectorExists = await page.locator('select, [class*="select"], [class*="dropdown"], [class*="analysis"]').count();
    console.log(`Found ${selectorExists} potential selector elements`);

    // Try clicking on analysis selector - might be a dropdown or select
    // First check what's on the page
    const pageText = await page.textContent('body');
    const hasComprehensive = pageText.includes('Comprehensive');
    const has15ideas = pageText.includes('15 ideas');
    console.log(`Page has "Comprehensive": ${hasComprehensive}`);
    console.log(`Page has "15 ideas": ${has15ideas}`);

    // Look for analysis selector/dropdown
    const selects = await page.locator('select').all();
    console.log(`Found ${selects.length} <select> elements`);

    for (let i = 0; i < selects.length; i++) {
      const options = await selects[i].locator('option').allTextContents();
      console.log(`Select ${i} options:`, options);
    }

    // Try to find and click the analysis that has "Comprehensive" or "15 ideas"
    // It might be a custom dropdown, let's look for it
    const dropdowns = await page.locator('[class*="dropdown"], [class*="selector"], [class*="picker"], [role="listbox"], [role="combobox"]').all();
    console.log(`Found ${dropdowns.length} dropdown-like elements`);

    // Check if there's a button/trigger to select analysis
    const buttons = await page.locator('button').allTextContents();
    console.log('Buttons found:', buttons.filter(b => b.trim()).slice(0, 15));

    // Look for analysis-related elements
    const analysisLinks = await page.locator('a, button, [class*="analysis"], [class*="run"]').evaluateAll(
      els => els
        .map(el => ({ tag: el.tagName, text: el.textContent?.trim()?.substring(0, 80), classes: el.className }))
        .filter(e => e.text && (e.text.includes('Comprehensive') || e.text.includes('15 ideas') || e.text.includes('analysis') || e.text.includes('Analysis')))
    );
    console.log('Analysis-related elements:', JSON.stringify(analysisLinks, null, 2));

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-02-before-select.png`, fullPage: false });

    // Try selecting from the first <select> if it has a comprehensive option
    if (selects.length > 0) {
      for (let i = 0; i < selects.length; i++) {
        const options = await selects[i].locator('option').allTextContents();
        const compIdx = options.findIndex(o => o.includes('Comprehensive') || o.includes('15 ideas'));
        if (compIdx >= 0) {
          console.log(`Selecting "${options[compIdx]}" from select ${i}`);
          const optionValues = await selects[i].locator('option').evaluateAll(opts => opts.map(o => o.value));
          await selects[i].selectOption(optionValues[compIdx]);
          await page.waitForTimeout(3000);
          break;
        }
      }
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-03-after-select.png`, fullPage: false });

    // Step 3: Click on the "Conditions of Possibility" tab
    console.log('\n=== Step 3: Click Conditions of Possibility tab ===');

    // Find all tab-like elements
    const tabs = await page.locator('[role="tab"], [class*="tab"], button').evaluateAll(
      els => els.map(el => ({
        tag: el.tagName,
        text: el.textContent?.trim()?.substring(0, 60),
        role: el.getAttribute('role'),
        classes: el.className?.substring(0, 60)
      })).filter(e => e.text)
    );
    console.log('Tab-like elements:', tabs.filter(t => t.text.includes('Condition') || t.text.includes('possibility') || t.text.includes('Possibility') || t.role === 'tab'));

    // Try clicking the Conditions of Possibility tab
    const copTab = page.locator('text=Conditions of Possibility').first();
    const copTabExists = await copTab.count();
    console.log(`"Conditions of Possibility" tab found: ${copTabExists > 0}`);

    if (copTabExists > 0) {
      await copTab.click();
      console.log('Clicked Conditions of Possibility tab');
      await page.waitForTimeout(3000);
    } else {
      // Try shorter text
      const copTab2 = page.locator('text=Conditions').first();
      const copTab2Exists = await copTab2.count();
      console.log(`"Conditions" text found: ${copTab2Exists > 0}`);
      if (copTab2Exists > 0) {
        await copTab2.click();
        console.log('Clicked Conditions tab');
        await page.waitForTimeout(3000);
      }
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-04-tab-clicked.png`, fullPage: true });

    // Step 4: Look for the 7 accordion sections
    console.log('\n=== Step 4: Identify accordion sections ===');

    const expectedSections = [
      'Enabling Conditions',
      'Constraining Conditions',
      'Path Dependencies',
      'Unacknowledged Debts',
      'Alternative Paths',
      'Counterfactual Analysis',
      'Synthetic Judgment'
    ];

    const bodyText = await page.textContent('body');
    for (const section of expectedSections) {
      const found = bodyText.includes(section);
      console.log(`${found ? 'FOUND' : 'MISSING'}: "${section}"`);
    }

    // Find accordion headers/buttons
    const accordionHeaders = await page.locator('button, [class*="accordion"], [class*="section"], summary, [role="button"], h3, h4').evaluateAll(
      els => els.map(el => ({
        tag: el.tagName,
        text: el.textContent?.trim()?.substring(0, 80),
        classes: el.className?.substring(0, 80)
      })).filter(e => e.text && expectedSections.some(s => e.text.includes(s)))
    );
    console.log('\nAccordion-like elements matching expected sections:');
    for (const h of accordionHeaders) {
      console.log(`  [${h.tag}] "${h.text}" (class: ${h.classes})`);
    }

    // Step 5: Try to expand the 3 new sections
    console.log('\n=== Step 5: Expand new sections ===');

    const newSections = ['Path Dependencies', 'Unacknowledged Debts', 'Alternative Paths'];

    for (const sectionName of newSections) {
      console.log(`\n--- Trying to expand: ${sectionName} ---`);
      const sectionEl = page.locator(`text=${sectionName}`).first();
      const exists = await sectionEl.count();

      if (exists > 0) {
        // Click to expand
        await sectionEl.click();
        await page.waitForTimeout(1500);
        console.log(`Clicked "${sectionName}"`);

        await page.screenshot({
          path: `${SCREENSHOTS_DIR}/cop-05-${sectionName.toLowerCase().replace(/\s+/g, '-')}-expanded.png`,
          fullPage: true
        });

        // Check what content appeared
        const sectionContent = await page.evaluate((name) => {
          // Find the section header and look at following content
          const all = document.querySelectorAll('*');
          let found = false;
          let content = '';
          for (const el of all) {
            if (el.textContent?.includes(name) && (el.tagName === 'BUTTON' || el.tagName === 'SUMMARY' || el.tagName === 'H3' || el.tagName === 'H4' || el.getAttribute('role') === 'button')) {
              found = true;
              // Get the next sibling or parent's content
              const parent = el.closest('[class*="accordion"], [class*="section"], details, [class*="collapse"]');
              if (parent) {
                content = parent.textContent?.substring(0, 500);
              }
            }
          }
          return content;
        }, sectionName);

        if (sectionContent) {
          console.log(`Content preview: ${sectionContent.substring(0, 200)}`);
        } else {
          console.log('Could not extract section content');
        }
      } else {
        console.log(`"${sectionName}" NOT FOUND on page`);
      }
    }

    // Step 6: Take a final full-page screenshot
    console.log('\n=== Step 6: Final screenshot ===');
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-06-final-fullpage.png`, fullPage: true });

    // Also get a more detailed DOM analysis of the conditions content area
    console.log('\n=== DOM Analysis of Conditions area ===');
    const conditionsArea = await page.evaluate(() => {
      // Find the conditions of possibility content area
      const allElements = document.querySelectorAll('*');
      const results = [];

      for (const el of allElements) {
        const text = el.textContent?.trim();
        if (!text) continue;

        // Look for section headers with counts or specific section names
        const isHeader = el.tagName === 'H3' || el.tagName === 'H4' || el.tagName === 'H5' ||
          el.getAttribute('role') === 'button' ||
          el.tagName === 'SUMMARY' ||
          (el.tagName === 'BUTTON' && text.length < 100);

        if (isHeader) {
          const keywords = ['Enabling', 'Constraining', 'Path Depend', 'Unacknowledged', 'Alternative Path', 'Counterfactual', 'Synthetic'];
          if (keywords.some(k => text.includes(k))) {
            results.push({
              tag: el.tagName,
              text: text.substring(0, 100),
              classes: el.className?.substring(0, 100),
              expanded: el.getAttribute('aria-expanded'),
              parentClasses: el.parentElement?.className?.substring(0, 100)
            });
          }
        }
      }
      return results;
    });

    console.log('Conditions area headers found:');
    for (const item of conditionsArea) {
      console.log(`  [${item.tag}] "${item.text}" expanded=${item.expanded} class="${item.classes}"`);
    }

    // Count total distinct sections visible
    const uniqueSections = new Set();
    for (const item of conditionsArea) {
      for (const name of expectedSections) {
        if (item.text.includes(name)) {
          uniqueSections.add(name);
        }
      }
    }
    console.log(`\n=== RESULT: Found ${uniqueSections.size} of 7 expected sections ===`);
    console.log('Sections found:', [...uniqueSections]);
    console.log('Sections missing:', expectedSections.filter(s => !uniqueSections.has(s)));

    // Log any relevant console errors
    const errors = consoleMsgs.filter(m => m.startsWith('[error]'));
    if (errors.length > 0) {
      console.log('\n=== Console Errors ===');
      for (const e of errors.slice(0, 10)) {
        console.log(e);
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-error.png`, fullPage: true });
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
