import { chromium } from 'playwright';
import { writeFileSync, mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/wiring-explainer';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await context.newPage();

// Collect console errors
const consoleErrors = [];
page.on('console', msg => {
  if (msg.type() === 'error') consoleErrors.push(msg.text());
});

// =========================================================
// TEST 1: Parent view - genealogy_target_profile
// =========================================================
console.log('\n=== TEST 1: Parent view (genealogy_target_profile) ===');
await page.goto('http://localhost:3000/views/genealogy_target_profile', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);

// Click the Renderer tab
const rendererTab1 = page.locator('button', { hasText: 'Renderer' });
await rendererTab1.click();
await page.waitForTimeout(3000); // Wait for renderer data to load

// Take full page screenshot
await page.screenshot({
  path: `${SCREENSHOT_DIR}/01-parent-view-renderer-tab.png`,
  fullPage: true
});

// Take focused screenshot of the wiring explainer panel
const wiringPanel1 = page.locator('.bg-indigo-50\\/40').first();
if (await wiringPanel1.isVisible()) {
  await wiringPanel1.screenshot({
    path: `${SCREENSHOT_DIR}/02-parent-view-wiring-explainer.png`
  });

  // Extract text content
  const wiringText1 = await wiringPanel1.textContent();
  console.log('\n--- Parent View Wiring Explainer Text ---');
  console.log(wiringText1);
  console.log('--- End ---\n');
} else {
  console.log('WARNING: Wiring explainer panel not found for parent view!');
  // Try to find it by heading text
  const explainerByHeading = page.locator('text=How this view is wired').first();
  if (await explainerByHeading.isVisible()) {
    const parent = explainerByHeading.locator('..');
    const text = await parent.textContent();
    console.log('Found by heading:', text);
  }
}

// =========================================================
// TEST 2: Child view - genealogy_tp_conceptual_framework
// =========================================================
console.log('\n=== TEST 2: Child view (genealogy_tp_conceptual_framework) ===');
await page.goto('http://localhost:3000/views/genealogy_tp_conceptual_framework', { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);

// Click the Renderer tab
const rendererTab2 = page.locator('button', { hasText: 'Renderer' });
await rendererTab2.click();
await page.waitForTimeout(3000);

// Take full page screenshot
await page.screenshot({
  path: `${SCREENSHOT_DIR}/03-child-view-renderer-tab.png`,
  fullPage: true
});

// Take focused screenshot of the wiring explainer panel
const wiringPanel2 = page.locator('.bg-indigo-50\\/40').first();
if (await wiringPanel2.isVisible()) {
  await wiringPanel2.screenshot({
    path: `${SCREENSHOT_DIR}/04-child-view-wiring-explainer.png`
  });

  const wiringText2 = await wiringPanel2.textContent();
  console.log('\n--- Child View Wiring Explainer Text ---');
  console.log(wiringText2);
  console.log('--- End ---\n');
} else {
  console.log('WARNING: Wiring explainer panel not found for child view!');
}

// Report console errors
if (consoleErrors.length > 0) {
  console.log('\n=== Console Errors ===');
  consoleErrors.forEach(e => console.log('  ERROR:', e));
} else {
  console.log('\nNo console errors detected.');
}

await browser.close();
console.log('\nScreenshots saved to:', SCREENSHOT_DIR);
