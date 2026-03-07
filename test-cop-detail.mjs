import { chromium } from 'playwright';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots';
const URL = 'https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy';

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
  const page = await context.newPage();

  console.log('Navigating to genealogy page...');
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForSelector('text=Analysis Results', { timeout: 30000 });

  // Click the Conditions of Possibility tab
  console.log('Clicking Conditions of Possibility tab...');
  await page.click('button:has-text("Conditions of Possibility")');
  await page.waitForTimeout(3000);

  // Screenshot 1: Top of the Conditions of Possibility content
  console.log('Taking detailed screenshots...');

  // Scroll to the tab content area first
  const tabContent = await page.$('.gen-tab-content');
  if (tabContent) {
    await tabContent.scrollIntoViewIfNeeded();
  }
  await page.waitForTimeout(500);

  // Screenshot of the full visible area
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-detail-01-top.png`, fullPage: false });

  // Now let's get detailed info about the structure
  console.log('\n=== DETAILED STRUCTURE ANALYSIS ===\n');

  // 1. Check enabling conditions section
  const enablingSection = await page.evaluate(() => {
    const sections = document.querySelectorAll('[class*="section"], h3, h4, [class*="heading"]');
    const results = [];
    sections.forEach(s => {
      if (s.textContent.includes('Enabling') || s.textContent.includes('Constraining') || s.textContent.includes('Synthetic')) {
        results.push({
          tag: s.tagName,
          class: s.className,
          text: s.textContent.trim().substring(0, 100)
        });
      }
    });
    return results;
  });
  console.log('Section headings found:');
  enablingSection.forEach(s => console.log(`  <${s.tag} class="${s.class}"> ${s.text}`));

  // 2. Check the card structure inside enabling conditions
  const cardStructure = await page.evaluate(() => {
    // Find all cards in the conditions content
    const cards = document.querySelectorAll('[class*="card"]');
    const conditionCards = [];
    cards.forEach(card => {
      const text = card.textContent || '';
      if (text.includes('implicitly_leveraged') || text.includes('explicitly_leveraged') ||
          text.includes('Implicitly') || text.includes('Explicitly') ||
          text.includes('How it enables') || text.includes('How it constrains')) {
        conditionCards.push({
          class: card.className,
          childElementCount: card.childElementCount,
          firstLine: text.trim().substring(0, 150)
        });
      }
    });
    return conditionCards;
  });
  console.log(`\nCondition cards found: ${cardStructure.length}`);
  cardStructure.slice(0, 3).forEach((c, i) => {
    console.log(`  Card ${i}: class="${c.class}", children=${c.childElementCount}`);
    console.log(`    Text: "${c.firstLine}"`);
  });

  // 3. Check for colored chips - look at the actual styles
  const chipDetails = await page.evaluate(() => {
    const chips = document.querySelectorAll('[class*="chip"], [class*="Chip"], [class*="badge"], [class*="Badge"], [class*="tag"], [class*="Tag"]');
    const results = [];
    chips.forEach(chip => {
      const style = window.getComputedStyle(chip);
      const text = chip.textContent.trim();
      if (text && (text.includes('leveraged') || text.includes('institutional') || text.includes('political') ||
          text.includes('economic') || text.includes('epistemic') || text.includes('technological') ||
          text.includes('cultural') || text.includes('discursive') || text.includes('material') ||
          text.includes('Authority') || text.includes('Methodological') || text.includes('Conceptual'))) {
        results.push({
          text: text.substring(0, 60),
          class: chip.className,
          bgColor: style.backgroundColor,
          color: style.color,
          borderColor: style.borderColor
        });
      }
    });
    return results;
  });
  console.log(`\nRelevant chips with colors: ${chipDetails.length}`);
  chipDetails.forEach(c => {
    console.log(`  "${c.text}" -> bg=${c.bgColor}, color=${c.color}, border=${c.borderColor}`);
    console.log(`    class: ${c.class}`);
  });

  // 4. Check if accordion is used for sections
  const sectionStructure = await page.evaluate(() => {
    // Look for the accordion-like sections
    const allElements = document.querySelectorAll('.gen-tab-content > div > *');
    const structure = [];
    allElements.forEach((el, i) => {
      if (i < 30) {
        structure.push({
          tag: el.tagName,
          class: el.className?.substring(0, 80),
          text: el.textContent?.substring(0, 80)?.trim(),
          childCount: el.childElementCount
        });
      }
    });
    return structure;
  });
  console.log('\nTab content top-level structure:');
  sectionStructure.forEach((s, i) => {
    console.log(`  [${i}] <${s.tag} class="${s.class}"> children=${s.childCount} "${s.text}"`);
  });

  // 5. Check for the specific sub-renderer classes
  const subRendererCheck = await page.evaluate(() => {
    const checks = {
      copWrapper: document.querySelector('[class*="cop-"]') !== null,
      enablingGrid: document.querySelector('[class*="enabling"]') !== null,
      constrainingList: document.querySelector('[class*="constraining"]') !== null,
      syntheticAccordion: document.querySelector('[class*="synthetic"]') !== null,
      accordionSection: document.querySelector('[class*="accordion-section"]') !== null,
      subRendererSection: document.querySelector('[class*="sub-renderer"]') !== null,
      copConditionCard: document.querySelector('[class*="cop-condition"]') !== null,
    };

    // Also check for any class names containing 'cop'
    const copElements = document.querySelectorAll('[class*="cop"]');
    checks.copElementCount = copElements.length;
    checks.copClasses = Array.from(copElements).slice(0, 5).map(e => e.className);

    return checks;
  });
  console.log('\nSub-renderer class checks:');
  Object.entries(subRendererCheck).forEach(([k, v]) => {
    console.log(`  ${k}: ${JSON.stringify(v)}`);
  });

  // 6. Look at the accordion sections more closely
  const accordionSections = await page.evaluate(() => {
    // The accordion uses collapsible sections - find them
    const headers = document.querySelectorAll('[class*="accordion"] [class*="header"], [class*="section-header"], [class*="collapsible"]');
    const results = [];
    headers.forEach(h => {
      results.push({
        class: h.className,
        text: h.textContent?.trim().substring(0, 100),
        tag: h.tagName
      });
    });

    // Also find the section containers
    const containers = document.querySelectorAll('[class*="accordion-section"], [class*="section-container"]');
    results.push({ containerCount: containers.length });

    return results;
  });
  console.log('\nAccordion sections:');
  accordionSections.forEach(a => console.log(`  ${JSON.stringify(a)}`));

  // 7. Scroll down to see constraining conditions and synthetic judgment
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-detail-02-bottom.png`, fullPage: false });

  // 8. Check the enabling conditions card layout specifically
  const enablingCardsLayout = await page.evaluate(() => {
    // Find the enabling conditions container
    const allText = document.body.innerText;
    const enablingIdx = allText.indexOf('Enabling Conditions');
    const constrainingIdx = allText.indexOf('Constraining Conditions');
    const syntheticIdx = allText.indexOf('Synthetic Judgment');

    return {
      enablingFound: enablingIdx > -1,
      constrainingFound: constrainingIdx > -1,
      syntheticFound: syntheticIdx > -1,
      enablingBeforeConstraining: enablingIdx < constrainingIdx,
      constrainingBeforeSynthetic: constrainingIdx < syntheticIdx,
    };
  });
  console.log('\nSection ordering:');
  console.log(`  Enabling before Constraining: ${enablingCardsLayout.enablingBeforeConstraining}`);
  console.log(`  Constraining before Synthetic: ${enablingCardsLayout.constrainingBeforeSynthetic}`);

  // 9. Get full page screenshot
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-detail-03-fullpage.png`, fullPage: true });

  // 10. Check if cards have colored condition_type headers
  const cardHeaders = await page.evaluate(() => {
    // Find elements that contain condition type labels
    const elements = document.querySelectorAll('span, div, p, label');
    const typeLabels = [];
    elements.forEach(el => {
      const text = el.textContent?.trim();
      if (['Authority Establishment', 'Methodological Foundation', 'Conceptual Prerequisite',
           'Empirical Grounding', 'Historical Contextualization', 'Institutional',
           'Political', 'Economic', 'Discursive'].some(t => text === t || text?.startsWith(t))) {
        const style = window.getComputedStyle(el);
        typeLabels.push({
          text: text.substring(0, 40),
          class: el.className,
          tag: el.tagName,
          bgColor: style.backgroundColor,
          color: style.color,
          padding: style.padding,
          borderRadius: style.borderRadius,
          fontSize: style.fontSize
        });
      }
    });
    return typeLabels;
  });
  console.log('\nCondition type labels styling:');
  cardHeaders.forEach(h => {
    console.log(`  "${h.text}" <${h.tag} class="${h.class}">`);
    console.log(`    bg=${h.bgColor}, color=${h.color}, padding=${h.padding}, radius=${h.borderRadius}, size=${h.fontSize}`);
  });

  // 11. Check how_managed values specifically
  const howManagedInfo = await page.evaluate(() => {
    const allText = document.body.innerText;
    const managed = [];
    ['implicitly_leveraged', 'explicitly_leveraged', 'Implicitly_leveraged', 'Explicitly_leveraged',
     'Implicitly Leveraged', 'Explicitly Leveraged'].forEach(term => {
      if (allText.includes(term)) managed.push(term);
    });

    // Find elements containing these terms
    const elements = document.querySelectorAll('span, div');
    const styledManaged = [];
    elements.forEach(el => {
      const text = el.textContent?.trim();
      if (text === 'implicitly_leveraged' || text === 'explicitly_leveraged' ||
          text === 'Implicitly_leveraged' || text === 'Explicitly_leveraged') {
        const style = window.getComputedStyle(el);
        styledManaged.push({
          text,
          class: el.className,
          bgColor: style.backgroundColor,
          color: style.color,
          borderRadius: style.borderRadius
        });
      }
    });

    return { termsFound: managed, styledElements: styledManaged };
  });
  console.log('\nHow_managed values:');
  console.log(`  Terms found: ${howManagedInfo.termsFound.join(', ')}`);
  howManagedInfo.styledElements.forEach(s => {
    console.log(`  "${s.text}" class="${s.class}" bg=${s.bgColor} color=${s.color} radius=${s.borderRadius}`);
  });

  console.log('\n=== TEST COMPLETE ===');
  await browser.close();
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
