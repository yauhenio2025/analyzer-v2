import { chromium } from 'playwright';
import { mkdirSync } from 'fs';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/renderer-tab';
mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  try {
    await page.goto('http://localhost:3000/views/genealogy_target_profile', {
      waitUntil: 'networkidle', timeout: 15000
    });
    await page.waitForTimeout(500);

    // Click Renderer tab
    await page.locator('button:has-text("Renderer")').click();
    await page.waitForTimeout(1000);

    // Find the "CURRENT" text - maybe it's an HTML entity or styled differently
    const currentTexts = await page.evaluate(() => {
      const all = document.querySelectorAll('*');
      const results = [];
      for (const el of all) {
        const ownText = Array.from(el.childNodes)
          .filter(n => n.nodeType === 3)
          .map(n => n.textContent?.trim())
          .filter(t => t)
          .join(' ');
        if (ownText.toLowerCase().includes('current')) {
          results.push({
            tag: el.tagName,
            ownText,
            className: el.className?.toString()?.substring(0, 80),
            innerHTML: el.innerHTML?.substring(0, 200)
          });
        }
      }
      return results;
    });
    console.log('Elements with "current" in own text:');
    currentTexts.forEach(t => console.log(JSON.stringify(t)));

    // Find which renderer has the view's renderer_key
    const viewRendererKey = await page.evaluate(() => {
      // The view's renderer config should reference the current renderer
      // Check the page for any data about the current renderer
      const allText = document.body.innerText;
      // Look for "tab_container" or "accordion" or "v2_tab_content" etc
      const rendererKeys = ['accordion', 'tab_container', 'v2_tab_content', 'card_grid',
        'prose', 'table', 'statistics', 'timeline', 'json_inspector'];
      const found = [];
      for (const key of rendererKeys) {
        if (allText.toLowerCase().includes(key)) {
          found.push(key);
        }
      }
      return found;
    });
    console.log('\nRenderer keys mentioned on page:', viewRendererKey);

    // Look for the checkmark SVG - find which renderer row contains it
    const checkmarkInfo = await page.evaluate(() => {
      const svgs = document.querySelectorAll('svg');
      const results = [];
      for (const svg of svgs) {
        // Check if it's a check/checkmark icon
        if (svg.querySelector('polyline, path[d*="M20 6"], path[d*="M5 13"]') ||
            svg.classList.contains('lucide-check') ||
            svg.getAttribute('data-lucide') === 'check') {
          let parent = svg.parentElement;
          for (let i = 0; i < 10; i++) {
            if (!parent) break;
            const text = parent.textContent || '';
            if (text.includes('%')) {
              results.push({
                rendererText: text.substring(0, 150).replace(/\n/g, ' '),
                className: parent.className?.toString()?.substring(0, 100)
              });
              break;
            }
            parent = parent.parentElement;
          }
        }
      }
      return results;
    });
    console.log('\nCheckmark locations:');
    checkmarkInfo.forEach(c => console.log(JSON.stringify(c)));

    // Take zoomed screenshots of the renderer list area
    // First, find the renderer selection card boundary
    const rendererSection = page.locator('text="Renderer Selection"').first();
    const box = await rendererSection.boundingBox().catch(() => null);
    if (box) {
      // Clip to just the renderer selection area
      await page.screenshot({
        path: `${SCREENSHOT_DIR}/07-renderer-selection-zoomed.png`,
        clip: { x: box.x - 20, y: box.y - 20, width: 1100, height: 600 }
      });
      console.log('\nSaved zoomed screenshot of renderer selection');
    }

    // Inspect the highlighted/current row
    const highlightedRow = await page.evaluate(() => {
      // Look for any element with a blue/highlighted border or background
      const allDivs = document.querySelectorAll('div');
      for (const div of allDivs) {
        const style = window.getComputedStyle(div);
        const borderColor = style.borderLeftColor || style.borderColor;
        // Look for blue-ish borders (common for "current" highlight)
        if (borderColor.includes('59, 130, 246') || // blue-500
            borderColor.includes('99, 102, 241') || // indigo-500
            borderColor.includes('37, 99, 235') ||  // blue-600
            style.backgroundColor.includes('239, 246, 255') || // blue-50
            style.backgroundColor.includes('219, 234, 254')) { // blue-100
          const text = div.textContent?.substring(0, 200)?.replace(/\n/g, ' ');
          if (text?.includes('%')) {
            return {
              text,
              bg: style.backgroundColor,
              border: style.border,
              borderLeft: style.borderLeft,
              borderColor: style.borderColor,
              className: div.className?.toString()?.substring(0, 120)
            };
          }
        }
      }
      return 'No highlighted row found';
    });
    console.log('\nHighlighted row:', JSON.stringify(highlightedRow, null, 2));

    // Network check - see if the renderers API was called
    console.log('\nConsole errors:', consoleErrors.length === 0 ? 'None' : consoleErrors);

    console.log('\n=== DONE ===');

  } catch (err) {
    console.error('Test error:', err.message);
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
