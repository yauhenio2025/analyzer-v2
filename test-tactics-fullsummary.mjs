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

// Scroll to show the summary box with 50px padding above
await page.evaluate(() => {
  const el = document.querySelector('.gen-tactics-summary');
  if (el) {
    const rect = el.getBoundingClientRect();
    window.scrollBy(0, rect.top - 80);
  }
});
await page.waitForTimeout(500);

await page.screenshot({
  path: `${screenshotDir}/30-full-summary-visible.png`,
  clip: { x: 30, y: 0, width: 1380, height: 500 }
});

await browser.close();
console.log('Done!');
