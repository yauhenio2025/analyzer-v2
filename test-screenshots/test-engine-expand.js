const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({type: msg.type(), text: msg.text()}));

  // ==========================================================================
  // TEST 4: Engine Card Expansion
  // ==========================================================================
  console.log('\n=== TEST 4: Engine Card Expansion ===');

  await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(5000);

  // Find the first engine card and click it to expand
  // Engine cards are buttons with engine names
  const engineCards = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    return buttons.filter(b => {
      // Engine cards contain CPU icon and engine name link
      const hasLink = b.querySelector('a[href*="/engines/"]');
      return !!hasLink;
    }).map((b, i) => ({
      index: i,
      text: b.textContent.trim().substring(0, 100),
      engineLink: b.querySelector('a[href*="/engines/"]')?.getAttribute('href')
    }));
  });
  console.log('Engine card buttons found:', engineCards.length);
  engineCards.slice(0, 3).forEach(c => console.log('  -', c.engineLink, ':', c.text.substring(0, 60)));

  // Click the first engine card
  if (engineCards.length > 0) {
    console.log('\nClicking first engine card:', engineCards[0].engineLink);

    // Click the button (not the link inside it)
    const firstEngineButton = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const engineBtn = buttons.find(b => b.querySelector('a[href*="/engines/"]'));
      if (engineBtn) {
        engineBtn.click();
        return true;
      }
      return false;
    });
    console.log('Clicked:', firstEngineButton);

    await page.waitForTimeout(1000);

    // Scroll to make expanded content visible
    await page.evaluate(() => {
      const expandedSection = document.querySelector('[class*="border-t"][class*="bg-gray-50"]');
      if (expandedSection) expandedSection.scrollIntoView({ block: 'center' });
    });

    await page.waitForTimeout(500);

    await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/04-engine-card-expanded.png', fullPage: true });
    console.log('Screenshot saved: 04-engine-card-expanded.png');

    // Check if expanded content is now visible
    const expandedContent = await page.evaluate(() => {
      const expandedSections = document.querySelectorAll('[class*="border-t"][class*="bg-gray-50"]');
      if (expandedSections.length > 0) {
        const section = expandedSections[0];
        return {
          hasProblematique: section.textContent.includes('Problematique') || section.textContent.includes('problematique'),
          hasDimensions: section.textContent.includes('Dimensions') || section.textContent.includes('dimension'),
          hasCapabilities: section.textContent.includes('Capabilities') || section.textContent.includes('capability'),
          hasLinks: section.querySelectorAll('a').length > 0,
          text: section.textContent.trim().substring(0, 1000)
        };
      }
      return null;
    });

    if (expandedContent) {
      console.log('\nExpanded content found:');
      console.log('  Has Problematique:', expandedContent.hasProblematique);
      console.log('  Has Dimensions:', expandedContent.hasDimensions);
      console.log('  Has Capabilities:', expandedContent.hasCapabilities);
      console.log('  Has Links:', expandedContent.hasLinks);
      console.log('  Text preview:', expandedContent.text.substring(0, 500));
    } else {
      console.log('WARNING: No expanded content found!');

      // Debug: check what elements exist
      const debugInfo = await page.evaluate(() => {
        const allBorderT = document.querySelectorAll('[class*="border-t"]');
        return {
          borderTCount: allBorderT.length,
          bodyText: document.body.innerText.includes('Problematique')
        };
      });
      console.log('Debug:', debugInfo);
    }
  }

  // Console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  console.log('\nConsole errors:', errors.length);
  errors.forEach(e => console.log('  ERROR:', e.text.substring(0, 200)));

  await browser.close();
  console.log('\n=== TEST 4 COMPLETE ===');
})().catch(e => { console.error('FATAL ERROR:', e.message); process.exit(1); });
