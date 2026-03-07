import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function screenshot(page, name) {
  const filepath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filepath, fullPage: false });
  console.log(`Screenshot saved: ${filepath}`);
  return filepath;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console errors
  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });
  page.on('pageerror', err => {
    consoleErrors.push(err.message);
  });

  // ===== STEP 1: Navigate to /implementations =====
  console.log('\n===== STEP 1: Navigate to /implementations =====');
  await page.goto('http://localhost:3001/implementations', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000); // Wait for full workflows to load
  await screenshot(page, '01-implementations-page');

  // ===== STEP 2: Check badge terminology =====
  console.log('\n===== STEP 2: Check badge terminology =====');
  const phaseBadges = await page.locator('text=/\\d+\\s*phases?/i').all();
  console.log(`Found ${phaseBadges.length} "phase(s)" badges`);
  for (const badge of phaseBadges) {
    const text = await badge.textContent();
    console.log(`  Badge: "${text.trim()}"`);
  }
  const passBadges = await page.locator('text=/\\d+\\s*passes?/i').all();
  if (passBadges.length > 0) {
    console.log(`FAIL: Found ${passBadges.length} "pass(es)" badges`);
  } else {
    console.log('PASS: No "pass(es)" badges found');
  }

  // Check for console errors from page load
  if (consoleErrors.length > 0) {
    console.log(`\n  Console errors: ${consoleErrors.length}`);
    consoleErrors.forEach(e => console.log(`    ERROR: ${e.substring(0, 200)}`));
    consoleErrors.length = 0;
  }

  // ===== STEP 3: Click on "Intellectual Genealogy Analysis" card =====
  console.log('\n===== STEP 3: Click Intellectual Genealogy Analysis card =====');
  // Wait for cards to be visible
  await page.waitForSelector('text=Intellectual Genealogy', { timeout: 5000 }).catch(() => {});
  const genealogyCard = page.locator('a:has-text("Intellectual Genealogy")').first();
  if (await genealogyCard.isVisible()) {
    console.log('Found Intellectual Genealogy card, clicking...');
    await genealogyCard.click();
    await page.waitForURL('**/implementations/intellectual_genealogy', { timeout: 5000 });
    await page.waitForTimeout(3000); // Wait for data loading
  } else {
    console.log('Card not found, navigating directly...');
    await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
  }

  // ===== STEP 4: Screenshot detail page =====
  console.log('\n===== STEP 4: Screenshot detail page =====');
  await screenshot(page, '02-genealogy-detail');
  console.log(`Current URL: ${page.url()}`);

  // Check for runtime errors
  if (consoleErrors.length > 0) {
    console.log(`\n  Console errors on detail page: ${consoleErrors.length}`);
    consoleErrors.forEach(e => console.log(`    ERROR: ${e.substring(0, 200)}`));
    consoleErrors.length = 0;
  }

  // ===== STEP 5: Verify terminology =====
  console.log('\n===== STEP 5: Check Phase-by-phase terminology =====');
  const detailText = await page.textContent('body');

  // Check for key phrases
  const checks = [
    ['Phase-by-phase', detailText.includes('Phase-by-phase')],
    ['Pipeline Flow', detailText.includes('Pipeline Flow')],
    ['Phases label', detailText.includes('Phases')],
    ['No "Pass-by-pass"', !detailText.includes('Pass-by-pass')],
    ['No "Pass-by-Pass"', !detailText.includes('Pass-by-Pass')],
  ];
  for (const [name, passed] of checks) {
    console.log(`  ${passed ? 'PASS' : 'FAIL'}: ${name}`);
  }

  // ===== STEP 6: Test depth selector =====
  console.log('\n===== STEP 6: Test depth selector =====');
  // Look for depth buttons
  for (const depthName of ['surface', 'standard', 'deep']) {
    const btn = page.locator(`button:text-is("${depthName}")`).first();
    if (await btn.isVisible().catch(() => false)) {
      console.log(`Found "${depthName}" depth button`);
      if (depthName !== 'standard') {
        await btn.click();
        await page.waitForTimeout(1000);
        await screenshot(page, `03-depth-${depthName}`);
        console.log(`Clicked "${depthName}" and took screenshot`);
      }
    } else {
      console.log(`NOT FOUND: "${depthName}" depth button`);
    }
  }

  // ===== STEP 7 & 8: Find and enable "Show Extension Points" =====
  console.log('\n===== STEP 7: Find Show Extension Points =====');

  // Look for the checkbox specifically
  const extensionCheckbox = page.locator('input[type="checkbox"]').first();
  const extensionLabel = page.locator('text=Show Extension Points').first();

  if (await extensionLabel.isVisible().catch(() => false)) {
    console.log('Found "Show Extension Points" label');
    // Click the label or the checkbox
    await extensionLabel.click();
    console.log('Clicked extension points toggle');
    await page.waitForTimeout(3000); // Wait for API call + rendering

    // Scroll down to see extension panels
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await screenshot(page, '05-extension-points');

    // Scroll to middle
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight / 2));
    await page.waitForTimeout(500);
    await screenshot(page, '06-extension-points-mid');
  } else if (await extensionCheckbox.isVisible().catch(() => false)) {
    console.log('Found checkbox, clicking...');
    await extensionCheckbox.click();
    await page.waitForTimeout(3000);
    await screenshot(page, '05-extension-points');
  } else {
    console.log('Extension points toggle NOT FOUND');
    // List all checkboxes and labels
    const allCheckboxes = await page.locator('input[type="checkbox"]').all();
    console.log(`  Total checkboxes on page: ${allCheckboxes.length}`);
  }

  // ===== STEP 9: Check candidate engines =====
  console.log('\n===== STEP 9: Check candidate engines =====');
  const bodyText = await page.textContent('body');

  if (bodyText.includes('Extension Points')) {
    console.log('PASS: Found "Extension Points" text on page');
  }
  if (bodyText.includes('Candidate Engines')) {
    console.log('PASS: Found "Candidate Engines" text');
  }
  if (bodyText.includes('Strong Recommendation') || bodyText.includes('Strong Recommendations')) {
    console.log('PASS: Found recommendation tiers');
  }

  // Check for scores
  const scoreMatches = bodyText.match(/\d+\.\d{2}/g);
  if (scoreMatches && scoreMatches.length > 0) {
    console.log(`PASS: Found ${scoreMatches.length} score values (e.g., ${scoreMatches.slice(0, 3).join(', ')})`);
  } else {
    console.log('INFO: No score values found yet (extension points may not be loaded)');
  }

  // ===== STEP 10: Navigate to /workflows =====
  console.log('\n===== STEP 10: Navigate to /workflows =====');
  await page.goto('http://localhost:3001/workflows', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);
  await screenshot(page, '07-workflows-page');

  // ===== STEP 11: Check terminology =====
  console.log('\n===== STEP 11: Check workflow page terminology =====');
  const workflowText = await page.textContent('body');

  if (workflowText.includes('Multi-phase')) {
    console.log('PASS: Found "Multi-phase" subtitle');
  } else if (workflowText.includes('Multi-pass')) {
    console.log('FAIL: Still shows "Multi-pass" subtitle');
  }

  // Check phase badges
  const wfPhaseBadges = await page.locator('text=/\\d+\\s*phases?/i').all();
  console.log(`Found ${wfPhaseBadges.length} phase badges on workflows page`);
  for (const badge of wfPhaseBadges) {
    const text = await badge.textContent();
    console.log(`  Badge: "${text.trim()}"`);
  }

  // ===== STEP 12: Click intellectual_genealogy workflow =====
  console.log('\n===== STEP 12: Click intellectual_genealogy workflow =====');
  const genealogyLink = page.locator('a:has-text("Intellectual Genealogy")').first();
  if (await genealogyLink.isVisible()) {
    await genealogyLink.click();
    await page.waitForURL('**/workflows/intellectual_genealogy', { timeout: 5000 });
    await page.waitForTimeout(2000);
  } else {
    await page.goto('http://localhost:3001/workflows/intellectual_genealogy', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
  }

  // ===== STEP 13: Verify workflow detail terminology =====
  console.log('\n===== STEP 13: Verify workflow detail terminology =====');
  await screenshot(page, '08-workflow-genealogy-detail');
  console.log(`Current URL: ${page.url()}`);

  const wfDetailText = await page.textContent('body');

  const wfChecks = [
    ['Has "Phases" heading', wfDetailText.includes('Phases')],
    ['Has "Phase Dependency Graph"', wfDetailText.includes('Phase Dependency Graph')],
    ['No "Pass Dependency Graph"', !wfDetailText.includes('Pass Dependency Graph')],
    ['No "Passes" heading', !wfDetailText.match(/\bPasses\b/)],
  ];
  for (const [name, passed] of wfChecks) {
    console.log(`  ${passed ? 'PASS' : 'FAIL'}: ${name}`);
  }

  // Print all headings
  const headings = await page.locator('h1, h2, h3').all();
  for (const h of headings) {
    const text = await h.textContent();
    if (text.trim()) {
      console.log(`  Heading: "${text.trim()}"`);
    }
  }

  // Scroll and take final screenshot
  await page.evaluate(() => window.scrollBy(0, 600));
  await page.waitForTimeout(500);
  await screenshot(page, '09-workflow-detail-scrolled');

  // Final console error check
  if (consoleErrors.length > 0) {
    console.log(`\nConsole errors encountered: ${consoleErrors.length}`);
    consoleErrors.forEach(e => console.log(`  ERROR: ${e.substring(0, 200)}`));
  } else {
    console.log('\nNo console errors encountered');
  }

  await browser.close();
  console.log('\n===== ALL TESTS COMPLETE =====');
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
