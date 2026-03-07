import { chromium } from 'playwright';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  try {
    // Go to a blank page and just make fetch calls
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Fetch results list
    const results = await page.evaluate(async () => {
      const resp = await fetch('https://the-critic.onrender.com/api/genealogy/results/morozov-on-varoufakis');
      return resp.json();
    });
    console.log('Results:', JSON.stringify(results.results?.map(r => ({
      id: r.id,
      mode: r.mode,
      ideas: r.ideas_analyzed,
      priors: r.prior_works_scanned,
      tactics: r.tactics_detected
    })), null, 2));

    // Fetch the comprehensive result (gen-08a2816482af)
    const compResult = await page.evaluate(async () => {
      const resp = await fetch('https://the-critic.onrender.com/api/genealogy/results/morozov-on-varoufakis/gen-08a2816482af');
      const data = await resp.json();

      // Check if it has pass_results with conditions data
      const passResults = data.pass_results || {};

      // Check pass3_conditions or similar
      const conditionsKey = Object.keys(passResults).find(k => k.includes('condition'));
      let conditionsData = conditionsKey ? passResults[conditionsKey] : null;

      // Also check pass_results.pass3_conditions
      if (!conditionsData) conditionsData = passResults.pass3_conditions;

      return {
        id: data.id,
        mode: data.mode,
        passResultKeys: Object.keys(passResults),
        hasConditions: !!conditionsData,
        conditionsKeys: conditionsData ? Object.keys(conditionsData) : [],
        conditionsPreview: conditionsData ? JSON.stringify(conditionsData).substring(0, 500) : null,
      };
    });
    console.log('\nComprehensive result:', JSON.stringify(compResult, null, 2));

    // Also check the v2 result
    const v2Result = await page.evaluate(async () => {
      const resp = await fetch('https://the-critic.onrender.com/api/genealogy/results/morozov-on-varoufakis/gen-v2-c65443c42c37');
      const data = await resp.json();

      const passResults = data.pass_results || {};
      const presentViews = passResults._presentation?.views || [];

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

      const condView = findView(presentViews, 'genealogy_conditions');

      return {
        id: data.id,
        mode: data.mode,
        passResultKeys: Object.keys(passResults),
        hasPresentViews: presentViews.length,
        conditionsView: condView ? {
          viewKey: condView.view_key,
          hasStructuredData: !!condView.structured_data,
          structuredDataKeys: condView.structured_data ? Object.keys(condView.structured_data) : [],
          hasPathDep: condView.structured_data ? 'path_dependencies' in condView.structured_data : false,
          hasUnackDebts: condView.structured_data ? 'unacknowledged_debts' in condView.structured_data : false,
          hasAltPaths: condView.structured_data ? 'alternative_paths' in condView.structured_data : false,
          pathDepCount: condView.structured_data?.path_dependencies
            ? (Array.isArray(condView.structured_data.path_dependencies) ? condView.structured_data.path_dependencies.length : 'not-array')
            : null,
          unackDebtsCount: condView.structured_data?.unacknowledged_debts
            ? (Array.isArray(condView.structured_data.unacknowledged_debts) ? condView.structured_data.unacknowledged_debts.length : 'not-array')
            : null,
          altPathsCount: condView.structured_data?.alternative_paths
            ? (Array.isArray(condView.structured_data.alternative_paths) ? condView.structured_data.alternative_paths.length : 'not-array')
            : null,
          hasProse: !!condView.prose,
          proseLength: condView.prose?.length,
          rendererConfig: condView.renderer_config,
        } : 'NOT FOUND',
        viewKeys: presentViews.map(v => v.view_key),
      };
    });
    console.log('\nV2 Presentation result:', JSON.stringify(v2Result, null, 2));

    // If conditions are in the comprehensive result, check its data shape
    if (compResult.conditionsKeys.length > 0) {
      const condDetails = await page.evaluate(async () => {
        const resp = await fetch('https://the-critic.onrender.com/api/genealogy/results/morozov-on-varoufakis/gen-08a2816482af');
        const data = await resp.json();
        const cond = data.pass_results?.pass3_conditions;
        if (!cond) return null;

        return {
          keys: Object.keys(cond),
          enabling_count: Array.isArray(cond.enabling_conditions) ? cond.enabling_conditions.length : 'n/a',
          constraining_count: Array.isArray(cond.constraining_conditions) ? cond.constraining_conditions.length : 'n/a',
          path_dependencies: cond.path_dependencies !== undefined ? (Array.isArray(cond.path_dependencies) ? cond.path_dependencies.length : typeof cond.path_dependencies) : 'MISSING',
          unacknowledged_debts: cond.unacknowledged_debts !== undefined ? (Array.isArray(cond.unacknowledged_debts) ? cond.unacknowledged_debts.length : typeof cond.unacknowledged_debts) : 'MISSING',
          alternative_paths: cond.alternative_paths !== undefined ? (Array.isArray(cond.alternative_paths) ? cond.alternative_paths.length : typeof cond.alternative_paths) : 'MISSING',
          counterfactual: typeof cond.counterfactual_analysis,
          synthetic: typeof cond.synthetic_judgment,
        };
      });
      console.log('\nComprehensive conditions details:', JSON.stringify(condDetails, null, 2));
    }

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
