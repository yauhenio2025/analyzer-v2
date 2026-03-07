import { chromium } from 'playwright';

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    await page.goto('http://localhost:3000/views/genealogy_target_profile', {
      waitUntil: 'networkidle', timeout: 15000
    });
    await page.waitForTimeout(500);

    // Click Renderer tab
    await page.locator('button:has-text("Renderer")').click();
    await page.waitForTimeout(1500);

    // Check which renderer has "current" badge and blue highlight
    const rendererItems = await page.evaluate(() => {
      // Find all renderer buttons in the scored list
      const buttons = document.querySelectorAll('button.w-full');
      return Array.from(buttons).map(btn => {
        const text = btn.textContent || '';
        const hasCurrent = text.toLowerCase().includes('current');
        const hasBlueClasses = btn.className.includes('blue');
        const percentMatch = text.match(/(\d+)%/);
        const nameMatch = text.match(/\d+%\s+(.+?)(?:\(|$)/);
        return {
          percentage: percentMatch ? percentMatch[1] + '%' : 'N/A',
          name: nameMatch ? nameMatch[1].trim() : text.substring(0, 50),
          hasCurrent,
          hasBlueClasses,
          className: btn.className.substring(0, 200)
        };
      });
    });

    console.log('All renderer items in the list:');
    rendererItems.forEach((item, i) => {
      const marker = item.hasCurrent ? ' <-- CURRENT' : '';
      const blue = item.hasBlueClasses ? ' [BLUE HIGHLIGHT]' : '';
      console.log(`  ${i+1}. ${item.percentage} ${item.name}${marker}${blue}`);
    });

    // Now check what renderer_type the view actually has
    const viewData = await page.evaluate(() => {
      // The view data should be available in the React component state
      // Let's check the header badges
      const badges = document.querySelectorAll('.badge');
      return Array.from(badges).map(b => b.textContent?.trim());
    });
    console.log('\nHeader badges:', viewData);

    // Check for the "accordion" badge in the header
    const accordionBadge = viewData.find(b => b?.includes('accordion'));
    console.log(`Header shows renderer_type badge: ${accordionBadge || 'NOT FOUND'}`);

    // Get the actual comparison happening
    const comparisonCheck = await page.evaluate(() => {
      // Look for accordion-related items
      const allText = document.body.innerText;
      const lines = allText.split('\n');
      return lines.filter(l =>
        l.includes('Accordion') || l.includes('accordion') || l.includes('Tab Container')
      ).slice(0, 10);
    });
    console.log('\nAccordion/Tab Container mentions:');
    comparisonCheck.forEach(l => console.log(`  ${l.trim()}`));

    console.log('\n=== DONE ===');

  } catch (err) {
    console.error('Test error:', err.message);
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
