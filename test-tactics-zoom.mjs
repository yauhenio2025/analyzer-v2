import { chromium } from 'playwright';
import fs from 'fs';

const screenshotDir = '/home/evgeny/projects/analyzer-v2/test-screenshots/tactics-debug';
fs.mkdirSync(screenshotDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

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

// Now scroll so the summary box is at the top
await page.evaluate(() => {
  const summaryBox = document.querySelector('.gen-tactics-summary');
  if (summaryBox) {
    summaryBox.scrollIntoView({ block: 'start' });
  }
});
await page.waitForTimeout(500);

// Screenshot the summary box area
await page.screenshot({ path: `${screenshotDir}/10-summary-box-top.png`, fullPage: false });

// Now zoom into specific elements
// 1. Screenshot just the summary box
const summaryBox = page.locator('.gen-tactics-summary');
if (await summaryBox.count() > 0) {
  await summaryBox.screenshot({ path: `${screenshotDir}/11-summary-box-only.png` });
}

// 2. Screenshot the distribution chips in the summary
const distChips = page.locator('.gen-tactic-dist');
if (await distChips.count() > 0) {
  await distChips.first().screenshot({ path: `${screenshotDir}/12-dist-chips-summary.png` });
}

// 3. Screenshot the narrative wrap
const narrativeWrap = page.locator('.gen-pattern-narrative-wrap');
if (await narrativeWrap.count() > 0) {
  await narrativeWrap.first().screenshot({ path: `${screenshotDir}/13-narrative-wrap.png` });
}

// 4. Screenshot the second distribution area (gen-rel-summary)
const relSummary = page.locator('.gen-rel-summary');
if (await relSummary.count() > 0) {
  await relSummary.first().screenshot({ path: `${screenshotDir}/14-rel-summary-chips.png` });
}

// Now get detailed DOM info about the two chip areas
const chipAnalysis = await page.evaluate(() => {
  const info = {};

  // AREA 1: Distribution chips in the summary box (.gen-tactic-dist)
  const distArea = document.querySelector('.gen-tactic-dist');
  if (distArea) {
    info.summaryDistArea = {
      className: distArea.className,
      rect: distArea.getBoundingClientRect(),
      childCount: distArea.children.length,
      display: getComputedStyle(distArea).display,
      flexWrap: getComputedStyle(distArea).flexWrap,
      gap: getComputedStyle(distArea).gap,
      children: Array.from(distArea.children).map(c => ({
        tag: c.tagName,
        className: c.className,
        text: c.textContent.trim(),
        rect: c.getBoundingClientRect()
      }))
    };
  }

  // AREA 2: rel-summary chips (.gen-rel-summary)
  const relSummary = document.querySelector('.gen-rel-summary');
  if (relSummary) {
    info.relSummaryArea = {
      className: relSummary.className,
      rect: relSummary.getBoundingClientRect(),
      display: getComputedStyle(relSummary).display,
      outerHTML: relSummary.outerHTML.slice(0, 3000),
      children: Array.from(relSummary.children).map(c => ({
        tag: c.tagName,
        className: c.className,
        text: c.textContent.trim().slice(0, 100),
        rect: c.getBoundingClientRect()
      }))
    };
  }

  // Check for gen-summary-top structure
  const summaryTop = document.querySelector('.gen-summary-top');
  if (summaryTop) {
    info.summaryTop = {
      outerHTML: summaryTop.outerHTML.slice(0, 2000),
      display: getComputedStyle(summaryTop).display,
      flexDirection: getComputedStyle(summaryTop).flexDirection,
      gap: getComputedStyle(summaryTop).gap,
      rect: summaryTop.getBoundingClientRect()
    };
  }

  // Check the gen-summary-stat (dominant pattern label)
  const summaryStat = document.querySelector('.gen-summary-stat');
  if (summaryStat) {
    info.summaryStat = {
      outerHTML: summaryStat.outerHTML,
      display: getComputedStyle(summaryStat).display,
      flexDirection: getComputedStyle(summaryStat).flexDirection,
      rect: summaryStat.getBoundingClientRect()
    };
  }

  // NARRATIVE ANALYSIS
  const narrativeWrap = document.querySelector('.gen-pattern-narrative-wrap');
  if (narrativeWrap) {
    info.narrativeWrap = {
      className: narrativeWrap.className,
      rect: narrativeWrap.getBoundingClientRect(),
      overflow: getComputedStyle(narrativeWrap).overflow,
      maxHeight: getComputedStyle(narrativeWrap).maxHeight,
      height: getComputedStyle(narrativeWrap).height,
      borderTop: getComputedStyle(narrativeWrap).borderTop,
      paddingTop: getComputedStyle(narrativeWrap).paddingTop,
      marginTop: getComputedStyle(narrativeWrap).marginTop,
    };

    const narrative = narrativeWrap.querySelector('.gen-pattern-narrative');
    if (narrative) {
      info.narrativeP = {
        rect: narrative.getBoundingClientRect(),
        lineHeight: getComputedStyle(narrative).lineHeight,
        fontSize: getComputedStyle(narrative).fontSize,
        whiteSpace: getComputedStyle(narrative).whiteSpace,
        textOverflow: getComputedStyle(narrative).textOverflow,
        textLength: narrative.textContent.length,
        // check if text is clipped
        isClipped: narrative.scrollHeight > narrative.clientHeight,
        scrollHeight: narrative.scrollHeight,
        clientHeight: narrative.clientHeight,
      };
    }

    // Check for toggle button
    const toggle = narrativeWrap.querySelector('.gen-narrative-toggle');
    if (toggle) {
      info.narrativeToggle = {
        text: toggle.textContent,
        rect: toggle.getBoundingClientRect(),
        visible: toggle.offsetParent !== null
      };
    }
  }

  // Check if there's a parent wrapping overflow
  const parentOverflows = [];
  let el = document.querySelector('.gen-pattern-narrative');
  while (el) {
    const style = getComputedStyle(el);
    if (style.overflow !== 'visible' || style.maxHeight !== 'none') {
      parentOverflows.push({
        tag: el.tagName,
        className: el.className,
        overflow: style.overflow,
        maxHeight: style.maxHeight,
        height: style.height,
      });
    }
    el = el.parentElement;
  }
  info.parentOverflows = parentOverflows;

  return info;
});

console.log('\n=== SUMMARY DISTRIBUTION CHIPS ===');
console.log(JSON.stringify(chipAnalysis.summaryDistArea, null, 2));

console.log('\n=== REL SUMMARY AREA (Second set of chips) ===');
console.log(JSON.stringify(chipAnalysis.relSummaryArea, null, 2));

console.log('\n=== SUMMARY TOP ===');
console.log(JSON.stringify(chipAnalysis.summaryTop, null, 2));

console.log('\n=== SUMMARY STAT ===');
console.log(JSON.stringify(chipAnalysis.summaryStat, null, 2));

console.log('\n=== NARRATIVE WRAP ===');
console.log(JSON.stringify(chipAnalysis.narrativeWrap, null, 2));

console.log('\n=== NARRATIVE P ===');
console.log(JSON.stringify(chipAnalysis.narrativeP, null, 2));

console.log('\n=== NARRATIVE TOGGLE ===');
console.log(JSON.stringify(chipAnalysis.narrativeToggle, null, 2));

console.log('\n=== PARENT OVERFLOW CHAIN ===');
console.log(JSON.stringify(chipAnalysis.parentOverflows, null, 2));

await browser.close();
console.log('\nDone!');
