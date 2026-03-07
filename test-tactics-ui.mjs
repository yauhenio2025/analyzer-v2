import puppeteer from 'puppeteer';

const URL = 'http://localhost:3001/p/morozov-on-varoufakis/genealogy';
const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  console.log('=== Step 1: Navigate to genealogy page ===');
  try {
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });
    console.log('Page loaded successfully');
  } catch (e) {
    console.log('Page load issue:', e.message);
    // Try waiting a bit more
    await new Promise(r => setTimeout(r, 3000));
  }

  // Take initial screenshot
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-01-initial.png`, fullPage: false });
  console.log('Screenshot 1 saved: tactics-01-initial.png');

  // Get page title and check for errors
  const title = await page.title();
  console.log('Page title:', title);

  // Check console errors
  const consoleMessages = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleMessages.push(msg.text());
  });

  // === Step 2: Find and click the Tactics & Strategies tab ===
  console.log('\n=== Step 2: Looking for Tactics & Strategies tab ===');

  // Wait a moment for any dynamic content
  await new Promise(r => setTimeout(r, 2000));

  // Find all tabs/buttons that might be the Tactics tab
  const allButtons = await page.$$eval('button, [role="tab"], .tab, [class*="tab"]', els =>
    els.map(e => ({ text: e.textContent.trim().substring(0, 80), tag: e.tagName, classes: e.className.substring(0, 100) }))
  );
  console.log('Found clickable elements:', JSON.stringify(allButtons.slice(0, 20), null, 2));

  // Try to find the Tactics tab specifically
  const tacticsTab = await page.evaluate(() => {
    const allEls = document.querySelectorAll('button, [role="tab"], a, div[class*="tab"], span');
    for (const el of allEls) {
      const text = el.textContent.trim().toLowerCase();
      if (text.includes('tactics') || text.includes('strateg')) {
        return { found: true, text: el.textContent.trim().substring(0, 80), tag: el.tagName, id: el.id, classes: el.className.substring(0, 100) };
      }
    }
    return { found: false };
  });
  console.log('Tactics tab search result:', JSON.stringify(tacticsTab, null, 2));

  if (tacticsTab.found) {
    // Click on it
    const clicked = await page.evaluate(() => {
      const allEls = document.querySelectorAll('button, [role="tab"], a, div[class*="tab"], span');
      for (const el of allEls) {
        const text = el.textContent.trim().toLowerCase();
        if (text.includes('tactics') || text.includes('strateg')) {
          el.click();
          return true;
        }
      }
      return false;
    });
    console.log('Clicked tactics tab:', clicked);

    // Wait for content to render
    await new Promise(r => setTimeout(r, 3000));

    // Take screenshot after clicking
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-02-after-click.png`, fullPage: false });
    console.log('Screenshot 2 saved: tactics-02-after-click.png');

    // === Step 3: Analyze the tactic cards ===
    console.log('\n=== Step 3: Analyzing tactic card content ===');

    const cardAnalysis = await page.evaluate(() => {
      const body = document.body.innerHTML;
      const results = {
        // Look for evidence trail markers
        hasEvidenceTrail: body.includes('Prior work') || body.includes('prior-work') || body.includes('evidence-trail') || body.includes('Evidence Trail'),
        hasSeverity: body.includes('severity') || body.includes('Severity') || body.includes('critical') || body.includes('high') || body.includes('moderate'),
        hasTypeBadges: body.includes('type-badge') || body.includes('TypeBadge'),
        hasGroupHeaders: body.includes('group-header') || body.includes('GroupHeader'),
        hasAssessment: body.includes('Assessment') || body.includes('assessment'),
        hasCurrentWork: body.includes('Current work') || body.includes('current-work'),
        // Count cards
        cardCount: document.querySelectorAll('[class*="card"], [class*="Card"]').length,
        // Look for any tactic-specific content
        tacticMentions: (body.match(/tactic/gi) || []).length,
        strategyMentions: (body.match(/strateg/gi) || []).length,
      };

      // Get visible text snippets around "tactic" mentions
      const allText = document.body.innerText;
      const lines = allText.split('\n').filter(l => l.trim().length > 0);
      results.visibleLineCount = lines.length;
      results.sampleLines = lines.slice(0, 50).map(l => l.substring(0, 120));

      return results;
    });
    console.log('Card analysis:', JSON.stringify(cardAnalysis, null, 2));

    // === Step 4: Scroll down and take more screenshots ===
    console.log('\n=== Step 4: Scrolling down to see more cards ===');

    // Scroll down by 800px
    await page.evaluate(() => window.scrollBy(0, 800));
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-03-scrolled-1.png`, fullPage: false });
    console.log('Screenshot 3 saved: tactics-03-scrolled-1.png');

    // Scroll down more
    await page.evaluate(() => window.scrollBy(0, 800));
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-04-scrolled-2.png`, fullPage: false });
    console.log('Screenshot 4 saved: tactics-04-scrolled-2.png');

    // Scroll more
    await page.evaluate(() => window.scrollBy(0, 800));
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-05-scrolled-3.png`, fullPage: false });
    console.log('Screenshot 5 saved: tactics-05-scrolled-3.png');

    // Get a more detailed DOM analysis of the cards
    console.log('\n=== Step 5: Detailed card DOM analysis ===');
    const detailedAnalysis = await page.evaluate(() => {
      // Find the main content area
      const mainContent = document.querySelector('main') || document.querySelector('[class*="content"]') || document.body;

      // Look for specific patterns in rendered HTML
      const html = mainContent.innerHTML;

      return {
        // Check for specific design elements
        hasBadgesWithColors: !!html.match(/background-color.*badge|badge.*background-color|class="[^"]*badge[^"]*"/i),
        hasTrailSections: !!html.match(/prior.*work|current.*work|assessment/i),
        hasSeverityIndicators: !!html.match(/critical|high|moderate|low|severity/i),
        // Get all unique class names containing key terms
        cardClasses: [...new Set(
          [...html.matchAll(/class="([^"]*(?:card|tactic|badge|trail|severity|group)[^"]*)"/gi)]
            .map(m => m[1])
        )].slice(0, 30),
        // Get the structure of the first few cards
        firstCardHTML: (() => {
          const cards = document.querySelectorAll('[class*="card"], [class*="tactic"]');
          if (cards.length > 0) {
            return cards[0].outerHTML.substring(0, 2000);
          }
          return 'No cards found';
        })(),
        totalCards: document.querySelectorAll('[class*="card"], [class*="tactic"]').length,
      };
    });
    console.log('Detailed analysis:', JSON.stringify(detailedAnalysis, null, 2));

  } else {
    console.log('Tactics tab NOT found. Taking full page screenshot to understand layout.');
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-02-no-tab-fullpage.png`, fullPage: true });

    // Dump all visible text to understand what we're looking at
    const pageText = await page.evaluate(() => document.body.innerText.substring(0, 5000));
    console.log('Page text (first 5000 chars):', pageText);
  }

  // Check for console errors
  if (consoleMessages.length > 0) {
    console.log('\n=== Console Errors ===');
    consoleMessages.forEach(msg => console.log('ERROR:', msg));
  }

  await browser.close();
  console.log('\nDone!');
}

run().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
