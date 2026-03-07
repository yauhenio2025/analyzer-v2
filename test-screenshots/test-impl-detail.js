const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({type: msg.type(), text: msg.text()}));

  // ==========================================================================
  // TEST 2: Intellectual Genealogy Detail Page
  // ==========================================================================
  console.log('\n=== TEST 2: Intellectual Genealogy Detail Page ===');

  // Navigate to list page first
  await page.goto('http://localhost:3001/implementations', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);

  // Click on intellectual_genealogy card
  const link = await page.waitForSelector('a[href="/implementations/intellectual_genealogy"]', { timeout: 10000 });
  await link.click();
  await page.waitForURL('**/implementations/intellectual_genealogy', { timeout: 15000 });

  // Wait for data to load (multiple API calls happen)
  await page.waitForTimeout(5000);

  await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/02-intellectual-genealogy-detail.png', fullPage: true });
  console.log('Screenshot saved: 02-intellectual-genealogy-detail.png');

  // Check headings
  const headings = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('h1, h2, h3')).map(e => e.textContent.trim());
  });
  console.log('Headings:', JSON.stringify(headings));

  // Check for error overlay
  const hasErrorOverlay = await page.evaluate(() => {
    const errorEl = document.querySelector('[data-nextjs-dialog]');
    if (errorEl) return errorEl.textContent.substring(0, 200);
    return null;
  });
  console.log('Error overlay:', hasErrorOverlay);

  // Check pass blocks
  const passBlocks = await page.evaluate(() => {
    // Look for pass numbers (circles with numbers)
    const circles = Array.from(document.querySelectorAll('[class*="rounded-full"]'));
    return circles.filter(c => c.textContent.trim().match(/^\d+$/)).map(c => c.textContent.trim());
  });
  console.log('Pass number circles found:', passBlocks);

  // Check for chain names
  const chainLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href*="/workflows/"]')).map(a => ({
      href: a.getAttribute('href'),
      text: a.textContent.trim()
    }));
  });
  console.log('Chain links found:', JSON.stringify(chainLinks));

  // Check for engine cards (CPU icons or engine links)
  const engineLinks = await page.evaluate(() => {
    return Array.from(document.querySelectorAll('a[href*="/engines/"]')).map(a => ({
      href: a.getAttribute('href'),
      text: a.textContent.trim()
    }));
  });
  console.log('Engine links found:', engineLinks.length);
  engineLinks.forEach(e => console.log('  -', e.href, ':', e.text));

  // Check for stance badges
  const stanceBadges = await page.evaluate(() => {
    const badges = Array.from(document.querySelectorAll('[class*="rounded-full"]'));
    return badges.filter(b => {
      const text = b.textContent.trim().toLowerCase();
      return ['discovery', 'inference', 'confrontation', 'architecture', 'integration', 'reflection', 'dialectical'].includes(text);
    }).map(b => b.textContent.trim());
  });
  console.log('Stance badges found:', stanceBadges.length, stanceBadges.slice(0, 20));

  // Body text for analysis
  const bodyText = await page.evaluate(() => document.body.innerText.substring(0, 5000));
  console.log('\nBody text (first 2000):', bodyText.substring(0, 2000));

  // Console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  console.log('\nConsole errors:', errors.length);
  errors.forEach(e => console.log('  ERROR:', e.text.substring(0, 300)));

  await browser.close();
  console.log('\n=== TEST 2 COMPLETE ===');
})().catch(e => { console.error('FATAL ERROR:', e.message); process.exit(1); });
