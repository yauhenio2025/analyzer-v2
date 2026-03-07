const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({type: msg.type(), text: msg.text()}));

  // ==========================================================================
  // TEST 5: Data Flow Summary
  // ==========================================================================
  console.log('\n=== TEST 5: Data Flow Summary ===');

  await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  // Scroll down to find Data Flow Summary
  const dataFlowExists = await page.evaluate(() => {
    const headings = Array.from(document.querySelectorAll('h2'));
    return headings.some(h => h.textContent.includes('Data Flow Summary'));
  });
  console.log('Data Flow Summary heading found:', dataFlowExists);

  if (dataFlowExists) {
    // Scroll to the Data Flow Summary button
    await page.evaluate(() => {
      const headings = Array.from(document.querySelectorAll('h2'));
      const dataFlowH = headings.find(h => h.textContent.includes('Data Flow Summary'));
      if (dataFlowH) {
        dataFlowH.scrollIntoView({ block: 'center' });
      }
    });
    await page.waitForTimeout(500);

    // Click the Data Flow Summary button to expand it
    console.log('Clicking Data Flow Summary to expand...');
    const clicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const dataFlowBtn = buttons.find(b => b.textContent.includes('Data Flow Summary'));
      if (dataFlowBtn) {
        dataFlowBtn.click();
        return true;
      }
      return false;
    });
    console.log('Clicked:', clicked);

    await page.waitForTimeout(1000);

    // Scroll to make expanded content visible
    await page.evaluate(() => {
      const headings = Array.from(document.querySelectorAll('h2'));
      const dataFlowH = headings.find(h => h.textContent.includes('Data Flow Summary'));
      if (dataFlowH) {
        const card = dataFlowH.closest('[class*="card"]') || dataFlowH.parentElement;
        if (card) card.scrollIntoView({ block: 'start' });
      }
    });
    await page.waitForTimeout(500);

    await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/05-data-flow-summary.png', fullPage: true });
    console.log('Screenshot saved: 05-data-flow-summary.png');

    // Check expanded content
    const expandedContent = await page.evaluate(() => {
      // Look for context parameter entries (font-mono elements with arrows)
      const monoElements = Array.from(document.querySelectorAll('[class*="font-mono"]'));
      const contextParams = monoElements.filter(el => {
        const parent = el.closest('[class*="border-t"]');
        return parent && el.textContent.trim().length > 0;
      }).map(el => el.textContent.trim());
      return {
        contextParams,
        // Also check if the expanded section is visible
        hasExpandedSection: !!document.querySelector('[class*="border-t"][class*="p-4"][class*="space-y"]')
      };
    });
    console.log('Expanded section visible:', expandedContent.hasExpandedSection);
    console.log('Context parameters found:', expandedContent.contextParams.length);
    expandedContent.contextParams.forEach(p => console.log('  -', p));
  }

  // Also take a focused screenshot of the bottom of the page
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/05b-data-flow-bottom.png' });
  console.log('Screenshot saved: 05b-data-flow-bottom.png');

  // Console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  console.log('\nConsole errors:', errors.length);
  errors.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));

  await browser.close();
  console.log('\n=== TEST 5 COMPLETE ===');
})().catch(e => { console.error('FATAL ERROR:', e.message); process.exit(1); });
