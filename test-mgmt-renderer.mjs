import { chromium } from 'playwright';

const DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

try {
  console.log('Navigating to Target Work Profile view...');
  await page.goto('https://analyzer-mgmt-frontend.onrender.com/views/genealogy_target_profile', {
    waitUntil: 'networkidle', timeout: 90000
  });
  await page.waitForTimeout(3000);

  // Click Renderer tab
  console.log('Clicking Renderer tab...');
  await page.click('button:has-text("Renderer")');
  await page.waitForTimeout(2000);

  // Take screenshots
  await page.screenshot({ path: DIR + '/mgmt-renderer-top.png', fullPage: false });
  console.log('Top screenshot taken');

  await page.evaluate(() => window.scrollTo(0, 500));
  await page.waitForTimeout(500);
  await page.screenshot({ path: DIR + '/mgmt-renderer-mid.png', fullPage: false });

  await page.evaluate(() => window.scrollTo(0, 1000));
  await page.waitForTimeout(500);
  await page.screenshot({ path: DIR + '/mgmt-renderer-mid2.png', fullPage: false });

  await page.evaluate(() => window.scrollTo(0, 1500));
  await page.waitForTimeout(500);
  await page.screenshot({ path: DIR + '/mgmt-renderer-bottom.png', fullPage: false });

  await page.evaluate(() => window.scrollTo(0, 2000));
  await page.waitForTimeout(500);
  await page.screenshot({ path: DIR + '/mgmt-renderer-bottom2.png', fullPage: false });

  // Check what elements are visible
  const check = await page.evaluate(() => {
    const cards = document.querySelectorAll('[class*="border-purple"], [class*="border-blue"]');
    const selects = document.querySelectorAll('select');
    const inputs = document.querySelectorAll('input[type="text"]');
    const hasJsonEditor = document.body.innerText.includes('Show Raw JSON') || document.body.innerText.includes('Hide Raw JSON');
    const hasSectionRenderers = document.body.innerText.includes('Section Renderers');
    const hasAccordionSections = document.body.innerText.includes('Accordion Sections');
    return {
      cardCount: cards.length,
      selectCount: selects.length,
      inputCount: inputs.length,
      hasJsonEditor,
      hasSectionRenderers,
      hasAccordionSections,
    };
  });
  console.log('\nUI check:', JSON.stringify(check, null, 2));

  if (check.hasSectionRenderers && check.hasAccordionSections) {
    console.log('\nPASS: Visual editor is rendering');
  } else {
    console.log('\nWARN: Visual editor may not be rendering correctly');
  }

} catch (err) {
  console.error('TEST FAILED:', err.message);
  await page.screenshot({ path: DIR + '/mgmt-renderer-error.png', fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
