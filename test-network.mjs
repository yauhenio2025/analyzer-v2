import { chromium } from 'playwright';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  // Intercept network requests
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/v1/workflows')) {
      const status = response.status();
      console.log(`\nRESPONSE: ${url} [${status}]`);
      try {
        const body = await response.json();
        if (Array.isArray(body)) {
          console.log(`  Array with ${body.length} items`);
          if (body.length > 0) {
            const first = body[0];
            console.log(`  First item keys: ${Object.keys(first).join(', ')}`);
            console.log(`  First item phase_count: ${first.phase_count}`);
            console.log(`  First item has phases array: ${'phases' in first}`);
          }
        } else {
          console.log(`  Object keys: ${Object.keys(body).join(', ')}`);
          if ('phases' in body) {
            console.log(`  phases is array: ${Array.isArray(body.phases)}`);
            console.log(`  phases length: ${body.phases?.length}`);
          } else {
            console.log(`  NO phases field!`);
          }
        }
      } catch (e) {
        console.log(`  Could not parse body: ${e.message}`);
      }
    }
  });

  console.log('=== Loading implementations page ===');
  await page.goto('http://localhost:3001/implementations', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  console.log('\n=== Loading implementation detail page ===');
  await page.goto('http://localhost:3001/implementations/intellectual_genealogy', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  console.log('\n=== Loading workflow detail page ===');
  await page.goto('http://localhost:3001/workflows/intellectual_genealogy', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  await browser.close();
  console.log('\n=== Done ===');
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
