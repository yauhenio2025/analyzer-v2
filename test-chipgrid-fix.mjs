import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/chipgrid';
mkdirSync(DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  // Step 1: Re-import to make sure v2 presentation is loaded
  console.log('Step 1: Importing v2 job...');
  const importResp = await fetch('https://the-critic.onrender.com/api/genealogy/import-v2/job-7d32be316d06?project_id=morozov-on-varoufakis', { method: 'POST' });
  const importData = await importResp.json();
  console.log('  Import:', JSON.stringify(importData));

  // Step 2: Navigate to genealogy page
  console.log('\nStep 2: Navigating to genealogy page...');
  await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
    waitUntil: 'networkidle', timeout: 90000
  });
  await page.waitForTimeout(6000);

  // Step 3: Click Target Work Profile tab
  console.log('Step 3: Clicking Target Work Profile...');
  await page.click('text=Target Work Profile');
  await page.waitForTimeout(3000);

  // Take screenshot at top
  await page.screenshot({ path: DIR + '/01-top.png', fullPage: false });

  // Step 4: Expand Conceptual Framework section
  console.log('Step 4: Expanding sections...');
  const h3s = await page.$$('h3');
  for (const h of h3s) {
    const t = await h.textContent();
    if (t && t.includes('▶')) {
      await h.click();
      await page.waitForTimeout(600);
    }
  }
  await page.waitForTimeout(1000);

  // Step 5: Check what rendering styles exist
  console.log('\nStep 5: Checking rendering styles...');
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

      // MiniCardList: gradient header bars
      const gradientHeaders = styles.filter(s => s.includes('linear-gradient')).length;
      // ChipGrid: border-radius: 16px chips
      const roundChips = styles.filter(s => s.includes('border-radius: 16px')).length;
      // ChipGrid container: border-radius: 8px + background: #f8fafc
      const chipContainer = styles.filter(s => s.includes('#f8fafc') && s.includes('border-radius: 8px')).length;
      // ProseBlock: purple bg #f5f3ff
      const proseBlocks = styles.filter(s => s.includes('#f5f3ff')).length;
      // MiniCardList colored headers
      const coloredHeaders = styles.filter(s => s.includes('border-radius: 8px 8px 0 0')).length;

      results[name] = {
        gradientHeaders,
        roundChips,
        chipContainer,
        proseBlocks,
        coloredHeaders,
        totalStyled: allEls.length
      };
    }
    return results;
  });

  for (const [section, info] of Object.entries(check)) {
    console.log(`  ${section}:`);
    console.log(`    Gradient headers (MiniCardList): ${info.gradientHeaders}`);
    console.log(`    Round chips (ChipGrid):          ${info.roundChips}`);
    console.log(`    Chip containers:                 ${info.chipContainer}`);
    console.log(`    Prose blocks:                    ${info.proseBlocks}`);
    console.log(`    Colored card headers:            ${info.coloredHeaders}`);
    console.log(`    Total styled:                    ${info.totalStyled}`);
  }

  // Step 6: Screenshots at multiple scroll positions
  console.log('\nStep 6: Taking screenshots...');
  for (let y = 0; y <= 3200; y += 400) {
    await page.evaluate(sy => window.scrollTo(0, sy), y);
    await page.waitForTimeout(200);
    await page.screenshot({ path: DIR + `/scroll-${y}.png`, fullPage: false });
  }

  // Check if chip_grid is rendering (roundChips > 0 means ChipGrid is dispatching)
  const allValues = Object.values(check);
  const totalChips = allValues.reduce((a, v) => a + v.roundChips, 0);
  const totalHeaders = allValues.reduce((a, v) => a + v.coloredHeaders, 0);

  if (totalChips > 0) {
    console.log(`\n✓ PASS: ChipGrid is rendering (${totalChips} round chips found)`);
  } else if (totalHeaders > 0) {
    console.log(`\n✗ ISSUE: Still seeing MiniCardList headers (${totalHeaders}), ChipGrid not dispatching`);
  } else {
    console.log('\n? UNCLEAR: Neither ChipGrid nor MiniCardList elements found');
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
