import puppeteer from 'puppeteer';

const url = process.argv[2] || 'http://localhost:3000/views';
const outFile = process.argv[3] || '/home/evgeny/projects/analyzer-v2/test-screenshots/views-tree-zoom.png';

const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 });
await new Promise(r => setTimeout(r, 2000));

// Full page screenshot
await page.screenshot({ path: outFile, fullPage: true });
console.log(`Full page screenshot saved to ${outFile}`);

await browser.close();
