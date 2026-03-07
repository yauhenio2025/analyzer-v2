import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await context.newPage();

const consoleMsgs = [];
page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

console.log('=== Navigate to /genealogy ===');
await page.goto('https://the-critic-1.onrender.com/genealogy', { waitUntil: 'networkidle', timeout: 90000 });
await page.waitForTimeout(3000);

// Import job
console.log('=== Importing ===');
await page.$eval('input[placeholder*="job"]', el => el.value = '');
await page.fill('input[placeholder*="job"]', 'job-7d32be316d06');
await page.click('button:has-text("Import")');

// Wait for import
let ready = false;
for (let i = 0; i < 40; i++) {
  await page.waitForTimeout(5000);
  const state = await page.evaluate(() => {
    if (document.body.innerText.includes('Import failed')) return 'FAILED';
    if (document.body.innerText.includes('Relationship')) return 'READY';
    return 'IMPORTING';
  });
  if (i % 6 === 0) console.log(`  ${(i+1)*5}s: ${state}`);
  if (state === 'READY') { ready = true; break; }
  if (state === 'FAILED') break;
}

if (!ready) {
  console.log('Import did not complete');
  await browser.close();
  process.exit(1);
}

// Click Relationship Landscape tab
console.log('\n=== TAB 1: Relationship Landscape ===');
await page.click('button:has-text("Relationship Landscape")');
await page.waitForTimeout(2000);

// Scroll to results
await page.evaluate(() => window.scrollTo(0, 700));
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/tab1-detail.png', fullPage: false });

// Get the relationship landscape data
const tab1Data = await page.evaluate(() => {
  // Get the v2Presentation object from React state
  // Look at the actual DOM for the relationship cards
  const resultsArea = document.querySelector('.gen-results-area') || 
                       document.querySelector('[class*="result"]');
  
  // Find all card-like elements in the results area after "Direct Precursor"
  const allCards = document.querySelectorAll('[class*="rel-card"], [class*="relationship-card"], [class*="card"]');
  const cardInfo = [];
  for (const card of allCards) {
    const rect = card.getBoundingClientRect();
    // Only cards in the lower half of the page (results area)
    if (rect.top > 400) {
      cardInfo.push({
        classes: card.className,
        text: card.innerText.substring(0, 200),
        childCount: card.children.length,
        innerHTML: card.innerHTML.substring(0, 300),
        width: rect.width,
        height: rect.height
      });
    }
  }
  return cardInfo;
});
console.log('Tab 1 cards in results area:', JSON.stringify(tab1Data, null, 2));

// Also get the full body of the Relationship Landscape results section
const rlSection = await page.evaluate(() => {
  // The tab content area
  const tabContent = document.querySelector('.gen-tab-content, [class*="tab-content"]');
  if (tabContent) return tabContent.innerHTML.substring(0, 5000);
  
  // Fallback: get everything after the tab buttons
  const tabButtons = document.querySelectorAll('button');
  const rlBtn = Array.from(tabButtons).find(b => b.textContent.includes('Relationship Landscape'));
  if (rlBtn) {
    const parent = rlBtn.closest('[class*="tab"]')?.parentElement;
    if (parent) return parent.innerHTML.substring(0, 5000);
  }
  return 'SECTION_NOT_FOUND';
});
console.log('\nRelationship Landscape section HTML:');
console.log(rlSection);

await browser.close();
