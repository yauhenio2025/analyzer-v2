import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

  try {
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Step 1: Before clicking, take a screenshot of what we see
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop6-01-initial.png`, fullPage: false });

    // Step 2: Check which result is currently loaded (the latest v2_presentation is likely auto-loaded)
    console.log('=== Step 1: Check initial state ===');
    const initState = await page.evaluate(() => {
      const resultHeader = document.querySelector('.gen-results-header');
      const activeCard = document.querySelector('.gen-result-card.viewing');
      return {
        resultHeader: resultHeader?.textContent?.substring(0, 200),
        activeCard: activeCard?.textContent?.substring(0, 100),
        activeCardClasses: activeCard?.className,
      };
    });
    console.log('Initial state:', JSON.stringify(initState, null, 2));

    // Step 3: Find the comprehensive card more precisely
    console.log('\n=== Step 2: Find comprehensive card ===');

    // Get all result cards with their exact content
    const allCards = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('.gen-result-card')).map((card, idx) => ({
        idx,
        text: card.textContent?.trim(),
        classes: card.className,
        isViewing: card.classList.contains('viewing'),
      }));
    });
    console.log('All result cards:');
    for (const c of allCards) {
      console.log(`  [${c.idx}] ${c.isViewing ? '[VIEWING] ' : ''}${c.text?.substring(0, 80)} (${c.classes})`);
    }

    // Step 4: Click the comprehensive card with 15 ideas, 4 prior works, 11 tactics
    // It should be the 9th card (index 8)
    const compIdx = allCards.findIndex(c => c.text?.includes('15 ideas') && c.text?.includes('4 prior works'));
    console.log(`\nComprehensive card index: ${compIdx}`);

    if (compIdx >= 0) {
      await page.locator('.gen-result-card').nth(compIdx).click();
      console.log('Clicked comprehensive card');

      // Wait longer for data to load
      await page.waitForTimeout(5000);

      // Check if it's now showing the right data
      const afterClick = await page.evaluate(() => {
        const cards = document.querySelectorAll('.gen-result-card');
        const viewingCard = Array.from(cards).find(c => c.classList.contains('viewing'));
        return {
          viewingCard: viewingCard?.textContent?.substring(0, 100),
          viewingClasses: viewingCard?.className,
        };
      });
      console.log('After click:', JSON.stringify(afterClick, null, 2));
    }

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop6-02-after-select.png`, fullPage: false });

    // Step 5: Click Conditions of Possibility tab
    console.log('\n=== Step 3: Click CoP tab ===');
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    if (await copTab.count() > 0) {
      await copTab.click();
      await page.waitForTimeout(3000);
      console.log('Clicked CoP tab');
    }

    // Step 6: Check what sections are visible
    console.log('\n=== Step 4: Check sections ===');
    const sections = await page.evaluate(() => {
      const secs = document.querySelectorAll('.gen-conditions-section');
      return Array.from(secs).map(s => {
        const h3 = s.querySelector('h3');
        return {
          title: h3?.textContent?.trim(),
          isExpanded: h3?.textContent?.includes('\u25BC'),
        };
      });
    });
    console.log(`Found ${sections.length} sections:`);
    for (const s of sections) {
      console.log(`  ${s.isExpanded ? 'EXPANDED' : 'collapsed'}: ${s.title}`);
    }

    // Check if prose mode badge is present
    const proseMode = await page.evaluate(() => {
      return {
        proseBadge: document.querySelector('.gen-prose-mode-badge')?.textContent,
        extracting: document.querySelector('.gen-extracting-notice')?.textContent,
      };
    });
    console.log('Prose mode:', JSON.stringify(proseMode));

    // Step 7: Take full page screenshot
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop6-03-cop-tab.png`, fullPage: true });

    // Step 8: Check the comprehensive result's conditions data via direct API
    console.log('\n=== Step 5: Check comprehensive result conditions data ===');
    const compData = await page.evaluate(async () => {
      const resp = await fetch('https://the-critic.onrender.com/api/genealogy/results/morozov-on-varoufakis/gen-08a2816482af');
      const data = await resp.json();
      const pass6 = data.pass_results?.pass6_conditions;
      if (!pass6) return { error: 'No pass6_conditions' };

      return {
        outputMode: pass6._output_mode,
        hasProse: !!pass6._prose_output,
        proseLength: pass6._prose_output?.length,
        // Check if prose mentions the new sections
        proseContains: {
          pathDependencies: pass6._prose_output?.includes('Path Dependencies') || pass6._prose_output?.includes('path dependencies') || pass6._prose_output?.includes('path-depend'),
          unacknowledgedDebts: pass6._prose_output?.includes('Unacknowledged Debts') || pass6._prose_output?.includes('unacknowledged debt'),
          alternativePaths: pass6._prose_output?.includes('Alternative Paths') || pass6._prose_output?.includes('alternative path'),
        },
        // Get section headers from the prose
        headers: (pass6._prose_output || '').match(/^#{1,3}\s+.+$/gm)?.slice(0, 20),
      };
    });
    console.log('Comprehensive conditions:', JSON.stringify(compData, null, 2));

    // Step 9: Check if the v2_presentation conditions data has the new fields
    console.log('\n=== Step 6: Check all v2 presentation conditions ===');
    const v2Data = await page.evaluate(async () => {
      const resp = await fetch('https://the-critic.onrender.com/api/genealogy/results/morozov-on-varoufakis/gen-v2-c65443c42c37');
      const data = await resp.json();
      const presentation = data.pass_results?._presentation;
      if (!presentation) return { error: 'No presentation' };

      const findView = (views, key) => {
        for (const v of views) {
          if (v.view_key === key) return v;
          if (v.children?.length) {
            const found = findView(v.children, key);
            if (found) return found;
          }
        }
        return null;
      };

      const condView = findView(presentation.views || [], 'genealogy_conditions');
      if (!condView) return { error: 'No conditions view' };

      return {
        structuredDataKeys: condView.structured_data ? Object.keys(condView.structured_data) : [],
        rendererConfigSections: condView.renderer_config?.sections?.map(s => s.key) || [],
        hasSectionRenderers: !!condView.renderer_config?.section_renderers,
        sectionRendererKeys: condView.renderer_config?.section_renderers ? Object.keys(condView.renderer_config.section_renderers) : [],
        // Check the prose that might contain the data
        hasProse: !!condView.prose,
        proseLength: condView.prose?.length,
      };
    });
    console.log('V2 conditions:', JSON.stringify(v2Data, null, 2));

    // Console errors
    const errors = consoleMsgs.filter(m => m.startsWith('[error]'));
    if (errors.length > 0) {
      console.log('\n=== Console Errors ===');
      for (const e of errors.slice(0, 10)) {
        console.log(e.substring(0, 200));
      }
    }

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
