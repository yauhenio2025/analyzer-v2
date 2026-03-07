import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';
const URL = 'https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console messages for debugging
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push(`[${msg.type()}] ${msg.text()}`);
  });

  console.log('Step 1: Navigating to genealogy page...');
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });

  // Wait for the page to fully load - look for Analysis Results section
  console.log('Step 2: Waiting for Analysis Results section...');
  try {
    await page.waitForSelector('text=Analysis Results', { timeout: 30000 });
    console.log('  Found "Analysis Results" text');
  } catch (e) {
    console.log('  "Analysis Results" not found, trying alternatives...');
    // Try waiting for any tab-like navigation
    await page.waitForTimeout(5000);
  }

  // Wait for tabs to appear
  try {
    await page.waitForSelector('[role="tab"], button:has-text("Conditions"), .tab, [class*="tab"]', { timeout: 15000 });
    console.log('  Found tab navigation elements');
  } catch (e) {
    console.log('  Tab navigation not found with standard selectors, continuing...');
  }

  // Step 3: Screenshot the initial state
  console.log('Step 3: Taking screenshot of initial state...');
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-01-initial-state.png`, fullPage: false });

  // Also take a full-page screenshot to see everything
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-01-initial-fullpage.png`, fullPage: true });

  // Let's examine the page structure to understand tab layout
  console.log('\nStep 4: Examining page structure for tabs...');

  // Look for all buttons/tabs containing relevant text
  const allButtons = await page.$$eval('button', buttons =>
    buttons.map(b => ({ text: b.textContent.trim().substring(0, 80), classes: b.className, role: b.getAttribute('role') }))
  );
  console.log('  All buttons on page:');
  allButtons.forEach((b, i) => {
    if (b.text) console.log(`    [${i}] "${b.text}" (class="${b.classes}", role="${b.role}")`);
  });

  // Look for anything that says "Conditions"
  const conditionsElements = await page.$$('text=Conditions');
  console.log(`\n  Found ${conditionsElements.length} elements with "Conditions" text`);

  // Also look for tab-related elements
  const tabs = await page.$$('[role="tab"]');
  console.log(`  Found ${tabs.length} elements with role="tab"`);

  // Look for tab panels
  const tabPanels = await page.$$('[role="tabpanel"]');
  console.log(`  Found ${tabPanels.length} elements with role="tabpanel"`);

  // Try to find the Conditions of Possibility tab and click it
  console.log('\nStep 5: Clicking "Conditions of Possibility" tab...');

  let clicked = false;

  // Try multiple selectors for the tab
  const tabSelectors = [
    'button:has-text("Conditions of Possibility")',
    'text=Conditions of Possibility',
    '[role="tab"]:has-text("Conditions")',
    'button:has-text("Conditions")',
    'a:has-text("Conditions")',
    '[class*="tab"]:has-text("Conditions")',
  ];

  for (const selector of tabSelectors) {
    try {
      const el = await page.$(selector);
      if (el) {
        const text = await el.textContent();
        console.log(`  Found element with selector "${selector}": "${text.trim().substring(0, 60)}"`);
        await el.click();
        clicked = true;
        console.log('  Clicked successfully!');
        break;
      }
    } catch (e) {
      // continue to next selector
    }
  }

  if (!clicked) {
    console.log('  Could not find Conditions of Possibility tab with any selector');
    console.log('  Dumping page content for debugging...');
    const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 3000));
    console.log(bodyText);
  }

  // Wait for content to render
  console.log('\nStep 6: Waiting for content to render...');
  await page.waitForTimeout(3000);

  // Take screenshot after clicking tab
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-02-after-tab-click.png`, fullPage: false });
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-02-after-tab-click-fullpage.png`, fullPage: true });
  console.log('  Screenshots taken after tab click');

  // Analyze what's on screen now
  console.log('\nStep 7: Analyzing rendered content...');

  // Look for enabling conditions
  const enablingSection = await page.$('text=Enabling Conditions');
  if (enablingSection) {
    console.log('  FOUND: Enabling Conditions section');
  } else {
    console.log('  NOT FOUND: Enabling Conditions section');
  }

  // Look for constraining conditions
  const constrainingSection = await page.$('text=Constraining Conditions');
  if (constrainingSection) {
    console.log('  FOUND: Constraining Conditions section');
  } else {
    console.log('  NOT FOUND: Constraining Conditions section');
  }

  // Look for synthetic judgment
  const syntheticJudgment = await page.$('text=Synthetic Judgment');
  if (syntheticJudgment) {
    console.log('  FOUND: Synthetic Judgment section');
  } else {
    // Try variations
    const synJudge2 = await page.$('text=synthetic_judgment');
    if (synJudge2) {
      console.log('  FOUND: synthetic_judgment (raw key, possible rendering issue)');
    } else {
      console.log('  NOT FOUND: Synthetic Judgment section');
    }
  }

  // Check for colored chips (condition_type)
  const chips = await page.$$('[class*="chip"], [class*="Chip"], [class*="badge"], [class*="Badge"], [class*="tag"], [class*="Tag"]');
  console.log(`  Found ${chips.length} chip/badge/tag elements`);

  if (chips.length > 0) {
    const chipTexts = await Promise.all(chips.slice(0, 10).map(c => c.textContent()));
    console.log('  Chip texts:', chipTexts.map(t => t.trim()).filter(t => t));
  }

  // Check for card grid layout
  const cardGrids = await page.$$('[class*="card-grid"], [class*="CardGrid"], [class*="cardGrid"], .grid');
  console.log(`  Found ${cardGrids.length} card grid elements`);

  // Check for accordion sections
  const accordions = await page.$$('[class*="accordion"], [class*="Accordion"], details, summary');
  console.log(`  Found ${accordions.length} accordion/details elements`);

  // Look for cards more broadly
  const cards = await page.$$('[class*="card"], [class*="Card"]');
  console.log(`  Found ${cards.length} card elements`);

  // Step 8: Scroll down to see more content
  console.log('\nStep 8: Scrolling to see full content...');
  await page.evaluate(() => window.scrollBy(0, 500));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-03-scrolled-down.png`, fullPage: false });

  // Scroll more
  await page.evaluate(() => window.scrollBy(0, 500));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-04-scrolled-more.png`, fullPage: false });

  // Step 9: Check for any how_managed badges
  console.log('\nStep 9: Checking for how_managed badges...');
  const howManagedElements = await page.$$('text=how_managed');
  const managedElements = await page.$$('text=managed');
  console.log(`  "how_managed" elements: ${howManagedElements.length}`);
  console.log(`  "managed" elements: ${managedElements.length}`);

  // Check for specific condition type values
  const conditionTypes = ['epistemic', 'institutional', 'technological', 'political', 'economic', 'cultural', 'discursive', 'material'];
  for (const ct of conditionTypes) {
    const found = await page.$(`text=${ct}`);
    if (found) {
      console.log(`  Found condition type: "${ct}"`);
    }
  }

  // Step 10: Get the HTML structure of the current tab content for analysis
  console.log('\nStep 10: Getting DOM structure of active content...');
  const activeTabContent = await page.evaluate(() => {
    // Try to find the active tab panel content
    const tabPanel = document.querySelector('[role="tabpanel"]') ||
                     document.querySelector('[class*="tabPanel"]') ||
                     document.querySelector('[class*="tab-content"]');
    if (tabPanel) {
      return {
        tagName: tabPanel.tagName,
        className: tabPanel.className,
        childrenCount: tabPanel.children.length,
        firstChild: tabPanel.children[0]?.outerHTML?.substring(0, 500) || 'empty',
        innerText: tabPanel.innerText?.substring(0, 1000) || 'empty'
      };
    }
    return { error: 'No tab panel found' };
  });
  console.log('  Active tab content:', JSON.stringify(activeTabContent, null, 2));

  // Print console messages
  if (consoleMessages.length > 0) {
    console.log('\n--- Console Messages ---');
    consoleMessages.slice(-20).forEach(m => console.log(`  ${m}`));
  }

  // Final full page screenshot
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-05-final-fullpage.png`, fullPage: true });

  console.log('\n--- Test Complete ---');
  console.log(`Screenshots saved to ${SCREENSHOT_DIR}/`);

  await browser.close();
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
