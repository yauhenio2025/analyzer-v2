import puppeteer from 'puppeteer';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleMessages.push(msg.text().substring(0, 200));
  });

  // Navigate directly
  console.log('=== Navigating to http://localhost:3001 ===');
  await page.goto('http://localhost:3001', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));

  console.log('Current URL:', await page.url());

  // Click on the Analysis dropdown
  console.log('\n=== Opening Analysis dropdown ===');
  const analysisClicked = await page.evaluate(() => {
    const btns = document.querySelectorAll('.nav-dropdown-trigger, button');
    for (const btn of btns) {
      if (btn.textContent.trim().toLowerCase().startsWith('analysis')) {
        btn.click();
        return true;
      }
    }
    return false;
  });
  console.log('Clicked Analysis:', analysisClicked);
  await new Promise(r => setTimeout(r, 500));

  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v3-01-analysis-menu.png`, fullPage: false });

  // Get all dropdown menu items
  const dropdownItems = await page.evaluate(() => {
    const items = document.querySelectorAll('.nav-dropdown-menu a, .nav-dropdown-item, .dropdown-menu a, .dropdown-item');
    return [...items].map(el => ({
      text: el.textContent.trim().substring(0, 80),
      href: el.href || '',
      classes: el.className.substring(0, 100)
    }));
  });
  console.log('Analysis dropdown items:', JSON.stringify(dropdownItems, null, 2));

  // Also look for any anchor elements that contain 'genealogy'
  const geneLinks = await page.evaluate(() => {
    const all = document.querySelectorAll('a');
    return [...all].filter(a => a.href.includes('genealogy') || a.textContent.toLowerCase().includes('genealogy'))
      .map(a => ({ text: a.textContent.trim().substring(0, 60), href: a.href }));
  });
  console.log('Genealogy links found:', JSON.stringify(geneLinks, null, 2));

  // Close dropdown and try Concepts dropdown
  await page.click('body');
  await new Promise(r => setTimeout(r, 300));

  console.log('\n=== Opening Concepts dropdown ===');
  const conceptsClicked = await page.evaluate(() => {
    const btns = document.querySelectorAll('.nav-dropdown-trigger, button');
    for (const btn of btns) {
      if (btn.textContent.trim().toLowerCase().startsWith('concepts')) {
        btn.click();
        return true;
      }
    }
    return false;
  });
  console.log('Clicked Concepts:', conceptsClicked);
  await new Promise(r => setTimeout(r, 500));

  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v3-02-concepts-menu.png`, fullPage: false });

  const conceptsItems = await page.evaluate(() => {
    const items = document.querySelectorAll('.nav-dropdown-menu a, .nav-dropdown-item, .dropdown-menu a, .dropdown-item, [class*="dropdown-menu"] *');
    return [...items].map(el => ({
      text: el.textContent.trim().substring(0, 80),
      href: el.href || '',
      tag: el.tagName,
      classes: el.className.substring(0, 100)
    }));
  });
  console.log('Concepts dropdown items:', JSON.stringify(conceptsItems, null, 2));

  // Also try Synthesis dropdown
  await page.click('body');
  await new Promise(r => setTimeout(r, 300));

  console.log('\n=== Opening Synthesis dropdown ===');
  await page.evaluate(() => {
    const btns = document.querySelectorAll('.nav-dropdown-trigger, button');
    for (const btn of btns) {
      if (btn.textContent.trim().toLowerCase().startsWith('synthesis')) {
        btn.click();
        return true;
      }
    }
  });
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v3-03-synthesis-menu.png`, fullPage: false });

  const synthesisItems = await page.evaluate(() => {
    const items = document.querySelectorAll('.nav-dropdown-menu a, .nav-dropdown-item');
    return [...items].map(el => ({
      text: el.textContent.trim().substring(0, 80),
      href: el.href || ''
    }));
  });
  console.log('Synthesis dropdown items:', JSON.stringify(synthesisItems, null, 2));

  // Navigate directly to the genealogy URL
  console.log('\n=== Trying direct navigation to genealogy ===');
  await page.goto('http://localhost:3001/p/morozov-benanav-001/genealogy', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 3000));

  console.log('URL after direct nav:', await page.url());
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v3-04-genealogy-direct.png`, fullPage: false });

  // Check what we see
  const geneContent = await page.evaluate(() => {
    return {
      url: window.location.href,
      bodyText: document.body.innerText.substring(0, 2000),
      allTabs: [...document.querySelectorAll('[role="tab"], button[class*="tab"], .tab, [class*="tab"]')]
        .map(el => el.textContent.trim().substring(0, 60))
        .filter(t => t.length > 0),
    };
  });
  console.log('Genealogy page content:', JSON.stringify(geneContent, null, 2));

  // Print unique console errors
  const uniqueErrors = [...new Set(consoleMessages)];
  if (uniqueErrors.length > 0) {
    console.log('\n=== Unique Console Errors ===');
    uniqueErrors.forEach(e => console.log('  -', e));
  }

  await browser.close();
  console.log('\nDone!');
}

run().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
