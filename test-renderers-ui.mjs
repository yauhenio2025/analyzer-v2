import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/renderers';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

let screenshotCount = 0;
function screenshotPath(name) {
  screenshotCount++;
  return `${SCREENSHOT_DIR}/${String(screenshotCount).padStart(2, '0')}-${name}.png`;
}

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // =========================================================================
    // TEST 1: Renderer API endpoint
    // =========================================================================
    console.log('\n=== TEST 1: Renderer API endpoint ===');
    const apiRes = await page.goto('http://localhost:8001/v1/renderers', { timeout: 10000 });
    const renderers = await apiRes.json();
    console.log(`Renderers from API: ${renderers.length}`);
    if (renderers.length === 8) {
      console.log('PASS: 8 renderers loaded');
    } else {
      console.log(`FAIL: Expected 8 renderers, got ${renderers.length}`);
    }

    // Check renderer structure
    const accordion = renderers.find(r => r.renderer_key === 'accordion');
    if (accordion) {
      console.log(`  accordion: ${accordion.renderer_name}`);
      console.log(`  category: ${accordion.category}`);
      console.log(`  stance_affinities keys: ${Object.keys(accordion.stance_affinities).join(', ')}`);
      console.log('PASS: Accordion has stance_affinities');
    } else {
      console.log('FAIL: accordion renderer not found');
    }

    // Test for-stance endpoint
    const stanceRes = await page.goto('http://localhost:8001/v1/renderers/for-stance/interactive', { timeout: 10000 });
    const stanceRenderers = await stanceRes.json();
    console.log(`\nRenderers for 'interactive' stance: ${stanceRenderers.length}`);
    if (stanceRenderers.length > 0) {
      console.log(`  Top renderer: ${stanceRenderers[0].renderer_key} (affinity: ${stanceRenderers[0].stance_affinities?.interactive})`);
      console.log('PASS: for-stance endpoint works');
    }

    // Test stance→renderers endpoint
    const stRendRes = await page.goto('http://localhost:8001/v1/operations/stances/evidence/renderers', { timeout: 10000 });
    const stRenderers = await stRendRes.json();
    console.log(`\nPreferred renderers for 'evidence' stance: ${stRenderers.length}`);
    for (const r of stRenderers) {
      console.log(`  ${r.renderer_key}: affinity=${r.affinity}`);
    }
    if (stRenderers.length >= 2) {
      console.log('PASS: stance→renderer mapping works');
    }

    // =========================================================================
    // TEST 2: Navigate to analyzer-mgmt views list
    // =========================================================================
    console.log('\n=== TEST 2: Analyzer-mgmt views list page ===');
    await page.goto('http://localhost:3001/views', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);

    await page.screenshot({ path: screenshotPath('mgmt-views-list'), fullPage: true });
    console.log('Screenshot taken: mgmt-views-list');

    // Find a view with section_renderers (genealogy_tp_conceptual_framework should have them)
    const viewLink = await page.$('a[href="/views/genealogy_tp_conceptual_framework"]');
    if (viewLink) {
      console.log('Found genealogy_tp_conceptual_framework view card');
    } else {
      console.log('genealogy_tp_conceptual_framework not found, trying any genealogy view...');
    }

    // Click any genealogy_tp view
    const anyTpLink = await page.$('a[href*="/views/genealogy_tp"]');
    if (!anyTpLink) {
      // Try a broader selector
      const allLinks = await page.$$eval('a[href^="/views/"]', els => els.map(e => e.getAttribute('href')));
      console.log(`Available view links: ${JSON.stringify(allLinks.slice(0, 10))}`);
    }

    // =========================================================================
    // TEST 3: Navigate to a view with section_renderers and check Renderer tab
    // =========================================================================
    console.log('\n=== TEST 3: View detail - Renderer tab ===');

    // Navigate directly to a view that has section_renderers
    await page.goto('http://localhost:3001/views/genealogy_tp_conceptual_framework', {
      waitUntil: 'networkidle',
      timeout: 15000
    });
    await page.waitForTimeout(2000);

    await page.screenshot({ path: screenshotPath('view-detail-identity'), fullPage: true });
    console.log('Screenshot taken: view-detail-identity');

    // Check page loaded
    const heading = await page.textContent('h1').catch(() => 'NOT FOUND');
    console.log(`View detail heading: "${heading}"`);

    // Click the Renderer tab
    const rendererTab = await page.$('button:has-text("Renderer")');
    if (rendererTab) {
      await rendererTab.click();
      await page.waitForTimeout(1500); // Wait for API fetch

      await page.screenshot({ path: screenshotPath('renderer-tab'), fullPage: true });
      console.log('Screenshot taken: renderer-tab');

      // Check that renderer dropdown has dynamic options from API
      const rendererSelect = await page.$('select');
      if (rendererSelect) {
        const options = await rendererSelect.$$eval('option', opts =>
          opts.map(o => ({ value: o.value, text: o.textContent.trim() }))
        );
        console.log(`Renderer dropdown options: ${options.length}`);
        for (const opt of options) {
          console.log(`  ${opt.value}: "${opt.text}"`);
        }

        // Check if we see "accordion" with category info (from API)
        const hasAccordion = options.some(o => o.value === 'accordion');
        const hasCardGrid = options.some(o => o.value === 'card_grid');
        const hasProse = options.some(o => o.value === 'prose');
        const hasTable = options.some(o => o.value === 'table');

        console.log(`\n  Has accordion: ${hasAccordion ? 'PASS' : 'FAIL'}`);
        console.log(`  Has card_grid: ${hasCardGrid ? 'PASS' : 'FAIL'}`);
        console.log(`  Has prose: ${hasProse ? 'PASS' : 'FAIL'}`);
        console.log(`  Has table: ${hasTable ? 'PASS' : 'FAIL'}`);

        if (options.length >= 8) {
          console.log('PASS: Dynamic renderer catalog loaded (8+ options)');
        } else {
          console.log(`WARN: Expected 8+ renderer options from API, got ${options.length}`);
        }
      } else {
        console.log('FAIL: No select element found on Renderer tab');
      }

      // Check if renderer metadata panel is shown (stance affinities, data shapes)
      const pageText = await page.textContent('body');
      const hasAffinities = pageText.includes('Stance Affinities') || pageText.includes('affinity') || pageText.includes('interactive');
      const hasDataShapes = pageText.includes('Data Shapes') || pageText.includes('ideal_data_shapes') || pageText.includes('nested_sections');
      console.log(`\n  Stance affinities shown: ${hasAffinities ? 'PASS' : 'CHECK'}`);
      console.log(`  Data shapes shown: ${hasDataShapes ? 'PASS' : 'CHECK'}`);

    } else {
      console.log('FAIL: Renderer tab button not found');
    }

    // =========================================================================
    // TEST 4: Check other genealogy_tp views have section_renderers in config
    // =========================================================================
    console.log('\n=== TEST 4: View definitions with section_renderers ===');

    const viewKeys = [
      'genealogy_tp_conceptual_framework',
      'genealogy_tp_semantic_constellation',
      'genealogy_tp_inferential_commitments',
      'genealogy_tp_concept_evolution'
    ];

    for (const key of viewKeys) {
      const res = await page.goto(`http://localhost:8001/v1/views/${key}`, { timeout: 10000 });
      const viewDef = await res.json();
      const hasSectionRenderers = viewDef.renderer_config?.section_renderers != null;
      const sectionCount = hasSectionRenderers ? Object.keys(viewDef.renderer_config.section_renderers).length : 0;
      console.log(`  ${key}: section_renderers=${hasSectionRenderers ? `PASS (${sectionCount} sections)` : 'FAIL'}`);
    }

    // =========================================================================
    // TEST 5: Try different views and check renderer tab behavior
    // =========================================================================
    console.log('\n=== TEST 5: Renderer tab on semantic_constellation ===');

    await page.goto('http://localhost:3001/views/genealogy_tp_semantic_constellation', {
      waitUntil: 'networkidle',
      timeout: 15000
    });
    await page.waitForTimeout(2000);

    const rendTab2 = await page.$('button:has-text("Renderer")');
    if (rendTab2) {
      await rendTab2.click();
      await page.waitForTimeout(1500);

      await page.screenshot({ path: screenshotPath('renderer-tab-semantic'), fullPage: true });
      console.log('Screenshot taken: renderer-tab-semantic');

      // Check that the current renderer type is pre-selected
      const selectedRenderer = await page.$eval('select', el => el.value).catch(() => 'N/A');
      console.log(`  Current renderer_type: "${selectedRenderer}"`);
    }

    // =========================================================================
    // TEST 6: Preview tab should show section_renderers in JSON
    // =========================================================================
    console.log('\n=== TEST 6: Preview tab shows section_renderers ===');

    const previewTab = await page.$('button:has-text("Preview")');
    if (previewTab) {
      await previewTab.click();
      await page.waitForTimeout(500);

      await page.screenshot({ path: screenshotPath('preview-with-section-renderers'), fullPage: true });

      const preElement = await page.$('pre');
      if (preElement) {
        const preText = await preElement.textContent();
        const hasSectionRenderers = preText.includes('section_renderers');
        console.log(`  JSON preview has section_renderers: ${hasSectionRenderers ? 'PASS' : 'FAIL'}`);
        if (hasSectionRenderers) {
          // Check for specific sub-renderer types
          const hasChipGrid = preText.includes('chip_grid');
          const hasMiniCardList = preText.includes('mini_card_list');
          const hasKeyValueTable = preText.includes('key_value_table');
          console.log(`  Contains chip_grid: ${hasChipGrid ? 'PASS' : 'FAIL'}`);
          console.log(`  Contains mini_card_list: ${hasMiniCardList ? 'PASS' : 'FAIL'}`);
          console.log(`  Contains key_value_table: ${hasKeyValueTable ? 'PASS' : 'FAIL'}`);
        }
      }
    }

    // =========================================================================
    // Final summary
    // =========================================================================
    console.log('\n=== CONSOLE ERRORS ===');
    if (consoleErrors.length === 0) {
      console.log('No console errors detected');
    } else {
      for (const err of consoleErrors) {
        console.log(`  ERROR: ${err}`);
      }
    }

    console.log(`\nTotal screenshots taken: ${screenshotCount}`);
    console.log(`Screenshots saved to: ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    await page.screenshot({ path: screenshotPath('error-state'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
