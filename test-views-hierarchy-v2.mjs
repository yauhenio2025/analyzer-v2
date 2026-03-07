import { chromium } from 'playwright';

const URL = 'https://analyzer-mgmt-frontend.onrender.com/views';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1400, height: 1200 } });

  console.log('Navigating to Views page...');
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(3000);

  // Screenshot 1: Top portion showing view count and Target Work Profile at top level
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-top-section.png',
    fullPage: false
  });
  console.log('Top section screenshot saved.');

  // Screenshot 2: Full page to see all views
  await page.screenshot({
    path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-full-page-hires.png',
    fullPage: true
  });
  console.log('Full page screenshot saved.');

  // Now let's extract structured data about the hierarchy
  console.log('\n=== HIERARCHY ANALYSIS ===\n');

  // Get all text content and look for specific patterns
  const bodyText = await page.textContent('body');

  // Check 1: Total view count
  const viewCountMatch = bodyText.match(/(\d+)\s*views/);
  const viewCount = viewCountMatch ? viewCountMatch[1] : 'NOT FOUND';
  console.log(`CHECK 1 - Total view count: ${viewCount} (expected: 18)`);
  console.log(`  Result: ${viewCount === '18' ? 'PASS' : 'FAIL'}`);

  // Check 2: Target Work Profile with "4 children"
  const twpChildrenMatch = bodyText.match(/Target Work Profile.*?(\d+)\s*child/s);
  const twpChildren = twpChildrenMatch ? twpChildrenMatch[1] : 'NOT FOUND';
  console.log(`\nCHECK 2 - Target Work Profile children: ${twpChildren} (expected: 4)`);
  console.log(`  Result: ${twpChildren === '4' ? 'PASS' : 'FAIL'}`);

  // Check 3: Idea Evolution Map with "1 child"
  const iemChildrenMatch = bodyText.match(/Idea Evolution Map.*?(\d+)\s*child/s);
  const iemChildren = iemChildrenMatch ? iemChildrenMatch[1] : 'NOT FOUND';
  console.log(`\nCHECK 3 - Idea Evolution Map children: ${iemChildren} (expected: 1)`);
  console.log(`  Result: ${iemChildren === '1' ? 'PASS' : 'FAIL'}`);

  // Check 4: Conditions of Possibility with "4 children"
  const copChildrenMatch = bodyText.match(/Conditions of Possibility.*?(\d+)\s*child/s);
  const copChildren = copChildrenMatch ? copChildrenMatch[1] : 'NOT FOUND';
  console.log(`\nCHECK 4 - Conditions of Possibility children: ${copChildren} (expected: 4)`);
  console.log(`  Result: ${copChildren === '4' ? 'PASS' : 'FAIL'}`);

  // Check 5: COP children - Enabling Conditions, Constraining Conditions, Counterfactual Analysis, Synthetic Judgment
  const copChildViews = [
    'Enabling Conditions',
    'Constraining Conditions',
    'Counterfactual Analysis',
    'Synthetic Judgment'
  ];
  console.log(`\nCHECK 5 - COP child views:`);
  for (const child of copChildViews) {
    const found = bodyText.includes(child);
    console.log(`  ${found ? 'FOUND' : 'MISSING'}: ${child}`);
  }

  // Check 6: Verify renderer types for COP children
  // From the text we can parse: "Enabling Conditions" should be card_grid, etc.
  console.log(`\nCHECK 6 - COP child renderer verification:`);
  // Look for the pattern near each child view name
  const enablingMatch = bodyText.match(/Enabling Conditions.*?card_grid/s);
  const constrainingMatch = bodyText.match(/Constraining Conditions.*?card_grid/s);
  const counterfactualMatch = bodyText.match(/Counterfactual Analysis.*?prose/s);
  const syntheticMatch = bodyText.match(/Synthetic Judgment.*?prose/s);
  console.log(`  Enabling Conditions -> card_grid: ${enablingMatch ? 'PASS' : 'FAIL'}`);
  console.log(`  Constraining Conditions -> card_grid: ${constrainingMatch ? 'PASS' : 'FAIL'}`);
  console.log(`  Counterfactual Analysis -> prose: ${counterfactualMatch ? 'PASS' : 'FAIL'}`);
  console.log(`  Synthetic Judgment -> prose: ${syntheticMatch ? 'PASS' : 'FAIL'}`);

  // Check 7: TWP child views
  const twpChildViews = [
    'Conceptual Framework',
    'Semantic Constellation',
    'Inferential Commitments',
    'Concept Evolution'
  ];
  console.log(`\nCHECK 7 - TWP child views:`);
  for (const child of twpChildViews) {
    const found = bodyText.includes(child);
    console.log(`  ${found ? 'FOUND' : 'MISSING'}: ${child}`);
  }

  // Check 8: Verify TWP is top-level (appears before any nested indent)
  // We can check its position relative to other top-level views
  const topLevelOrder = [];
  const topLevelViews = [
    'Target Work Profile',
    'Relationship Landscape',
    'Idea Evolution Map',
    'Tactics & Strategies',
    'Conditions of Possibility',
    'Genealogical Portrait',
    'Raw Engine Output',
    'Chain Execution Log'
  ];

  console.log(`\nCHECK 8 - Top-level view order (by position in page text):`);
  for (const view of topLevelViews) {
    const pos = bodyText.indexOf(view);
    if (pos >= 0) {
      topLevelOrder.push({ name: view, pos });
    }
  }
  topLevelOrder.sort((a, b) => a.pos - b.pos);
  topLevelOrder.forEach((v, i) => {
    console.log(`  ${i + 1}. ${v.name} (pos: ${v.pos})`);
  });

  // Now let's take targeted screenshots of specific sections
  // Find the COP section and screenshot it
  console.log('\n=== TAKING TARGETED SCREENSHOTS ===\n');

  // Scroll to Conditions of Possibility section
  const copSection = await page.$('text=Conditions of Possibility');
  if (copSection) {
    await copSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    // Get bounding box to take a region screenshot
    const copBox = await copSection.boundingBox();
    if (copBox) {
      await page.screenshot({
        path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-cop-section.png',
        clip: {
          x: 0,
          y: Math.max(0, copBox.y - 20),
          width: 1400,
          height: 350
        }
      });
      console.log('COP section screenshot saved.');
    }
  }

  // Scroll to Target Work Profile section
  const twpSection = await page.$('text=Target Work Profile');
  if (twpSection) {
    await twpSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    const twpBox = await twpSection.boundingBox();
    if (twpBox) {
      await page.screenshot({
        path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-twp-section.png',
        clip: {
          x: 0,
          y: Math.max(0, twpBox.y - 20),
          width: 1400,
          height: 350
        }
      });
      console.log('TWP section screenshot saved.');
    }
  }

  // Scroll to Idea Evolution Map section
  const iemSection = await page.$('text=Idea Evolution Map');
  if (iemSection) {
    await iemSection.scrollIntoViewIfNeeded();
    await page.waitForTimeout(500);

    const iemBox = await iemSection.boundingBox();
    if (iemBox) {
      await page.screenshot({
        path: '/home/evgeny/projects/analyzer-v2/test-screenshots/views-iem-section.png',
        clip: {
          x: 0,
          y: Math.max(0, iemBox.y - 20),
          width: 1400,
          height: 200
        }
      });
      console.log('IEM section screenshot saved.');
    }
  }

  console.log('\n=== SUMMARY ===');
  console.log(`Total views: ${viewCount}/18`);
  console.log(`TWP is top-level: ${topLevelOrder[0]?.name === 'Target Work Profile' ? 'YES (first!)' : 'Check position above'}`);
  console.log(`TWP children: ${twpChildren}/4`);
  console.log(`IEM children: ${iemChildren}/1`);
  console.log(`COP children: ${copChildren}/4`);

  await browser.close();
  console.log('\nDone!');
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
