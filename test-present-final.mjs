import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-final';
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

    const context = await browser.newContext({
        viewport: { width: 1440, height: 1200 }
    });

    const page = await context.newPage();

    // Track ALL console messages
    page.on('console', msg => {
        const text = msg.text();
        console.log(`  [console.${msg.type()}] ${text.substring(0, 300)}`);
    });

    // Track polish request/response in detail
    page.on('request', req => {
        if (req.url().includes('polish')) {
            console.log(`  [POLISH REQ ->] ${req.method()} ${req.url()}`);
            console.log(`  [POLISH BODY] ${req.postData()?.substring(0, 300)}`);
        }
    });
    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            console.log(`  [POLISH RESP <-] ${resp.status()} ${resp.url()}`);
            try {
                const body = await resp.text();
                console.log(`  [POLISH RESP BODY] (${body.length} chars) ${body.substring(0, 500)}`);
            } catch (e) {
                console.log(`  [POLISH RESP ERROR] ${e.message}`);
            }
        }
    });

    try {
        // Step 1: Navigate
        console.log('\n=== Navigate ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-benanav-001/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await page.waitForTimeout(5000);

        // Check if V2 data already loaded
        let bodyText = await page.textContent('body');
        const hasV2 = bodyText.includes('V2 ORCHESTRATOR') || bodyText.includes('Idea Evolution');
        console.log(`  V2 loaded: ${hasV2}`);

        if (!hasV2) {
            console.log('  Need to import...');
            await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
            await page.waitForTimeout(1000);
            const input = await page.$('input[placeholder*="job"]');
            if (input) {
                await input.fill('job-7d32be316d06');
                const btn = await page.$('button:has-text("Import from v2")');
                if (btn && !(await btn.isDisabled())) {
                    await btn.click();
                    for (let i = 0; i < 150; i++) {
                        await page.waitForTimeout(2000);
                        bodyText = await page.textContent('body');
                        if (bodyText.includes('Present') || bodyText.includes('Idea Evolution')) {
                            console.log(`  Import done (~${(i+1)*2}s)`);
                            break;
                        }
                        if (bodyText.includes('Import failed')) {
                            console.log('  Import failed');
                            break;
                        }
                        if (i % 15 === 14) console.log(`  Importing... (${(i+1)*2}s)`);
                    }
                }
            }
        }

        // Scroll to the Analysis Results section
        await page.evaluate(() => {
            const headings = document.querySelectorAll('h2, h3');
            for (const h of headings) {
                if (h.textContent.includes('Analysis Results')) {
                    h.scrollIntoView({ block: 'start' });
                    window.scrollBy(0, -20);
                    return;
                }
            }
        });
        await page.waitForTimeout(1000);

        // Click on a V2 tab to ensure we're seeing it (Idea Evolution Map)
        const ideaTab = await page.$('.gen-tab-btn:has-text("Idea Evolution")');
        if (ideaTab) {
            console.log('  Clicking "Idea Evolution Map" tab...');
            await ideaTab.click();
            await page.waitForTimeout(2000);
        }

        await screenshot(page, 'v2-loaded');

        // Scroll down to see the content
        await page.evaluate(() => {
            const results = document.querySelector('.gen-v2-results');
            if (results) {
                const tabs = results.querySelector('.gen-tabs-nav, .gen-results-tabs');
                if (tabs) {
                    tabs.scrollIntoView({ block: 'start' });
                    window.scrollBy(0, -30);
                }
            }
        });
        await page.waitForTimeout(500);
        await screenshot(page, 'scrolled-to-content');

        // Step 2: Find Present button
        console.log('\n=== Find Present button ===');
        let presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            presentBtn = await page.$('button:has-text("Present")');
        }

        if (!presentBtn) {
            // Scroll more to find it
            for (let y = 600; y < 3000; y += 300) {
                await page.evaluate(y => window.scrollTo(0, y), y);
                await page.waitForTimeout(200);
                presentBtn = await page.$('button:has-text("Present")');
                if (presentBtn) break;
            }
        }

        if (!presentBtn) {
            console.log('  Present button NOT found');
            await screenshot(page, 'no-present', { fullPage: true });

            // Debug: list all buttons
            const allBtns = await page.$$eval('button', els =>
                els.filter(el => el.offsetParent !== null).map(el => `[${el.textContent.trim().substring(0,40)}] .${el.className}`)
            );
            console.log('  All visible buttons:', allBtns.join('\n    '));
            return;
        }

        console.log('  Found Present button');
        await presentBtn.scrollIntoViewIfNeeded();
        await page.waitForTimeout(500);

        // BEFORE screenshots
        await screenshot(page, 'BEFORE-present');

        // Scroll down a bit to show more content
        await page.evaluate(() => window.scrollBy(0, 200));
        await page.waitForTimeout(300);
        await screenshot(page, 'BEFORE-content');

        // Scroll back to Present button
        await presentBtn.scrollIntoViewIfNeeded();
        await page.waitForTimeout(300);

        // Step 3: Click Present and monitor carefully
        console.log('\n=== Click Present ===');
        await presentBtn.click();
        console.log('  Present clicked!');

        // Monitor the response closely
        let polishCompleted = false;
        for (let i = 0; i < 90; i++) {
            await page.waitForTimeout(1000);

            // Check for Reset button (appears when polish succeeds)
            const resetExists = await page.$('button:has-text("Reset")');
            if (resetExists && await resetExists.isVisible()) {
                console.log(`  Reset button appeared after ${i+1}s -- POLISHING COMPLETE`);
                polishCompleted = true;
                break;
            }

            // Check for error
            const errorSpan = await page.$('span:has-text("Polish failed")');
            if (errorSpan) {
                const errText = await errorSpan.textContent();
                console.log(`  POLISH ERROR: ${errText}`);
                polishCompleted = true;
                break;
            }

            // Check for "Polishing..." text
            const polishingBtn = await page.$('button:has-text("Polishing...")');
            if (polishingBtn) {
                if (i % 10 === 9) console.log(`  Still polishing... (${i+1}s)`);
            } else {
                // Not polishing anymore, not error, not reset -- check state
                const pageText = await page.textContent('body');
                const hasPresent = pageText.includes('Present') && !pageText.includes('Polishing');
                const hasReset = pageText.includes('Reset');
                console.log(`  Button state at ${i+1}s: Present=${hasPresent} Reset=${hasReset}`);
                if (hasReset) {
                    polishCompleted = true;
                    break;
                }
                if (hasPresent && i > 5) {
                    console.log('  Present button is back without Reset -- polish might have failed silently');
                    break;
                }
            }
        }

        await page.waitForTimeout(1000);

        // AFTER screenshots
        await screenshot(page, 'AFTER-present');
        await page.evaluate(() => window.scrollBy(0, 200));
        await page.waitForTimeout(300);
        await screenshot(page, 'AFTER-content');

        // Check style info
        const styleSpans = await page.$$eval('span', els =>
            els.filter(el => {
                const t = el.textContent || '';
                return (t.includes('cached') || t.includes('explanatory') || t.includes('narrative') || t.includes('school')) && t.length < 200;
            }).map(el => el.textContent.trim())
        );
        console.log('  Style info spans:', styleSpans);

        // Check for style_overrides being applied
        const overrideCheck = await page.evaluate(() => {
            // Look at the rendered content for inline styles from polish
            const allElements = document.querySelectorAll('.gen-v2-results *, .gen-tab-content *');
            const withInlineStyles = [];
            for (const el of allElements) {
                if (el.style.cssText && el.style.cssText.length > 20) {
                    withInlineStyles.push({
                        tag: el.tagName,
                        class: el.className?.toString()?.substring(0, 50) || '',
                        style: el.style.cssText.substring(0, 200)
                    });
                }
            }
            return withInlineStyles.slice(0, 15);
        });
        console.log('  Elements with substantial inline styles:');
        overrideCheck.forEach(e => console.log(`    <${e.tag} class="${e.class}"> style="${e.style}"`));

        // Step 4: Test Reset
        console.log('\n=== Test Reset ===');
        const resetBtn = await page.$('button:has-text("Reset")');
        if (resetBtn) {
            await resetBtn.scrollIntoViewIfNeeded();
            await screenshot(page, 'before-reset');
            await resetBtn.click();
            await page.waitForTimeout(2000);
            await screenshot(page, 'AFTER-reset');

            const afterText = await page.textContent('body');
            console.log(`  Present restored: ${afterText.includes('Present')}`);
            console.log(`  Reset gone: ${!afterText.includes('Reset')}`);

            // Check styles reverted
            const revertCheck = await page.evaluate(() => {
                const allElements = document.querySelectorAll('.gen-v2-results *, .gen-tab-content *');
                let inlineCount = 0;
                for (const el of allElements) {
                    if (el.style.cssText && el.style.cssText.length > 20) inlineCount++;
                }
                return inlineCount;
            });
            console.log(`  Elements with inline styles after reset: ${revertCheck}`);
        } else {
            console.log('  No Reset button found');
        }

        // Step 5: Try clicking Present again (should be instant from cache)
        console.log('\n=== Click Present again (should be cached) ===');
        const present2 = await page.$('button:has-text("Present")');
        if (present2) {
            await present2.scrollIntoViewIfNeeded();
            await present2.click();

            let resetFound = false;
            for (let i = 0; i < 30; i++) {
                await page.waitForTimeout(1000);
                const reset2 = await page.$('button:has-text("Reset")');
                if (reset2 && await reset2.isVisible()) {
                    console.log(`  Cached polish returned after ${i+1}s`);
                    resetFound = true;
                    break;
                }
            }

            if (resetFound) {
                await screenshot(page, 'cached-present-result');
                const cachedInfo = await page.$$eval('span', els =>
                    els.filter(el => el.textContent?.includes('cached')).map(el => el.textContent.trim())
                );
                console.log('  Cached info:', cachedInfo);
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
