import puppeteer from 'puppeteer';

const BASE_URL = 'http://localhost:3001';
const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  const consoleErrors = [];
  page.on('console', msg => {
    if (msg.type() === 'error') consoleErrors.push(msg.text().substring(0, 200));
  });

  // Step 1: Navigate to the genealogy page
  console.log('=== Step 1: Navigate to genealogy page ===');
  await page.goto(`${BASE_URL}/p/morozov-benanav-001/genealogy`, {
    waitUntil: 'networkidle2',
    timeout: 30000
  });
  await new Promise(r => setTimeout(r, 3000));

  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-01-genealogy-page.png`, fullPage: false });
  console.log('Screenshot 1: genealogy page');

  // Check if we see analysis results
  const pageState = await page.evaluate(() => {
    const text = document.body.innerText;
    return {
      url: window.location.href,
      hasResults: text.includes('View Results') || text.includes('tactics') || text.includes('Tactics'),
      visibleText: text.substring(0, 2000),
    };
  });
  console.log('Page URL:', pageState.url);
  console.log('Has results mention:', pageState.hasResults);

  // Step 2: Check if there are analysis results listed
  console.log('\n=== Step 2: Looking for analysis results to click ===');

  // Look for clickable results or the results list
  const resultInfo = await page.evaluate(() => {
    const text = document.body.innerText;
    // Look for the analysis result summary
    const has10Tactics = text.includes('10 tactics');
    const hasViewResults = text.includes('View Results') || text.includes('view results') || text.includes('View');
    const hasResultCards = document.querySelectorAll('.gen-result-card, [class*="result-card"], [class*="result-row"]').length;

    // Look for clickable elements that might be results
    const clickableResults = [...document.querySelectorAll('button, a, [class*="result"], [class*="click"]')]
      .filter(el => {
        const t = el.textContent.trim().toLowerCase();
        return t.includes('view') || t.includes('result') || t.includes('tactic') || t.includes('comprehensive');
      })
      .map(el => ({ text: el.textContent.trim().substring(0, 80), tag: el.tagName, classes: el.className.substring(0, 100) }));

    return {
      has10Tactics,
      hasViewResults,
      hasResultCards,
      clickableResults,
    };
  });
  console.log('Result info:', JSON.stringify(resultInfo, null, 2));

  // Try to click on the result
  const clickedResult = await page.evaluate(() => {
    // First try: explicit result cards
    const resultCards = document.querySelectorAll('.gen-result-card, [class*="result-card"], [class*="result-row"]');
    if (resultCards.length > 0) {
      resultCards[0].click();
      return 'Clicked result card';
    }

    // Second try: any button/link mentioning comprehensive or view
    const btns = document.querySelectorAll('button, a');
    for (const btn of btns) {
      const t = btn.textContent.trim().toLowerCase();
      if (t.includes('view') && (t.includes('result') || t.includes('comprehensive'))) {
        btn.click();
        return `Clicked: ${btn.textContent.trim().substring(0, 60)}`;
      }
    }

    // Third try: anything with 10 tactics or result-related
    for (const btn of btns) {
      const t = btn.textContent.trim().toLowerCase();
      if (t.includes('10 tactic') || t.includes('3 ideas')) {
        btn.click();
        return `Clicked: ${btn.textContent.trim().substring(0, 60)}`;
      }
    }

    return null;
  });
  console.log('Clicked result:', clickedResult);

  await new Promise(r => setTimeout(r, 3000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-02-after-click-result.png`, fullPage: false });
  console.log('Screenshot 2: after clicking result');

  // Step 3: Look for the Evolution Tactics tab
  console.log('\n=== Step 3: Looking for Evolution Tactics tab ===');

  const tabsState = await page.evaluate(() => {
    const tabs = [...document.querySelectorAll('button, [role="tab"]')]
      .filter(el => el.textContent.trim().length > 0 && el.textContent.trim().length < 60)
      .map(el => ({ text: el.textContent.trim(), classes: el.className.substring(0, 80), active: el.className.includes('active') }));
    return tabs;
  });
  console.log('Available tabs:', JSON.stringify(tabsState, null, 2));

  // Click the Evolution Tactics tab
  const clickedTacticsTab = await page.evaluate(() => {
    const btns = document.querySelectorAll('button');
    for (const btn of btns) {
      const t = btn.textContent.trim().toLowerCase();
      if (t.includes('evolution tactics') || t.includes('tactics')) {
        btn.click();
        return btn.textContent.trim();
      }
    }
    return null;
  });
  console.log('Clicked tactics tab:', clickedTacticsTab);

  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-03-tactics-tab.png`, fullPage: false });
  console.log('Screenshot 3: tactics tab content');

  // Step 4: Analyze the rendered tactic cards
  console.log('\n=== Step 4: Analyzing rendered tactic cards ===');

  const tacticAnalysis = await page.evaluate(() => {
    const html = document.body.innerHTML;
    const text = document.body.innerText;

    return {
      // Card structure
      tacticCards: document.querySelectorAll('.gen-tactic-card').length,
      typeBadges: document.querySelectorAll('.gen-tactic-type-badge').length,
      severityBadges: document.querySelectorAll('.gen-severity-badge').length,
      evidenceTrails: document.querySelectorAll('.gen-evidence-trail').length,
      trailSteps: document.querySelectorAll('.gen-trail-step').length,
      priorWorkSteps: document.querySelectorAll('.gen-trail-step--prior').length,
      currentWorkSteps: document.querySelectorAll('.gen-trail-step--current').length,
      assessmentSteps: document.querySelectorAll('.gen-trail-step--assessment').length,
      trailQuotes: document.querySelectorAll('.gen-trail-quote').length,
      ideaTags: document.querySelectorAll('.gen-idea-tag').length,
      trailConnectors: document.querySelectorAll('.gen-trail-connector').length,

      // Group headers
      groupHeaders: document.querySelectorAll('.card-grid-group-header, [class*="group-header"]').length,
      groupHeaderTexts: [...document.querySelectorAll('.card-grid-group-header, [class*="group-header"]')]
        .map(el => el.textContent.trim().substring(0, 100)),

      // Text content checks
      hasSurplusPopulation: text.includes('Surplus Population'),
      hasSilentRevision: text.includes('Silent Revision'),
      hasPriorWork: text.includes('Prior work'),
      hasCurrentWork: text.includes('Current work'),
      hasAssessment: text.includes('Assessment'),
      hasEvidenceTrail: text.includes('Evidence trail'),

      // Severity mentions
      hasMajor: text.includes('major'),
      hasModerate: text.includes('moderate'),
      hasMinor: text.includes('minor'),

      // Color badges
      typeBadgeTexts: [...document.querySelectorAll('.gen-tactic-type-badge')]
        .map(el => el.textContent.trim()),
      severityBadgeTexts: [...document.querySelectorAll('.gen-severity-badge')]
        .map(el => el.textContent.trim()),

      // CardGrid or other renderer
      hasCardGrid: html.includes('card-grid'),
      hasTacticsGrid: html.includes('gen-tactics-grid'),

      // Sample text from the area
      visibleText: text.substring(0, 3000),
    };
  });
  console.log('Tactic analysis:', JSON.stringify(tacticAnalysis, null, 2));

  // Step 5: Scroll down to see more cards
  console.log('\n=== Step 5: Scrolling through tactic cards ===');

  await page.evaluate(() => window.scrollBy(0, 600));
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-04-scrolled-1.png`, fullPage: false });
  console.log('Screenshot 4: scrolled down 1');

  await page.evaluate(() => window.scrollBy(0, 600));
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-05-scrolled-2.png`, fullPage: false });
  console.log('Screenshot 5: scrolled down 2');

  await page.evaluate(() => window.scrollBy(0, 600));
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-06-scrolled-3.png`, fullPage: false });
  console.log('Screenshot 6: scrolled down 3');

  await page.evaluate(() => window.scrollBy(0, 600));
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-07-scrolled-4.png`, fullPage: false });
  console.log('Screenshot 7: scrolled down 4');

  await page.evaluate(() => window.scrollBy(0, 600));
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/final-08-scrolled-5.png`, fullPage: false });
  console.log('Screenshot 8: scrolled down 5');

  // Step 6: Take a full page screenshot
  await page.evaluate(() => window.scrollTo(0, 0));
  await new Promise(r => setTimeout(r, 500));

  // First let's get the first card's HTML for detailed inspection
  const firstCardHTML = await page.evaluate(() => {
    const card = document.querySelector('.gen-tactic-card');
    return card ? card.outerHTML.substring(0, 3000) : 'No card found';
  });
  console.log('\n=== First card HTML ===');
  console.log(firstCardHTML);

  // Console errors summary
  const uniqueErrors = [...new Set(consoleErrors)].filter(e => !e.includes('ERR_CONNECTION_REFUSED') && !e.includes('Failed to fetch'));
  if (uniqueErrors.length > 0) {
    console.log('\n=== Non-trivial Console Errors ===');
    uniqueErrors.forEach(e => console.log('  -', e));
  } else {
    console.log('\n=== No non-trivial console errors ===');
  }

  await browser.close();
  console.log('\nDone!');
}

run().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
