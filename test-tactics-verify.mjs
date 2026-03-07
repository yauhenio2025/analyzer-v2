import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  console.log('Step 1: Navigating to genealogy page...');
  await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
    waitUntil: 'networkidle',
    timeout: 120000
  });
  console.log('Page loaded. URL:', page.url());
  await page.waitForTimeout(2000);

  // Scroll down to find the Comprehensive analyses with tactics
  console.log('\nStep 2: Scrolling to find Comprehensive analysis with tactics...');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(1500);

  // Find all analysis entries and locate the one with 11 tactics
  const entries = await page.evaluate(() => {
    const items = document.querySelectorAll('.gen-analysis-item, [class*="analysis-item"], div, li');
    const results = [];
    for (const item of items) {
      const text = item.textContent.trim();
      if (text.includes('Comprehensive') && text.includes('11 tactics')) {
        results.push({
          tag: item.tagName,
          classes: item.className,
          text: text.substring(0, 120),
          rect: item.getBoundingClientRect(),
          clickable: item.style.cursor === 'pointer' || item.tagName === 'A' || item.onclick !== null
        });
      }
    }
    return results;
  });

  console.log('Matching entries:', entries.length);
  for (const e of entries) {
    console.log(`  <${e.tag} class="${e.classes}"> y=${Math.round(e.rect.y)} "${e.text}"`);
  }

  // Click on the Comprehensive entry with 11 tactics
  // Look for an element containing "11 tactics" that is near "Comprehensive"
  const clickTarget = page.locator('text=Comprehensive').filter({ hasText: '11 tactics' }).first();
  try {
    const visible = await clickTarget.isVisible({ timeout: 3000 });
    if (!visible) throw new Error('Not visible');
    console.log('Clicking Comprehensive entry with 11 tactics...');
    await clickTarget.click();
  } catch {
    // Try a different approach - click on the parent row of the "11 tactics" text
    console.log('Trying alternative: click the row containing "11 tactics"...');
    const tacticText = page.locator('text=11 tactics').first();
    const row = tacticText.locator('xpath=ancestor::div[contains(@class, "gen-analysis-item") or contains(@class, "analysis")]').first();
    try {
      await row.click();
    } catch {
      // Last resort - use evaluate to click
      console.log('Trying evaluate click...');
      await page.evaluate(() => {
        const allDivs = document.querySelectorAll('div');
        for (const div of allDivs) {
          const text = div.textContent;
          if (text && text.includes('Comprehensive') && text.includes('11 tactics') && text.includes('2/16/2026')) {
            // Find the closest clickable ancestor or the div itself
            if (div.className.includes('item') || div.className.includes('analysis')) {
              div.click();
              return true;
            }
          }
        }
        // Fallback: click any element with 11 tactics
        const els = document.querySelectorAll('*');
        for (const el of els) {
          if (el.textContent.includes('11 tactics') && el.children.length < 5 && el.offsetHeight > 20 && el.offsetHeight < 80) {
            el.click();
            return true;
          }
        }
        return false;
      });
    }
  }

  console.log('Waiting for analysis to load...');
  await page.waitForTimeout(5000);
  console.log('URL after click:', page.url());
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-01-after-click.png`, fullPage: false });
  console.log('Screenshot 1: After clicking Comprehensive analysis.');

  // Check if we're now in an analysis view with tabs
  const tabButtons = await page.evaluate(() => {
    const buttons = document.querySelectorAll('button');
    return Array.from(buttons)
      .filter(b => b.offsetHeight > 0 && b.offsetWidth > 0)
      .map(b => ({
        text: b.textContent.trim(),
        classes: b.className,
        rect: { x: Math.round(b.getBoundingClientRect().x), y: Math.round(b.getBoundingClientRect().y) }
      }))
      .filter(b => b.text.length < 80);
  });

  console.log('\nVisible buttons:');
  for (const btn of tabButtons) {
    console.log(`  "${btn.text}" class="${btn.classes}" pos=(${btn.rect.x}, ${btn.rect.y})`);
  }

  // Click the Tactics & Strategies tab
  console.log('\nStep 3: Clicking Tactics & Strategies tab...');
  const tacticsBtn = page.locator('button:has-text("Tactics")').first();
  try {
    await tacticsBtn.scrollIntoViewIfNeeded();
    const btnText = await tacticsBtn.textContent();
    console.log(`Found button: "${btnText.trim()}"`);
    await tacticsBtn.click();
    console.log('Clicked!');
    await page.waitForTimeout(3000);
  } catch (e) {
    console.log('Could not click Tactics button:', e.message);
  }

  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-02-tactics-tab.png`, fullPage: false });
  console.log('Screenshot 2: Tactics tab view.');

  // Now verify the three fixes
  console.log('\n====== VERIFICATION ======\n');

  // === FIX 1: Duplicate distribution chips ===
  console.log('=== FIX 1: Checking for duplicate distribution chips ===');

  const chipAnalysis = await page.evaluate(() => {
    // Look for all elements that look like distribution chips (tactic type + count)
    const allEls = document.querySelectorAll('button, span, div, a');
    const chips = [];
    const chipPattern = /^[\w\s]+:\s*\d+$/;

    for (const el of allEls) {
      const text = el.textContent.trim();
      // Match patterns like "Vocabulary Migration: 2" or "Position Reversal: 2"
      if (chipPattern.test(text) && text.length < 40 && el.offsetHeight > 0) {
        chips.push({
          tag: el.tagName,
          text: text,
          isButton: el.tagName === 'BUTTON',
          y: Math.round(el.getBoundingClientRect().y),
          x: Math.round(el.getBoundingClientRect().x),
          classes: el.className.substring(0, 60)
        });
      }
    }

    // Group by tactic name
    const groups = {};
    for (const chip of chips) {
      const name = chip.text.split(':')[0].trim();
      if (!groups[name]) groups[name] = [];
      groups[name].push(chip);
    }

    return { chips, groups };
  });

  console.log(`Total chip-like elements: ${chipAnalysis.chips.length}`);
  for (const chip of chipAnalysis.chips) {
    console.log(`  <${chip.tag}> "${chip.text}" y=${chip.y} button=${chip.isButton} class="${chip.classes}"`);
  }

  const duplicateGroups = Object.entries(chipAnalysis.groups).filter(([_, items]) => items.length > 1);
  if (duplicateGroups.length > 0) {
    console.log('DUPLICATES FOUND:');
    for (const [name, items] of duplicateGroups) {
      console.log(`  "${name}" appears ${items.length} times at y=${items.map(i => i.y).join(', ')}`);
    }
    console.log('FIX 1 VERDICT: FAIL - Duplicate chips detected');
  } else if (chipAnalysis.chips.length === 0) {
    console.log('No distribution chips found at all - checking if data is loaded...');
    // Look for any tactic type names
    const tacticNames = await page.evaluate(() => {
      const text = document.body.innerText;
      const names = ['Vocabulary Migration', 'Position Reversal', 'Concept Rebranding',
                     'Authority Appropriation', 'Evidence Recontextualization', 'Dialectical Integration'];
      return names.filter(n => text.includes(n));
    });
    console.log('Tactic type names found in page text:', tacticNames);
    if (tacticNames.length === 0) {
      console.log('FIX 1 VERDICT: INCONCLUSIVE - No tactics data loaded');
    } else {
      console.log('FIX 1 VERDICT: NEEDS INVESTIGATION - Tactic names present but no chip elements detected');
    }
  } else {
    console.log('FIX 1 VERDICT: PASS - No duplicate chips');
  }

  // === FIX 2: Read full analysis button ===
  console.log('\n=== FIX 2: Checking for "Read full analysis" button ===');

  const readFullBtn = page.locator('text=/[Rr]ead full analysis/').first();
  let fix2Pass = false;
  try {
    const isVisible = await readFullBtn.isVisible({ timeout: 3000 });
    if (isVisible) {
      const box = await readFullBtn.boundingBox();
      console.log(`"Read full analysis" IS VISIBLE at y=${Math.round(box.y)}, height=${Math.round(box.height)}`);

      // Click it to expand
      console.log('Clicking to expand...');
      await readFullBtn.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-03-expanded.png`, fullPage: false });
      console.log('Screenshot 3: After expanding narrative.');
      fix2Pass = true;
      console.log('FIX 2 VERDICT: PASS - Button visible and clickable');
    } else {
      console.log('"Read full analysis" exists but is NOT visible.');

      // Check if hidden behind overflow
      const overflowInfo = await page.evaluate(() => {
        const el = [...document.querySelectorAll('a, button, span')].find(e => e.textContent.includes('Read full analysis'));
        if (!el) return null;
        const rect = el.getBoundingClientRect();
        let parent = el.parentElement;
        while (parent) {
          const style = window.getComputedStyle(parent);
          if (style.overflow === 'hidden' || style.overflowY === 'hidden') {
            const parentRect = parent.getBoundingClientRect();
            return {
              elY: rect.y,
              elBottom: rect.bottom,
              parentBottom: parentRect.bottom,
              parentOverflow: style.overflow,
              parentMaxHeight: style.maxHeight,
              parentClasses: parent.className.substring(0, 60)
            };
          }
          parent = parent.parentElement;
        }
        return { elY: rect.y, elBottom: rect.bottom, noOverflowParent: true };
      });
      console.log('Overflow info:', JSON.stringify(overflowInfo, null, 2));
      console.log('FIX 2 VERDICT: FAIL - Button hidden');
    }
  } catch (e) {
    console.log('"Read full analysis" not found on page.');
    // Check if there's any expandable text
    const expandLinks = await page.evaluate(() => {
      return [...document.querySelectorAll('a, button, span')]
        .filter(el => el.textContent.toLowerCase().includes('read') || el.textContent.toLowerCase().includes('expand') || el.textContent.toLowerCase().includes('more'))
        .filter(el => el.offsetHeight > 0)
        .map(el => ({ text: el.textContent.trim().substring(0, 40), tag: el.tagName }));
    });
    console.log('Other expandable links:', expandLinks);
    console.log('FIX 2 VERDICT: FAIL - Button not found');
  }

  // === FIX 3: Narrative text spacing ===
  console.log('\n=== FIX 3: Checking narrative text spacing ===');

  const narrativeInfo = await page.evaluate(() => {
    // Find the narrative/summary text container
    const candidates = document.querySelectorAll('div, p, section');
    let best = null;
    let bestScore = 0;

    for (const el of candidates) {
      const text = el.textContent.trim();
      // Look for substantial text blocks that are likely the narrative
      if (text.length > 300 && text.length < 10000 && el.offsetHeight > 0) {
        // Prefer elements that are direct text containers
        const directText = el.childNodes.length > 0 ?
          Array.from(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim().length : 0;

        const style = window.getComputedStyle(el);
        const lineHeight = parseFloat(style.lineHeight) || 0;
        const fontSize = parseFloat(style.fontSize) || 0;

        if (lineHeight > 0 && fontSize > 10) {
          const score = directText > 100 ? directText : text.length / el.children.length;
          if (score > bestScore) {
            bestScore = score;
            best = {
              tag: el.tagName,
              classes: el.className.substring(0, 80),
              textLength: text.length,
              lineHeight: lineHeight,
              fontSize: fontSize,
              lineHeightRatio: (lineHeight / fontSize).toFixed(2),
              overflow: style.overflow,
              maxHeight: style.maxHeight,
              height: el.offsetHeight,
              textPreview: text.substring(0, 200)
            };
          }
        }
      }
    }
    return best;
  });

  if (narrativeInfo) {
    console.log('Narrative text container:');
    console.log(`  Element: <${narrativeInfo.tag} class="${narrativeInfo.classes}">`);
    console.log(`  Font size: ${narrativeInfo.fontSize}px`);
    console.log(`  Line height: ${narrativeInfo.lineHeight}px (ratio: ${narrativeInfo.lineHeightRatio})`);
    console.log(`  Overflow: ${narrativeInfo.overflow}, Max-height: ${narrativeInfo.maxHeight}`);
    console.log(`  Container height: ${narrativeInfo.height}px`);
    console.log(`  Text preview: "${narrativeInfo.textPreview}..."`);

    const ratio = parseFloat(narrativeInfo.lineHeightRatio);
    if (ratio < 1.2) {
      console.log('FIX 3 VERDICT: FAIL - Line height ratio too tight (< 1.2), text may overlap');
    } else if (ratio >= 1.2 && ratio <= 2.0) {
      console.log(`FIX 3 VERDICT: PASS - Line height ratio ${ratio} is readable`);
    } else {
      console.log(`FIX 3 VERDICT: PASS - Line height ratio ${ratio} (generous spacing)`);
    }
  } else {
    console.log('Could not identify narrative text container.');
    console.log('FIX 3 VERDICT: INCONCLUSIVE');
  }

  // Take final full page screenshot
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-05-final-fullpage.png`, fullPage: true });
  console.log('\nScreenshot 5: Final full page view.');

  await browser.close();
  console.log('\nDone. All screenshots in test-screenshots/');
}

main().catch(e => {
  console.error('Fatal error:', e.message);
  process.exit(1);
});
