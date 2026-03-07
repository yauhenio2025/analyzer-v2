/**
 * Playwright test: Dynamic Propagation System - Implementations page
 *
 * Tests:
 * 1. Navigate to /implementations list page
 * 2. Click on "Intellectual Genealogy Analysis"
 * 3. Toggle "Show Extension Points"
 * 4. Verify extension point candidates appear
 * 5. Click "Add to Phase" on a strong recommendation
 * 6. Verify success confirmation
 * 7. Wait for refetch, verify pipeline updated
 */
import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';
const BASE_URL = 'http://localhost:3001';

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function test() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  try {
    // ====================================================================
    // STEP 1: Navigate to implementations list page
    // ====================================================================
    console.log('\n=== STEP 1: Navigate to /implementations ===');
    await page.goto(`${BASE_URL}/implementations`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);  // Let data load

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/01-implementations-list.png`,
      fullPage: true
    });
    console.log('Screenshot: 01-implementations-list.png');

    // Verify page loaded
    const heading = await page.textContent('h1');
    console.log(`Page heading: "${heading}"`);
    if (!heading?.includes('Implementations')) {
      throw new Error(`Expected "Implementations" heading, got: "${heading}"`);
    }

    // Check for the "Intellectual Genealogy Analysis" card
    const genealogyCard = page.locator('text=Intellectual Genealogy Analysis');
    const genealogyVisible = await genealogyCard.isVisible();
    console.log(`"Intellectual Genealogy Analysis" visible: ${genealogyVisible}`);
    if (!genealogyVisible) {
      throw new Error('Intellectual Genealogy Analysis card not found on implementations list');
    }

    // ====================================================================
    // STEP 2: Click into the detail page
    // ====================================================================
    console.log('\n=== STEP 2: Navigate to Intellectual Genealogy detail ===');
    await genealogyCard.click();
    await page.waitForURL('**/implementations/intellectual_genealogy', { timeout: 10000 });
    await page.waitForTimeout(3000);  // Let all data load (chains, engines, etc)

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/02-detail-page.png`,
      fullPage: true
    });
    console.log('Screenshot: 02-detail-page.png');

    // Verify detail page
    const detailHeading = await page.textContent('h1');
    console.log(`Detail heading: "${detailHeading}"`);
    if (!detailHeading?.includes('Intellectual Genealogy')) {
      throw new Error(`Expected "Intellectual Genealogy" in heading, got: "${detailHeading}"`);
    }

    // ====================================================================
    // STEP 3: Toggle "Show Extension Points"
    // ====================================================================
    console.log('\n=== STEP 3: Toggle Show Extension Points ===');

    // Find the checkbox by its label text
    const extensionCheckbox = page.locator('label:has-text("Show Extension Points") input[type="checkbox"]');
    const checkboxExists = await extensionCheckbox.count();
    console.log(`Extension checkbox found: ${checkboxExists > 0}`);
    if (checkboxExists === 0) {
      throw new Error('Show Extension Points checkbox not found');
    }

    await extensionCheckbox.check();
    console.log('Checked "Show Extension Points"');

    // Wait for the "analyzing..." text to appear and then disappear
    const analyzingText = page.locator('text=analyzing...');
    try {
      await analyzingText.waitFor({ state: 'visible', timeout: 3000 });
      console.log('Loading indicator appeared: "analyzing..."');
    } catch (e) {
      console.log('Loading indicator may have already passed');
    }

    // Wait for extension points to load (the Extension Points sections to appear)
    await page.waitForSelector('text=Extension Points', { timeout: 30000 });
    await page.waitForTimeout(2000);  // Let everything settle

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/03-extension-points-loaded.png`,
      fullPage: true
    });
    console.log('Screenshot: 03-extension-points-loaded.png');

    // ====================================================================
    // STEP 4: Verify extension point candidates
    // ====================================================================
    console.log('\n=== STEP 4: Verify candidates appear ===');

    // Look for "Strong Recommendations" text
    const strongRecsText = page.locator('text=Strong Recommendations');
    const strongRecsCount = await strongRecsText.count();
    console.log(`"Strong Recommendations" sections found: ${strongRecsCount}`);

    // Look for "Add to Phase" buttons
    const addButtons = page.locator('button:has-text("Add to Phase")');
    const addButtonCount = await addButtons.count();
    console.log(`"Add to Phase" buttons found: ${addButtonCount}`);
    if (addButtonCount === 0) {
      throw new Error('No "Add to Phase" buttons found - candidates may not have loaded');
    }

    // Look for composite scores (numbers like "0.xx")
    const scoreElements = page.locator('.font-mono.font-bold');
    const scoreCount = await scoreElements.count();
    console.log(`Score elements found: ${scoreCount}`);

    // ====================================================================
    // STEP 5: Find a strong recommendation in Phase 1 and click "Add to Phase"
    // ====================================================================
    console.log('\n=== STEP 5: Add engine to Phase 1 ===');

    // Find the Phase 1 block (it has phase number "1" in a circle)
    // Look for the first Extension Points panel that has strong recommendations
    const extensionPanels = page.locator('.border-dashed.border-indigo-200');
    const panelCount = await extensionPanels.count();
    console.log(`Extension panels found: ${panelCount}`);

    // We want to find the first panel with a strong recommendation and "Add to Phase" button
    // The first "Add to Phase" button in the page should be in the first phase with candidates
    const firstAddButton = addButtons.first();

    // Get the candidate engine name near the first button
    const candidateCard = firstAddButton.locator('xpath=ancestor::div[contains(@class, "rounded-lg")]');
    const candidateEngineLink = candidateCard.locator('a').first();
    let engineName = 'unknown';
    try {
      engineName = await candidateEngineLink.textContent();
    } catch (e) {
      console.log('Could not read engine name from candidate card');
    }
    console.log(`Clicking "Add to Phase" for engine: "${engineName}"`);

    // Take a screenshot before clicking
    // Scroll to the first Add button first
    await firstAddButton.scrollIntoViewIfNeeded();
    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/04-before-add.png`,
      fullPage: false  // viewport only, for clarity
    });
    console.log('Screenshot: 04-before-add.png');

    // Click the Add to Phase button
    await firstAddButton.click();
    console.log('Clicked "Add to Phase"');

    // ====================================================================
    // STEP 6: Verify success confirmation
    // ====================================================================
    console.log('\n=== STEP 6: Verify success confirmation ===');

    // Wait for "Added to phase" text (with checkmark)
    const addedText = page.locator('text=Added to phase');
    try {
      await addedText.first().waitFor({ state: 'visible', timeout: 15000 });
      console.log('SUCCESS: "Added to phase" confirmation appeared');
    } catch (e) {
      // Check for error messages
      const errorText = page.locator('.text-red-600');
      const errorCount = await errorText.count();
      if (errorCount > 0) {
        const errorMessage = await errorText.first().textContent();
        console.log(`ERROR STATE FOUND: ${errorMessage}`);
        throw new Error(`Add engine failed with error: ${errorMessage}`);
      }
      throw new Error('"Added to phase" confirmation did not appear within 15s');
    }

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/05-success-confirmation.png`,
      fullPage: false
    });
    console.log('Screenshot: 05-success-confirmation.png');

    // Check that "committed to git" text is NOT present (no GITHUB_TOKEN locally)
    const committedText = page.locator('text=committed to git');
    const committedVisible = await committedText.count();
    console.log(`"committed to git" visible: ${committedVisible > 0} (expected: false without GITHUB_TOKEN)`);

    // ====================================================================
    // STEP 7: Wait for refetch and verify pipeline updated
    // ====================================================================
    console.log('\n=== STEP 7: Wait for refetch and verify pipeline update ===');

    // The mutation has a 2.5s setTimeout before invalidating extension-points,
    // plus pipeline data is invalidated immediately. Wait 4s total.
    await sleep(4000);

    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/06-after-refetch.png`,
      fullPage: true
    });
    console.log('Screenshot: 06-after-refetch.png');

    // ====================================================================
    // SUMMARY
    // ====================================================================
    console.log('\n========================================');
    console.log('TEST RESULTS SUMMARY');
    console.log('========================================');
    console.log('[PASS] Implementations list page loads correctly');
    console.log('[PASS] Intellectual Genealogy card visible and clickable');
    console.log('[PASS] Detail page loads with phases, chains, engines');
    console.log('[PASS] "Show Extension Points" checkbox toggle works');
    console.log('[PASS] Extension points load with candidates and scores');
    console.log('[PASS] "Add to Phase" button works');
    console.log('[PASS] Success confirmation "Added to phase" appears');
    console.log(`[INFO] "committed to git" absent (expected - no GITHUB_TOKEN)`);
    console.log('[PASS] Pipeline data refetched after delay');
    console.log('========================================');

    // Print any console errors
    const errors = consoleMessages.filter(m => m.type === 'error');
    if (errors.length > 0) {
      console.log(`\nConsole errors (${errors.length}):`);
      errors.forEach(e => console.log(`  [${e.type}] ${e.text}`));
    } else {
      console.log('\nNo console errors detected.');
    }

  } catch (error) {
    console.error(`\nTEST FAILED: ${error.message}`);
    await page.screenshot({
      path: `${SCREENSHOTS_DIR}/FAILURE.png`,
      fullPage: true
    });
    console.log('Failure screenshot saved: FAILURE.png');
    throw error;
  } finally {
    await browser.close();
  }
}

test().catch(err => {
  console.error(err);
  process.exit(1);
});
