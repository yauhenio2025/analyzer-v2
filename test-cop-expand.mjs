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
  await page.waitForTimeout(2000);

  // Now click on Constraining Conditions to expand it
  console.log('Expanding Constraining Conditions...');
  const constrainingHeader = await page.$('h3:has-text("Constraining Conditions")');
  if (constrainingHeader) {
    await constrainingHeader.click();
    await page.waitForTimeout(1500);
    console.log('  Clicked Constraining Conditions header');
  } else {
    // Try clicking the section itself
    const section = await page.$('.gen-conditions-section:has-text("Constraining Conditions")');
    if (section) {
      await section.click();
      await page.waitForTimeout(1500);
      console.log('  Clicked Constraining Conditions section');
    }
  }

  // Scroll down to see the constraining conditions
  await page.evaluate(() => {
    const el = document.querySelector('.gen-conditions-section:nth-child(3)');
    if (el) el.scrollIntoView({ behavior: 'instant', block: 'start' });
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-constraining-01.png`, fullPage: false });

  // Analyze constraining conditions cards
  const constrainingCards = await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    let constrainingSection = null;
    sections.forEach(s => {
      if (s.textContent.includes('Constraining Conditions')) {
        constrainingSection = s;
      }
    });
    if (!constrainingSection) return { error: 'Section not found' };

    const cards = constrainingSection.querySelectorAll('.gen-condition-card');
    const result = {
      cardCount: cards.length,
      cards: []
    };

    cards.forEach((card, i) => {
      const typeChip = card.querySelector('.gen-condition-type');
      const managedBadge = card.querySelector('.gen-managed-badge');
      const style = typeChip ? window.getComputedStyle(typeChip) : null;

      result.cards.push({
        index: i,
        class: card.className,
        typeText: typeChip?.textContent?.trim() || 'none',
        typeColor: style?.color || 'none',
        typeBg: style?.backgroundColor || 'none',
        managedText: managedBadge?.textContent?.trim() || 'none',
        firstLine: card.textContent?.trim().substring(0, 120)
      });
    });

    return result;
  });
  console.log('\nConstraining condition cards:');
  console.log(`  Total cards: ${constrainingCards.cardCount}`);
  constrainingCards.cards?.forEach(c => {
    console.log(`  Card ${c.index}: class="${c.class}"`);
    console.log(`    type="${c.typeText}" (color=${c.typeColor}, bg=${c.typeBg})`);
    console.log(`    managed="${c.managedText}"`);
    console.log(`    text: "${c.firstLine}"`);
  });

  // Scroll more to see constraining cards
  await page.evaluate(() => window.scrollBy(0, 600));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-constraining-02.png`, fullPage: false });

  // Now expand Synthetic Judgment
  console.log('\nExpanding Synthetic Judgment...');
  const syntheticHeader = await page.$('h3:has-text("Synthetic Judgment")');
  if (syntheticHeader) {
    await syntheticHeader.click();
    await page.waitForTimeout(1500);
    console.log('  Clicked Synthetic Judgment header');
  }

  // Scroll to synthetic judgment
  await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    const last = sections[sections.length - 1];
    if (last) last.scrollIntoView({ behavior: 'instant', block: 'start' });
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-synthetic-01.png`, fullPage: false });

  // Analyze synthetic judgment content
  const syntheticContent = await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    let syntheticSection = null;
    sections.forEach(s => {
      if (s.textContent.includes('Synthetic Judgment')) {
        syntheticSection = s;
      }
    });
    if (!syntheticSection) return { error: 'Section not found' };

    return {
      class: syntheticSection.className,
      childCount: syntheticSection.childElementCount,
      innerText: syntheticSection.innerText?.substring(0, 500),
      hasAccordion: syntheticSection.querySelector('[class*="accordion"]') !== null,
      hasCard: syntheticSection.querySelector('[class*="card"]') !== null,
      children: Array.from(syntheticSection.children).map(c => ({
        tag: c.tagName,
        class: c.className,
        textPreview: c.textContent?.trim().substring(0, 80)
      }))
    };
  });
  console.log('\nSynthetic Judgment section:');
  console.log(`  Class: ${syntheticContent.class}`);
  console.log(`  Child count: ${syntheticContent.childCount}`);
  console.log(`  Has accordion: ${syntheticContent.hasAccordion}`);
  console.log(`  Has card: ${syntheticContent.hasCard}`);
  console.log('  Children:');
  syntheticContent.children?.forEach((c, i) => {
    console.log(`    [${i}] <${c.tag} class="${c.class}"> "${c.textPreview}"`);
  });
  console.log(`  Content preview: "${syntheticContent.innerText?.substring(0, 300)}"`);

  // Scroll down within synthetic judgment
  await page.evaluate(() => window.scrollBy(0, 500));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-synthetic-02.png`, fullPage: false });

  // Also check Counterfactual Analysis
  console.log('\nExpanding Counterfactual Analysis...');
  const counterfactualHeader = await page.$('h3:has-text("Counterfactual Analysis")');
  if (counterfactualHeader) {
    await counterfactualHeader.click();
    await page.waitForTimeout(1500);
    console.log('  Clicked Counterfactual Analysis header');
  }

  await page.evaluate(() => {
    const sections = document.querySelectorAll('.gen-conditions-section');
    sections.forEach(s => {
      if (s.textContent.includes('Counterfactual')) {
        s.scrollIntoView({ behavior: 'instant', block: 'start' });
      }
    });
  });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-counterfactual-01.png`, fullPage: false });

  // Check the overall coloring scheme of enabling vs constraining type chips
  const allTypeChips = await page.evaluate(() => {
    const chips = document.querySelectorAll('.gen-condition-type');
    return Array.from(chips).map(chip => {
      const style = window.getComputedStyle(chip);
      const parent = chip.closest('.gen-condition-card');
      return {
        text: chip.textContent?.trim(),
        bgColor: style.backgroundColor,
        color: style.color,
        parentClass: parent?.className || 'none'
      };
    });
  });
  console.log('\nAll condition type chips:');
  allTypeChips.forEach(c => {
    console.log(`  "${c.text}" -> bg=${c.bgColor}, color=${c.color}, parent=${c.parentClass}`);
  });

  // Final full page screenshot with all sections expanded
  await page.screenshot({ path: `${SCREENSHOT_DIR}/cop-all-expanded-fullpage.png`, fullPage: true });

  console.log('\n=== EXPANSION TEST COMPLETE ===');
  await browser.close();
}

main().catch(err => {
  console.error('Test failed:', err);
  process.exit(1);
});
