import puppeteer from 'puppeteer';

const URL = 'http://localhost:3001/p/morozov-on-varoufakis/genealogy';
const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';

async function run() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  // Collect console messages
  const consoleMessages = [];
  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  console.log('=== Step 1: Navigate to genealogy page ===');
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });

  // Wait for React to render
  await new Promise(r => setTimeout(r, 3000));

  // Check what project is actually loaded
  const projectInfo = await page.evaluate(() => {
    return {
      url: window.location.href,
      title: document.title,
      projectName: document.querySelector('.project-selector-button')?.textContent || 'N/A',
      headerText: document.querySelector('header')?.textContent?.substring(0, 200) || 'N/A',
      bodyText: document.body.innerText.substring(0, 500),
    };
  });
  console.log('Project info:', JSON.stringify(projectInfo, null, 2));

  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v2-01-initial.png`, fullPage: false });
  console.log('Screenshot 1 saved');

  // Check if we need to switch projects - look for the project selector
  console.log('\n=== Step 2: Check for project "Varoufakis" ===');

  // Try clicking the project selector dropdown
  const hasProjectSelector = await page.evaluate(() => {
    const btn = document.querySelector('.project-selector-button');
    if (btn) {
      btn.click();
      return btn.textContent.trim();
    }
    return null;
  });
  console.log('Project selector text:', hasProjectSelector);

  if (hasProjectSelector) {
    await new Promise(r => setTimeout(r, 1000));
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v2-02-project-dropdown.png`, fullPage: false });

    // Look for Varoufakis in the dropdown
    const projects = await page.evaluate(() => {
      const items = document.querySelectorAll('.project-option, .dropdown-item, [class*="project"], [class*="menu-item"]');
      return [...items].map(el => ({ text: el.textContent.trim().substring(0, 100), classes: el.className.substring(0, 100) }));
    });
    console.log('Available projects:', JSON.stringify(projects, null, 2));

    // Try to click on Varoufakis
    const clickedVaroufakis = await page.evaluate(() => {
      const allEls = document.querySelectorAll('*');
      for (const el of allEls) {
        if (el.textContent.trim().toLowerCase().includes('varoufakis') && el.children.length <= 2) {
          el.click();
          return el.textContent.trim().substring(0, 80);
        }
      }
      return null;
    });
    console.log('Clicked Varoufakis project:', clickedVaroufakis);

    await new Promise(r => setTimeout(r, 3000));
  }

  // Now check what page we're on
  const currentState = await page.evaluate(() => {
    return {
      url: window.location.href,
      projectName: document.querySelector('.project-selector-button')?.textContent || 'N/A',
    };
  });
  console.log('Current state:', JSON.stringify(currentState, null, 2));

  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v2-03-after-project.png`, fullPage: false });
  console.log('Screenshot 3 saved');

  // Now look for the Genealogy view - check navigation
  console.log('\n=== Step 3: Navigate to Genealogy page ===');

  // Check the current page sections
  const navInfo = await page.evaluate(() => {
    // Check top nav
    const navItems = document.querySelectorAll('nav a, .nav-link, .nav-item, [class*="nav"] a');
    const navTexts = [...navItems].map(el => ({ text: el.textContent.trim().substring(0, 80), href: el.href || '' }));

    // Check for genealogy-specific content
    const hasGenealogy = document.body.innerHTML.includes('genealogy') || document.body.innerHTML.includes('Genealogy');

    // Check for tabs
    const tabs = document.querySelectorAll('[role="tab"], .tab-btn, [class*="tab"]');
    const tabTexts = [...tabs].map(el => el.textContent.trim().substring(0, 60));

    return { navTexts: navTexts.slice(0, 20), hasGenealogy, tabTexts };
  });
  console.log('Navigation info:', JSON.stringify(navInfo, null, 2));

  // Look for genealogy in top nav and click it
  const clickedGenealogy = await page.evaluate(() => {
    // Try nav links
    const links = document.querySelectorAll('a, button');
    for (const el of links) {
      const text = el.textContent.trim().toLowerCase();
      if (text === 'genealogy' || text.includes('genealogy')) {
        el.click();
        return el.textContent.trim();
      }
    }

    // Try the Analysis dropdown
    const analysisBtn = [...document.querySelectorAll('button, [class*="dropdown"]')]
      .find(el => el.textContent.trim().toLowerCase().includes('analysis'));
    if (analysisBtn) {
      analysisBtn.click();
      return 'Opened Analysis dropdown';
    }

    return null;
  });
  console.log('Clicked genealogy:', clickedGenealogy);

  await new Promise(r => setTimeout(r, 2000));

  // If we clicked Analysis dropdown, look for Genealogy inside
  if (clickedGenealogy === 'Opened Analysis dropdown') {
    await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v2-04-analysis-dropdown.png`, fullPage: false });

    const menuItems = await page.evaluate(() => {
      const items = document.querySelectorAll('.dropdown-item, .menu-item, [class*="dropdown"] a, [class*="dropdown"] button, [class*="dropdown"] li');
      return [...items].map(el => el.textContent.trim().substring(0, 80));
    });
    console.log('Dropdown items:', menuItems);

    // Click on Genealogy
    const clickedGenealogyItem = await page.evaluate(() => {
      const items = document.querySelectorAll('a, button, li, [class*="item"]');
      for (const el of items) {
        if (el.textContent.trim().toLowerCase() === 'genealogy') {
          el.click();
          return true;
        }
      }
      return false;
    });
    console.log('Clicked genealogy item:', clickedGenealogyItem);
    await new Promise(r => setTimeout(r, 3000));
  }

  await page.screenshot({ path: `${SCREENSHOT_DIR}/tactics-v2-05-genealogy-page.png`, fullPage: false });
  console.log('Screenshot 5 saved');

  // Now look for Tactics & Strategies tab
  console.log('\n=== Step 4: Looking for Tactics & Strategies tab ===');

  const pageState = await page.evaluate(() => {
    const allText = document.body.innerText;
    const html = document.body.innerHTML;

    return {
      url: window.location.href,
      hasTacticsTab: !!html.match(/tactics/i),
      hasStrategies: !!html.match(/strateg/i),
      allTabs: [...document.querySelectorAll('[role="tab"], button[class*="tab"], .tab, [class*="view-tab"], [class*="genealogy"]')]
        .map(el => ({ text: el.textContent.trim().substring(0, 60), classes: el.className.substring(0, 80) })),
      visibleText: allText.substring(0, 3000)
    };
  });
  console.log('Page state:', JSON.stringify(pageState, null, 2));

  // Print console errors
  const errors = consoleMessages.filter(m => m.type === 'error');
  if (errors.length > 0) {
    console.log('\n=== Console Errors ===');
    errors.forEach(e => console.log('ERROR:', e.text.substring(0, 200)));
  }

  await browser.close();
  console.log('\nDone!');
}

run().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
