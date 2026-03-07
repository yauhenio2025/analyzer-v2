import { chromium } from 'playwright';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const screenshotDir = __dirname;

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  // Collect network errors
  const networkErrors = [];
  page.on('response', response => {
    if (response.status() >= 400) {
      networkErrors.push({ url: response.url(), status: response.status() });
    }
  });

  const testName = process.argv[2] || 'list';

  try {
    if (testName === 'list') {
      console.log('--- Test 1: Transformations List Page ---');
      await page.goto('http://localhost:3000/transformations', { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(screenshotDir, '01-list-page.png'), fullPage: true });
      console.log('Screenshot saved: 01-list-page.png');

      // Check what's visible
      const heading = await page.$('h1');
      if (heading) {
        console.log('Page heading:', await heading.textContent());
      } else {
        console.log('No h1 found');
      }

      // Check for error states
      const errorEl = await page.$('.text-red-600');
      if (errorEl) {
        const errorText = await errorEl.textContent();
        console.log('ERROR on page:', errorText);
      } else {
        console.log('No error state visible - good!');
      }

      // Count links to template details
      const templateLinks = await page.$$('a[href^="/transformations/"]');
      console.log('Template card links:', templateLinks.length);

      // Count type badges
      const badges = await page.$$('[class*="rounded-full"]');
      console.log('Type badges (rounded-full):', badges.length);

      // Get template names
      for (const link of templateLinks.slice(0, 5)) {
        const href = await link.getAttribute('href');
        const name = await link.$('h3');
        const nameText = name ? await name.textContent() : 'unknown';
        console.log(`  - ${nameText} -> ${href}`);
      }

    } else if (testName === 'detail') {
      console.log('--- Test 2: Click first template -> Detail Page ---');
      await page.goto('http://localhost:3000/transformations', { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);

      // Get the first template link
      const firstLink = await page.$('a[href^="/transformations/"]');
      if (firstLink) {
        const href = await firstLink.getAttribute('href');
        console.log('Navigating to:', href);

        // Navigate directly
        await page.goto(`http://localhost:3000${href}`, { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(3000);
        await page.screenshot({ path: path.join(screenshotDir, '02-detail-page.png'), fullPage: true });
        console.log('Screenshot saved: 02-detail-page.png');

        const h1 = await page.$('h1');
        if (h1) {
          console.log('Detail page heading:', await h1.textContent());
        }

        // Check tabs
        const allButtons = await page.$$('button');
        const tabLabels = [];
        for (const btn of allButtons) {
          const cls = await btn.getAttribute('class');
          if (cls && cls.includes('border-b')) {
            tabLabels.push(await btn.textContent());
          }
        }
        console.log('Tabs found:', tabLabels.join(', '));

        // Click Specification tab
        for (const btn of allButtons) {
          const text = await btn.textContent();
          if (text === 'Specification') {
            console.log('Clicking Specification tab...');
            await btn.click();
            await page.waitForTimeout(1000);
            await page.screenshot({ path: path.join(screenshotDir, '03-specification-tab.png'), fullPage: true });
            console.log('Screenshot saved: 03-specification-tab.png');
            break;
          }
        }
      } else {
        console.log('ERROR: No template links found on list page!');
      }

    } else if (testName === 'create') {
      console.log('--- Test 3: Create New Template ---');
      await page.goto('http://localhost:3000/transformations/new', { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: path.join(screenshotDir, '04-create-form.png'), fullPage: true });
      console.log('Screenshot saved: 04-create-form.png');

      const h1 = await page.$('h1');
      if (h1) {
        console.log('Create page heading:', await h1.textContent());
      }

      // Click Specification tab
      const allButtons = await page.$$('button');
      for (const btn of allButtons) {
        const text = await btn.textContent();
        if (text === 'Specification') {
          await btn.click();
          await page.waitForTimeout(500);
          await page.screenshot({ path: path.join(screenshotDir, '05-create-specification.png'), fullPage: true });
          console.log('Screenshot saved: 05-create-specification.png');
          break;
        }
      }

      // Click different type buttons to show conditional fields
      const typeButtons = await page.$$('button');
      for (const btn of typeButtons) {
        const text = await btn.textContent();
        if (text && text.trim() === 'llm_extract') {
          await btn.click();
          await page.waitForTimeout(500);
          await page.screenshot({ path: path.join(screenshotDir, '05b-create-llm-extract.png'), fullPage: true });
          console.log('Screenshot saved: 05b-create-llm-extract.png');
          break;
        }
      }

    } else if (testName === 'navigate-back') {
      console.log('--- Test 4: Navigate back from detail to list ---');
      await page.goto('http://localhost:3000/transformations', { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);

      const firstLink = await page.$('a[href^="/transformations/"]');
      if (firstLink) {
        const href = await firstLink.getAttribute('href');
        await page.goto(`http://localhost:3000${href}`, { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(2000);

        // Click back arrow
        const backLink = await page.$('a[href="/transformations"]');
        if (backLink) {
          console.log('Found back link, clicking...');
          await backLink.click();
          await page.waitForTimeout(3000);
          await page.screenshot({ path: path.join(screenshotDir, '06-back-to-list.png'), fullPage: true });
          console.log('Screenshot saved: 06-back-to-list.png');
          const h1 = await page.$('h1');
          if (h1) {
            console.log('Back on list page, heading:', await h1.textContent());
          }
        } else {
          console.log('ERROR: No back link found!');
        }
      }
    }
  } finally {
    // Print console errors/warnings
    const issues = consoleMessages.filter(m => m.type === 'error' || m.type === 'warning');
    if (issues.length > 0) {
      console.log('\n--- Console Issues ---');
      for (const msg of issues) {
        console.log(`[${msg.type}] ${msg.text.substring(0, 200)}`);
      }
    }

    if (networkErrors.length > 0) {
      console.log('\n--- Network Errors ---');
      for (const err of networkErrors) {
        console.log(`[${err.status}] ${err.url}`);
      }
    }

    await browser.close();
  }
}

main().catch(err => {
  console.error('Test failed:', err.message);
  process.exit(1);
});
