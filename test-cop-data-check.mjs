import { chromium } from 'playwright';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
  const page = await context.newPage();

  const consoleMsgs = [];
  page.on('console', msg => consoleMsgs.push(`[${msg.type()}] ${msg.text()}`));

  try {
    // Navigate
    await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });

    // Select Comprehensive 2/16/2026
    const compCard = page.locator('button.gen-result-card').filter({ hasText: '15 ideas' }).filter({ hasText: '4 prior works' });
    if (await compCard.count() > 0) {
      await compCard.first().click();
      await page.waitForTimeout(3000);
    }

    // Click CoP tab
    const copTab = page.locator('button:has-text("Conditions of Possibility")').first();
    if (await copTab.count() > 0) {
      await copTab.click();
      await page.waitForTimeout(2000);
    }

    // Now intercept the React state to see what data keys exist in the conditions data
    console.log('=== Check conditions data structure ===');

    // Approach: Look at the presentation API response to see what data the conditions phase has
    // The data is stored in the presentation. Let's fetch it from the API
    const presentationData = await page.evaluate(async () => {
      // Try to find the active presentation ID from the page
      // Look for API calls in the network
      const results = {};

      // Check what data-keys are in the conditions section
      // The accordion renderer would receive data as a Record<string, unknown>
      // where each key is a section key from the sections config

      // Let's check: what does the stored conditions data look like?
      // The data comes from the PagePresentation which has view payloads

      // Try to inspect via React devtools or a known global
      // Since we can't directly inspect React state, let's try the API

      // The presentation is loaded from /api/genealogy/presentations/{id}
      // Let's see what endpoints were called
      return null;
    });

    // Instead, let's intercept the accordion rendering by injecting a console log
    // First, let me check what the AccordionRenderer receives
    console.log('\n=== Check AccordionRenderer section handling ===');

    // Read the AccordionRenderer source to understand how it processes sections
    // Actually, let's just check the data by looking at the network

    // Method: Look at console messages for any clues about the data
    console.log('Console messages (first 30):');
    for (const msg of consoleMsgs.slice(0, 30)) {
      console.log(`  ${msg}`);
    }

    // Method 2: Check what API endpoint serves the presentation data
    // Let's look for the conditions structured data
    console.log('\n=== Try fetching conditions data from API ===');

    // The conditions data is stored as part of the genealogy analysis result
    // Let's find what API endpoints were hit
    const apiCalls = await page.evaluate(() => {
      // Check for any stored data
      const perf = performance.getEntriesByType('resource');
      return perf
        .filter(e => e.name.includes('api') || e.name.includes('presentation') || e.name.includes('genealogy'))
        .map(e => ({ url: e.name, duration: Math.round(e.duration) }))
        .slice(0, 20);
    });
    console.log('API-like resource loads:');
    for (const call of apiCalls) {
      console.log(`  ${call.url} (${call.duration}ms)`);
    }

    // Method 3: Navigate to the storage API to see what data exists
    // The presentation data comes from a specific genealogy result
    // Let's check the gen-result-card to find the presentation ID
    const resultInfo = await page.evaluate(() => {
      // Find the active result card
      const activeCard = document.querySelector('button.gen-result-card.selected, button.gen-result-card.active');
      if (activeCard) {
        return {
          text: activeCard.textContent?.trim()?.substring(0, 200),
          dataAttrs: Object.fromEntries(
            Array.from(activeCard.attributes).filter(a => a.name.startsWith('data-')).map(a => [a.name, a.value])
          )
        };
      }

      // Check all result cards
      return Array.from(document.querySelectorAll('button.gen-result-card')).map(card => ({
        text: card.textContent?.trim()?.substring(0, 100),
        classes: card.className
      }));
    });
    console.log('\nResult card info:', JSON.stringify(resultInfo, null, 2));

    // Method 4: Use page.evaluate to dig into the React component tree
    console.log('\n=== Inspect accordion data via DOM ===');

    // The AccordionRenderer creates div.gen-conditions-section for each section
    // The sections array defines what to show, but data is the actual data object
    // If a section key (like 'path_dependencies') doesn't exist in the data,
    // the section may still render (collapsed) or be filtered out

    // Let's check: does the AccordionRenderer skip sections with no data?
    // I need to read the AccordionRenderer source

    // For now, let's check what data the API gives for this specific view
    // by intercepting React state
    const reactData = await page.evaluate(() => {
      // Try to find React internal state on the root
      const root = document.getElementById('root');
      if (!root) return null;

      // React fiber
      const fiberKey = Object.keys(root).find(k => k.startsWith('__reactFiber'));
      if (!fiberKey) return { error: 'No React fiber found' };

      // Try to walk the fiber tree to find accordion renderer state
      // This is fragile but useful for debugging
      function findComponentState(fiber, depth = 0) {
        if (depth > 50) return null;

        // Check memoizedState or memoizedProps
        const props = fiber?.memoizedProps;
        if (props?.view?.view_key === 'genealogy_conditions') {
          return {
            found: 'genealogy_conditions view props',
            data: props.data ? Object.keys(props.data) : null,
            rendererConfig: props.view?.renderer_config?.sections?.map(s => s.key),
          };
        }

        // Check if this is an accordion renderer
        if (props?.className === 'gen-conditions-list' ||
            (typeof props?.children === 'object' && fiber?.type?.name === 'AccordionRenderer')) {
          return {
            found: 'AccordionRenderer',
            props: JSON.stringify(props).substring(0, 500)
          };
        }

        // Walk children
        let child = fiber?.child;
        while (child) {
          const result = findComponentState(child, depth + 1);
          if (result) return result;
          child = child.sibling;
        }
        return null;
      }

      return findComponentState(root[fiberKey]) || { error: 'Component not found' };
    });
    console.log('React component data:', JSON.stringify(reactData, null, 2));

    // Method 5: More direct - check what structured_data is being rendered
    // The AccordionRenderer should receive data that has keys matching section keys
    console.log('\n=== Dig into structured data ===');

    const structuredCheck = await page.evaluate(() => {
      // Walk the DOM to find the accordion content and understand data
      const condsSections = document.querySelectorAll('.gen-conditions-section');
      const sectionInfo = [];

      for (const section of condsSections) {
        const h3 = section.querySelector('h3');
        const content = section.querySelector('.gen-section-content');
        sectionInfo.push({
          title: h3?.textContent?.trim(),
          hasContent: !!content,
          contentClasses: content?.className,
          contentChildCount: content?.children?.length || 0,
          contentText: content?.textContent?.substring(0, 150)
        });
      }

      // Also check if there are hidden sections
      const allGenElements = document.querySelectorAll('[class*="gen-"]');
      const genClasses = new Set();
      for (const el of allGenElements) {
        for (const cls of el.classList) {
          if (cls.startsWith('gen-')) genClasses.add(cls);
        }
      }

      return {
        visibleSections: sectionInfo,
        allGenClasses: [...genClasses].sort()
      };
    });
    console.log('Visible sections:', JSON.stringify(structuredCheck.visibleSections, null, 2));
    console.log('All gen- classes:', structuredCheck.allGenClasses);

    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop4-data-check.png`, fullPage: true });

  } catch (err) {
    console.error('Error:', err.message);
    console.error(err.stack);
    await page.screenshot({ path: `${SCREENSHOTS_DIR}/cop4-error.png`, fullPage: true });
  } finally {
    await browser.close();
  }
}

run().catch(console.error);
