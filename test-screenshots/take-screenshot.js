const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  console.log('Navigating to http://localhost:3001/implementations ...');
  await page.goto('http://localhost:3001/implementations', { waitUntil: 'networkidle' });

  // Wait for initial render
  console.log('Waiting 5 seconds for dependent API calls to resolve...');
  await page.waitForTimeout(5000);

  // Take screenshot
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/06-implementations-list-fixed.png',
    fullPage: true
  });
  console.log('Screenshot saved to test-screenshots/06-implementations-list-fixed.png');

  await browser.close();
})();
