import { chromium } from 'playwright';

async function test() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const consoleErrors = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });

  try {
    // Navigate and click Renderer tab
    await page.goto('http://localhost:3000/views/genealogy_target_profile', {
      waitUntil: 'networkidle', timeout: 15000
    });
    await page.waitForTimeout(500);

    const rendererTab = page.locator('button:has-text("Renderer")');
    await rendererTab.click();
    await page.waitForTimeout(1000);

    // ======= Verify Renderer Selection Section =======
    console.log('=== RENDERER SELECTION SECTION ===');

    const sectionTitle = await page.locator('text="Renderer Selection"').count();
    console.log(`"Renderer Selection" heading present: ${sectionTitle > 0}`);

    const subtitle = await page.locator('text=/scored by stance/i').count();
    console.log(`Subtitle about scoring present: ${subtitle > 0}`);

    // ======= Verify Scored Renderer List =======
    console.log('\n=== SCORED RENDERER LIST ===');

    // Extract all renderer entries with their scores
    const rendererEntries = await page.evaluate(() => {
      const results = [];
      // Look for elements containing percentage scores
      const allText = document.body.innerText;
      const lines = allText.split('\n').filter(l => l.match(/\d+%/));
      return lines.map(l => l.trim()).filter(l => l.length > 0);
    });
    console.log('Lines containing percentage scores:');
    rendererEntries.forEach(e => console.log(`  ${e}`));

    // ======= Verify Colored Dots =======
    console.log('\n=== COLORED DOTS ===');
    const coloredDots = await page.evaluate(() => {
      // Look for small colored circles/dots
      const elements = document.querySelectorAll('*');
      const dots = [];
      for (const el of elements) {
        const style = window.getComputedStyle(el);
        const width = parseFloat(style.width);
        const height = parseFloat(style.height);
        const borderRadius = style.borderRadius;
        // Small circular elements
        if (width < 20 && height < 20 && width > 4 &&
            (borderRadius === '50%' || borderRadius === '9999px' || parseFloat(borderRadius) >= width/2)) {
          const bg = style.backgroundColor;
          if (bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') {
            dots.push({ width, height, bg, borderRadius });
          }
        }
      }
      return dots;
    });
    console.log(`Colored dot elements found: ${coloredDots.length}`);
    coloredDots.forEach((d, i) => console.log(`  Dot ${i}: ${d.width}x${d.height}, bg=${d.bg}`));

    // ======= Verify Badges (Stance, Shape, Container, App) =======
    console.log('\n=== BADGES ===');
    const badges = await page.evaluate(() => {
      const results = [];
      const allElements = document.querySelectorAll('span, div, label');
      for (const el of allElements) {
        const text = el.textContent?.trim();
        if (text && (text.match(/^Stance:/) || text.match(/^Shape:/) ||
            text.match(/^Container:/) || text.match(/^App:/))) {
          const style = window.getComputedStyle(el);
          results.push({
            text,
            bg: style.backgroundColor,
            color: style.color,
            borderRadius: style.borderRadius
          });
        }
      }
      return results;
    });
    console.log(`Badge elements found: ${badges.length}`);
    badges.forEach((b, i) => console.log(`  Badge ${i}: "${b.text}" bg=${b.bg} color=${b.color}`));

    // ======= Verify Current Renderer Indicator =======
    console.log('\n=== CURRENT RENDERER ===');
    const currentBadge = await page.locator('text="CURRENT"').count();
    console.log(`"CURRENT" badge present: ${currentBadge > 0}`);

    // Which renderer has the CURRENT badge?
    const currentRenderer = await page.evaluate(() => {
      const currentEl = Array.from(document.querySelectorAll('*')).find(
        el => el.textContent?.trim() === 'CURRENT'
      );
      if (currentEl) {
        // Walk up to find the renderer name
        let parent = currentEl.parentElement;
        for (let i = 0; i < 5; i++) {
          const text = parent?.textContent || '';
          if (text.includes('%')) {
            // Get just the name part
            const match = text.match(/\d+%\s+(.+?)(?:\s*\(|$)/);
            if (match) return match[1].trim();
          }
          parent = parent?.parentElement;
        }
        return currentEl.parentElement?.textContent?.substring(0, 100);
      }
      return 'NOT FOUND';
    });
    console.log(`Current renderer: ${currentRenderer}`);

    // Check for checkmark on current
    const checkmark = await page.evaluate(() => {
      const svgs = document.querySelectorAll('svg');
      let checkCount = 0;
      svgs.forEach(svg => {
        if (svg.innerHTML.includes('polyline') || svg.innerHTML.includes('check') ||
            svg.classList.contains('lucide-check')) {
          checkCount++;
        }
      });
      return checkCount;
    });
    console.log(`Checkmark SVGs found: ${checkmark}`);

    // ======= Verify AI Recommendation Section =======
    console.log('\n=== AI RECOMMENDATION SECTION ===');
    const aiHeading = await page.locator('text="AI Recommendation"').count();
    console.log(`"AI Recommendation" heading present: ${aiHeading > 0}`);

    const recommendBtn = await page.locator('button:has-text("Recommend Renderer")');
    const btnCount = await recommendBtn.count();
    console.log(`"Recommend Renderer" button present: ${btnCount > 0}`);
    if (btnCount > 0) {
      const isEnabled = await recommendBtn.isEnabled();
      const isVisible = await recommendBtn.isVisible();
      console.log(`  Button enabled: ${isEnabled}`);
      console.log(`  Button visible: ${isVisible}`);
    }

    // ======= Verify Highlight on Current Renderer =======
    console.log('\n=== CURRENT RENDERER STYLING ===');
    const currentRowStyle = await page.evaluate(() => {
      // Find the renderer item that contains "CURRENT"
      const allItems = document.querySelectorAll('[class*="renderer"], [class*="item"], [class*="row"], [class*="card"]');
      for (const item of allItems) {
        if (item.textContent?.includes('CURRENT')) {
          const style = window.getComputedStyle(item);
          return {
            bg: style.backgroundColor,
            border: style.border,
            borderColor: style.borderColor,
            boxShadow: style.boxShadow,
            className: item.className
          };
        }
      }
      // Try a more general approach
      const currentEl = Array.from(document.querySelectorAll('*')).find(
        el => el.textContent?.trim() === 'CURRENT'
      );
      if (currentEl) {
        let parent = currentEl;
        for (let i = 0; i < 10; i++) {
          parent = parent.parentElement;
          if (!parent) break;
          const style = window.getComputedStyle(parent);
          if (style.border !== 'none' || style.borderColor !== 'rgb(0, 0, 0)' ||
              style.backgroundColor !== 'rgba(0, 0, 0, 0)') {
            return {
              tag: parent.tagName,
              bg: style.backgroundColor,
              border: style.border,
              borderLeft: style.borderLeft,
              className: parent.className?.substring(0, 100)
            };
          }
        }
      }
      return 'NOT FOUND';
    });
    console.log('Current renderer row styling:', JSON.stringify(currentRowStyle, null, 2));

    // ======= Verify how many renderers are shown =======
    console.log('\n=== RENDERER COUNT ===');
    const rendererCount = await page.evaluate(() => {
      const text = document.body.innerText;
      const percentages = text.match(/\d+%/g) || [];
      return percentages.length;
    });
    console.log(`Total renderers with percentage scores: ${rendererCount}`);

    // Get all scores
    const scores = await page.evaluate(() => {
      const text = document.body.innerText;
      const matches = [...text.matchAll(/(\d+)%\s+(.+?)(?:\n|$)/g)];
      return matches.map(m => ({ score: m[1] + '%', name: m[2].trim().substring(0, 60) }));
    });
    console.log('All scored renderers:');
    scores.forEach(s => console.log(`  ${s.score} - ${s.name}`));

    // ======= Console errors =======
    console.log('\n=== CONSOLE ERRORS ===');
    if (consoleErrors.length === 0) {
      console.log('No console errors');
    } else {
      consoleErrors.forEach(e => console.log(`  ERROR: ${e}`));
    }

    console.log('\n=== DONE ===');

  } catch (err) {
    console.error('Test error:', err.message);
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
