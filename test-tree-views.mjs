import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/tree-views';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

let screenshotCount = 0;
function screenshotPath(name) {
  screenshotCount++;
  return `${SCREENSHOT_DIR}/${String(screenshotCount).padStart(2, '0')}-${name}.png`;
}

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  const results = [];
  function check(name, pass, detail = '') {
    const status = pass ? 'PASS' : 'FAIL';
    results.push({ name, status, detail });
    console.log(`  [${status}] ${name}${detail ? ': ' + detail : ''}`);
  }

  try {
    // =========================================================================
    // STEP 1: Navigate to /views and take full-page screenshot
    // =========================================================================
    console.log('\n=== STEP 1: Navigate to /views list page ===');
    await page.goto('http://localhost:3000/views', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);

    await page.screenshot({ path: screenshotPath('views-list-full'), fullPage: true });
    console.log('Screenshot: views-list-full');

    // Also take a viewport-only screenshot for above-the-fold view
    await page.screenshot({ path: screenshotPath('views-list-viewport'), fullPage: false });
    console.log('Screenshot: views-list-viewport');

    // =========================================================================
    // STEP 2: Verify "Target Work Profile" has a "4 children" badge (indigo)
    // =========================================================================
    console.log('\n=== STEP 2: Verify "Target Work Profile" parent card ===');

    // Find the text "Target Work Profile" on the page
    const twpCard = await page.locator('text=Target Work Profile').first();
    const twpExists = await twpCard.count() > 0;
    check('Target Work Profile text exists', twpExists);

    if (twpExists) {
      // Look for "4 children" badge near it
      const parentContainer = await twpCard.locator('..').locator('..').locator('..').first();
      const containerHTML = await parentContainer.innerHTML();

      const has4Children = containerHTML.includes('4 children');
      check('Has "4 children" badge', has4Children);

      // Check for indigo coloring on the badge
      const hasIndigo = containerHTML.includes('indigo') || containerHTML.includes('bg-indigo');
      check('Badge has indigo styling', hasIndigo, hasIndigo ? 'indigo classes found' : 'No indigo classes detected');

      // Try to find the exact badge element
      const childBadge = await page.locator('text=4 children').first();
      if (await childBadge.count() > 0) {
        const badgeClasses = await childBadge.evaluate(el => {
          // Walk up to find the element with indigo classes
          let node = el;
          for (let i = 0; i < 5; i++) {
            if (node.className && node.className.includes('indigo')) {
              return node.className;
            }
            node = node.parentElement;
            if (!node) break;
          }
          return el.className;
        });
        console.log(`    Badge classes: ${badgeClasses}`);
      }
    }

    // =========================================================================
    // STEP 3: Verify children appear INDENTED with left border connector
    // =========================================================================
    console.log('\n=== STEP 3: Verify child views indented with border connector ===');

    const expectedChildren = [
      'Conceptual Framework',
      'Semantic Constellation',
      'Inferential Commitments',
      'Concept Evolution'
    ];

    for (const childName of expectedChildren) {
      const childEl = await page.locator(`text=${childName}`).first();
      const childExists = await childEl.count() > 0;
      check(`Child "${childName}" visible`, childExists);
    }

    // Check for indigo-200 left border on the children container
    const indigoBorderElements = await page.locator('[class*="border-indigo"]').count();
    check('Indigo border elements present', indigoBorderElements > 0, `Found ${indigoBorderElements} elements`);

    // Check for left border specifically (border-l)
    const leftBorderElements = await page.locator('[class*="border-l"]').count();
    check('Left border elements present', leftBorderElements > 0, `Found ${leftBorderElements} elements`);

    // Check indentation - children should be in a container with left margin/padding
    const childrenContainer = await page.locator('[class*="border-l"][class*="indigo"]').first();
    if (await childrenContainer.count() > 0) {
      const containerClasses = await childrenContainer.getAttribute('class');
      check('Children container has indigo left border', true, containerClasses);

      // Check it has margin-left for indentation
      const hasML = containerClasses.includes('ml-') || containerClasses.includes('pl-');
      check('Children container has left indentation', hasML, containerClasses);
    } else {
      check('Children container with indigo border-l', false, 'Not found - trying alternative selectors');

      // Try broader search
      const allBorderL = await page.$$('[class*="border-l"]');
      for (const el of allBorderL) {
        const cls = await el.getAttribute('class');
        if (cls && cls.includes('indigo')) {
          console.log(`    Found border-l with indigo: ${cls}`);
        }
      }
    }

    // Take a focused screenshot of the Target Work Profile area
    const twpSection = await page.locator('text=Target Work Profile').first();
    if (await twpSection.count() > 0) {
      // Scroll to it and screenshot
      await twpSection.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
      await page.screenshot({ path: screenshotPath('target-work-profile-area'), fullPage: false });
      console.log('Screenshot: target-work-profile-area');
    }

    // =========================================================================
    // STEP 4: Verify standalone views in normal 2-column grid
    // =========================================================================
    console.log('\n=== STEP 4: Verify standalone views in 2-column grid ===');

    const standaloneNames = ['Tactics & Strategies', 'Genealogical Portrait'];
    for (const name of standaloneNames) {
      const el = await page.locator(`text=${name}`).first();
      const exists = await el.count() > 0;
      check(`Standalone "${name}" visible`, exists);
    }

    // Check for grid layout (grid-cols-2 or grid-cols-1 md:grid-cols-2)
    const gridElements = await page.locator('[class*="grid-cols"]').count();
    check('Grid layout elements present', gridElements > 0, `Found ${gridElements} grid elements`);

    // =========================================================================
    // STEP 5: Verify "All views" dropdown filter
    // =========================================================================
    console.log('\n=== STEP 5: Verify "All views" dropdown filter ===');

    // Look for select elements
    const allSelects = await page.$$('select');
    console.log(`    Total select elements: ${allSelects.length}`);

    let viewFilterSelect = null;
    for (const sel of allSelects) {
      const options = await sel.$$eval('option', opts => opts.map(o => o.textContent.trim()));
      console.log(`    Select options: ${JSON.stringify(options)}`);
      if (options.some(o => o.includes('All views') || o.includes('all views'))) {
        viewFilterSelect = sel;
        check('"All views" filter dropdown exists', true, `Options: ${JSON.stringify(options)}`);

        // Verify expected options
        const hasTopLevel = options.some(o => o.includes('Top-level'));
        const hasParents = options.some(o => o.includes('Parents'));
        const hasChildren = options.some(o => o.includes('Children'));
        check('Has "Top-level only" option', hasTopLevel);
        check('Has "Parents only" option', hasParents);
        check('Has "Children only" option', hasChildren);
        break;
      }
    }

    if (!viewFilterSelect) {
      check('"All views" filter dropdown exists', false, 'No select with "All views" option found');
    }

    // =========================================================================
    // STEP 6: Test "Top-level only" filter
    // =========================================================================
    console.log('\n=== STEP 6: Test "Top-level only" filter ===');

    if (viewFilterSelect) {
      // Get all option values
      const optionValues = await viewFilterSelect.$$eval('option', opts =>
        opts.map(o => ({ text: o.textContent.trim(), value: o.value }))
      );
      console.log(`    Option values: ${JSON.stringify(optionValues)}`);

      // Find the "Top-level only" option value
      const topLevelOpt = optionValues.find(o => o.text.includes('Top-level'));
      if (topLevelOpt) {
        await viewFilterSelect.selectOption(topLevelOpt.value);
        await page.waitForTimeout(1000);

        await page.screenshot({ path: screenshotPath('filter-top-level-only'), fullPage: true });
        console.log('Screenshot: filter-top-level-only');

        // Children should NOT be visible
        for (const childName of expectedChildren) {
          const childVisible = await page.locator(`text=${childName}`).count() > 0;
          check(`Child "${childName}" hidden with top-level filter`, !childVisible,
            childVisible ? 'STILL VISIBLE' : 'Correctly hidden');
        }

        // Parent "Target Work Profile" should still be visible
        const twpStillVisible = await page.locator('text=Target Work Profile').count() > 0;
        check('Parent "Target Work Profile" still visible', twpStillVisible);

      } else {
        check('Top-level only option found', false);
      }
    }

    // =========================================================================
    // STEP 7: Test "Children only" filter
    // =========================================================================
    console.log('\n=== STEP 7: Test "Children only" filter ===');

    if (viewFilterSelect) {
      const optionValues = await viewFilterSelect.$$eval('option', opts =>
        opts.map(o => ({ text: o.textContent.trim(), value: o.value }))
      );

      const childrenOpt = optionValues.find(o => o.text.includes('Children'));
      if (childrenOpt) {
        await viewFilterSelect.selectOption(childrenOpt.value);
        await page.waitForTimeout(1000);

        await page.screenshot({ path: screenshotPath('filter-children-only'), fullPage: true });
        console.log('Screenshot: filter-children-only');

        // Children SHOULD be visible
        for (const childName of expectedChildren) {
          const childVisible = await page.locator(`text=${childName}`).count() > 0;
          check(`Child "${childName}" visible with children filter`, childVisible);
        }

        // Standalone views should NOT be visible
        for (const name of standaloneNames) {
          const visible = await page.locator(`text=${name}`).count() > 0;
          check(`Standalone "${name}" hidden with children filter`, !visible,
            visible ? 'STILL VISIBLE' : 'Correctly hidden');
        }

      } else {
        check('Children only option found', false);
      }
    }

    // =========================================================================
    // STEP 8: Reset filter to "All views" and take final screenshot
    // =========================================================================
    console.log('\n=== STEP 8: Reset to All views ===');

    if (viewFilterSelect) {
      const optionValues = await viewFilterSelect.$$eval('option', opts =>
        opts.map(o => ({ text: o.textContent.trim(), value: o.value }))
      );
      const allOpt = optionValues.find(o => o.text.includes('All views'));
      if (allOpt) {
        await viewFilterSelect.selectOption(allOpt.value);
        await page.waitForTimeout(1000);
        await page.screenshot({ path: screenshotPath('filter-all-views-reset'), fullPage: true });
        console.log('Screenshot: filter-all-views-reset');
      }
    }

    // =========================================================================
    // STEP 9: Check "Parents only" filter too
    // =========================================================================
    console.log('\n=== STEP 9: Test "Parents only" filter ===');

    if (viewFilterSelect) {
      const optionValues = await viewFilterSelect.$$eval('option', opts =>
        opts.map(o => ({ text: o.textContent.trim(), value: o.value }))
      );
      const parentsOpt = optionValues.find(o => o.text.includes('Parents'));
      if (parentsOpt) {
        await viewFilterSelect.selectOption(parentsOpt.value);
        await page.waitForTimeout(1000);

        await page.screenshot({ path: screenshotPath('filter-parents-only'), fullPage: true });
        console.log('Screenshot: filter-parents-only');

        // Only parent(s) with children should show
        const twpVisible = await page.locator('text=Target Work Profile').count() > 0;
        check('Parent "Target Work Profile" visible with parents filter', twpVisible);

        // Standalone views should NOT be visible (they're not parents)
        for (const name of standaloneNames) {
          const visible = await page.locator(`text=${name}`).count() > 0;
          check(`Standalone "${name}" hidden with parents filter`, !visible,
            visible ? 'STILL VISIBLE' : 'Correctly hidden');
        }
      }
    }

    // =========================================================================
    // FINAL SUMMARY
    // =========================================================================
    console.log('\n========================================');
    console.log('         FINAL TEST SUMMARY');
    console.log('========================================');

    const passed = results.filter(r => r.status === 'PASS').length;
    const failed = results.filter(r => r.status === 'FAIL').length;
    console.log(`\nTotal: ${results.length} checks, ${passed} PASSED, ${failed} FAILED`);

    if (failed > 0) {
      console.log('\nFailed checks:');
      for (const r of results.filter(r => r.status === 'FAIL')) {
        console.log(`  - ${r.name}${r.detail ? ': ' + r.detail : ''}`);
      }
    }

    console.log('\n=== Console Errors ===');
    if (consoleErrors.length === 0) {
      console.log('No console errors detected');
    } else {
      for (const err of consoleErrors) {
        console.log(`  ERROR: ${err}`);
      }
    }

    console.log(`\nTotal screenshots: ${screenshotCount}`);
    console.log(`Screenshots saved to: ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: screenshotPath('error-state'), fullPage: true });
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
