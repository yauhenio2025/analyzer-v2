import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-detail';
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// Clean previous screenshots
for (const f of fs.readdirSync(SCREENSHOTS_DIR)) {
    fs.unlinkSync(path.join(SCREENSHOTS_DIR, f));
}

let stepNum = 0;
async function screenshot(page, name, opts = {}) {
    stepNum++;
    const filepath = path.join(SCREENSHOTS_DIR, `${String(stepNum).padStart(2, '0')}-${name}.png`);
    await page.screenshot({ path: filepath, ...opts });
    console.log(`  [Screenshot ${stepNum}] ${name}`);
    return filepath;
}

async function main() {
    const browser = await chromium.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    // Use larger viewport for better detail
    const context = await browser.newContext({
        viewport: { width: 1440, height: 1200 }
    });

    const page = await context.newPage();

    page.on('console', msg => {
        const text = msg.text();
        const lower = text.toLowerCase();
        if (lower.includes('present') || lower.includes('polish') || msg.type() === 'error') {
            console.log(`  [console.${msg.type()}] ${text.substring(0, 300)}`);
        }
    });

    page.on('response', resp => {
        const url = resp.url();
        if (url.includes('polish') || url.includes('import-v2') || url.includes('genealogy/jobs')) {
            console.log(`  [NET <-] ${resp.status()} ${url}`);
        }
    });

    try {
        // Step 1: Navigate to genealogy page
        console.log('\n=== Navigate to Genealogy page ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-benanav-001/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await page.waitForTimeout(5000);

        // Step 2: Check if V2 data is already loaded (from previous import)
        let bodyText = await page.textContent('body');
        let hasV2 = bodyText.includes('Present') || bodyText.includes('Idea Evolution') || bodyText.includes('Close V2');
        console.log(`  V2 data already loaded: ${hasV2}`);

        if (!hasV2) {
            // Need to import
            console.log('  Need to import V2 data...');
            await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
            await page.waitForTimeout(1000);

            const jobInput = await page.$('input[placeholder*="job"]');
            if (jobInput) {
                await jobInput.fill('job-7d32be316d06');
                await page.waitForTimeout(300);
                const importBtn = await page.$('button:has-text("Import from v2")');
                if (importBtn && !(await importBtn.isDisabled())) {
                    console.log('  Clicking Import...');
                    await importBtn.click();

                    // Wait for import (up to 5 min)
                    for (let i = 0; i < 150; i++) {
                        await page.waitForTimeout(2000);
                        bodyText = await page.textContent('body');
                        if (bodyText.includes('Present') || bodyText.includes('Idea Evolution')) {
                            console.log(`  Import completed after ~${(i+1)*2}s`);
                            break;
                        }
                        if (bodyText.includes('Import failed')) {
                            console.log('  Import failed!');
                            break;
                        }
                        if (i % 15 === 14) console.log(`  Waiting... (${(i+1)*2}s)`);
                    }
                }
            }
        }

        // Scroll to Analysis Results section
        await page.evaluate(() => {
            const el = document.querySelector('.gen-v2-results') ||
                        document.querySelector('[class*="v2-result"]') ||
                        document.querySelector('h2');
            // Find "Analysis Results" heading
            const headings = document.querySelectorAll('h2, h3');
            for (const h of headings) {
                if (h.textContent.includes('Analysis Results') || h.textContent.includes('V2')) {
                    h.scrollIntoView({ block: 'start' });
                    window.scrollBy(0, -50);
                    return;
                }
            }
        });
        await page.waitForTimeout(1000);
        await screenshot(page, 'v2-results-section');

        // Step 3: Find the V2 tab content with Present button
        console.log('\n=== Find V2 tab content ===');

        // Get all gen-tab-btn elements (the V2 view tabs)
        const tabTexts = await page.$$eval('.gen-tab-btn', els =>
            els.map(el => ({
                text: el.textContent.trim().substring(0, 60),
                active: el.classList.contains('active')
            }))
        );
        console.log('  V2 tabs:');
        tabTexts.forEach(t => console.log(`    ${t.active ? '>> ' : '   '}[${t.text}]`));

        // Click on the first (active) tab to ensure we're on the right view
        const firstTab = await page.$('.gen-tab-btn.active');
        if (firstTab) {
            const tabName = await firstTab.textContent();
            console.log(`  Active tab: "${tabName.trim()}"`);
        }

        // Step 4: Get the Present button and take detailed BEFORE screenshots
        console.log('\n=== BEFORE Present click ===');

        let presentBtn = await page.$('button:has-text("Present")');
        if (!presentBtn) {
            // May need to look for it within the gen-link-btn class
            presentBtn = await page.$('.gen-link-btn:has-text("Present")');
        }

        if (!presentBtn) {
            console.log('  Present button NOT found');
            // List all buttons with gen-link class
            const genBtns = await page.$$eval('.gen-link-btn', els =>
                els.map(el => el.textContent.trim())
            );
            console.log('  gen-link-btn buttons:', genBtns);
            await screenshot(page, 'no-present', true);
            return;
        }

        // Scroll to show the V2 content area (the rendered view)
        await presentBtn.scrollIntoViewIfNeeded();
        await page.waitForTimeout(500);

        // Take a screenshot focused on the toolbar + content area
        // First, find the V2 content container
        const v2ContentBounds = await page.evaluate(() => {
            // The V2 content is in .gen-v2-results or similar
            const container = document.querySelector('.gen-v2-results') ||
                             document.querySelector('.gen-tab-content');
            if (container) {
                const rect = container.getBoundingClientRect();
                return { x: rect.x, y: rect.y, width: rect.width, height: Math.min(rect.height, 1200) };
            }
            return null;
        });

        // Take a detail screenshot of just the content area
        if (v2ContentBounds) {
            await screenshot(page, 'BEFORE-content-area', {
                clip: {
                    x: Math.max(0, v2ContentBounds.x),
                    y: Math.max(0, v2ContentBounds.y),
                    width: Math.min(v2ContentBounds.width, 1440),
                    height: Math.min(v2ContentBounds.height, 1200)
                }
            });
        }

        // Take full viewport BEFORE screenshot
        await screenshot(page, 'BEFORE-viewport');

        // Check inline styles BEFORE polishing
        const beforeStyles = await page.evaluate(() => {
            const cards = document.querySelectorAll('.accordion-card, .gen-prose-card, [class*="card"]');
            const styles = [];
            for (const card of Array.from(cards).slice(0, 5)) {
                const computed = getComputedStyle(card);
                styles.push({
                    class: card.className.substring(0, 60),
                    bg: computed.backgroundColor,
                    color: computed.color,
                    border: computed.border,
                    padding: computed.padding,
                    fontFamily: computed.fontFamily.substring(0, 40),
                    inlineStyle: card.style.cssText.substring(0, 100)
                });
            }
            return styles;
        });
        console.log('  Before styles (first 5 cards):');
        beforeStyles.forEach(s => console.log(`    bg=${s.bg} color=${s.color} border="${s.border}" inline="${s.inlineStyle}"`));

        // Step 5: Click Present
        console.log('\n=== Clicking Present ===');
        await presentBtn.click();

        // Wait for polishing
        for (let i = 0; i < 60; i++) {
            await page.waitForTimeout(2000);
            const text = await page.textContent('body');
            if (text.includes('Reset') && !text.includes('Polishing')) {
                console.log(`  Polishing done after ~${(i+1)*2}s`);
                break;
            }
            if (text.includes('Polish failed')) {
                const errSpan = await page.$('span:has-text("Polish failed")');
                const errText = errSpan ? await errSpan.textContent() : 'unknown';
                console.log(`  Polish FAILED: ${errText}`);
                await screenshot(page, 'POLISH-FAILED');
                break;
            }
            if (i % 5 === 4) console.log(`  Polishing... (${(i+1)*2}s)`);
        }

        await page.waitForTimeout(1000);

        // Step 6: AFTER screenshots
        console.log('\n=== AFTER Present click ===');

        // Style info
        const styleInfo = await page.$$eval('span', els =>
            els.filter(el => {
                const t = el.textContent;
                return t && (t.includes('cached') || (t.includes('s)') && t.includes('(')));
            }).map(el => el.textContent.trim())
        );
        console.log('  Style info:', styleInfo);

        // Take AFTER viewport screenshot
        await screenshot(page, 'AFTER-viewport');

        // Take AFTER content area
        if (v2ContentBounds) {
            const afterBounds = await page.evaluate(() => {
                const container = document.querySelector('.gen-v2-results') ||
                                 document.querySelector('.gen-tab-content');
                if (container) {
                    const rect = container.getBoundingClientRect();
                    return { x: rect.x, y: rect.y, width: rect.width, height: Math.min(rect.height, 1200) };
                }
                return null;
            });
            if (afterBounds) {
                await screenshot(page, 'AFTER-content-area', {
                    clip: {
                        x: Math.max(0, afterBounds.x),
                        y: Math.max(0, afterBounds.y),
                        width: Math.min(afterBounds.width, 1440),
                        height: Math.min(afterBounds.height, 1200)
                    }
                });
            }
        }

        // Check inline styles AFTER polishing
        const afterStyles = await page.evaluate(() => {
            const cards = document.querySelectorAll('.accordion-card, .gen-prose-card, [class*="card"]');
            const styles = [];
            for (const card of Array.from(cards).slice(0, 5)) {
                const computed = getComputedStyle(card);
                styles.push({
                    class: card.className.substring(0, 60),
                    bg: computed.backgroundColor,
                    color: computed.color,
                    border: computed.border,
                    padding: computed.padding,
                    fontFamily: computed.fontFamily.substring(0, 40),
                    inlineStyle: card.style.cssText.substring(0, 200)
                });
            }
            return styles;
        });
        console.log('  After styles (first 5 cards):');
        afterStyles.forEach(s => console.log(`    bg=${s.bg} color=${s.color} border="${s.border}" inline="${s.inlineStyle}"`));

        // Compare styles
        console.log('\n  === STYLE COMPARISON ===');
        for (let i = 0; i < Math.min(beforeStyles.length, afterStyles.length); i++) {
            const b = beforeStyles[i];
            const a = afterStyles[i];
            if (b.bg !== a.bg) console.log(`  Card ${i}: bg changed: ${b.bg} -> ${a.bg}`);
            if (b.color !== a.color) console.log(`  Card ${i}: color changed: ${b.color} -> ${a.color}`);
            if (b.border !== a.border) console.log(`  Card ${i}: border changed`);
            if (b.inlineStyle !== a.inlineStyle) console.log(`  Card ${i}: inline style changed: "${a.inlineStyle}"`);
        }

        // Check for _style_overrides in the DOM
        const styleOverrides = await page.evaluate(() => {
            // Look for elements with style attributes that might be from polish
            const styled = document.querySelectorAll('[style*="background"], [style*="color"], [style*="border"]');
            return Array.from(styled).slice(0, 10).map(el => ({
                tag: el.tagName,
                class: el.className?.toString()?.substring(0, 50) || '',
                style: el.style.cssText.substring(0, 200)
            }));
        });
        console.log('\n  Elements with inline styles (potential polish overrides):');
        styleOverrides.forEach(e => console.log(`    <${e.tag} class="${e.class}"> style="${e.style}"`));

        // Step 7: Reset
        console.log('\n=== Reset ===');
        const resetBtn = await page.$('button:has-text("Reset")');
        if (resetBtn) {
            await resetBtn.click();
            await page.waitForTimeout(2000);
            await screenshot(page, 'AFTER-reset-viewport');

            // Verify Present is back
            const afterReset = await page.textContent('body');
            console.log(`  Present restored: ${afterReset.includes('Present')}`);
        }

        // Step 8: Try a second tab to test Present on different content
        console.log('\n=== Try Present on different tab ===');
        const allTabs = await page.$$('.gen-tab-btn');
        if (allTabs.length > 1) {
            // Click second tab
            const secondTab = allTabs[1];
            const tabText = await secondTab.textContent();
            console.log(`  Clicking tab: "${tabText.trim()}"...`);
            await secondTab.click();
            await page.waitForTimeout(2000);
            await screenshot(page, 'second-tab');

            // Find and click Present on new tab
            const present2 = await page.$('button:has-text("Present"), .gen-link-btn:has-text("Present")');
            if (present2) {
                console.log('  Clicking Present on second tab...');
                await screenshot(page, 'second-tab-BEFORE');
                await present2.click();

                for (let i = 0; i < 60; i++) {
                    await page.waitForTimeout(2000);
                    const text = await page.textContent('body');
                    if (text.includes('Reset') && !text.includes('Polishing')) {
                        console.log(`  Polishing done after ~${(i+1)*2}s`);
                        break;
                    }
                    if (text.includes('Polish failed')) {
                        console.log('  Polish failed on second tab');
                        break;
                    }
                    if (i % 5 === 4) console.log(`  Polishing... (${(i+1)*2}s)`);
                }
                await page.waitForTimeout(1000);
                await screenshot(page, 'second-tab-AFTER');

                // Style info for second tab
                const info2 = await page.$$eval('span', els =>
                    els.filter(el => el.textContent?.includes('cached') || (el.textContent?.includes('s)') && el.textContent?.includes('('))).map(el => el.textContent.trim())
                );
                console.log('  Style info:', info2);
            }
        }

        console.log('\n=== TEST COMPLETE ===');

    } catch (err) {
        console.error('ERROR:', err.message);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
