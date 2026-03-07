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

// Scroll so the gen-summary-top is fully visible (scroll a bit above the summary box)
await page.evaluate(() => {
  const el = document.querySelector('.gen-tactics-summary');
  if (el) {
    const rect = el.getBoundingClientRect();
    window.scrollBy(0, rect.top - 10);
  }
});
await page.waitForTimeout(500);

// Clip screenshot to show just the summary box area
await page.screenshot({
  path: `${screenshotDir}/25-dompattern-top.png`,
  clip: { x: 50, y: 0, width: 1340, height: 350 }
});

// Also capture the gen-summary-top element directly
const summaryTop = page.locator('.gen-summary-top');
if (await summaryTop.count() > 0) {
  await summaryTop.screenshot({ path: `${screenshotDir}/26-summary-top-element.png` });
}

// Capture gen-summary-stat
const summaryStat = page.locator('.gen-summary-stat');
if (await summaryStat.count() > 0) {
  await summaryStat.screenshot({ path: `${screenshotDir}/27-summary-stat.png` });
}

await browser.close();
console.log('Done!');
