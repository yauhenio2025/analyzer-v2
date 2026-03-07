import { chromium } from 'playwright';

const URL = 'https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy';

(async () => {
  const browser = await chromium.launch({ headless: true });
  // Use a narrower viewport so the pencil is more visible proportionally
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  console.log('Navigating...');
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });

  // Click "Conditions of Possibility" tab
  const tabs = await page.$$('button');
  for (const tab of tabs) {
    const text = await tab.textContent();
    if (text.includes('Conditions of Possibility')) {
      await tab.click();
      await page.waitForTimeout(2000);
      break;
    }
  }
  await page.waitForSelector('.gen-conditions-section', { timeout: 15000 });

  // Take a zoomed screenshot of the right portion of a collapsed section header during hover
  const sections = await page.$$('.gen-conditions-section');
  const targetSection = sections[2]; // "Path Dependencies"
  const h3 = await targetSection.$('h3');
  await h3.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);

  // Get the h3 bounding box
  const h3Box = await h3.boundingBox();
  console.log('h3 box:', h3Box);

  // Screenshot the RIGHT portion of the h3 - where the pencil lives
  // Pencil is at x ~1361, width 18
  const clipRight = {
    x: h3Box.x + h3Box.width - 100,  // last 100px of the h3
    y: h3Box.y - 5,
    width: 100,
    height: h3Box.height + 10
  };

  // No hover first
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-07-right-nohover.png',
    clip: clipRight
  });
  console.log('Screenshot: right edge, no hover');

  // Now hover
  await h3.hover();
  await page.waitForTimeout(500);

  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-08-right-hover.png',
    clip: clipRight
  });
  console.log('Screenshot: right edge, WITH hover');

  // Also test: click the pencil to see if the feedback row appears
  const pencil = await targetSection.$('.section-polish-pencil');
  if (pencil) {
    // First hover to make it visible
    await h3.hover();
    await page.waitForTimeout(300);

    await pencil.click({ force: true });
    await page.waitForTimeout(1000);

    // Check if feedback row appeared
    const feedbackRow = await targetSection.$('.section-polish-feedback-row');
    console.log('\nAfter clicking pencil:');
    console.log('  Feedback row present:', !!feedbackRow);

    if (feedbackRow) {
      const feedbackBox = await feedbackRow.boundingBox();
      console.log('  Feedback row box:', feedbackBox);
    }

    // Screenshot showing feedback row
    const sectionBox = await targetSection.boundingBox();
    await page.screenshot({
      path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-09-feedback-row.png',
      clip: { x: sectionBox.x - 5, y: sectionBox.y - 5, width: sectionBox.width + 10, height: Math.min(sectionBox.height + 10, 200) }
    });
    console.log('Screenshot: section after pencil click');
  }

  // Test with a WIDER viewport that more closely mimics a real monitor
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(500);

  const layout1920 = await page.evaluate(() => {
    const section = document.querySelectorAll('.gen-conditions-section')[0];
    const h3 = section?.querySelector('h3');
    const pencil = section?.querySelector('.section-polish-pencil');
    return {
      viewportWidth: window.innerWidth,
      h3Right: h3?.getBoundingClientRect().right,
      pencilLeft: pencil?.getBoundingClientRect().left,
      pencilRight: pencil?.getBoundingClientRect().right,
    };
  });
  console.log('\nAt 1920px viewport:', layout1920);

  // Now test a narrow viewport (laptop)
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.waitForTimeout(500);

  const layout1280 = await page.evaluate(() => {
    const section = document.querySelectorAll('.gen-conditions-section')[0];
    const h3 = section?.querySelector('h3');
    const pencil = section?.querySelector('.section-polish-pencil');
    return {
      viewportWidth: window.innerWidth,
      h3Right: h3?.getBoundingClientRect().right,
      pencilLeft: pencil?.getBoundingClientRect().left,
      pencilRight: pencil?.getBoundingClientRect().right,
    };
  });
  console.log('At 1280px viewport:', layout1280);

  await browser.close();
  console.log('\nDone.');
})();
