import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/renderer-tab';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

let screenshotCount = 0;
function screenshotPath(name) {
  screenshotCount++;
  return `${SCREENSHOT_DIR}/${String(screenshotCount).padStart(2, '0')}-${name}.png`;
}

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Collect console errors
  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  try {
    // =========================================================================
    // STEP 1: Navigate to the view page
    // =========================================================================
    console.log('\n=== STEP 1: Navigate to genealogy_target_profile view ===');
    await page.goto('http://localhost:3000/views/genealogy_target_profile', {
      waitUntil: 'networkidle',
      timeout: 15000
    });
    await page.waitForTimeout(1000);

    await page.screenshot({ path: screenshotPath('view-page-loaded'), fullPage: false });
    console.log('Screenshot 1 saved: view-page-loaded');

    // Check page title / heading
    const heading = await page.locator('h1, h2, h3').first().textContent().catch(() => 'N/A');
    console.log(`Page heading: ${heading}`);

    // =========================================================================
    // STEP 2: Find and click the "Renderer" tab
    // =========================================================================
    console.log('\n=== STEP 2: Click the Renderer tab ===');

    // Look for all tab-like elements
    const allTabs = await page.locator('[role="tab"], button, .tab, [class*="tab"]').allTextContents();
    console.log('Available tab-like elements:', allTabs.filter(t => t.trim()).slice(0, 20));

    // Try to find the Renderer tab
    let rendererTab = page.locator('[role="tab"]:has-text("Renderer")');
    let tabCount = await rendererTab.count();

    if (tabCount === 0) {
      rendererTab = page.locator('button:has-text("Renderer")');
      tabCount = await rendererTab.count();
    }

    if (tabCount === 0) {
      // Try broader search
      rendererTab = page.locator('text=Renderer').first();
      tabCount = await rendererTab.count();
    }

    console.log(`Found ${tabCount} Renderer tab element(s)`);

    if (tabCount > 0) {
      await rendererTab.first().click();
      await page.waitForTimeout(1500);

      await page.screenshot({ path: screenshotPath('renderer-tab-clicked'), fullPage: false });
      console.log('Clicked Renderer tab and took screenshot');
    } else {
      console.log('ERROR: Could not find Renderer tab!');
      // Take screenshot of what we see anyway
      await page.screenshot({ path: screenshotPath('no-renderer-tab-found'), fullPage: true });
    }

    // =========================================================================
    // STEP 3: Analyze the renderer list
    // =========================================================================
    console.log('\n=== STEP 3: Analyze renderer list content ===');

    // Look for scored renderer items
    const rendererItems = await page.locator('[class*="renderer"], [class*="score"], [data-renderer]').count();
    console.log(`Renderer-related elements found: ${rendererItems}`);

    // Look for percentage scores
    const percentElements = await page.locator('text=/%/').allTextContents().catch(() => []);
    console.log(`Percentage elements: ${percentElements.slice(0, 10)}`);

    // Look for badges (stance, shape, container, app)
    const badgeTexts = await page.locator('[class*="badge"], .badge, span[class*="tag"]').allTextContents().catch(() => []);
    console.log(`Badge elements: ${badgeTexts.slice(0, 20)}`);

    // Look for colored dots
    const dots = await page.locator('[class*="dot"], [class*="circle"], [style*="border-radius: 50%"], [style*="border-radius:50%"]').count();
    console.log(`Dot-like elements found: ${dots}`);

    // Take full-page screenshot of renderer tab content
    await page.screenshot({ path: screenshotPath('renderer-tab-fullpage'), fullPage: true });

    // =========================================================================
    // STEP 4: Look for "accordion" as current renderer
    // =========================================================================
    console.log('\n=== STEP 4: Check for accordion as current renderer ===');

    const accordionMentions = await page.locator('text=/accordion/i').allTextContents().catch(() => []);
    console.log(`Accordion mentions: ${accordionMentions.slice(0, 10)}`);

    // Check for "current" indicator near accordion
    const currentIndicator = await page.locator('text=/current|selected|active/i').allTextContents().catch(() => []);
    console.log(`Current/selected/active indicators: ${currentIndicator.slice(0, 10)}`);

    // =========================================================================
    // STEP 5: Look for AI Recommendation section
    // =========================================================================
    console.log('\n=== STEP 5: Check for AI Recommendation section ===');

    const recommendBtn = await page.locator('button:has-text("Recommend")').count();
    console.log(`"Recommend" buttons found: ${recommendBtn}`);

    const aiSection = await page.locator('text=/AI|Recommend|recommendation/i').allTextContents().catch(() => []);
    console.log(`AI/Recommend mentions: ${aiSection.slice(0, 10)}`);

    // Scroll down to see more content if needed
    await page.evaluate(() => window.scrollBy(0, 500));
    await page.waitForTimeout(500);
    await page.screenshot({ path: screenshotPath('renderer-tab-scrolled'), fullPage: false });

    // =========================================================================
    // STEP 6: Detailed DOM inspection of the renderer tab panel
    // =========================================================================
    console.log('\n=== STEP 6: Detailed DOM inspection ===');

    // Get the visible tab panel content
    const tabPanelContent = await page.evaluate(() => {
      // Find the active tab panel
      const panels = document.querySelectorAll('[role="tabpanel"], .tab-panel, [class*="tabpanel"], [class*="TabPanel"]');
      let content = [];
      panels.forEach(p => {
        if (p.offsetHeight > 0) {
          content.push({
            className: p.className,
            textPreview: p.textContent?.substring(0, 500),
            childCount: p.children.length
          });
        }
      });
      return content;
    });
    console.log('Visible tab panels:', JSON.stringify(tabPanelContent, null, 2));

    // Get all visible text content in main area
    const mainContent = await page.evaluate(() => {
      const main = document.querySelector('main, [role="main"], .main-content, [class*="content"]');
      if (main) {
        return main.textContent?.substring(0, 2000);
      }
      return document.body.textContent?.substring(0, 2000);
    });
    console.log('\nMain content text (first 2000 chars):\n', mainContent);

    // =========================================================================
    // STEP 7: Final screenshot with any expanded/visible renderer details
    // =========================================================================
    console.log('\n=== STEP 7: Final screenshots ===');

    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(300);
    await page.screenshot({ path: screenshotPath('final-top'), fullPage: false });

    // Full page final
    await page.screenshot({ path: screenshotPath('final-fullpage'), fullPage: true });

    // =========================================================================
    // Report console errors
    // =========================================================================
    console.log('\n=== Console Errors ===');
    if (consoleErrors.length === 0) {
      console.log('No console errors detected.');
    } else {
      consoleErrors.forEach((err, i) => {
        console.log(`  Error ${i + 1}: ${err}`);
      });
    }

    console.log('\n=== TEST COMPLETE ===');
    console.log(`Total screenshots: ${screenshotCount}`);
    console.log(`Screenshots directory: ${SCREENSHOT_DIR}`);

  } catch (err) {
    console.error('Test failed with error:', err.message);
    await page.screenshot({ path: screenshotPath('error-state'), fullPage: true }).catch(() => {});
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
