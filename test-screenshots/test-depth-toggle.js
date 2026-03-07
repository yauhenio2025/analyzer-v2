const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({type: msg.type(), text: msg.text()}));

  // ==========================================================================
  // TEST 3: Depth Toggle
  // ==========================================================================
  console.log('\n=== TEST 3: Depth Toggle ===');

  await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  // Capture stance badges in "standard" depth (default)
  const standardBadges = await page.evaluate(() => {
    const badges = Array.from(document.querySelectorAll('span'));
    return badges.filter(b => {
      const parent = b.closest('[class*="rounded-full"]');
      const text = b.textContent.trim().toLowerCase();
      return ['discovery', 'inference', 'confrontation', 'architecture', 'integration', 'reflection', 'dialectical'].includes(text);
    }).map(b => b.textContent.trim());
  });
  console.log('Standard depth stance badges:', standardBadges.length, standardBadges.slice(0, 10));

  // Click "deep" button
  console.log('Clicking "deep" button...');
  const deepButton = await page.locator('button', { hasText: 'deep' }).first();
  await deepButton.click();
  await page.waitForTimeout(3000);

  await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/03-depth-toggle-deep.png', fullPage: true });
  console.log('Screenshot saved: 03-depth-toggle-deep.png');

  // Check which depth button is now active (has indigo background)
  const activeDepth = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    const depthButtons = buttons.filter(b => ['surface', 'standard', 'deep'].includes(b.textContent.trim().toLowerCase()));
    return depthButtons.map(b => ({
      text: b.textContent.trim(),
      classes: b.className,
      isActive: b.className.includes('indigo') || b.className.includes('bg-indigo')
    }));
  });
  console.log('Depth buttons:', JSON.stringify(activeDepth));

  // Capture stance badges after switching to "deep"
  const deepBadges = await page.evaluate(() => {
    const badges = Array.from(document.querySelectorAll('span'));
    return badges.filter(b => {
      const text = b.textContent.trim().toLowerCase();
      return ['discovery', 'inference', 'confrontation', 'architecture', 'integration', 'reflection', 'dialectical'].includes(text);
    }).map(b => b.textContent.trim());
  });
  console.log('Deep depth stance badges:', deepBadges.length, deepBadges.slice(0, 15));

  // Compare
  console.log('\nComparison:');
  console.log('  Standard depth badges:', standardBadges.length);
  console.log('  Deep depth badges:', deepBadges.length);
  if (standardBadges.length !== deepBadges.length) {
    console.log('  PASS: Badge count changed when switching depths');
  } else if (JSON.stringify(standardBadges) !== JSON.stringify(deepBadges)) {
    console.log('  PASS: Badge sequence changed when switching depths');
  } else {
    console.log('  NOTE: Badges appear identical - may need operationalization data for different depths');
  }

  // Console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  console.log('\nConsole errors:', errors.length);
  errors.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));

  await browser.close();
  console.log('\n=== TEST 3 COMPLETE ===');
})().catch(e => { console.error('FATAL ERROR:', e.message); process.exit(1); });
