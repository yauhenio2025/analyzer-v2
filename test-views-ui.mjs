import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/views';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

let screenshotCount = 0;
function screenshotPath(name) {
  screenshotCount++;
  return `${SCREENSHOT_DIR}/${String(screenshotCount).padStart(2, '0')}-${name}.png`;
}

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Collect console errors
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // =========================================================================
    // STEP 1: Navigate to /views list page
    // =========================================================================
    console.log('\n=== STEP 1: Navigate to /views list page ===');
    await page.goto('http://localhost:3001/views', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000); // Allow React to render

    // Screenshot of list page
    await page.screenshot({ path: screenshotPath('views-list-page'), fullPage: true });
    console.log('Screenshot taken: views-list-page');

    // Check page title / heading
    const heading = await page.textContent('h1');
    console.log(`Page heading: "${heading}"`);
    if (heading && heading.includes('View Definitions')) {
      console.log('PASS: Page heading is correct');
    } else {
      console.log('FAIL: Expected heading "View Definitions"');
    }

    // Check view count text
    const countText = await page.textContent('p.text-gray-500');
    console.log(`View count text: "${countText}"`);

    // =========================================================================
    // STEP 2: Verify filter dropdowns and search
    // =========================================================================
    console.log('\n=== STEP 2: Verify filter dropdowns and search box ===');

    const searchInput = await page.$('input[placeholder="Search views..."]');
    console.log(`Search input found: ${!!searchInput}`);

    const selects = await page.$$('select.input');
    console.log(`Select dropdowns found: ${selects.length}`);

    // Check the first select (app filter)
    if (selects.length >= 1) {
      const appOptions = await selects[0].$$eval('option', opts => opts.map(o => o.textContent));
      console.log(`App filter options: ${JSON.stringify(appOptions)}`);
    }

    // Check the second select (page filter)
    if (selects.length >= 2) {
      const pageOptions = await selects[1].$$eval('option', opts => opts.map(o => o.textContent));
      console.log(`Page filter options: ${JSON.stringify(pageOptions)}`);
    }

    // =========================================================================
    // STEP 3: Verify view cards grouped by target_app:target_page
    // =========================================================================
    console.log('\n=== STEP 3: Verify grouped view cards ===');

    // Check group headers
    const groupHeaders = await page.$$eval(
      'button .text-sm.font-semibold.text-gray-900',
      els => els.map(el => el.textContent)
    );
    console.log(`Group headers: ${JSON.stringify(groupHeaders)}`);

    // =========================================================================
    // STEP 4: Verify view card content (name, key, renderer badge, target badge, position)
    // =========================================================================
    console.log('\n=== STEP 4: Verify view card content ===');

    // Get all view cards (links to /views/*)
    const viewCards = await page.$$('a[href^="/views/"]');
    console.log(`View cards found: ${viewCards.length}`);

    if (viewCards.length > 0) {
      // Inspect the first card
      const firstCard = viewCards[0];
      const cardHref = await firstCard.getAttribute('href');
      console.log(`First card href: ${cardHref}`);

      // Check view_name (h3)
      const viewName = await firstCard.$eval('h3', el => el.textContent).catch(() => 'NOT FOUND');
      console.log(`  view_name: "${viewName}"`);

      // Check view_key (mono text)
      const viewKey = await firstCard.$eval('.font-mono.text-gray-400', el => el.textContent).catch(() => 'NOT FOUND');
      console.log(`  view_key: "${viewKey}"`);

      // Check renderer_type badge (rounded-full in card)
      const badges = await firstCard.$$eval(
        '.rounded-full',
        els => els.map(el => el.textContent.trim())
      );
      console.log(`  badges: ${JSON.stringify(badges)}`);

      // Check target_app:target_page text
      const targetText = await firstCard.$eval('.font-medium', el => el.textContent).catch(() => 'NOT FOUND');
      console.log(`  target text: "${targetText}"`);

      // Check position
      const posText = await firstCard.$$eval(
        '.text-xs.text-gray-500 span',
        els => els.map(el => el.textContent.trim())
      );
      console.log(`  meta spans: ${JSON.stringify(posText)}`);
    }

    await page.screenshot({ path: screenshotPath('views-cards-detail'), fullPage: false });

    // =========================================================================
    // STEP 5: Click first view card to navigate to detail page
    // =========================================================================
    console.log('\n=== STEP 5: Click first view card ===');

    const firstViewLink = await page.$('a[href^="/views/genealogy"]');
    if (firstViewLink) {
      const href = await firstViewLink.getAttribute('href');
      console.log(`Clicking on: ${href}`);
      await firstViewLink.click();
      await page.waitForURL('**/views/**', { timeout: 10000 });
      await page.waitForTimeout(2000);

      await page.screenshot({ path: screenshotPath('view-detail-page'), fullPage: true });
      console.log('Screenshot taken: view-detail-page');

      // Check detail page heading
      const detailHeading = await page.textContent('h1');
      console.log(`Detail page heading: "${detailHeading}"`);

      // Check for tabs
      const tabs = await page.$$eval(
        'button.border-b-2',
        els => els.map(el => el.textContent.trim())
      );
      console.log(`Tabs found: ${JSON.stringify(tabs)}`);

      const expectedTabs = ['Identity', 'Target', 'Renderer', 'Data Source', 'Transformation', 'Preview'];
      const missingTabs = expectedTabs.filter(t => !tabs.includes(t));
      if (missingTabs.length === 0) {
        console.log('PASS: All expected tabs present');
      } else {
        console.log(`FAIL: Missing tabs: ${JSON.stringify(missingTabs)}`);
      }

      // Check badges on detail page
      const detailBadges = await page.$$eval(
        '.badge',
        els => els.map(el => el.textContent.trim())
      );
      console.log(`Detail badges: ${JSON.stringify(detailBadges)}`);
    } else {
      console.log('FAIL: No view card link found to click');
    }

    // =========================================================================
    // STEP 6: Click Target tab
    // =========================================================================
    console.log('\n=== STEP 6: Click Target tab ===');

    const targetTab = await page.$('button:has-text("Target")');
    if (targetTab) {
      await targetTab.click();
      await page.waitForTimeout(500);

      await page.screenshot({ path: screenshotPath('view-target-tab'), fullPage: true });
      console.log('Screenshot taken: view-target-tab');

      // Check for target fields
      const targetLabels = await page.$$eval(
        'label.label',
        els => els.map(el => el.textContent.trim())
      );
      console.log(`Target tab labels: ${JSON.stringify(targetLabels)}`);

      const hasTargetApp = targetLabels.some(l => l.includes('Target App'));
      const hasTargetPage = targetLabels.some(l => l.includes('Target Page'));
      const hasTargetSection = targetLabels.some(l => l.includes('Target Section'));

      console.log(`  Target App field: ${hasTargetApp ? 'PASS' : 'FAIL'}`);
      console.log(`  Target Page field: ${hasTargetPage ? 'PASS' : 'FAIL'}`);
      console.log(`  Target Section field: ${hasTargetSection ? 'PASS' : 'FAIL'}`);
    } else {
      console.log('FAIL: Target tab button not found');
    }

    // =========================================================================
    // STEP 7: Click Preview tab
    // =========================================================================
    console.log('\n=== STEP 7: Click Preview tab ===');

    const previewTab = await page.$('button:has-text("Preview")');
    if (previewTab) {
      await previewTab.click();
      await page.waitForTimeout(500);

      await page.screenshot({ path: screenshotPath('view-preview-tab'), fullPage: true });
      console.log('Screenshot taken: view-preview-tab');

      // Check for JSON preview (pre element)
      const preElement = await page.$('pre');
      if (preElement) {
        const preText = await preElement.textContent();
        const isValidJson = preText.includes('view_key') && preText.includes('renderer_type');
        console.log(`JSON preview found: ${isValidJson ? 'PASS' : 'FAIL (no expected fields)'}`);
        console.log(`JSON preview length: ${preText.length} chars`);
      } else {
        console.log('FAIL: No <pre> element found for JSON preview');
      }

      // Check for Composition Tree Position section
      const treeSection = await page.$('text=Composition Tree Position');
      console.log(`Composition Tree Position section: ${treeSection ? 'PASS' : 'FAIL'}`);
    } else {
      console.log('FAIL: Preview tab button not found');
    }

    // =========================================================================
    // STEP 8: Go back to /views and click Create View
    // =========================================================================
    console.log('\n=== STEP 8: Navigate to /views and click Create View ===');

    await page.goto('http://localhost:3001/views', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);

    const createBtn = await page.$('a[href="/views/new"]');
    if (createBtn) {
      const btnText = await createBtn.textContent();
      console.log(`Create button text: "${btnText.trim()}"`);

      await createBtn.click();
      await page.waitForURL('**/views/new', { timeout: 10000 });
      await page.waitForTimeout(2000);

      await page.screenshot({ path: screenshotPath('create-view-page'), fullPage: true });
      console.log('Screenshot taken: create-view-page');

      // Check create page heading
      const createHeading = await page.textContent('h1');
      console.log(`Create page heading: "${createHeading}"`);

      // Check that form fields are empty
      const viewKeyInput = await page.$('input[placeholder="snake_case_key"]');
      if (viewKeyInput) {
        const val = await viewKeyInput.inputValue();
        console.log(`View Key input value: "${val}" (${val === '' ? 'PASS - empty' : 'FAIL - not empty'})`);
      }

      const viewNameInput = await page.$('input[placeholder="Human-readable name"]');
      if (viewNameInput) {
        const val = await viewNameInput.inputValue();
        console.log(`View Name input value: "${val}" (${val === '' ? 'PASS - empty' : 'FAIL - not empty'})`);
      }

      // Check that the save button says "Create"
      const saveBtn = await page.$('button:has-text("Create")');
      console.log(`Create button found: ${!!saveBtn}`);
    } else {
      console.log('FAIL: Create View button/link not found');
    }

    // =========================================================================
    // Final summary
    // =========================================================================
    console.log('\n=== CONSOLE ERRORS ===');
    if (consoleErrors.length === 0) {
      console.log('No console errors detected');
    } else {
      for (const err of consoleErrors) {
        console.log(`  ERROR: ${err}`);
      }
    }

    console.log(`\nTotal screenshots taken: ${screenshotCount}`);
    console.log(`Screenshots saved to: ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    await page.screenshot({ path: screenshotPath('error-state'), fullPage: true });
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
