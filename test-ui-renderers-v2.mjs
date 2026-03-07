import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function test() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ level: msg.type(), text: msg.text() });
  });
  page.on('pageerror', err => {
    consoleMessages.push({ level: 'pageerror', text: err.message });
  });

  try {
    // ======================
    // TEST 2 REDO: Renderer Detail Page - Timeline (with correct tab clicking)
    // ======================
    console.log('\n=== TEST 2: Renderer Detail Page (timeline) ===');

    await page.goto('http://localhost:3001/renderers/timeline', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);

    // Get the tab structure more carefully
    const tabInfo = await page.evaluate(() => {
      // Look for the tab bar near the top (not sidebar nav)
      const allElements = document.querySelectorAll('*');
      const tabLike = [];
      for (const el of allElements) {
        const text = el.textContent.trim();
        const classList = el.className || '';
        if (typeof classList === 'string' && classList.includes('tab') && text.length < 60) {
          tabLike.push({
            tag: el.tagName,
            text: text.substring(0, 50),
            classes: classList.substring(0, 100),
            rect: el.getBoundingClientRect()
          });
        }
      }
      return tabLike.filter(t => t.rect.y < 200 && t.rect.y > 50); // Tabs near top, not sidebar
    });
    console.log('Tab elements near top:', JSON.stringify(tabInfo.slice(0, 10), null, 2));

    // Click Primitives & Variants tab using more specific selector
    console.log('\n--- Clicking Primitives & Variants tab ---');
    // Use text matching on elements that are visually in the tab bar area
    const clicked = await page.evaluate(() => {
      const allEls = [...document.querySelectorAll('*')];
      // Find elements whose DIRECT text includes "Primitives & Variants"
      for (const el of allEls) {
        if (el.children.length <= 3) { // Leaf-ish elements
          const ownText = el.textContent.trim();
          if (ownText.startsWith('Primitives & Variants') || ownText.startsWith('Primitives &')) {
            const rect = el.getBoundingClientRect();
            // Must be in tab area (top of page, not sidebar)
            if (rect.y > 50 && rect.y < 200 && rect.x > 250) {
              el.click();
              return { text: ownText, rect: {x: rect.x, y: rect.y}, tag: el.tagName };
            }
          }
        }
      }
      return null;
    });
    console.log('Clicked:', clicked);
    await page.waitForTimeout(1500);

    // Verify we're still on the timeline page
    const currentUrl = page.url();
    console.log('Current URL after tab click:', currentUrl);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/03-timeline-primitives-tab-v2.png`, fullPage: true });
    console.log('Screenshot saved: 03-timeline-primitives-tab-v2.png');

    // Check for primitive content
    const primContent = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        hasTemporal: text.includes('temporal_evolution'),
        hasBranching: text.includes('branching_foreclosure'),
        hasVertical: text.includes('vertical_evolution'),
        hasHorizontal: text.includes('horizontal_bifurcation'),
        hasConceptDrift: text.includes('concept_drift'),
        pageTitle: document.querySelector('h1, h2')?.textContent?.trim() || 'N/A',
        hasVariants: text.includes('Variant') || text.includes('variant'),
        snippet: text.substring(0, 600)
      };
    });
    console.log('Primitives content:', JSON.stringify(primContent, null, 2));

    // Now click Data Contract tab
    console.log('\n--- Clicking Data Contract tab ---');
    const clicked2 = await page.evaluate(() => {
      const allEls = [...document.querySelectorAll('*')];
      for (const el of allEls) {
        if (el.children.length <= 3) {
          const ownText = el.textContent.trim();
          if (ownText === 'Data Contract' || ownText.startsWith('Data Contract')) {
            const rect = el.getBoundingClientRect();
            if (rect.y > 50 && rect.y < 200 && rect.x > 250) {
              el.click();
              return { text: ownText, rect: {x: rect.x, y: rect.y}, tag: el.tagName };
            }
          }
        }
      }
      return null;
    });
    console.log('Clicked:', clicked2);
    await page.waitForTimeout(1500);

    const currentUrl2 = page.url();
    console.log('Current URL after Data Contract click:', currentUrl2);

    await page.screenshot({ path: `${SCREENSHOT_DIR}/04-timeline-data-contract-v2.png`, fullPage: true });
    console.log('Screenshot saved: 04-timeline-data-contract-v2.png');

    // Check for data contract content
    const dcContent = await page.evaluate(() => {
      const text = document.body.innerText;
      // Look for green checkmark indicators
      const greenEls = [...document.querySelectorAll('*')].filter(el => {
        const style = window.getComputedStyle(el);
        return (style.color === 'rgb(34, 197, 94)' || style.color === 'rgb(22, 163, 74)' ||
                style.color === 'rgb(16, 185, 129)' || el.textContent === '✓' || el.textContent === '✔');
      });
      return {
        hasInputDataSchema: text.includes('input_data_schema') || text.includes('Input Data Schema') || text.includes('input data schema'),
        hasSchema: text.includes('schema') || text.includes('Schema'),
        hasJsonEditor: !!document.querySelector('textarea, pre, code, [class*="json"], [class*="editor"], [class*="monaco"]'),
        greenCheckmarks: greenEls.length,
        pageTitle: document.querySelector('h1, h2')?.textContent?.trim() || 'N/A',
        snippet: text.substring(0, 800)
      };
    });
    console.log('Data Contract content:', JSON.stringify(dcContent, null, 2));

    // Also try clicking each remaining tab to take screenshots
    // Click Stance Affinities
    console.log('\n--- Clicking Stance Affinities tab ---');
    await page.evaluate(() => {
      const allEls = [...document.querySelectorAll('*')];
      for (const el of allEls) {
        if (el.children.length <= 3) {
          const ownText = el.textContent.trim();
          if (ownText === 'Stance Affinities') {
            const rect = el.getBoundingClientRect();
            if (rect.y > 50 && rect.y < 200 && rect.x > 250) {
              el.click();
              return true;
            }
          }
        }
      }
      return false;
    });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05-timeline-stances-tab.png`, fullPage: true });

    // Click Config Schema
    console.log('--- Clicking Config Schema tab ---');
    await page.evaluate(() => {
      const allEls = [...document.querySelectorAll('*')];
      for (const el of allEls) {
        if (el.children.length <= 3) {
          const ownText = el.textContent.trim();
          if (ownText === 'Config Schema') {
            const rect = el.getBoundingClientRect();
            if (rect.y > 50 && rect.y < 200 && rect.x > 250) {
              el.click();
              return true;
            }
          }
        }
      }
      return false;
    });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06-timeline-config-schema-tab.png`, fullPage: true });

    // Click Preview
    console.log('--- Clicking Preview tab ---');
    await page.evaluate(() => {
      const allEls = [...document.querySelectorAll('*')];
      for (const el of allEls) {
        if (el.children.length <= 2) {
          const ownText = el.textContent.trim();
          if (ownText === 'Preview') {
            const rect = el.getBoundingClientRect();
            if (rect.y > 50 && rect.y < 200 && rect.x > 250) {
              el.click();
              return true;
            }
          }
        }
      }
      return false;
    });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/07-timeline-preview-tab.png`, fullPage: true });

    // ======================
    // TEST 3: Transformations Applicability Tab (already done, check screenshot)
    // ======================
    console.log('\n=== Verified Transformations Applicability from previous run ===');

    // Print console errors
    const allErrors = consoleMessages.filter(m => m.level === 'error' || m.level === 'pageerror');
    console.log('\n=== FINAL CONSOLE ERROR SUMMARY ===');
    console.log(`Total errors: ${allErrors.length}`);
    allErrors.forEach((e, i) => console.log(`  ${i + 1}. [${e.level}] ${e.text.substring(0, 300)}`));

  } catch (err) {
    console.error('Test error:', err.message, err.stack);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/error-state.png`, fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test();
