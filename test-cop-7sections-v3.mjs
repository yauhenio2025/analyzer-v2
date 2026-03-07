import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

  try {
    // Navigate
    console.log('=== Step 1: Navigate ===');
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Select Comprehensive 2/16/2026
    console.log('=== Step 2: Select Comprehensive ===');
    const compCard = page.locator('button.gen-result-card').filter({ hasText: '15 ideas' }).filter({ hasText: '4 prior works' });
    if (await compCard.count() > 0) {
      await compCard.first().click();
      await page.waitForTimeout(3000);
      console.log('Selected comprehensive analysis');
    }

    // Click CoP tab
    console.log('=== Step 3: Click CoP tab ===');
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    if (await copTab.count() > 0) {
      await copTab.click();
      await page.waitForTimeout(2000);
      console.log('Clicked CoP tab');
    }

    // Now: check the view definition fetched from analyzer-v2
    console.log('\n=== Step 4: Check view definition from analyzer-v2 ===');

    // Fetch the view definition directly from the API
    const viewDefResponse = await page.evaluate(async () => {
      try {
        const resp = await fetch('https://analyzer-v2.onrender.com/v1/views/genealogy_conditions');
        const data = await resp.json();
        return { status: resp.status, data };
      } catch (e) {
        return { error: String(e) };
      }
    });
    console.log('View definition from API:');
    console.log(JSON.stringify(viewDefResponse.data?.renderer_config?.sections, null, 2));
    console.log('Section renderers:', JSON.stringify(Object.keys(viewDefResponse.data?.renderer_config?.section_renderers || {})));

    // Check the composed views endpoint
    console.log('\n=== Step 5: Check composed views ===');
    const composedResp = await page.evaluate(async () => {
      try {
        const resp = await fetch('https://analyzer-v2.onrender.com/v1/views/compose/the-critic/genealogy');
        const data = await resp.json();
        return data;
      } catch (e) {
        return { error: String(e) };
      }
    });
    const conditionsView = composedResp?.find?.((v) => v.view_key === 'genealogy_conditions');
    if (conditionsView) {
      console.log('Conditions view from compose endpoint:');
      console.log('Sections:', JSON.stringify(conditionsView.renderer_config?.sections, null, 2));
      console.log('Section renderers:', JSON.stringify(Object.keys(conditionsView.renderer_config?.section_renderers || {})));
    } else {
      console.log('Conditions view NOT found in composed views');
      console.log('Available views:', composedResp?.map?.((v) => v.view_key));
    }

    // Check the actual rendered accordion sections
    console.log('\n=== Step 6: Check rendered accordion sections ===');
    const accordionSections = await page.evaluate(() => {
      const sections = [];
      // Look for accordion section elements
      const allElements = document.querySelectorAll('[class*="accordion"], [class*="section"], [class*="conditions"]');
      for (const el of allElements) {
        if (el.className.includes('section') || el.className.includes('accordion')) {
          const header = el.querySelector('h3, h4, button, summary, [class*="header"]');
          if (header) {
            sections.push({
              text: header.textContent?.trim()?.substring(0, 100),
              classes: el.className,
              expanded: el.getAttribute('aria-expanded') || header.getAttribute('aria-expanded'),
              childCount: el.children.length
            });
          }
        }
      }
      return sections;
    });
    console.log('Accordion sections found:');
    for (const s of accordionSections) {
      console.log(`  "${s.text}" (class: ${s.classes}, expanded: ${s.expanded}, children: ${s.childCount})`);
    }

    // Check what data keys exist in the conditions result
    console.log('\n=== Step 7: Check conditions data ===');
    const conditionsData = await page.evaluate(() => {
      // The data might be in a React state. Let's try to find it in the DOM
      // or from window.__data or similar
      const bodyText = document.body.textContent;
      return {
        hasEnabling: bodyText.includes('Enabling Conditions'),
        hasConstraining: bodyText.includes('Constraining Conditions'),
        hasPathDep: bodyText.includes('Path Dependencies'),
        hasUnackDebts: bodyText.includes('Unacknowledged Debts'),
        hasAltPaths: bodyText.includes('Alternative Paths'),
        hasCounterfactual: bodyText.includes('Counterfactual Analysis'),
        hasSynthetic: bodyText.includes('Synthetic Judgment'),
      };
    });
    console.log('Section visibility in DOM:', JSON.stringify(conditionsData, null, 2));

    // Take screenshot of the CoP tab content
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop3-01-cop-content.png`, fullPage: true });

    // Now let's look at the AccordionRenderer to understand how it processes sections
    console.log('\n=== Step 8: Check if view_key tab matches ===');

    // Check what tab is actually active and what view is being rendered
    const activeTabInfo = await page.evaluate(() => {
      const activeBtn = document.querySelector('.gen-tabs button.active');
      return {
        activeButtonText: activeBtn?.textContent?.trim(),
        activeButtonClasses: activeBtn?.className,
        // Check for data attributes
        allTabButtons: Array.from(document.querySelectorAll('.gen-tabs button')).map(b => ({
          text: b.textContent?.trim()?.substring(0, 50),
          active: b.classList.contains('active'),
          onclick: b.getAttribute('onclick'),
        }))
      };
    });
    console.log('Active tab:', JSON.stringify(activeTabInfo.activeButtonText));
    console.log('All tabs:', JSON.stringify(activeTabInfo.allTabButtons?.map(t => `${t.text}${t.active ? ' [ACTIVE]' : ''}`)));

    // Check if the view has section_renderers being applied
    console.log('\n=== Step 9: Look at the actual section DOM ===');
    const sectionDOM = await page.evaluate(() => {
      // Find all gen-conditions-section elements
      const sections = document.querySelectorAll('.gen-conditions-section, [class*="conditions-section"], [class*="accordion-section"]');
      return Array.from(sections).map(s => ({
        classes: s.className,
        text: s.textContent?.substring(0, 200),
        childCount: s.children.length,
        html: s.outerHTML?.substring(0, 300)
      }));
    });
    console.log(`Found ${sectionDOM.length} section DOM elements:`);
    for (const s of sectionDOM) {
      console.log(`  classes="${s.classes}" children=${s.childCount}`);
      console.log(`  text: ${s.text?.substring(0, 120)}`);
    }

    // Console errors
    const errors = consoleMsgs.filter(m => m.startsWith('[error]') || m.startsWith('[warning]'));
    if (errors.length > 0) {
      console.log('\n=== Console Errors/Warnings ===');
      for (const e of errors.slice(0, 20)) {
        console.log(e);
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop3-error.png`, fullPage: true });
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
