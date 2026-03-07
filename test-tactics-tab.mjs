import puppeteer from 'puppeteer';

const BASE = 'http://localhost:3001';
const PROJECT_ID = 'morozov-benanav-001';
const URL = `${BASE}/p/${PROJECT_ID}/genealogy`;
const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1400,1200'],
    executablePath: '/usr/bin/google-chrome-stable',
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 1200 });

  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({ type: msg.type(), text: msg.text() }));

  console.log('Navigating to genealogy page...');
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 3000));

  // Scroll down to the results section
  await page.evaluate(() => {
    const resultsHeading = Array.from(document.querySelectorAll('h2, h3')).find(h => h.textContent?.includes('Analysis Results'));
    if (resultsHeading) resultsHeading.scrollIntoView({ behavior: 'instant', block: 'start' });
    else window.scrollTo(0, 800);
  });
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-01-results-section.png`, fullPage: false });
  console.log('Screenshot 1: Results section');

  // Click "Tactics & Strategies" tab
  const clickResult = await page.evaluate(() => {
    // Find all elements that could be tabs
    const allEls = document.querySelectorAll('button, a, span, div');
    for (const el of allEls) {
      const text = el.textContent || '';
      // Match "Tactics & Strategies" specifically (the tab text)
      if (text.includes('Tactics & Strategies') && !text.includes('Idea Evolution') && !text.includes('Relationship')) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.click();
        return `Clicked: "${text.trim().substring(0, 60)}" tag=${el.tagName} class="${el.className?.substring(0, 80)}"`;
      }
    }
    // Fallback: try any element containing just "Tactics"
    for (const el of allEls) {
      const text = (el.textContent || '').trim();
      if (text.startsWith('Tactics') && text.length < 40) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.click();
        return `Fallback clicked: "${text}" tag=${el.tagName} class="${el.className?.substring(0, 80)}"`;
      }
    }
    return 'Tactics tab not found';
  });
  console.log('Click result:', clickResult);

  // Wait for tab content to render
  await new Promise(r => setTimeout(r, 2000));

  // Scroll to see the tab content
  await page.evaluate(() => {
    const tabContent = document.querySelector('.gen-tab-content');
    if (tabContent) tabContent.scrollIntoView({ behavior: 'instant', block: 'start' });
  });
  await new Promise(r => setTimeout(r, 500));
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-02-tab-active.png`, fullPage: false });
  console.log('Screenshot 2: Tactics tab active');

  // Full page screenshot
  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-03-fullpage.png`, fullPage: true });
  console.log('Screenshot 3: Full page');

  // Verification
  const v = await page.evaluate(() => {
    const r = {};
    r.tacticCards = document.querySelectorAll('.gen-tactic-card').length;
    r.typeBadges = document.querySelectorAll('.gen-tactic-type-badge').length;
    r.severityBadges = document.querySelectorAll('.gen-severity-badge').length;
    r.trailChains = document.querySelectorAll('.gen-trail-chain').length;
    r.trailSteps = document.querySelectorAll('.gen-trail-step').length;
    r.trailDots = document.querySelectorAll('.gen-trail-dot').length;
    r.trailLabels = document.querySelectorAll('.gen-trail-label').length;
    r.trailConnectors = document.querySelectorAll('.gen-trail-connector').length;
    r.trailQuotes = document.querySelectorAll('.gen-trail-quote').length;
    r.quoteMarks = document.querySelectorAll('.gen-quote-mark').length;
    r.assessments = document.querySelectorAll('.gen-tactic-assessment').length;
    r.groupHeaders = document.querySelectorAll('[class*="group-header"]').length;
    r.ideaTags = document.querySelectorAll('.gen-idea-tag').length;
    r.sectionLabels = document.querySelectorAll('.gen-tactic-section-label').length;

    if (r.trailLabels > 0) {
      r.labelTexts = Array.from(document.querySelectorAll('.gen-trail-label')).slice(0, 12).map(l => l.textContent);
    }
    if (r.typeBadges > 0) {
      r.typeBadgeTexts = Array.from(document.querySelectorAll('.gen-tactic-type-badge')).map(b => b.textContent?.trim());
    }
    if (r.severityBadges > 0) {
      r.severityBadgeTexts = Array.from(document.querySelectorAll('.gen-severity-badge')).map(b => b.textContent?.trim());
    }
    const ghEls = document.querySelectorAll('[class*="group-header"]');
    if (ghEls.length > 0) {
      r.groupHeaderTexts = Array.from(ghEls).map(g => g.textContent?.trim().substring(0, 80));
    }

    // Check active tab
    const tabContent = document.querySelector('.gen-tab-content');
    if (tabContent) {
      r.tabContentFirstChildClass = tabContent.firstElementChild?.className;
      r.tabContentHTML = tabContent.innerHTML.substring(0, 500);
    }

    return r;
  });

  console.log('\n=== VERIFICATION RESULTS ===');
  console.log(JSON.stringify(v, null, 2));

  // Styles
  const styles = await page.evaluate(() => {
    function cs(el) {
      if (!el) return null;
      const s = getComputedStyle(el);
      return {
        display: s.display, bg: s.backgroundColor, color: s.color,
        borderLeft: s.borderLeft?.substring(0, 60),
        padding: s.padding, fontSize: s.fontSize,
        borderRadius: s.borderRadius,
        height: s.height?.substring(0, 20),
        width: s.width?.substring(0, 20),
        lineHeight: s.lineHeight,
      };
    }
    return {
      card: cs(document.querySelector('.gen-tactic-card')),
      dot: cs(document.querySelector('.gen-trail-dot')),
      connector: cs(document.querySelector('.gen-trail-connector')),
      quote: cs(document.querySelector('.gen-trail-quote')),
      typeBadge: cs(document.querySelector('.gen-tactic-type-badge')),
      sevBadge: cs(document.querySelector('.gen-severity-badge')),
    };
  });
  console.log('\n=== COMPUTED STYLES ===');
  console.log(JSON.stringify(styles, null, 2));

  // Zoomed screenshots of cards and evidence trails
  if (v.tacticCards > 0) {
    await page.evaluate(() => {
      const card = document.querySelector('.gen-tactic-card');
      if (card) card.scrollIntoView({ behavior: 'instant', block: 'start' });
    });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-04-first-card.png`, fullPage: false });
    console.log('Screenshot 4: First tactic card');

    await page.evaluate(() => {
      const cards = document.querySelectorAll('.gen-tactic-card');
      if (cards.length > 2) cards[2].scrollIntoView({ behavior: 'instant', block: 'start' });
      else if (cards.length > 1) cards[1].scrollIntoView({ behavior: 'instant', block: 'start' });
    });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-05-more-cards.png`, fullPage: false });
    console.log('Screenshot 5: More cards');

    // Evidence trail close-up
    await page.evaluate(() => {
      const trail = document.querySelector('.gen-trail-chain');
      if (trail) trail.scrollIntoView({ behavior: 'instant', block: 'center' });
    });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-06-evidence-trail.png`, fullPage: false });
    console.log('Screenshot 6: Evidence trail close-up');

    // Group header area
    await page.evaluate(() => {
      const gh = document.querySelector('[class*="group-header"]');
      if (gh) gh.scrollIntoView({ behavior: 'instant', block: 'start' });
    });
    await new Promise(r => setTimeout(r, 500));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-07-group-header.png`, fullPage: false });
    console.log('Screenshot 7: Group header');
  }

  // Console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  if (errors.length > 0) {
    console.log('\n=== CONSOLE ERRORS ===');
    errors.slice(0, 10).forEach(e => console.log(`  ERROR: ${e.text.substring(0, 200)}`));
  } else {
    console.log('\nNo console errors detected.');
  }

  await browser.close();
  console.log('\nDone.');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
