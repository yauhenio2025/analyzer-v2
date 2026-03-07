const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({type: msg.type(), text: msg.text()}));

  // ==========================================================================
  // TEST 1: Implementations List Page
  // ==========================================================================
  console.log('\n=== TEST 1: Implementations List Page ===');
  await page.goto('http://localhost:3001/implementations', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);
  await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/01-implementations-list.png', fullPage: true });
  console.log('Screenshot saved: 01-implementations-list.png');

  // Check headings
  const headings = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('h1, h2, h3')).map(e => e.textContent.trim());
  });
  console.log('Headings:', JSON.stringify(headings));

  // Check for errors in overlay
  const hasErrorOverlay = await page.evaluate(() => {
    return !!document.querySelector('[data-nextjs-dialog], [class*="error"]');
  });
  console.log('Has error overlay:', hasErrorOverlay);

  // Check body text
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 3000));
  console.log('Body text (first 3000):', bodyText.substring(0, 1000));

  // Check workflow cards
  const workflowCards = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href*="/implementations/"]')).map(a => ({
      href: a.getAttribute('href'),
      text: a.textContent.trim().substring(0, 100)
    }));
  });
  console.log('Workflow cards found:', workflowCards.length);
  workflowCards.forEach(c => console.log('  -', c.href, ':', c.text.substring(0, 60)));

  // Console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  console.log('Console errors:', errors.length);
  errors.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));

  await browser.close();
  console.log('\n=== TEST 1 COMPLETE ===');
})().catch(e => { console.error('FATAL ERROR:', e.message); process.exit(1); });
