import { chromium } from 'playwright';

const URL = 'https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy';

(async () => {
  const browser = await chromium.launch({ headless: true });
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

  // Wait for sections
  await page.waitForSelector('.gen-conditions-section', { timeout: 15000 });

  // Get positions of all section headers and pencil icons
  const layout = await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    return Array.from(sections).map((s, i) => {
      const h3 = s.querySelector('h3');
      const pencil = s.querySelector('.section-polish-pencil');
      const h3Rect = h3?.getBoundingClientRect();
      const pencilRect = pencil?.getBoundingClientRect();
      const h3Style = h3 ? getComputedStyle(h3) : null;
      return {
        index: i,
        sectionText: h3?.textContent?.trim().substring(0, 40),
        h3: h3Rect ? { top: h3Rect.top, left: h3Rect.left, right: h3Rect.right, width: h3Rect.width, height: h3Rect.height } : null,
        h3Display: h3Style?.display,
        h3FlexDirection: h3Style?.flexDirection,
        h3JustifyContent: h3Style?.justifyContent,
        h3AlignItems: h3Style?.alignItems,
        pencil: pencilRect ? { top: pencilRect.top, left: pencilRect.left, right: pencilRect.right, width: pencilRect.width, height: pencilRect.height } : null,
        pencilOverflow: pencilRect ? (pencilRect.right > window.innerWidth ? 'OVERFLOWS' : 'OK') : 'N/A',
      };
    });
  });

  console.log('\nSection layout analysis:');
  layout.forEach(l => {
    console.log(`\n  [${l.index}] "${l.sectionText}"`);
    console.log(`    h3: display=${l.h3Display}, left=${l.h3?.left?.toFixed(0)}, right=${l.h3?.right?.toFixed(0)}, width=${l.h3?.width?.toFixed(0)}`);
    console.log(`    pencil: left=${l.pencil?.left?.toFixed(0)}, right=${l.pencil?.right?.toFixed(0)}, width=${l.pencil?.width?.toFixed(0)}`);
    console.log(`    pencil overflow: ${l.pencilOverflow}`);
  });

  // Scroll to the first section and take a clip screenshot
  const firstSection = await page.$('.gen-conditions-section');
  await firstSection.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);

  // Get bounding box for clip
  const box = await firstSection.boundingBox();

  // Screenshot of just that section (not hovered)
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-04-section-nohover.png',
    clip: { x: Math.max(0, box.x - 10), y: Math.max(0, box.y - 10), width: box.width + 20, height: Math.min(box.height + 20, 500) }
  });
  console.log('\nScreenshot: section without hover');

  // Now hover over the h3 element
  const h3 = await firstSection.$('h3');
  await h3.hover();
  await page.waitForTimeout(500);

  // Screenshot while hovering
  const box2 = await firstSection.boundingBox();
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-05-section-hover.png',
    clip: { x: Math.max(0, box2.x - 10), y: Math.max(0, box2.y - 10), width: box2.width + 20, height: Math.min(box2.height + 20, 500) }
  });
  console.log('Screenshot: section WITH hover');

  // Also check the pencil opacity after hover
  const pencilOpacity = await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    return Array.from(sections).map((s, i) => {
      const pencil = s.querySelector('.section-polish-pencil');
      return pencil ? { index: i, opacity: getComputedStyle(pencil).opacity } : null;
    }).filter(Boolean);
  });
  console.log('\nPencil opacity while hovering first section:');
  pencilOpacity.forEach(p => console.log(`  [${p.index}] opacity: ${p.opacity}`));

  // Now test: hover over a COLLAPSED section header
  const sections = await page.$$('.gen-conditions-section');
  if (sections.length > 1) {
    const collapsedH3 = await sections[2].$('h3'); // "Path Dependencies" (collapsed)
    await collapsedH3.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await collapsedH3.hover();
    await page.waitForTimeout(500);

    const box3 = await sections[2].boundingBox();
    await page.screenshot({
      path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-06-collapsed-hover.png',
      clip: { x: Math.max(0, box3.x - 10), y: Math.max(0, box3.y - 10), width: box3.width + 20, height: Math.min(box3.height + 20, 200) }
    });
    console.log('\nScreenshot: collapsed section WITH hover');

    const pencilOpacity2 = await page.evaluate(() => {
      const pencil = document.querySelectorAll('.gen-conditions-section')[2].querySelector('.section-polish-pencil');
      return pencil ? getComputedStyle(pencil).opacity : 'N/A';
    });
    console.log(`Pencil opacity on collapsed hover: ${pencilOpacity2}`);
  }

  await browser.close();
  console.log('\nDone.');
})();
