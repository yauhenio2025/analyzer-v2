import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  // Intercept API responses to see what data the conditions view gets
  const apiResponses = [];
  page.on('response', async (response) => {
    const url = response.url();
    if (url.includes('presentation') || url.includes('genealogy') || url.includes('conditions') || url.includes('views/compose')) {
      try {
        const body = await response.text();
        apiResponses.push({
          url,
          status: response.status(),
          bodyLength: body.length,
          bodyPreview: body.substring(0, 500)
        });
      } catch (e) {
        apiResponses.push({ url, status: response.status(), error: String(e) });
      }
    }
  });

  try {
    // Navigate
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Select Comprehensive 2/16/2026
    const compCard = page.locator('button.gen-result-card').filter({ hasText: '15 ideas' }).filter({ hasText: '4 prior works' });
    if (await compCard.count() > 0) {
      await compCard.first().click();
      await page.waitForTimeout(3000);
    }

    // Click CoP tab
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    if (await copTab.count() > 0) {
      await copTab.click();
      await page.waitForTimeout(2000);
    }

    // Print all API responses captured
    console.log(`=== Captured ${apiResponses.length} API responses ===`);
    for (const resp of apiResponses) {
      console.log(`\n${resp.url} [${resp.status}] (${resp.bodyLength} bytes)`);
      if (resp.url.includes('compose')) {
        console.log('  Preview: ...views/compose response...');
      } else {
        console.log(`  Preview: ${resp.bodyPreview?.substring(0, 200)}`);
      }
    }

    // Now check: what keys does the conditions structured_data have?
    // We need to find the presentation response and extract the conditions view data
    console.log('\n=== Check conditions data keys ===');

    const conditionsKeys = await page.evaluate(async () => {
      // The presentation data is loaded from the-critic API
      // Try to fetch the stored genealogy data directly
      const apiBase = window.location.origin;

      // Check for stored presentations
      const listResp = await fetch(`${apiBase}/api/genealogy/stored-results`);
      if (!listResp.ok) {
        return { error: `stored-results: ${listResp.status}` };
      }
      const results = await listResp.json();

      // Find the Comprehensive 2/16/2026 result
      const comp = results.find(r =>
        r.mode === 'comprehensive' && r.ideas_count === 15 && r.prior_works_count === 4
      );

      if (!comp) {
        return { error: 'Comprehensive result not found', available: results.map(r => `${r.mode} ${r.ideas_count} ideas ${r.prior_works_count} prior`) };
      }

      // Get the full presentation
      const presentResp = await fetch(`${apiBase}/api/genealogy/presentations/${comp.id}`);
      if (!presentResp.ok) {
        return { error: `presentation: ${presentResp.status}` };
      }

      const presentation = await presentResp.json();

      // Find the conditions view
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
      if (!condView) {
        return {
          error: 'conditions view not found in presentation',
          viewKeys: (presentation.views || []).map(v => v.view_key)
        };
      }

      // Check the structured_data keys
      const sd = condView.structured_data;
      return {
        viewKey: condView.view_key,
        rendererType: condView.renderer_type,
        hasStructuredData: !!sd,
        structuredDataKeys: sd ? Object.keys(sd) : [],
        hasPathDep: sd ? 'path_dependencies' in sd : false,
        hasUnackDebts: sd ? 'unacknowledged_debts' in sd : false,
        hasAltPaths: sd ? 'alternative_paths' in sd : false,
        pathDepData: sd?.path_dependencies ? (Array.isArray(sd.path_dependencies) ? sd.path_dependencies.length : typeof sd.path_dependencies) : null,
        unackDebtsData: sd?.unacknowledged_debts ? (Array.isArray(sd.unacknowledged_debts) ? sd.unacknowledged_debts.length : typeof sd.unacknowledged_debts) : null,
        altPathsData: sd?.alternative_paths ? (Array.isArray(sd.alternative_paths) ? sd.alternative_paths.length : typeof sd.alternative_paths) : null,
        // Also check the prose (unstructured) data
        hasProse: !!condView.prose,
        proseLength: condView.prose?.length,
        prosePreview: condView.prose?.substring(0, 300),
        rendererConfig: condView.renderer_config,
      };
    });

    console.log('Conditions view data:', JSON.stringify(conditionsKeys, null, 2));

    // Check the prose for mentions of the new sections
    if (conditionsKeys.prosePreview) {
      const prose = conditionsKeys.prosePreview;
      console.log('\n=== Prose mentions ===');
      console.log('Contains "path depend":', prose.toLowerCase().includes('path depend'));
      console.log('Contains "unacknowledged":', prose.toLowerCase().includes('unacknowledged'));
      console.log('Contains "alternative":', prose.toLowerCase().includes('alternative'));
    }

    // Also check: does the prose extraction (schema-on-read) extract these fields?
    console.log('\n=== Check prose extraction ===');
    const proseCheck = await page.evaluate(async () => {
      const apiBase = window.location.origin;
      const listResp = await fetch(`${apiBase}/api/genealogy/stored-results`);
      const results = await listResp.json();
      const comp = results.find(r =>
        r.mode === 'comprehensive' && r.ideas_count === 15 && r.prior_works_count === 4
      );
      if (!comp) return { error: 'No comp result' };

      // Check if there's a prose endpoint for conditions
      const proseResp = await fetch(`${apiBase}/api/genealogy/presentations/${comp.id}/prose/conditions`);
      if (proseResp.ok) {
        const proseData = await proseResp.json();
        return {
          hasProse: true,
          keys: proseData ? Object.keys(proseData) : [],
          hasPathDep: proseData ? 'path_dependencies' in proseData : false,
        };
      } else {
        return { proseEndpoint: proseResp.status };
      }
    });
    console.log('Prose extraction:', JSON.stringify(proseCheck, null, 2));

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
