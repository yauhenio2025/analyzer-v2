import { chromium } from 'playwright';
import fs from 'fs';

const screenshotDir = '/home/evgeny/projects/analyzer-v2/test-screenshots/tactics-debug';
fs.mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

console.log('Navigating...');
await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
  waitUntil: 'networkidle',
  timeout: 60000
});
await page.waitForTimeout(2000);

// Click Tactics tab
const tacticsTab = page.locator('text="Tactics & Strategies"').first();
await tacticsTab.click();
await page.waitForTimeout(3000);

// Scroll the summary box into view and take a tall viewport screenshot
await page.evaluate(() => {
  const el = document.querySelector('.gen-tactics-summary');
  if (el) el.scrollIntoView({ block: 'start', behavior: 'instant' });
});
await page.waitForTimeout(500);

// Take a big screenshot with a tall viewport to capture the whole summary+chips area
await page.screenshot({ path: `${screenshotDir}/20-summary-area-tall.png`, fullPage: false });

// Also capture with clipping to get just the top portion at high resolution
await page.screenshot({
  path: `${screenshotDir}/21-summary-box-clipped.png`,
  clip: { x: 50, y: 0, width: 1340, height: 500 }
});

// And the second chips area
await page.evaluate(() => {
  const el = document.querySelector('.gen-rel-summary');
  if (el) el.scrollIntoView({ block: 'start', behavior: 'instant' });
});
await page.waitForTimeout(500);
await page.screenshot({
  path: `${screenshotDir}/22-rel-summary-clipped.png`,
  clip: { x: 50, y: 0, width: 1340, height: 300 }
});

await browser.close();
console.log('Done!');
