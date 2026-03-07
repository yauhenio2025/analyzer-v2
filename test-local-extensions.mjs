import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Override ANALYZER_V2_URL to point to local backend
  await page.addInitScript(() => {
    // This won't work because env vars are set at build time in Next.js
    // Instead, we'll intercept fetch calls
  });

  // Route extension-points requests to local API
  await page.route('**/v1/workflows/*/extension-points*', async (route) => {
    const url = new URL(route.request().url());
    const localUrl = `http://localhost:8001${url.pathname}${url.search}`;
    console.log(`Routing extension-points to local: ${localUrl}`);
    try {
      const response = await fetch(localUrl);
      const body = await response.text();
      await route.fulfill({
        status: response.status,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: body,
      });
    } catch (e) {
      console.log(`Local fetch failed: ${e.message}`);
      await route.continue();
    }
  });

  // Navigate to implementation detail
  console.log('=== Navigating to implementation detail page ===');
  await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // Enable extension points
  console.log('=== Enabling extension points ===');
  const extensionLabel = page.locator('text=Show Extension Points');
  await extensionLabel.click();
  console.log('Clicked extension points toggle');
  await page.waitForTimeout(5000);

  // Full page screenshot
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '20-local-extensions-full.png'), fullPage: true });
  console.log('Full page screenshot saved');

  // Check what's visible
  const bodyText = await page.textContent('body');
  const checks = [
    'Extension Points', 'Candidate Engines', 'Dimension Coverage',
    'Strong Recommendations', 'Moderate Fit', 'Exploratory',
    'high potential', 'moderate potential', 'Capability Gaps',
  ];
  for (const check of checks) {
    console.log(`  ${bodyText.includes(check) ? 'FOUND' : 'NOT FOUND'}: "${check}"`);
  }

  // Score values
  const scores = bodyText.match(/\d+\.\d{2}/g);
  console.log(`  Score values found: ${scores ? scores.length : 0}`);
  if (scores) console.log(`  Examples: ${scores.slice(0, 5).join(', ')}`);

  // Take viewport screenshots at different scroll positions
  for (const [pos, name] of [[0, '21'], [600, '22'], [1200, '23'], [1800, '24'], [2400, '25'], [3200, '26']]) {
    await page.evaluate((y) => window.scrollTo(0, y), pos);
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, `${name}-scroll-${pos}.png`), fullPage: false });
  }

  // Scroll to bottom
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '27-scroll-bottom.png'), fullPage: false });

  console.log('All screenshots saved');

  await browser.close();
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
