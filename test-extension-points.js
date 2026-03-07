const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  // Collect page errors
  const pageErrors = [];
  page.on('pageerror', err => {
    pageErrors.push(err.message);
  });

  console.log('=== STEP 1: Navigate to the implementation page ===');
  try {
    await page.goto('https://analyzer-mgmt.onrender.com/implementations/intellectual_genealogy', {
      waitUntil: 'networkidle',
      timeout: 60000
    });
    console.log('Page loaded successfully');
    console.log('Page title:', await page.title());
    console.log('Page URL:', page.url());
  } catch (err) {
    console.log('Navigation error:', err.message);
  }

  // Wait a moment for any dynamic content
  await page.waitForTimeout(3000);

  // Take initial screenshot
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/01-initial-state.png',
    fullPage: true
  });
  console.log('Screenshot 1 saved: 01-initial-state.png');

  // Check the page content
  console.log('\n=== STEP 2: Examine page structure ===');

  // Look for the depth selector card area
  const depthSelectorText = await page.evaluate(() => {
    const allText = document.body.innerText;
    // Find text around "depth" or "extension" keywords
    const lines = allText.split('\n').filter(l => l.trim());
    return lines.filter(l =>
      l.toLowerCase().includes('depth') ||
      l.toLowerCase().includes('extension') ||
      l.toLowerCase().includes('show') ||
      l.toLowerCase().includes('checkbox') ||
      l.toLowerCase().includes('toggle')
    ).slice(0, 30);
  });
  console.log('Relevant text on page:', JSON.stringify(depthSelectorText, null, 2));

  // Look for checkboxes
  const checkboxes = await page.evaluate(() => {
    const inputs = document.querySelectorAll('input[type="checkbox"]');
    return Array.from(inputs).map(input => ({
      id: input.id,
      name: input.name,
      checked: input.checked,
      label: input.labels?.[0]?.textContent || '',
      parentText: input.parentElement?.textContent?.trim()?.substring(0, 100) || '',
      ariaLabel: input.getAttribute('aria-label') || ''
    }));
  });
  console.log('\nCheckboxes found:', JSON.stringify(checkboxes, null, 2));

  // Look for elements with "extension" in text
  const extensionElements = await page.evaluate(() => {
    const allElements = document.querySelectorAll('*');
    const results = [];
    for (const el of allElements) {
      const text = el.textContent?.trim() || '';
      if (text.toLowerCase().includes('extension') && text.length < 200) {
        results.push({
          tag: el.tagName,
          text: text.substring(0, 150),
          className: el.className?.substring?.(0, 100) || '',
          id: el.id || ''
        });
      }
    }
    // Deduplicate by text
    const seen = new Set();
    return results.filter(r => {
      if (seen.has(r.text)) return false;
      seen.add(r.text);
      return true;
    }).slice(0, 20);
  });
  console.log('\nElements mentioning "extension":', JSON.stringify(extensionElements, null, 2));

  // Look for any toggle/switch components
  const toggleElements = await page.evaluate(() => {
    // Look for various toggle patterns
    const selectors = [
      'input[type="checkbox"]',
      '[role="switch"]',
      '[role="checkbox"]',
      '.toggle',
      '.switch',
      '[class*="toggle"]',
      '[class*="switch"]',
      '[class*="checkbox"]',
      'label:has(input)',
    ];
    const results = [];
    for (const selector of selectors) {
      const els = document.querySelectorAll(selector);
      for (const el of els) {
        results.push({
          selector,
          tag: el.tagName,
          text: el.textContent?.trim()?.substring(0, 100) || '',
          className: el.className?.substring?.(0, 100) || '',
          checked: el.checked ?? null,
          ariaChecked: el.getAttribute('aria-checked')
        });
      }
    }
    return results.slice(0, 30);
  });
  console.log('\nToggle/switch elements:', JSON.stringify(toggleElements, null, 2));

  console.log('\n=== STEP 3: Look for "Show Extension Points" specifically ===');

  // Search specifically for extension points checkbox/toggle
  const extensionToggle = await page.evaluate(() => {
    // Method 1: Text search
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      if (el.textContent?.includes('Extension Points') && el.children.length < 5) {
        return {
          found: true,
          method: 'text-search',
          tag: el.tagName,
          text: el.textContent.trim().substring(0, 200),
          className: el.className?.substring?.(0, 100) || '',
          hasCheckbox: !!el.querySelector('input[type="checkbox"]'),
          innerHTML: el.innerHTML?.substring(0, 300) || ''
        };
      }
    }

    // Method 2: Label search
    const labels = document.querySelectorAll('label');
    for (const label of labels) {
      if (label.textContent?.includes('Extension')) {
        return {
          found: true,
          method: 'label-search',
          text: label.textContent.trim(),
          forId: label.htmlFor || '',
          hasInput: !!label.querySelector('input')
        };
      }
    }

    return { found: false };
  });
  console.log('Extension toggle search result:', JSON.stringify(extensionToggle, null, 2));

  // Try to find and click the extension points toggle
  console.log('\n=== STEP 4: Try to toggle extension points ===');

  // Try various selectors
  let clicked = false;

  // Try clicking by text
  try {
    const extCheckbox = await page.locator('text=Extension Points').first();
    if (await extCheckbox.isVisible()) {
      console.log('Found "Extension Points" element, clicking...');
      await extCheckbox.click();
      clicked = true;
      await page.waitForTimeout(2000);
    }
  } catch (e) {
    console.log('Could not find/click "Extension Points" text:', e.message);
  }

  if (!clicked) {
    // Try finding checkbox near extension text
    try {
      const checkbox = await page.locator('label:has-text("Extension")').first();
      if (await checkbox.isVisible()) {
        console.log('Found label with "Extension", clicking...');
        await checkbox.click();
        clicked = true;
        await page.waitForTimeout(2000);
      }
    } catch (e) {
      console.log('Could not find label with Extension:', e.message);
    }
  }

  if (!clicked) {
    // Try any checkbox that mentions extension or show
    try {
      const showCheckboxes = await page.locator('input[type="checkbox"]').all();
      console.log(`Found ${showCheckboxes.length} checkboxes total`);
      for (let i = 0; i < showCheckboxes.length; i++) {
        const cb = showCheckboxes[i];
        const parentText = await cb.evaluate(el => el.parentElement?.textContent?.trim() || '');
        console.log(`Checkbox ${i}: parentText = "${parentText.substring(0, 80)}"`);
        if (parentText.toLowerCase().includes('extension') || parentText.toLowerCase().includes('show')) {
          console.log(`Clicking checkbox ${i}...`);
          await cb.click();
          clicked = true;
          await page.waitForTimeout(2000);
          break;
        }
      }
    } catch (e) {
      console.log('Error scanning checkboxes:', e.message);
    }
  }

  // Take screenshot after attempting to toggle
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/02-after-toggle-attempt.png',
    fullPage: true
  });
  console.log('Screenshot 2 saved: 02-after-toggle-attempt.png');

  // If we found and clicked, look for extension panels
  if (clicked) {
    console.log('\n=== STEP 5: Check for extension panels ===');

    const extensionPanels = await page.evaluate(() => {
      const allElements = document.querySelectorAll('*');
      const results = [];
      for (const el of allElements) {
        const text = el.textContent?.trim() || '';
        if ((text.toLowerCase().includes('candidate') ||
             text.toLowerCase().includes('score') ||
             text.toLowerCase().includes('extension point')) &&
            text.length < 500 &&
            el.children.length < 10) {
          results.push({
            tag: el.tagName,
            text: text.substring(0, 200),
            className: el.className?.substring?.(0, 100) || '',
            visible: el.offsetParent !== null
          });
        }
      }
      const seen = new Set();
      return results.filter(r => {
        if (seen.has(r.text)) return false;
        seen.add(r.text);
        return true;
      }).slice(0, 20);
    });
    console.log('Extension panel elements:', JSON.stringify(extensionPanels, null, 2));
  }

  // Scroll down to see if there's more content
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(1000);
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/03-scrolled-bottom.png',
    fullPage: true
  });
  console.log('Screenshot 3 saved: 03-scrolled-bottom.png');

  // Also capture the depth selector area specifically
  console.log('\n=== STEP 6: Examine depth selector card area ===');
  const depthCardInfo = await page.evaluate(() => {
    // Look for cards or sections with depth-related content
    const cards = document.querySelectorAll('.card, .panel, [class*="card"], [class*="panel"], [class*="depth"]');
    return Array.from(cards).map(card => ({
      tag: card.tagName,
      className: card.className?.substring?.(0, 150) || '',
      textPreview: card.textContent?.trim()?.substring(0, 200) || '',
      childCount: card.children.length
    })).filter(c => c.textPreview.toLowerCase().includes('depth') || c.textPreview.toLowerCase().includes('extension')).slice(0, 10);
  });
  console.log('Depth/Extension cards:', JSON.stringify(depthCardInfo, null, 2));

  // Print console messages
  console.log('\n=== Console Messages ===');
  const importantMessages = consoleMessages.filter(m =>
    m.type === 'error' || m.type === 'warning' || m.text.toLowerCase().includes('extension')
  );
  if (importantMessages.length > 0) {
    importantMessages.forEach(m => console.log(`[${m.type}] ${m.text.substring(0, 200)}`));
  } else {
    console.log('No errors, warnings, or extension-related console messages');
  }

  if (pageErrors.length > 0) {
    console.log('\n=== Page Errors ===');
    pageErrors.forEach(e => console.log(e));
  }

  await browser.close();
  console.log('\n=== Test complete ===');
})();
