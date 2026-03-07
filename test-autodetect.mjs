import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/autodetect';
mkdirSync(DIR, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  // Re-import
  console.log('Importing v2 job...');
  await fetch('https://the-critic.onrender.com/api/genealogy/import-v2/job-7d32be316d06?project_id=morozov-on-varoufakis', { method: 'POST' });

  console.log('Navigating...');
  await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
    waitUntil: 'networkidle', timeout: 90000
  });
  await page.waitForTimeout(6000);

  // Click Target Work Profile
  await page.click('text=Target Work Profile');
  await page.waitForTimeout(3000);

  // Expand all sections
  const h3s = await page.$$('h3');
  for (const h of h3s) {
    const t = await h.textContent();
    if (t && t.includes('▶')) { await h.click(); await page.waitForTimeout(600); }
  }
  await page.waitForTimeout(1000);

  // Check for JSON dumps (the problem indicator)
  const jsonCheck = await page.evaluate(() => {
    const body = document.body.innerText;
    // Look for raw JSON object patterns like {"name": or {"term":
    const jsonPatterns = body.match(/\{"[a-z_]+"\s*:\s*"/g) || [];
    // Look for clean rendered text (framework names etc.)
    const hasCleanLabels = body.includes('Technofeudal Marxism') && !body.includes('"name":"Technofeudal Marxism"');
    return {
      rawJsonCount: jsonPatterns.length,
      samplePatterns: jsonPatterns.slice(0, 5),
      hasCleanLabels,
    };
  });

  console.log('\nJSON dump check:');
  console.log(`  Raw JSON patterns found: ${jsonCheck.rawJsonCount}`);
  console.log(`  Sample patterns: ${JSON.stringify(jsonCheck.samplePatterns)}`);
  console.log(`  Clean labels rendering: ${jsonCheck.hasCleanLabels}`);

  // Check rendering elements
  const renderCheck = await page.evaluate(() => {
    const allStyled = document.querySelectorAll('[style]');
    const styles = Array.from(allStyled).map(el => el.getAttribute('style') || '');

    return {
      // ChipGrid compact cards (have border-radius: 6px + lightBg)
      compactCards: styles.filter(s => s.includes('border-radius: 6px') && s.includes('border: 1px solid')).length,
      // Simple chips (border-radius: 16px)
      simpleChips: styles.filter(s => s.includes('border-radius: 16px')).length,
      // MiniCardList gradient headers
      gradientHeaders: styles.filter(s => s.includes('linear-gradient')).length,
      // Prose blocks
      proseBlocks: styles.filter(s => s.includes('#f5f3ff')).length,
      // Uppercase labels (auto-detected subtitle)
      uppercaseLabels: styles.filter(s => s.includes('text-transform: uppercase')).length,
    };
  });

  console.log('\nRendering check:');
  for (const [k, v] of Object.entries(renderCheck)) {
    console.log(`  ${k}: ${v}`);
  }

  // Screenshots
  console.log('\nTaking screenshots...');
  for (let y = 0; y <= 3200; y += 400) {
    await page.evaluate(sy => window.scrollTo(0, sy), y);
    await page.waitForTimeout(200);
    await page.screenshot({ path: DIR + `/scroll-${y}.png`, fullPage: false });
  }

  if (jsonCheck.rawJsonCount === 0 && jsonCheck.hasCleanLabels) {
    console.log('\n✓ PASS: No raw JSON dumps, clean labels rendering');
  } else if (jsonCheck.rawJsonCount < 5 && jsonCheck.hasCleanLabels) {
    console.log(`\n~ PARTIAL: ${jsonCheck.rawJsonCount} raw JSON patterns but clean labels present`);
  } else {
    console.log(`\n✗ FAIL: ${jsonCheck.rawJsonCount} raw JSON dumps found`);
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
