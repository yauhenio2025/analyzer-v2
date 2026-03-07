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
    // TEST 1: Renderers List Page
    // ======================
    console.log('\n=== TEST 1: Renderers List Page ===');
    await page.goto('http://localhost:3001/renderers', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/01-renderers-list.png`, fullPage: true });
    console.log('Screenshot saved: 01-renderers-list.png');

    // Check for key elements
    const h1 = await page.textContent('h1').catch(() => 'NOT FOUND');
    console.log('Page heading:', h1);

    // Check for search input
    const searchInput = await page.$('input[type="text"], input[placeholder*="earch"], input[placeholder*="ilter"]');
    console.log('Search input found:', !!searchInput);

    // Check for category filter
    const categoryFilter = await page.$('select, [class*="filter"], [class*="Filter"]');
    console.log('Category filter found:', !!categoryFilter);

    // Check for info banner
    const bannerText = await page.evaluate(() => {
      const els = document.querySelectorAll('[class*="banner"], [class*="info"], [class*="alert"], [class*="notice"]');
      for (const el of els) {
        if (el.textContent.includes('primitive') || el.textContent.includes('cross-reference')) {
          return el.textContent.substring(0, 200);
        }
      }
      // Try looking at all paragraphs and divs
      const allText = document.body.innerText;
      const crossRefIdx = allText.indexOf('cross-reference');
      if (crossRefIdx >= 0) return allText.substring(Math.max(0, crossRefIdx - 80), crossRefIdx + 120);
      const primIdx = allText.indexOf('primitive');
      if (primIdx >= 0) return allText.substring(Math.max(0, primIdx - 80), primIdx + 120);
      return 'NOT FOUND';
    });
    console.log('Info banner about primitives:', bannerText);

    // Check for Create Renderer button
    const createBtn = await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button, a')];
      const found = btns.find(b => b.textContent.includes('Create'));
      return found ? found.textContent.trim() : 'NOT FOUND';
    });
    console.log('Create Renderer button:', createBtn);

    // Check for renderer cards
    const cards = await page.evaluate(() => {
      // Try various card selectors
      const cardEls = document.querySelectorAll('[class*="card"], [class*="Card"], [class*="renderer-item"], [class*="list-item"]');
      const results = [];
      for (const card of cardEls) {
        const text = card.textContent.substring(0, 200);
        if (text.includes('timeline') || text.includes('accordion') || text.includes('card_grid') || text.includes('prose')) {
          results.push(text.substring(0, 150));
        }
      }
      return { count: cardEls.length, rendererCards: results.length, samples: results.slice(0, 3) };
    });
    console.log('Cards found:', JSON.stringify(cards, null, 2));

    // Check for left border color coding
    const colorCoding = await page.evaluate(() => {
      const cards = document.querySelectorAll('[class*="card"], [class*="Card"]');
      const borders = [];
      for (const card of cards) {
        const style = window.getComputedStyle(card);
        if (style.borderLeftColor && style.borderLeftColor !== 'rgb(0, 0, 0)') {
          borders.push(style.borderLeftColor);
        }
        if (style.borderLeftWidth && parseInt(style.borderLeftWidth) > 1) {
          borders.push(`${style.borderLeftWidth} ${style.borderLeftColor}`);
        }
      }
      return [...new Set(borders)].slice(0, 5);
    });
    console.log('Left border colors:', colorCoding);

    // Print console errors so far
    const errors1 = consoleMessages.filter(m => m.level === 'error' || m.level === 'pageerror');
    console.log('Console errors:', errors1.length);
    if (errors1.length > 0) {
      errors1.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));
    }

    // ======================
    // TEST 2: Renderer Detail Page - Timeline
    // ======================
    console.log('\n=== TEST 2: Renderer Detail Page (timeline) ===');
    consoleMessages.length = 0; // Clear for new page

    await page.goto('http://localhost:3001/renderers/timeline', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/02-renderer-detail-timeline.png`, fullPage: true });
    console.log('Screenshot saved: 02-renderer-detail-timeline.png');

    // Check for tabs
    const tabs = await page.evaluate(() => {
      const tabEls = document.querySelectorAll('[class*="tab"], [role="tab"], button, nav a');
      const tabTexts = [];
      for (const t of tabEls) {
        const text = t.textContent.trim();
        if (['Identity', 'Data Contract', 'Primitives', 'Stance', 'Config', 'Preview'].some(k => text.includes(k))) {
          tabTexts.push(text);
        }
      }
      return [...new Set(tabTexts)];
    });
    console.log('Tabs found:', tabs);

    // Check which tab is active by default
    const activeTab = await page.evaluate(() => {
      const active = document.querySelector('[class*="active"][class*="tab"], [aria-selected="true"], .tab-active');
      return active ? active.textContent.trim() : 'unknown';
    });
    console.log('Active tab:', activeTab);

    // Click on Primitives & Variants tab
    console.log('\n--- Clicking Primitives & Variants tab ---');
    const primitivesTab = await page.evaluate(() => {
      const tabs = document.querySelectorAll('[class*="tab"], [role="tab"], button, nav a, span');
      for (const t of tabs) {
        if (t.textContent.includes('Primitives') || t.textContent.includes('Variant')) {
          t.click();
          return t.textContent.trim();
        }
      }
      return 'NOT FOUND';
    });
    console.log('Clicked tab:', primitivesTab);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/03-timeline-primitives-tab.png`, fullPage: true });
    console.log('Screenshot saved: 03-timeline-primitives-tab.png');

    // Check for primitive affinities
    const primitiveAffinities = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        hasTemporal: text.includes('temporal_evolution'),
        hasBranching: text.includes('branching_foreclosure'),
        hasVertical: text.includes('vertical_evolution'),
        hasHorizontal: text.includes('horizontal_bifurcation'),
        hasConceptDrift: text.includes('concept_drift')
      };
    });
    console.log('Primitive affinities & variants:', primitiveAffinities);

    // Click on Data Contract tab
    console.log('\n--- Clicking Data Contract tab ---');
    const dataContractTab = await page.evaluate(() => {
      const tabs = document.querySelectorAll('[class*="tab"], [role="tab"], button, nav a, span');
      for (const t of tabs) {
        if (t.textContent.includes('Data Contract')) {
          t.click();
          return t.textContent.trim();
        }
      }
      return 'NOT FOUND';
    });
    console.log('Clicked tab:', dataContractTab);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/04-timeline-data-contract-tab.png`, fullPage: true });
    console.log('Screenshot saved: 04-timeline-data-contract-tab.png');

    // Check for green checkmark and JSON schema
    const dataContractContent = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        hasInputDataSchema: text.includes('input_data_schema') || text.includes('Input Data Schema'),
        hasGreenCheck: !!document.querySelector('[class*="check"], [class*="green"], svg[class*="check"]'),
        hasJsonEditor: !!document.querySelector('[class*="json"], [class*="editor"], [class*="monaco"], textarea, pre, code'),
        snippet: text.substring(0, 500)
      };
    });
    console.log('Data Contract content:', JSON.stringify(dataContractContent, null, 2));

    // Print console errors for detail page
    const errors2 = consoleMessages.filter(m => m.level === 'error' || m.level === 'pageerror');
    console.log('Console errors:', errors2.length);
    if (errors2.length > 0) {
      errors2.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));
    }

    // ======================
    // TEST 3: Transformations Applicability Tab
    // ======================
    console.log('\n=== TEST 3: Transformations Applicability Tab ===');
    consoleMessages.length = 0;

    await page.goto('http://localhost:3001/transformations/idea_evolution_extraction', { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/05-transformation-detail.png`, fullPage: true });
    console.log('Screenshot saved: 05-transformation-detail.png');

    // Check current page state
    const transformTitle = await page.evaluate(() => {
      const h1 = document.querySelector('h1, h2, [class*="title"]');
      return h1 ? h1.textContent.trim() : 'NOT FOUND';
    });
    console.log('Transformation title:', transformTitle);

    // Find and list all tabs
    const transTabs = await page.evaluate(() => {
      const tabEls = document.querySelectorAll('[class*="tab"], [role="tab"], button, nav a');
      const tabTexts = [];
      for (const t of tabEls) {
        const text = t.textContent.trim();
        if (text.length > 0 && text.length < 50) {
          tabTexts.push(text);
        }
      }
      return tabTexts;
    });
    console.log('All tabs/buttons:', transTabs);

    // Click on Applicability tab
    console.log('\n--- Clicking Applicability tab ---');
    const applicabilityTab = await page.evaluate(() => {
      const tabs = document.querySelectorAll('[class*="tab"], [role="tab"], button, nav a, span');
      for (const t of tabs) {
        if (t.textContent.includes('Applicability')) {
          t.click();
          return t.textContent.trim();
        }
      }
      return 'NOT FOUND';
    });
    console.log('Clicked tab:', applicabilityTab);
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/06-transformation-applicability-tab.png`, fullPage: true });
    console.log('Screenshot saved: 06-transformation-applicability-tab.png');

    // Check for Primitive Affinities section and TagEditor
    const applicabilityContent = await page.evaluate(() => {
      const text = document.body.innerText;
      return {
        hasPrimitiveAffinities: text.includes('Primitive Affinit') || text.includes('primitive_affinit'),
        hasTemporalEvolution: text.includes('temporal_evolution'),
        hasRendererPresets: text.includes('Renderer Config Preset') || text.includes('renderer_config_preset'),
        hasTimeline: text.includes('timeline'),
        hasTagEditor: !!document.querySelector('[class*="tag"], [class*="Tag"], [class*="chip"], [class*="Chip"]'),
        snippet: text.substring(0, 1000)
      };
    });
    console.log('Applicability content:', JSON.stringify(applicabilityContent, null, 2));

    // Print console errors
    const errors3 = consoleMessages.filter(m => m.level === 'error' || m.level === 'pageerror');
    console.log('Console errors:', errors3.length);
    if (errors3.length > 0) {
      errors3.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));
    }

    // ======================
    // FINAL SUMMARY
    // ======================
    console.log('\n=== FINAL CONSOLE ERROR SUMMARY ===');
    const allErrors = consoleMessages.filter(m => m.level === 'error' || m.level === 'pageerror');
    console.log(`Total errors across all pages: ${allErrors.length}`);
    allErrors.forEach((e, i) => console.log(`  ${i + 1}. [${e.level}] ${e.text.substring(0, 300)}`));

    const allWarnings = consoleMessages.filter(m => m.level === 'warning');
    console.log(`Total warnings: ${allWarnings.length}`);

  } catch (err) {
    console.error('Test error:', err.message);
    await page.screenshot({ path: `${SCREENSHOT_DIR}/error-state.png`, fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test();
