import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/tree-views';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

let screenshotCount = 10; // Start from 10 to avoid overwriting previous
function screenshotPath(name) {
  screenshotCount++;
  return `${SCREENSHOT_DIR}/${String(screenshotCount).padStart(2, '0')}-${name}.png`;
}

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  try {
    await page.goto('http://localhost:3000/views', { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);

    // =========================================================================
    // CHECK 1: Badge counts for parent views
    // =========================================================================
    console.log('\n=== Badge Count Verification ===');

    // Find all elements with "children" or "child" text in badges
    const badges = await page.$$eval(
      '.rounded-full',
      els => els.map(el => el.textContent.trim()).filter(t => t.includes('child'))
    );
    console.log(`All child-count badges found: ${JSON.stringify(badges)}`);

    // Check specific badge for "Target Work Profile"
    const twpCard = await page.locator('h3:has-text("Target Work Profile")').first();
    if (await twpCard.count() > 0) {
      // Get the parent container and find badge
      const cardContainer = await twpCard.locator('..').first(); // flex row
      const badgesInCard = await cardContainer.locator('.rounded-full').allTextContents();
      console.log(`Target Work Profile badges: ${JSON.stringify(badgesInCard.map(b => b.trim()))}`);
      const childBadge = badgesInCard.find(b => b.includes('child'));
      if (childBadge && childBadge.includes('4')) {
        console.log('PASS: Target Work Profile shows "4 children" badge');
      } else {
        console.log(`FAIL: Expected "4 children", got "${childBadge}"`);
      }
    }

    // Check badge for "Idea Evolution Map"
    const iemCard = await page.locator('h3:has-text("Idea Evolution Map")').first();
    if (await iemCard.count() > 0) {
      const cardContainer = await iemCard.locator('..').first();
      const badgesInCard = await cardContainer.locator('.rounded-full').allTextContents();
      console.log(`Idea Evolution Map badges: ${JSON.stringify(badgesInCard.map(b => b.trim()))}`);
      const childBadge = badgesInCard.find(b => b.includes('child'));
      console.log(`  Child badge: "${childBadge}"`);
    }

    // Check badge for "Genealogical Portrait"
    const gpCard = await page.locator('h3:has-text("Genealogical Portrait")').first();
    if (await gpCard.count() > 0) {
      const cardContainer = await gpCard.locator('..').first();
      const badgesInCard = await cardContainer.locator('.rounded-full').allTextContents();
      console.log(`Genealogical Portrait badges: ${JSON.stringify(badgesInCard.map(b => b.trim()))}`);
      const childBadge = badgesInCard.find(b => b.includes('child'));
      console.log(`  Child badge: "${childBadge}"`);
    }

    // =========================================================================
    // CHECK 2: Indentation levels - verify 2-level nesting
    // =========================================================================
    console.log('\n=== Indentation / Nesting Verification ===');

    // Find all border-l-2 border-indigo-200 containers
    const indigoContainers = await page.$$('.border-indigo-200.border-l-2');
    console.log(`Indigo border containers (nesting levels): ${indigoContainers.length}`);

    for (let i = 0; i < indigoContainers.length; i++) {
      const html = await indigoContainers[i].innerHTML();
      const viewNames = [];
      const h3s = await indigoContainers[i].$$('h3');
      for (const h3 of h3s) {
        viewNames.push(await h3.textContent());
      }
      console.log(`  Container ${i}: contains ${viewNames.length} views: ${JSON.stringify(viewNames)}`);
    }

    // =========================================================================
    // CHECK 3: Standalone views grid verification
    // =========================================================================
    console.log('\n=== Standalone Views Grid ===');

    const gridContainer = await page.$('.grid.grid-cols-1');
    if (gridContainer) {
      const gridClasses = await gridContainer.getAttribute('class');
      console.log(`Grid classes: ${gridClasses}`);
      const gridItems = await gridContainer.$$(':scope > a');
      const gridViewNames = [];
      for (const item of gridItems) {
        const name = await item.$eval('h3', el => el.textContent).catch(() => 'unknown');
        gridViewNames.push(name);
      }
      console.log(`Standalone views in grid: ${JSON.stringify(gridViewNames)}`);
      console.log(`Grid has 2-col layout: ${gridClasses.includes('lg:grid-cols-2') ? 'YES' : 'NO'}`);
    } else {
      console.log('No standalone grid found');
    }

    // =========================================================================
    // CHECK 4: Visual nesting screenshot - zoom into the tree area
    // =========================================================================
    console.log('\n=== Zoomed Screenshots ===');

    // Scroll to Idea Evolution Map and take a zoomed screenshot
    const iemSection = await page.locator('h3:has-text("Idea Evolution Map")').first();
    if (await iemSection.count() > 0) {
      await iemSection.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);

      // Get bounding box of the tree section (parent card + children)
      const iemParent = await iemSection.locator('xpath=ancestor::div[contains(@class, "space-y-0")]').first();
      if (await iemParent.count() > 0) {
        const box = await iemParent.boundingBox();
        if (box) {
          console.log(`Tree section bounds: x=${box.x}, y=${box.y}, w=${box.width}, h=${box.height}`);
          await page.screenshot({
            path: screenshotPath('idea-evolution-tree-zoomed'),
            clip: { x: Math.max(0, box.x - 20), y: Math.max(0, box.y - 20), width: box.width + 40, height: Math.min(box.height + 40, 2000) }
          });
          console.log('Screenshot: idea-evolution-tree-zoomed');
        }
      }
    }

    // Screenshot of Genealogical Portrait + its child
    const gpSection = await page.locator('h3:has-text("Genealogical Portrait")').first();
    if (await gpSection.count() > 0) {
      await gpSection.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
      const gpParent = await gpSection.locator('xpath=ancestor::div[contains(@class, "space-y-0")]').first();
      if (await gpParent.count() > 0) {
        const box = await gpParent.boundingBox();
        if (box) {
          await page.screenshot({
            path: screenshotPath('genealogical-portrait-tree'),
            clip: { x: Math.max(0, box.x - 20), y: Math.max(0, box.y - 20), width: box.width + 40, height: Math.min(box.height + 40, 800) }
          });
          console.log('Screenshot: genealogical-portrait-tree');
        }
      }
    }

    console.log('\nDone.');

  } catch (err) {
    console.error('TEST FAILED:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: screenshotPath('error-detail'), fullPage: true });
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
