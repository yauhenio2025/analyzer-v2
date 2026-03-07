import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

  try {
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // List all result cards and their data
    const cards = await page.evaluate(() => {
      return Array.from(document.querySelectorAll('button.gen-result-card')).map(card => ({
        text: card.textContent?.trim()?.substring(0, 150),
        classes: card.className,
        selected: card.classList.contains('selected') || card.classList.contains('active'),
      }));
    });
    console.log('All result cards:');
    for (const card of cards) {
      console.log(`  ${card.selected ? '[SELECTED] ' : ''}${card.text}`);
    }

    // Click the Comprehensive card (15 ideas, 4 prior works, 11 tactics)
    const compCard = page.locator('button.gen-result-card').filter({ hasText: '15 ideas' }).filter({ hasText: '4 prior works' }).filter({ hasText: '11 tactics' });
    console.log(`\nComprehensive card count: ${await compCard.count()}`);
    if (await compCard.count() > 0) {
      await compCard.first().click();
      await page.waitForTimeout(3000);
    }

    // Check which card is now selected and what result ID it refers to
    const selectedInfo = await page.evaluate(() => {
      const selected = document.querySelector('button.gen-result-card.selected, button.gen-result-card.active, button.gen-result-card[aria-selected="true"]');
      return {
        selectedText: selected?.textContent?.trim()?.substring(0, 200),
        selectedClasses: selected?.className,
      };
    });
    console.log('\nSelected card:', selectedInfo);

    // Check the URL or React state for current result ID
    const currentUrl = page.url();
    console.log('Current URL:', currentUrl);

    // Look at all console messages for result loading info
    console.log('\n=== Console messages about result loading ===');
    for (const msg of consoleMsgs) {
      if (msg.includes('result') || msg.includes('Result') || msg.includes('presentation') || msg.includes('Presentation') || msg.includes('conditions')) {
        console.log(`  ${msg}`);
      }
    }

    // Click CoP tab and take screenshot
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    if (await copTab.count() > 0) {
      await copTab.click();
      await page.waitForTimeout(2000);
    }

    // Check if the view is using structured_data or prose mode
    const viewMode = await page.evaluate(() => {
      // Check for prose mode badge
      const proseBadge = document.querySelector('.gen-prose-mode-badge');
      // Check for extracting notice
      const extracting = document.querySelector('.gen-extracting-notice');

      return {
        hasProseBadge: !!proseBadge,
        proseBadgeText: proseBadge?.textContent,
        isExtracting: !!extracting,
        extractingText: extracting?.textContent,
      };
    });
    console.log('\nView mode:', JSON.stringify(viewMode));

    // Take screenshot
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop5-which-result.png`, fullPage: true });

    // Now specifically check: is this the comprehensive result or the v2_presentation?
    // The comprehensive one has pass6_conditions with prose mode
    // The v2_presentation has structured_data
    const whichResult = await page.evaluate(() => {
      const bodyText = document.body.textContent;
      return {
        hasComprehensiveTag: bodyText.includes('comprehensive'),
        hasV2PresentationTag: bodyText.includes('v2_presentation') || bodyText.includes('v2 orchestrator'),
        has15ideas: bodyText.includes('15 ideas'),
        has4priorWorks: bodyText.includes('4 prior works'),
        has11tactics: bodyText.includes('11 tactics'),
      };
    });
    console.log('Which result:', JSON.stringify(whichResult));

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
