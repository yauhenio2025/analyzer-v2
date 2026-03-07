import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function screenshot(page, name) {
  const filepath = path.join(SCREENSHOT_DIR, `${name}.png`);
  await page.screenshot({ path: filepath, fullPage: true });
  console.log(`Screenshot saved: ${filepath}`);
  return filepath;
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Monitor network for extension points calls
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('extension-points')) {
      const status = response.status();
      console.log(`\nEXTENSION POINTS RESPONSE: ${url} [${status}]`);
      if (status === 200) {
        try {
          const body = await response.json();
          console.log(`  workflow_key: ${body.workflow_key}`);
          console.log(`  total_candidate_engines: ${body.total_candidate_engines}`);
          console.log(`  strong_recommendations: ${body.strong_recommendations}`);
          console.log(`  phase_extensions count: ${body.phase_extensions?.length}`);
          if (body.phase_extensions?.length > 0) {
            for (const pe of body.phase_extensions) {
              console.log(`    Phase ${pe.phase_number}: ${pe.candidate_engines?.length} candidates, potential=${pe.extension_potential}`);
            }
          }
        } catch (e) {
          console.log(`  Parse error: ${e.message}`);
        }
      } else {
        try {
          const text = await response.text();
          console.log(`  Error body: ${text.substring(0, 300)}`);
        } catch {}
      }
    }
  });

  // Navigate directly to the implementation detail page
  console.log('=== Navigating to implementation detail page ===');
  await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // Take full-page screenshot of the detail page
  await screenshot(page, '10-impl-detail-full');

  // Enable extension points
  console.log('\n=== Enabling extension points ===');
  const extensionLabel = page.locator('text=Show Extension Points');
  if (await extensionLabel.isVisible()) {
    await extensionLabel.click();
    console.log('Clicked extension points toggle');

    // Wait for the API call and rendering
    await page.waitForTimeout(5000);

    // Take full-page screenshot
    await screenshot(page, '11-impl-extensions-full');

    // Check what's on the page
    const bodyText = await page.textContent('body');

    // Check for extension point indicators
    const extensionChecks = [
      ['Extension Points panel', bodyText.includes('Extension Points')],
      ['Candidate Engines text', bodyText.includes('Candidate Engines')],
      ['Dimension Coverage', bodyText.includes('Dimension Coverage')],
      ['Strong Recommendations', bodyText.includes('Strong Recommendations')],
      ['Moderate Fit', bodyText.includes('Moderate Fit')],
      ['Exploratory', bodyText.includes('Exploratory')],
      ['high potential', bodyText.includes('high potential') || bodyText.includes('moderate potential')],
      ['composite score', /\d+\.\d{2}/.test(bodyText)],
      ['analyzing...', bodyText.includes('analyzing')],
    ];

    for (const [name, found] of extensionChecks) {
      console.log(`  ${found ? 'FOUND' : 'NOT FOUND'}: ${name}`);
    }

    // Scroll to find extension panels
    console.log('\n=== Scrolling through page ===');
    const scrollPositions = [0, 500, 1000, 1500, 2000, 3000];
    for (const pos of scrollPositions) {
      await page.evaluate((y) => window.scrollTo(0, y), pos);
      await page.waitForTimeout(300);
    }

    // Take viewport screenshot at different scroll positions
    await page.evaluate(() => window.scrollTo(0, 800));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12-impl-scroll-800.png'), fullPage: false });

    await page.evaluate(() => window.scrollTo(0, 1600));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '13-impl-scroll-1600.png'), fullPage: false });

    await page.evaluate(() => window.scrollTo(0, 2400));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '14-impl-scroll-2400.png'), fullPage: false });

    // Scroll to bottom
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '15-impl-scroll-bottom.png'), fullPage: false });

    console.log('All screenshots taken');
  } else {
    console.log('Extension points toggle NOT FOUND');
  }

  await browser.close();
  console.log('\n=== Done ===');
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
