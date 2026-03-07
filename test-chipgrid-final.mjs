import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/chipgrid-final';
mkdirSync(DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  // Step 1: Verify analyzer-v2 has chip_grid
  console.log('Step 1: Checking analyzer-v2 view definition...');
  const viewResp = await fetch('https://analyzer-v2.onrender.com/v1/views/genealogy_target_profile');
  const viewData = await viewResp.json();
  const fwRenderer = viewData.renderer_config.section_renderers.conceptual_framework.sub_renderers.frameworks;
  console.log(`  frameworks renderer_type: ${fwRenderer.renderer_type}`);
  if (fwRenderer.renderer_type !== 'chip_grid') {
    console.log('  WARN: Not chip_grid on analyzer-v2!');
  }

  // Step 2: Re-import v2 job
  console.log('\nStep 2: Importing v2 job...');
  await fetch('https://the-critic.onrender.com/api/genealogy/import-v2/job-7d32be316d06?project_id=morozov-on-varoufakis', { method: 'POST' });

  // Step 3: Navigate to genealogy page (fresh load clears module cache)
  console.log('Step 3: Navigating with fresh load...');
  await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
    waitUntil: 'networkidle', timeout: 90000
  });
  await page.waitForTimeout(6000);

  // Step 4: Click Target Work Profile tab
  console.log('Step 4: Clicking Target Work Profile...');
  await page.click('text=Target Work Profile');
  await page.waitForTimeout(3000);

  // Step 5: Expand all sections
  console.log('Step 5: Expanding sections...');
  const h3s = await page.$$('h3');
  for (const h of h3s) {
    const t = await h.textContent();
    if (t && t.includes('▶')) { await h.click(); await page.waitForTimeout(600); }
  }
  await page.waitForTimeout(1000);

  // Step 6: Check which renderer is being used
  console.log('\nStep 6: Checking renderer dispatch...');
  const check = await page.evaluate(() => {
    const body = document.body.innerText;
    const results = {};
    const h3s = Array.from(document.querySelectorAll('h3'));
    const expanded = h3s.filter(h => h.textContent && h.textContent.includes('▼'));

    for (const h of expanded) {
      const name = (h.textContent || '').trim().replace(/[▼▶]\s*/, '');
      const content = h.nextElementSibling;
      if (!content) continue;

      const allEls = content.querySelectorAll('[style]');
      const styles = Array.from(allEls).map(el => el.getAttribute('style') || '');

      results[name] = {
        // MiniCardList: gradient header bars
        gradientHeaders: styles.filter(s => s.includes('linear-gradient')).length,
        // ChipGrid compact cards: border-radius: 6px
        compactCards: styles.filter(s => s.includes('border-radius: 6px') && !s.includes('border-radius: 6px 6px')).length,
        // Round chips: border-radius: 16px
        roundChips: styles.filter(s => s.includes('border-radius: 16px')).length,
        // Prose blocks
        proseBlocks: styles.filter(s => s.includes('#f5f3ff')).length,
        // Uppercase labels (auto-detected subtitle badges in chip_grid)
        subtitleBadges: styles.filter(s => s.includes('border-radius: 10px') && s.includes('text-transform: uppercase')).length,
        totalStyled: allEls.length,
      };
    }

    // Also check for raw JSON dumps
    const rawJson = (body.match(/\{"[a-z_]+"\s*:\s*"/g) || []).length;
    return { sections: results, rawJsonCount: rawJson };
  });

  for (const [section, info] of Object.entries(check.sections)) {
    console.log(`  ${section}:`);
    for (const [k, v] of Object.entries(info)) {
      console.log(`    ${k}: ${v}`);
    }
  }
  console.log(`  Raw JSON dumps: ${check.rawJsonCount}`);

  // Step 7: Screenshots
  console.log('\nStep 7: Taking screenshots...');
  for (let y = 0; y <= 3200; y += 400) {
    await page.evaluate(sy => window.scrollTo(0, sy), y);
    await page.waitForTimeout(200);
    await page.screenshot({ path: DIR + `/scroll-${y}.png`, fullPage: false });
  }

  // Verdict
  const allSections = Object.values(check.sections);
  const totalGradient = allSections.reduce((a, v) => a + v.gradientHeaders, 0);
  const totalCompact = allSections.reduce((a, v) => a + v.compactCards, 0);
  const totalBadges = allSections.reduce((a, v) => a + v.subtitleBadges, 0);

  if (totalGradient > 0 && totalCompact === 0) {
    console.log(`\n✗ ISSUE: Still showing MiniCardList (${totalGradient} gradient headers), ChipGrid not dispatching`);
  } else if (totalCompact > 0 || totalBadges > 0) {
    console.log(`\n✓ PASS: ChipGrid compact cards rendering (${totalCompact} cards, ${totalBadges} badges)`);
  } else {
    console.log(`\n? Mixed: ${totalGradient} gradient, ${totalCompact} compact, ${totalBadges} badges`);
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
