import { chromium } from 'playwright';
import fs from 'fs';

const screenshotDir = '/home/evgeny/projects/analyzer-v2/test-screenshots/tactics-debug';
fs.mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

// Navigate to the page
console.log('Navigating to genealogy page...');
await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
  waitUntil: 'networkidle',
  timeout: 60000
});

console.log('Page loaded, taking initial screenshot...');
await page.screenshot({ path: `${screenshotDir}/01-initial-page.png`, fullPage: false });
await page.waitForTimeout(2000);
await page.screenshot({ path: `${screenshotDir}/02-page-loaded.png`, fullPage: false });

// Find and click Tactics tab
console.log('Clicking Tactics & Strategies tab...');
const tacticsTab = page.locator('text="Tactics & Strategies"').first();
await tacticsTab.click();
await page.waitForTimeout(3000);
await page.screenshot({ path: `${screenshotDir}/03-tactics-tab-clicked.png`, fullPage: false });

// Full page screenshot
await page.screenshot({ path: `${screenshotDir}/04-tactics-full.png`, fullPage: true });

// Scroll slowly and take screenshots
console.log('Scrolling and capturing...');
// First scroll to top of content area
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(300);

for (let i = 0; i < 15; i++) {
  await page.evaluate(() => window.scrollBy(0, 500));
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${screenshotDir}/05-scroll-${String(i).padStart(2, '0')}.png`, fullPage: false });
}

// Now gather DOM analysis
console.log('\n=== DOM ANALYSIS ===\n');

const analysisInfo = await page.evaluate(() => {
  const info = {};

  // Get the full HTML structure of the tactics tab content
  // Look for the active tab panel or content area
  const activePanel = document.querySelector('[class*="tactics"], [class*="Tactics"], [data-tab*="tactics"]');
  info.activePanelHTML = activePanel ? activePanel.outerHTML.slice(0, 3000) : 'not found';

  // Find elements with "pattern" in class or text
  const patternEls = document.querySelectorAll('[class*="pattern"], [class*="Pattern"], [class*="summary"], [class*="Summary"]');
  info.patternElements = Array.from(patternEls).map(el => ({
    tag: el.tagName,
    className: el.className,
    textLength: el.textContent.length,
    textPreview: el.textContent.slice(0, 300),
    rect: el.getBoundingClientRect(),
    computedStyles: {
      lineHeight: getComputedStyle(el).lineHeight,
      fontSize: getComputedStyle(el).fontSize,
      padding: getComputedStyle(el).padding,
      margin: getComputedStyle(el).margin,
      overflow: getComputedStyle(el).overflow,
      maxHeight: getComputedStyle(el).maxHeight,
      height: getComputedStyle(el).height
    }
  }));

  // Find chip/pill elements
  const chipEls = document.querySelectorAll('[class*="chip"], [class*="Chip"], [class*="pill"], [class*="Pill"], [class*="badge"], [class*="Badge"]');
  info.chipElements = Array.from(chipEls).map(el => ({
    tag: el.tagName,
    className: el.className,
    text: el.textContent.trim().slice(0, 100),
    rect: el.getBoundingClientRect(),
    parentClass: el.parentElement?.className || 'none',
    grandparentClass: el.parentElement?.parentElement?.className || 'none'
  }));

  // Find distribution/count container elements
  const distEls = document.querySelectorAll('[class*="distribution"], [class*="Distribution"], [class*="count"], [class*="Count"], [class*="tactic-type"], [class*="TacticType"]');
  info.distributionElements = Array.from(distEls).map(el => ({
    tag: el.tagName,
    className: el.className,
    text: el.textContent.trim().slice(0, 300),
    rect: el.getBoundingClientRect(),
    childCount: el.children.length
  }));

  // Find narrative text areas
  const narrativeEls = document.querySelectorAll('[class*="narrative"], [class*="Narrative"], [class*="prose"], [class*="Prose"], [class*="text-content"], [class*="body"], [class*="description"]');
  info.narrativeElements = Array.from(narrativeEls).map(el => ({
    tag: el.tagName,
    className: el.className,
    textLength: el.textContent.length,
    textPreview: el.textContent.slice(0, 200),
    rect: el.getBoundingClientRect(),
    computedStyles: {
      lineHeight: getComputedStyle(el).lineHeight,
      fontSize: getComputedStyle(el).fontSize,
      padding: getComputedStyle(el).padding,
      margin: getComputedStyle(el).margin
    }
  }));

  // Get complete HTML of the visible content area for tactics tab
  // Look more broadly
  const mainContent = document.querySelector('.genealogy-detail, [class*="detail"], [class*="tab-content"], main');
  info.mainContentOuterHTML = mainContent ? mainContent.outerHTML.slice(0, 8000) : 'main not found';

  // Get all flex/grid containers that might be chip grids
  const flexGridEls = document.querySelectorAll('[class*="flex"], [class*="grid"], [class*="wrap"]');
  info.flexGridElements = Array.from(flexGridEls)
    .filter(el => {
      const text = el.textContent;
      return text.includes('tactic') || text.includes('Tactic') || text.includes('strateg') || text.includes('Strateg');
    })
    .map(el => ({
      tag: el.tagName,
      className: el.className,
      childCount: el.children.length,
      rect: el.getBoundingClientRect(),
      textPreview: el.textContent.slice(0, 200)
    }));

  return info;
});

console.log('\n=== PATTERN ELEMENTS ===');
console.log(JSON.stringify(analysisInfo.patternElements, null, 2));

console.log('\n=== CHIP/PILL ELEMENTS ===');
console.log(JSON.stringify(analysisInfo.chipElements, null, 2));

console.log('\n=== DISTRIBUTION ELEMENTS ===');
console.log(JSON.stringify(analysisInfo.distributionElements, null, 2));

console.log('\n=== NARRATIVE ELEMENTS ===');
console.log(JSON.stringify(analysisInfo.narrativeElements, null, 2));

console.log('\n=== FLEX/GRID CONTAINERS WITH TACTIC/STRATEGY CONTENT ===');
console.log(JSON.stringify(analysisInfo.flexGridElements, null, 2));

console.log('\n=== ACTIVE PANEL HTML ===');
console.log(analysisInfo.activePanelHTML);

console.log('\n=== MAIN CONTENT HTML (first 8000) ===');
console.log(analysisInfo.mainContentOuterHTML);

await browser.close();
console.log('\nDone! Screenshots saved to:', screenshotDir);
