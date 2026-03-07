import { chromium } from 'playwright';

const URL = 'https://analyzer-mgmt-frontend.onrender.com/views';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

  console.log('Navigating to Views page...');
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });

  // Wait a moment for any dynamic content
  await page.waitForTimeout(3000);

  // Screenshot 1: Full page
  console.log('Taking full page screenshot...');
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-full-page.png',
    fullPage: true
  });
  console.log('Full page screenshot saved.');

  // Get the page text content for analysis
  const bodyText = await page.textContent('body');
  console.log('\n=== PAGE TEXT CONTENT ===');
  console.log(bodyText);
  console.log('=== END PAGE TEXT ===\n');

  // Look for view count
  const viewCountMatch = bodyText.match(/(\d+)\s*views?\s*(defined|total|found)?/i);
  if (viewCountMatch) {
    console.log(`View count found: ${viewCountMatch[0]}`);
  }

  // Check for specific views and their nesting
  const checks = [
    'Target Work Profile',
    'Idea Evolution Map',
    'Conditions of Possibility',
    'Enabling Conditions',
    'Constraining Conditions',
    'Counterfactual Analysis',
    'Synthetic Judgment',
    'Per-Work Scan Detail',
    'Conceptual Framework',
  ];

  console.log('\n=== VIEW PRESENCE CHECK ===');
  for (const view of checks) {
    const found = bodyText.includes(view);
    console.log(`${found ? '[FOUND]' : '[MISSING]'} ${view}`);
  }

  // Try to find and click expandable sections
  // Look for elements that might be expandable (accordion, tree nodes, etc.)
  const expandableElements = await page.$$('[class*="expand"], [class*="toggle"], [class*="collapse"], [class*="accordion"], [role="button"], [class*="tree"], button, [class*="chevron"], [class*="arrow"]');
  console.log(`\nFound ${expandableElements.length} potentially expandable elements`);

  // Try to get the DOM structure to understand the hierarchy
  const htmlContent = await page.content();

  // Look for "Conditions of Possibility" and try to expand it
  console.log('\n=== TRYING TO EXPAND SECTIONS ===');

  // Find all elements containing "Conditions of Possibility"
  const copElements = await page.$$('text=Conditions of Possibility');
  console.log(`Found ${copElements.length} elements with "Conditions of Possibility"`);

  for (let i = 0; i < copElements.length; i++) {
    try {
      await copElements[i].click();
      await page.waitForTimeout(1000);
      console.log(`Clicked COP element ${i}`);
    } catch (e) {
      console.log(`Could not click COP element ${i}: ${e.message}`);
    }
  }

  // Screenshot 2: After expanding COP
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-cop-expanded.png',
    fullPage: true
  });
  console.log('COP expanded screenshot saved.');

  // Get updated text
  const bodyText2 = await page.textContent('body');

  // Look for "children" counts
  const childrenMatches = bodyText2.match(/\d+ child(ren)?/gi);
  if (childrenMatches) {
    console.log('\n=== CHILDREN COUNTS FOUND ===');
    childrenMatches.forEach(m => console.log(`  ${m}`));
  }

  // Find "Target Work Profile" and try to expand it
  const twpElements = await page.$$('text=Target Work Profile');
  console.log(`\nFound ${twpElements.length} elements with "Target Work Profile"`);

  for (let i = 0; i < twpElements.length; i++) {
    try {
      await twpElements[i].click();
      await page.waitForTimeout(1000);
      console.log(`Clicked TWP element ${i}`);
    } catch (e) {
      console.log(`Could not click TWP element ${i}: ${e.message}`);
    }
  }

  // Screenshot 3: After expanding TWP
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-twp-expanded.png',
    fullPage: true
  });
  console.log('TWP expanded screenshot saved.');

  // Find "Idea Evolution Map" and check its children
  const iemElements = await page.$$('text=Idea Evolution Map');
  console.log(`\nFound ${iemElements.length} elements with "Idea Evolution Map"`);

  for (let i = 0; i < iemElements.length; i++) {
    try {
      await iemElements[i].click();
      await page.waitForTimeout(1000);
      console.log(`Clicked IEM element ${i}`);
    } catch (e) {
      console.log(`Could not click IEM element ${i}: ${e.message}`);
    }
  }

  // Screenshot 4: After expanding IEM
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-iem-expanded.png',
    fullPage: true
  });
  console.log('IEM expanded screenshot saved.');

  // Final full page screenshot with everything expanded
  const bodyText3 = await page.textContent('body');
  console.log('\n=== FINAL PAGE TEXT (after all expansions) ===');
  console.log(bodyText3);

  await browser.close();
  console.log('\nDone!');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
