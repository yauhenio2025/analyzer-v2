import puppeteer from 'puppeteer';

const url = process.argv[2] || 'http://localhost:3000/views';
const outFile = process.argv[3] || '/home/evgeny/projects/analyzer-v2/test-screenshots/views-current.png';

const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

const page = await browser.newPage();
// Use 2x device scale for sharper screenshots
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

// Collect console errors
const errors = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(msg.text());
});
page.on('pageerror', err => errors.push(err.message));

await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 });

// Wait for SPA to settle
await new Promise(r => setTimeout(r, 2000));

if (errors.length > 0) {
  console.log('Console errors:');
  errors.forEach(e => console.log('  -', e));
}

// Take a full page screenshot
await page.screenshot({ path: outFile, fullPage: true });
console.log(`Screenshot saved to ${outFile}`);

await browser.close();
