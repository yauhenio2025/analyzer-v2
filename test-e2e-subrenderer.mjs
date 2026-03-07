import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/e2e';
mkdirSync(DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  // Step 1: Import v2 job via API (this also saves to DB now)
  console.log('Step 1: Importing v2 job via API...');
  const importResp = await fetch('https://the-critic.onrender.com/api/genealogy/import-v2/job-7d32be316d06?project_id=morozov-on-varoufakis', { method: 'POST' });
  const importData = await importResp.json();
  console.log('  Import:', JSON.stringify(importData));

  // Step 2: Navigate to page (should auto-load v2 presentation from DB)
  console.log('\nStep 2: Navigating to genealogy page...');
  await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
    waitUntil: 'networkidle', timeout: 90000
  });
  await page.waitForTimeout(6000);

  // Check what state we're in
  const pageState = await page.evaluate(() => {
    const hasV2Badge = !!document.querySelector('.gen-v2-badge');
    const hasTPTab = document.body.innerText.includes('Target Work Profile');
    return { hasV2Badge, hasTPTab };
  });
  console.log('  Page state:', JSON.stringify(pageState));

  if (!pageState.hasTPTab) {
    console.log('  WARN: No Target Work Profile tab yet. Waiting...');
    await page.waitForTimeout(5000);
    await page.screenshot({ path: DIR + '/no-tp.png', fullPage: true });
  }

  if (!pageState.hasV2Badge && !pageState.hasTPTab) {
    console.log('  FAIL: Neither v2 badge nor Target Work Profile found');
    await browser.close();
    process.exit(1);
  }

  // Step 3: Click Target Work Profile
  console.log('\nStep 3: Clicking Target Work Profile...');
  await page.click('text=Target Work Profile');
  await page.waitForTimeout(3000);

  // Step 4: Expand all accordion sections
  console.log('Step 4: Expanding all sections...');
  const h3s = await page.$$('h3');
  for (const h of h3s) {
    const t = await h.textContent();
    if (t && t.includes('▶')) { await h.click(); await page.waitForTimeout(600); }
  }
  await page.waitForTimeout(1000);

  // Step 5: Verify sub-renderer dispatch
  console.log('\nStep 5: Checking sub-renderer elements...');
  const check = await page.evaluate(() => {
    const results = {};
    const h3s = Array.from(document.querySelectorAll('h3'));
    const expanded = h3s.filter(h => h.textContent && h.textContent.includes('▼'));

    for (const h of expanded) {
      const name = (h.textContent || '').trim().replace(/[▼▶]\s*/, '');
      const content = h.nextElementSibling;
      if (!content) continue;

      const allEls = content.querySelectorAll('[style]');
      const styles = Array.from(allEls).map(el => el.getAttribute('style') || '');

      // MiniCardList: indigo left border rgb(99, 102, 241)
      const indigo = styles.filter(s => s.includes('rgb(99, 102, 241)')).length;
      // ProseBlock: purple border rgb(165, 180, 252) + bg rgb(250, 250, 255)
      const purple = styles.filter(s => s.includes('rgb(165, 180, 252)')).length;
      // Pill badges: 10px border-radius
      const pills = styles.filter(s => s.includes('border-radius: 10px')).length;
      // Inline chips: 3px border-radius
      const chips = styles.filter(s => s.includes('border-radius: 3px')).length;
      // Old generic: border-left: 2px solid
      const generic = styles.filter(s => s.includes('border-left: 2px solid')).length;

      results[name] = { indigo, purple, pills, chips, generic, totalEls: allEls.length };
    }
    return results;
  });

  let totalNew = 0, totalOld = 0;
  for (const [section, info] of Object.entries(check)) {
    const newCount = info.indigo + info.purple;
    totalNew += newCount;
    totalOld += info.generic;
    console.log(`  ${section}:`);
    console.log(`    MiniCardList (indigo border): ${info.indigo}`);
    console.log(`    ProseBlock (purple border):   ${info.purple}`);
    console.log(`    Pill badges (10px):           ${info.pills}`);
    console.log(`    Inline chips (3px):           ${info.chips}`);
    console.log(`    Old generic borders:          ${info.generic}`);
    console.log(`    Total styled elements:        ${info.totalEls}`);
  }

  console.log(`\n  TOTAL: ${totalNew} new sub-renderer, ${totalOld} old generic`);

  // Step 6: Screenshots
  console.log('\nStep 6: Taking screenshots...');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: DIR + '/01-top.png', fullPage: false });

  for (let y = 400; y <= 3200; y += 400) {
    await page.evaluate(sy => window.scrollTo(0, sy), y);
    await page.waitForTimeout(200);
    await page.screenshot({ path: DIR + `/scroll-${y}.png`, fullPage: false });
  }

  if (totalNew > 0) {
    console.log(`\n✓ PASS: Sub-renderers dispatching with enhanced styling (${totalNew} new elements)`);
  } else if (check && Object.values(check).some(v => v.pills > 0 || v.chips > 0)) {
    console.log(`\n✓ PASS: Sub-renderers dispatching (pills: ${Object.values(check).reduce((a,v) => a + v.pills, 0)}, chips: ${Object.values(check).reduce((a,v) => a + v.chips, 0)})`);
  } else {
    console.log('\n✗ FAIL: No sub-renderer elements detected');
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
