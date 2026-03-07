import { chromium } from 'playwright';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/v2fix';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

// Intercept network to find the API URL the frontend uses
const apiUrls = [];
page.on('request', req => {
  if (req.url().includes('/api/')) apiUrls.push(req.url());
});

await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', { waitUntil: 'networkidle', timeout: 90000 });
await page.waitForTimeout(5000);

console.log('API URLs seen:');
for (const url of apiUrls.slice(0, 10)) console.log('  ' + url);

// Try to import via the detected API base
const apiBase = apiUrls.length > 0 ? new URL(apiUrls[0]).origin : 'https://the-critic.onrender.com';
console.log('\nDetected API base:', apiBase);

// Do the import from the page context
const importResult = await page.evaluate(async (base) => {
  try {
    const resp = await fetch(base + '/api/genealogy/import-v2/job-7d32be316d06?project_id=morozov-on-varoufakis', { method: 'POST' });
    if (resp.status !== 200) return { error: 'HTTP ' + resp.status, text: await resp.text() };
    const data = await resp.json();
    return data;
  } catch (e) {
    return { error: e.message };
  }
}, apiBase);

console.log('Import result:', JSON.stringify(importResult));

if (importResult.job_id) {
  // Reload the page to pick up the new job
  console.log('Reloading page...');
  await page.reload({ waitUntil: 'networkidle', timeout: 90000 });
  await page.waitForTimeout(5000);

  const hasTP = await page.evaluate(() => document.body.innerText.includes('Target Work Profile'));
  console.log('Has Target Work Profile:', hasTP);

  if (hasTP) {
    await page.click('text=Target Work Profile');
    await page.waitForTimeout(3000);

    // Expand all
    const h3s = await page.$$('h3');
    for (const h of h3s) {
      const t = await h.textContent();
      if (t && t.includes('▶')) { await h.click(); await page.waitForTimeout(600); }
    }
    await page.waitForTimeout(1000);

    // Check for sub-renderer patterns (using rgb values since React converts hex)
    const check = await page.evaluate(() => {
      const results = {};
      const h3s = Array.from(document.querySelectorAll('h3'));
      const expanded = h3s.filter(h => h.textContent && h.textContent.includes('▼'));

      for (const h of expanded) {
        const name = (h.textContent || '').trim().replace(/[▼▶]\s*/, '');
        const content = h.nextElementSibling;
        if (!content) continue;

        const allStyles = Array.from(content.querySelectorAll('[style]'))
          .map(el => el.getAttribute('style') || '');

        const indigoCount = allStyles.filter(s => s.includes('rgb(99, 102, 241)')).length;
        const purpleCount = allStyles.filter(s => s.includes('rgb(165, 180, 252)')).length;
        const pillCount = allStyles.filter(s => s.includes('border-radius: 10px')).length;
        const chip3Count = allStyles.filter(s => s.includes('border-radius: 3px')).length;
        const genericBorderCount = allStyles.filter(s => s.includes('border-left: 2px solid')).length;

        results[name] = { indigo: indigoCount, purple: purpleCount, pills: pillCount, chips3: chip3Count, generic: genericBorderCount };
      }
      return results;
    });

    console.log('\nSub-renderer verification:');
    let totalNew = 0;
    for (const [section, info] of Object.entries(check)) {
      const newEl = info.indigo + info.purple;
      totalNew += newEl;
      console.log(`  ${section}: indigo=${info.indigo} purple=${info.purple} pills=${info.pills} chips=${info.chips3} generic=${info.generic}`);
    }

    // Screenshots
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: DIR + '/verified-top.png', fullPage: false });
    for (let y = 400; y <= 2400; y += 400) {
      await page.evaluate(sy => window.scrollTo(0, sy), y);
      await page.waitForTimeout(200);
      await page.screenshot({ path: DIR + '/verified-scroll-' + y + '.png', fullPage: false });
    }

    console.log(totalNew > 0 ? '\n✓ PASS: Sub-renderers with enhanced styling' : '\n✗ Sub-renderers dispatching but without new colors (check CSS)');
  }
}

await browser.close();
