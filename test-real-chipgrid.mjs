import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/real-chipgrid';
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

  // Expand sections
  const h3s = await page.$$('h3');
  for (const h of h3s) {
    const t = await h.textContent();
    if (t && t.includes('▶')) { await h.click(); await page.waitForTimeout(600); }
  }
  await page.waitForTimeout(1000);

  // Check for chip-like rendering
  const check = await page.evaluate(() => {
    const allStyled = document.querySelectorAll('[style]');
    const styles = Array.from(allStyled).map(el => ({
      style: el.getAttribute('style') || '',
      text: el.textContent?.substring(0, 50) || '',
    }));

    // Chips: border-radius: 20px (the new chip style)
    const chips = styles.filter(s => s.style.includes('border-radius: 20px'));
    // Gradient headers (MiniCardList)
    const gradients = styles.filter(s => s.style.includes('linear-gradient'));
    // Chip container: border-radius: 10px + background: #f8fafc
    const containers = styles.filter(s => s.style.includes('border-radius: 10px') && s.style.includes('#f8fafc'));

    return {
      chipCount: chips.length,
      chipSamples: chips.slice(0, 5).map(c => c.text.trim()),
      gradientCount: gradients.length,
      containerCount: containers.length,
    };
  });

  console.log('Chip check:');
  console.log(`  Chips (20px radius): ${check.chipCount}`);
  console.log(`  Sample chips: ${JSON.stringify(check.chipSamples)}`);
  console.log(`  Gradient headers (MiniCardList): ${check.gradientCount}`);
  console.log(`  Chip containers: ${check.containerCount}`);

  // Screenshots
  for (let y = 0; y <= 2400; y += 400) {
    await page.evaluate(sy => window.scrollTo(0, sy), y);
    await page.waitForTimeout(200);
    await page.screenshot({ path: DIR + `/scroll-${y}.png`, fullPage: false });
  }

  if (check.chipCount > 0 && check.gradientCount === 0) {
    console.log(`\n✓ PASS: Real chip grid! ${check.chipCount} chips, no MiniCardList headers`);
  } else if (check.chipCount > 0 && check.gradientCount > 0) {
    console.log(`\n~ MIXED: ${check.chipCount} chips + ${check.gradientCount} gradient headers`);
  } else {
    console.log(`\n✗ FAIL: ${check.chipCount} chips, ${check.gradientCount} gradients`);
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
