import { chromium } from 'playwright';

const URL = 'https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy';

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  console.log('1. Navigating to:', URL);
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
  console.log('   Page loaded.');

  // Wait for data to appear
  console.log('2. Waiting for accordion sections to appear...');
  try {
    await page.waitForSelector('.gen-conditions-section', { timeout: 30000 });
    console.log('   Accordion sections found!');
  } catch (e) {
    console.log('   No .gen-conditions-section found, trying alternative selectors...');
    // Try clicking on "Conditions of Possibility" tab first
    const tabs = await page.$$('[role="tab"], .tab, button');
    console.log(`   Found ${tabs.length} tab-like elements`);
    for (const tab of tabs) {
      const text = await tab.textContent();
      if (text.includes('Conditions') || text.includes('Possibility')) {
        console.log(`   Clicking tab: "${text.trim()}"`);
        await tab.click();
        await page.waitForTimeout(3000);
        break;
      }
    }
  }

  // Take initial screenshot
  await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-01-initial.png', fullPage: false });
  console.log('3. Screenshot saved: pencil-01-initial.png');

  // Check for section-polish-controls
  const polishControlsCount = await page.evaluate(() => {
    return document.querySelectorAll('.section-polish-controls').length;
  });
  console.log(`\n4. .section-polish-controls elements: ${polishControlsCount}`);

  // Check for section-polish-pencil
  const pencilCount = await page.evaluate(() => {
    return document.querySelectorAll('.section-polish-pencil').length;
  });
  console.log(`5. .section-polish-pencil elements: ${pencilCount}`);

  // Check pencil visibility if they exist
  if (pencilCount > 0) {
    const pencilInfo = await page.evaluate(() => {
      const results = [];
      document.querySelectorAll('.section-polish-pencil').forEach(el => {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        results.push({
          rect: { top: rect.top, left: rect.left, width: rect.width, height: rect.height },
          opacity: style.opacity,
          display: style.display,
          visibility: style.visibility,
          innerHTML: el.innerHTML.substring(0, 100)
        });
      });
      return results;
    });
    console.log('6. Pencil element details:', JSON.stringify(pencilInfo, null, 2));
  } else {
    console.log('6. No pencil elements found - checking h3 structure...');
  }

  // Check h3 elements inside accordion sections
  const h3Info = await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    const results = [];
    sections.forEach((section, i) => {
      const h3s = section.querySelectorAll('h3');
      h3s.forEach(h3 => {
        results.push({
          sectionIndex: i,
          sectionClass: section.className,
          h3Text: h3.textContent.trim().substring(0, 80),
          h3InnerHTML: h3.innerHTML.substring(0, 300),
          h3ChildNodes: Array.from(h3.childNodes).map(n => ({
            type: n.nodeType,
            name: n.nodeName,
            class: n.className || '',
            text: (n.textContent || '').substring(0, 50)
          }))
        });
      });
    });
    return results;
  });
  console.log(`\n7. H3 elements in .gen-conditions-section (${h3Info.length} found):`);
  h3Info.forEach((info, i) => {
    console.log(`   [${i}] Section ${info.sectionIndex} (${info.sectionClass})`);
    console.log(`       h3 text: "${info.h3Text}"`);
    console.log(`       h3 innerHTML: ${info.h3InnerHTML}`);
    console.log(`       h3 children:`, JSON.stringify(info.h3ChildNodes));
  });

  // Also check ALL h3 elements on the page to find accordion headers
  const allH3Info = await page.evaluate(() => {
    const h3s = document.querySelectorAll('h3');
    return Array.from(h3s).slice(0, 20).map(h3 => ({
      text: h3.textContent.trim().substring(0, 60),
      parent: h3.parentElement?.className || 'none',
      grandparent: h3.parentElement?.parentElement?.className || 'none',
      innerHTML: h3.innerHTML.substring(0, 200)
    }));
  });
  console.log(`\n8. All h3 elements on page (first 20 of ${allH3Info.length}):`);
  allH3Info.forEach((info, i) => {
    console.log(`   [${i}] "${info.text}" | parent: ${info.parent} | gp: ${info.grandparent}`);
    console.log(`         innerHTML: ${info.innerHTML}`);
  });

  // Check for the "Present" button and any polish-related elements
  const polishRelated = await page.evaluate(() => {
    const results = {};
    // Present button
    const presentBtns = document.querySelectorAll('[class*="present"], [class*="polish"]');
    results.presentButtons = Array.from(presentBtns).map(el => ({
      tag: el.tagName,
      class: el.className,
      text: (el.textContent || '').substring(0, 50)
    }));
    // Any element with 'pencil' or 'polish' in class
    const polishEls = document.querySelectorAll('[class*="pencil"], [class*="polish"]');
    results.polishElements = Array.from(polishEls).map(el => ({
      tag: el.tagName,
      class: el.className,
      id: el.id || '',
      text: (el.textContent || '').substring(0, 50)
    }));
    return results;
  });
  console.log('\n9. Polish-related elements:');
  console.log('   Present/polish buttons:', JSON.stringify(polishRelated.presentButtons, null, 2));
  console.log('   Pencil/polish elements:', JSON.stringify(polishRelated.polishElements, null, 2));

  // Check console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  const warnings = consoleMessages.filter(m => m.type === 'warning');
  console.log(`\n10. Console errors (${errors.length}):`);
  errors.slice(0, 10).forEach(e => console.log(`    ERROR: ${e.text.substring(0, 200)}`));
  console.log(`    Warnings (${warnings.length}):`);
  warnings.slice(0, 5).forEach(w => console.log(`    WARN: ${w.text.substring(0, 200)}`));

  // Now try to hover over a section header to see if pencil appears
  const sectionHeaders = await page.$$('.gen-conditions-section h3');
  if (sectionHeaders.length > 0) {
    console.log('\n11. Hovering over first section header...');
    await sectionHeaders[0].hover();
    await page.waitForTimeout(1000);
    await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-02-hovered.png', fullPage: false });
    console.log('    Screenshot saved: pencil-02-hovered.png');

    // Re-check pencil visibility after hover
    const pencilAfterHover = await page.evaluate(() => {
      const pencils = document.querySelectorAll('.section-polish-pencil');
      return Array.from(pencils).map(el => ({
        opacity: getComputedStyle(el).opacity,
        display: getComputedStyle(el).display,
        visibility: getComputedStyle(el).visibility,
      }));
    });
    console.log('    Pencil state after hover:', JSON.stringify(pencilAfterHover));
  }

  // Check what CSS styles exist for section-polish-pencil
  const cssCheck = await page.evaluate(() => {
    const sheets = Array.from(document.styleSheets);
    const rules = [];
    for (const sheet of sheets) {
      try {
        for (const rule of sheet.cssRules) {
          if (rule.selectorText && (rule.selectorText.includes('polish') || rule.selectorText.includes('pencil'))) {
            rules.push({
              selector: rule.selectorText,
              cssText: rule.cssText.substring(0, 300)
            });
          }
        }
      } catch (e) {
        // Cross-origin stylesheet
      }
    }
    return rules;
  });
  console.log(`\n12. CSS rules containing "polish" or "pencil" (${cssCheck.length}):`);
  cssCheck.forEach(r => console.log(`    ${r.selector}: ${r.cssText}`));

  // Check the AccordionRenderer config
  const rendererCheck = await page.evaluate(() => {
    // Try to find the renderer instances or config
    const results = {};
    // Check if window has any renderer config
    if (window.__rendererConfigs) {
      results.configs = window.__rendererConfigs;
    }
    // Check for data attributes that might indicate polish support
    const sections = document.querySelectorAll('.gen-conditions-section');
    results.sectionDataAttrs = Array.from(sections).slice(0, 3).map(s => ({
      dataset: { ...s.dataset },
      allAttrs: Array.from(s.attributes).map(a => `${a.name}="${a.value}"`)
    }));
    return results;
  });
  console.log('\n13. Renderer config check:', JSON.stringify(rendererCheck, null, 2));

  // Full page screenshot
  await page.screenshot({ path: '/home/evgeny/projects/analyzer-v2/test-screenshots/pencil-03-fullpage.png', fullPage: true });
  console.log('\n14. Full page screenshot saved: pencil-03-fullpage.png');

  await browser.close();
  console.log('\nDiagnosis complete.');
})();
