import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const screenshotDir = __dirname;

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  const consoleMessages = [];
  page.on('console', msg => consoleMessages.push({ type: msg.type(), text: msg.text() }));
  const networkErrors = [];
  page.on('response', response => {
    if (response.status() >= 400) networkErrors.push({ url: response.url(), status: response.status() });
  });

  // Test search
  console.log('--- Test: Search filter ---');
  await page.goto('http://localhost:3000/transformations', { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(3000);

  const searchInput = await page.$('input[placeholder="Search templates..."]');
  if (searchInput) {
    await searchInput.fill('conditions');
    await page.waitForTimeout(1000);
    const links = await page.$$('a[href^="/transformations/"]');
    const templateLinks = [];
    for (const link of links) {
      const href = await link.getAttribute('href');
      if (!href.endsWith('/new')) templateLinks.push(href);
    }
    console.log('Search "conditions" results:', templateLinks.length, 'templates');
    for (const href of templateLinks) console.log('  -', href);
    await page.screenshot({ path: path.join(screenshotDir, '08-search-filter.png'), fullPage: true });

    // Clear search
    await searchInput.fill('');
    await page.waitForTimeout(500);
  }

  // Test type filter
  console.log('\n--- Test: Type filter ---');
  const typeSelect = await page.$('select');
  if (typeSelect) {
    await typeSelect.selectOption('schema_map');
    await page.waitForTimeout(1000);
    const links2 = await page.$$('a[href^="/transformations/"]');
    const templateLinks2 = [];
    for (const link of links2) {
      const href = await link.getAttribute('href');
      if (!href.endsWith('/new')) templateLinks2.push(href);
    }
    console.log('Filter "schema_map" results:', templateLinks2.length, 'templates');
    for (const href of templateLinks2) console.log('  -', href);
    await page.screenshot({ path: path.join(screenshotDir, '09-type-filter.png'), fullPage: true });

    // Reset filter
    await typeSelect.selectOption('');
    await page.waitForTimeout(500);
  }

  // Test type filter with llm_extract
  console.log('\n--- Test: Type filter llm_extract ---');
  if (typeSelect) {
    await typeSelect.selectOption('llm_extract');
    await page.waitForTimeout(1000);
    const links3 = await page.$$('a[href^="/transformations/"]');
    const templateLinks3 = [];
    for (const link of links3) {
      const href = await link.getAttribute('href');
      if (!href.endsWith('/new')) templateLinks3.push(href);
    }
    console.log('Filter "llm_extract" results:', templateLinks3.length, 'templates');
    for (const href of templateLinks3) console.log('  -', href);
  }

  // Print issues
  const issues = consoleMessages.filter(m => m.type === 'error' || m.type === 'warning');
  if (issues.length > 0) {
    console.log('\n--- Console Issues ---');
    for (const msg of issues) console.log(`[${msg.type}] ${msg.text.substring(0, 300)}`);
  } else {
    console.log('\nNo console errors or warnings!');
  }
  if (networkErrors.length > 0) {
    console.log('\n--- Network Errors ---');
    for (const err of networkErrors) console.log(`[${err.status}] ${err.url}`);
  } else {
    console.log('No network errors!');
  }

  await browser.close();
}

main().catch(err => { console.error('Test failed:', err.message); process.exit(1); });
