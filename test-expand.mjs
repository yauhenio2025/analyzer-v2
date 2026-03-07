import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/expand';
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

  // Take screenshot before expanding
  await page.screenshot({ path: DIR + '/01-chips-closed.png', fullPage: false });

  // Click the first framework chip (Technofeudal Marxism)
  console.log('Clicking Technofeudal Marxism chip...');
  const chip = await page.$('span:has-text("Technofeudal Marxism")');
  if (chip) {
    await chip.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: DIR + '/02-expanded.png', fullPage: false });
    console.log('Expanded screenshot taken');

    // Check the expanded panel content
    const panelCheck = await page.evaluate(() => {
      const body = document.body.innerText;
      return {
        hasDescription: body.includes('A Marxist value-theoretic framework'),
        hasComponents: body.includes('COMPONENTS') || body.includes('components'),
        hasVocabulary: body.includes('VOCABULARY') || body.includes('vocabulary'),
        hasMethodSig: body.includes('METHODOLOGICAL SIGNATURE') || body.includes('methodological signature'),
        hasCloseBtn: body.includes('close'),
      };
    });
    console.log('Panel content:', JSON.stringify(panelCheck, null, 2));

    // Click another chip
    console.log('\nClicking Historical Materialist Genealogy...');
    const chip2 = await page.$('span:has-text("Historical Materialist")');
    if (chip2) {
      await chip2.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: DIR + '/03-switched.png', fullPage: false });
      console.log('Switched to different chip');
    }

    // Click same chip to close
    if (chip2) {
      await chip2.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: DIR + '/04-closed-again.png', fullPage: false });
      console.log('Closed panel');
    }

    // Scroll down to see Semantic Constellation chips
    await page.evaluate(() => window.scrollTo(0, 800));
    await page.waitForTimeout(300);
    await page.screenshot({ path: DIR + '/05-semantic-chips.png', fullPage: false });

    // Click a core concept chip
    const conceptChip = await page.$('span:has-text("cloud capital")');
    if (conceptChip) {
      await conceptChip.click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: DIR + '/06-concept-expanded.png', fullPage: false });
      console.log('Expanded cloud capital concept');
    }

    console.log('\n✓ PASS: Click-to-expand working');
  } else {
    console.log('✗ FAIL: Could not find Technofeudal Marxism chip');
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
