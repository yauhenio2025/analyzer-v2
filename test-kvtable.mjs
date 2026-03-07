import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/kvtable';
mkdirSync(DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  await fetch('https://the-critic.onrender.com/api/genealogy/import-v2/job-7d32be316d06?project_id=morozov-on-varoufakis', { method: 'POST' });

  await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
    waitUntil: 'networkidle', timeout: 90000
  });
  await page.waitForTimeout(6000);

  await page.click('text=Target Work Profile');
  await page.waitForTimeout(3000);

  // Expand all sections
  const h3s = await page.$$('h3');
  for (const h of h3s) {
    const t = await h.textContent();
    if (t && t.includes('▶')) { await h.click(); await page.waitForTimeout(600); }
  }
  await page.waitForTimeout(1000);

  // Check what's rendering
  const check = await page.evaluate(() => {
    const allStyled = document.querySelectorAll('[style]');
    const styles = Array.from(allStyled).map(el => el.getAttribute('style') || '');

    return {
      // KV table: borderCollapse + zebra bg
      tables: document.querySelectorAll('table').length,
      // Chips (20px radius)
      chips: styles.filter(s => s.includes('border-radius: 20px')).length,
      // KV blue key column: #eef2ff bg + #6366f1 right border
      kvKeys: styles.filter(s => s.includes('#eef2ff') || s.includes('#e8ecff')).length,
      // Gradient headers (MiniCardList)
      gradients: styles.filter(s => s.includes('linear-gradient')).length,
    };
  });

  console.log('Rendering check:');
  console.log(`  <table> elements: ${check.tables}`);
  console.log(`  KV blue key cells: ${check.kvKeys}`);
  console.log(`  Chip elements: ${check.chips}`);
  console.log(`  Gradient headers: ${check.gradients}`);

  // Screenshots
  for (let y = 0; y <= 2400; y += 400) {
    await page.evaluate(sy => window.scrollTo(0, sy), y);
    await page.waitForTimeout(200);
    await page.screenshot({ path: DIR + `/scroll-${y}.png`, fullPage: false });
  }

  if (check.tables > 0 && check.kvKeys > 0) {
    console.log(`\n✓ PASS: Key-Value Tables rendering (${check.tables} tables, ${check.kvKeys} key cells)`);
  } else if (check.chips > 0) {
    console.log(`\n✗ Still showing ChipGrid (${check.chips} chips) — cache issue?`);
  } else {
    console.log(`\n? Unclear rendering state`);
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
