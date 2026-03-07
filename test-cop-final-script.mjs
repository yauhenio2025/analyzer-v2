import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  try {
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Wait for result to auto-load
    await page.waitForTimeout(3000);

    // Click CoP tab directly (the v2 presentation auto-loaded)
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    if (await copTab.count() > 0) {
      await copTab.click();
      await page.waitForTimeout(2000);
    }

    // Expand all 4 sections one by one and screenshot
    console.log('=== Expanding all sections ===');

    const sectionHeaders = await page.locator('.gen-conditions-section h3').all();
    console.log(`Found ${sectionHeaders.length} section headers`);

    for (let i = 0; i < sectionHeaders.length; i++) {
      const text = await sectionHeaders[i].textContent();
      console.log(`Section ${i}: ${text}`);
    }

    // Take a screenshot with all sections visible (collapsed state shows all titles)
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-final-01-all-sections.png`, fullPage: true });

    // Now expand Constraining Conditions to see its content
    if (sectionHeaders.length > 1) {
      await sectionHeaders[1].click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-final-02-constraining.png`, fullPage: true });
    }

    // Expand Counterfactual Analysis
    if (sectionHeaders.length > 2) {
      await sectionHeaders[2].click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-final-03-counterfactual.png`, fullPage: true });
    }

    // Expand Synthetic Judgment
    if (sectionHeaders.length > 3) {
      await sectionHeaders[3].click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop-final-04-synthetic.png`, fullPage: true });
    }

    // Final summary
    console.log('\n=== FINAL SUMMARY ===');
    console.log(`Total sections visible: ${sectionHeaders.length}`);
    console.log('Expected: 7 sections');
    console.log('Actual: 4 sections');
    console.log('Missing: Path Dependencies, Unacknowledged Debts, Alternative Paths');

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
