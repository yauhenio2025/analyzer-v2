import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-comprehensive';
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
for (const f of fs.readdirSync(SCREENSHOTS_DIR)) fs.unlinkSync(path.join(SCREENSHOTS_DIR, f));

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

    page.on('console', msg => {
        const text = msg.text();
        if (text.includes('[STATE]') || text.includes('[POLISH]') || msg.type() === 'error') {
            console.log(`  [console.${msg.type()}] ${text.substring(0, 500)}`);
        }
    });

    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            try {
                const body = await resp.text();
                console.log(`  [POLISH RESP] ${resp.status()} (${body.length} chars)`);
                // Parse and show style_overrides keys
                try {
                    const parsed = JSON.parse(body);
                    console.log(`  [POLISH] style_school: ${parsed.style_school}`);
                    console.log(`  [POLISH] cached: ${parsed.cached}`);
                    const overrides = parsed.polished_payload?.style_overrides;
                    if (overrides) {
                        console.log(`  [POLISH] style_overrides keys: ${Object.keys(overrides).join(', ')}`);
                    }
                } catch {}
            } catch {}
        }
    });

    try {
        console.log('\n=== Navigate ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-benanav-001/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await page.waitForTimeout(5000);

        let bodyText = await page.textContent('body');
        const hasV2 = bodyText.includes('V2 ORCHESTRATOR') || bodyText.includes('Idea Evolution') || bodyText.includes('Present');
        console.log(`  V2 loaded: ${hasV2}`);

        if (!hasV2) {
            console.log('  V2 data not found. Importing...');
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
                        if (bodyText.includes('Import failed')) { console.log('  Import failed'); break; }
                        if (i % 15 === 14) console.log(`  Importing... (${(i+1)*2}s)`);
                    }
                }
            }
        }

        // List all available tabs
        console.log('\n=== List V2 tabs ===');
        const tabs = await page.$$eval('button', els =>
            els.filter(el => {
                const parent = el.closest('.gen-v2-results');
                return parent && el.offsetParent !== null && !el.textContent.includes('Present') && !el.textContent.includes('Reset');
            }).map(el => ({
                text: el.textContent.trim().substring(0, 60),
                active: el.classList.contains('active') || el.getAttribute('aria-selected') === 'true',
                className: el.className,
            }))
        );
        console.log('  Tabs:');
        tabs.forEach(t => console.log(`    ${t.active ? '>> ' : '   '}[${t.text}] class="${t.className}"`));

        // ============================================================
        // TEST 1: Present on "Conditions of Possibility" (accordion renderer)
        // ============================================================
        console.log('\n========================================');
        console.log('=== TEST 1: Conditions of Possibility (accordion) ===');
        console.log('========================================');

        // Click Conditions of Possibility tab
        const conditionsTab = await page.$('button:has-text("Conditions of Possibility")');
        if (conditionsTab) {
            await conditionsTab.click();
            await page.waitForTimeout(2000);
        } else {
            console.log('  WARNING: Conditions of Possibility tab not found');
        }

        // Scroll to content area
        await page.evaluate(() => {
            const v2 = document.querySelector('.gen-v2-results');
            if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
        });
        await page.waitForTimeout(500);

        // BEFORE screenshot
        await screenshot(page, 'conditions-BEFORE-top');
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'conditions-BEFORE-content');

        // Count elements with inline styles BEFORE
        const beforeStyles = await page.evaluate(() => {
            const all = document.querySelectorAll('.gen-v2-results *');
            let withStyles = 0;
            let totalStyleLength = 0;
            for (const el of all) {
                if (el.style.cssText && el.style.cssText.length > 10) {
                    withStyles++;
                    totalStyleLength += el.style.cssText.length;
                }
            }
            return { withStyles, totalStyleLength, totalElements: all.length };
        });
        console.log(`  BEFORE: ${beforeStyles.withStyles} elements with inline styles (${beforeStyles.totalStyleLength} chars total out of ${beforeStyles.totalElements} elements)`);

        // Scroll back to Present button
        await page.evaluate(() => {
            const v2 = document.querySelector('.gen-v2-results');
            if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
        });
        await page.waitForTimeout(300);

        // Click Present
        console.log('  Clicking Present...');
        const present1 = await page.$('button.gen-link-btn:has-text("Present")');
        if (!present1) {
            console.log('  Present button not found!');
            await screenshot(page, 'no-present-btn', { fullPage: true });
            return;
        }
        await present1.scrollIntoViewIfNeeded();
        await present1.click();

        // Wait for completion
        let polishDone = false;
        for (let i = 0; i < 90; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                console.log(`  Polish completed in ${i+1}s`);
                polishDone = true;
                break;
            }
            const errSpan = await page.$('span:has-text("Polish failed")');
            if (errSpan) {
                console.log(`  Polish FAILED: ${await errSpan.textContent()}`);
                break;
            }
            if (i % 10 === 9) console.log(`  Polishing... (${i+1}s)`);
        }

        if (!polishDone) {
            console.log('  Polish did not complete in 90s');
            await screenshot(page, 'conditions-TIMEOUT');
        } else {
            await page.waitForTimeout(1000);

            // AFTER screenshots
            await page.evaluate(() => {
                const v2 = document.querySelector('.gen-v2-results');
                if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
            });
            await page.waitForTimeout(300);
            await screenshot(page, 'conditions-AFTER-top');
            await page.evaluate(() => window.scrollBy(0, 400));
            await page.waitForTimeout(300);
            await screenshot(page, 'conditions-AFTER-content');

            // Count elements with inline styles AFTER
            const afterStyles = await page.evaluate(() => {
                const all = document.querySelectorAll('.gen-v2-results *');
                let withStyles = 0;
                let totalStyleLength = 0;
                const samples = [];
                for (const el of all) {
                    if (el.style.cssText && el.style.cssText.length > 10) {
                        withStyles++;
                        totalStyleLength += el.style.cssText.length;
                        if (samples.length < 5) {
                            samples.push({
                                tag: el.tagName,
                                class: (el.className?.toString() || '').substring(0, 50),
                                style: el.style.cssText.substring(0, 200),
                            });
                        }
                    }
                }
                return { withStyles, totalStyleLength, totalElements: all.length, samples };
            });
            console.log(`  AFTER: ${afterStyles.withStyles} elements with inline styles (${afterStyles.totalStyleLength} chars total out of ${afterStyles.totalElements} elements)`);
            console.log(`  DIFF: +${afterStyles.withStyles - beforeStyles.withStyles} elements, +${afterStyles.totalStyleLength - beforeStyles.totalStyleLength} chars`);
            console.log('  Sample styled elements:');
            afterStyles.samples.forEach(s => console.log(`    <${s.tag} .${s.class}> ${s.style}`));

            // Style info
            const styleInfo = await page.$$eval('span', els =>
                els.filter(el => {
                    const t = el.textContent || '';
                    return (t.includes('cached') || t.match(/\(\d+\.\d+s\)/)) && t.length < 100;
                }).map(el => el.textContent.trim())
            );
            console.log('  Style info:', styleInfo);

            // ============================================================
            // TEST Reset
            // ============================================================
            console.log('\n=== Test Reset ===');
            const resetBtn = await page.$('button:has-text("Reset")');
            if (resetBtn) {
                await resetBtn.click();
                await page.waitForTimeout(1500);

                const resetStyles = await page.evaluate(() => {
                    const all = document.querySelectorAll('.gen-v2-results *');
                    let withStyles = 0;
                    let totalStyleLength = 0;
                    for (const el of all) {
                        if (el.style.cssText && el.style.cssText.length > 10) {
                            withStyles++;
                            totalStyleLength += el.style.cssText.length;
                        }
                    }
                    return { withStyles, totalStyleLength };
                });
                console.log(`  AFTER RESET: ${resetStyles.withStyles} elements with inline styles (${resetStyles.totalStyleLength} chars)`);

                const hasPresent = await page.$('button.gen-link-btn:has-text("Present")');
                console.log(`  Present button restored: ${!!hasPresent}`);

                await screenshot(page, 'conditions-AFTER-reset');
            }
        }

        // ============================================================
        // TEST 2: Present on "Target Work Profile" (accordion renderer)
        // ============================================================
        console.log('\n========================================');
        console.log('=== TEST 2: Target Work Profile (accordion) ===');
        console.log('========================================');

        const targetTab = await page.$('button:has-text("Target Work Profile")');
        if (targetTab) {
            await targetTab.click();
            await page.waitForTimeout(2000);

            // BEFORE
            await page.evaluate(() => {
                const v2 = document.querySelector('.gen-v2-results');
                if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
            });
            await page.waitForTimeout(500);
            await screenshot(page, 'target-BEFORE');
            await page.evaluate(() => window.scrollBy(0, 400));
            await page.waitForTimeout(300);
            await screenshot(page, 'target-BEFORE-content');

            // Click Present
            const present2 = await page.$('button.gen-link-btn:has-text("Present")');
            if (present2) {
                await present2.scrollIntoViewIfNeeded();
                console.log('  Clicking Present on Target Work Profile...');
                await present2.click();

                for (let i = 0; i < 90; i++) {
                    await page.waitForTimeout(1000);
                    const r = await page.$('button:has-text("Reset")');
                    if (r && await r.isVisible()) {
                        console.log(`  Polish completed in ${i+1}s`);
                        break;
                    }
                    const errSpan = await page.$('span:has-text("Polish failed")');
                    if (errSpan) {
                        console.log(`  Polish FAILED: ${await errSpan.textContent()}`);
                        break;
                    }
                    if (i % 10 === 9) console.log(`  Polishing... (${i+1}s)`);
                }

                await page.waitForTimeout(1000);

                // AFTER
                await page.evaluate(() => {
                    const v2 = document.querySelector('.gen-v2-results');
                    if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
                });
                await page.waitForTimeout(500);
                await screenshot(page, 'target-AFTER');
                await page.evaluate(() => window.scrollBy(0, 400));
                await page.waitForTimeout(300);
                await screenshot(page, 'target-AFTER-content');
            }
        } else {
            console.log('  Target Work Profile tab not found');
        }

        // ============================================================
        // TEST 3: Present on "Relationship Landscape" (card_grid renderer)
        // ============================================================
        console.log('\n========================================');
        console.log('=== TEST 3: Relationship Landscape (card_grid) ===');
        console.log('========================================');

        const relTab = await page.$('button:has-text("Relationship Landscape")');
        if (relTab) {
            await relTab.click();
            await page.waitForTimeout(2000);

            await page.evaluate(() => {
                const v2 = document.querySelector('.gen-v2-results');
                if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
            });
            await page.waitForTimeout(500);
            await screenshot(page, 'relationship-BEFORE');

            const present3 = await page.$('button.gen-link-btn:has-text("Present")');
            if (present3) {
                await present3.scrollIntoViewIfNeeded();
                console.log('  Clicking Present on Relationship Landscape...');
                await present3.click();

                for (let i = 0; i < 90; i++) {
                    await page.waitForTimeout(1000);
                    const r = await page.$('button:has-text("Reset")');
                    if (r && await r.isVisible()) {
                        console.log(`  Polish completed in ${i+1}s`);
                        break;
                    }
                    const errSpan = await page.$('span:has-text("Polish failed")');
                    if (errSpan) {
                        console.log(`  Polish FAILED: ${await errSpan.textContent()}`);
                        break;
                    }
                    if (i % 10 === 9) console.log(`  Polishing... (${i+1}s)`);
                }

                await page.waitForTimeout(1000);
                await page.evaluate(() => {
                    const v2 = document.querySelector('.gen-v2-results');
                    if (v2) { v2.scrollIntoView({ block: 'start' }); window.scrollBy(0, -20); }
                });
                await page.waitForTimeout(500);
                await screenshot(page, 'relationship-AFTER');

                // Check what changed
                const relAfter = await page.evaluate(() => {
                    const all = document.querySelectorAll('.gen-v2-results *');
                    let withStyles = 0;
                    const samples = [];
                    for (const el of all) {
                        if (el.style.cssText && el.style.cssText.length > 10) {
                            withStyles++;
                            if (samples.length < 5) {
                                samples.push({
                                    tag: el.tagName,
                                    class: (el.className?.toString() || '').substring(0, 50),
                                    style: el.style.cssText.substring(0, 200),
                                });
                            }
                        }
                    }
                    return { withStyles, samples };
                });
                console.log(`  Elements with inline styles: ${relAfter.withStyles}`);
                console.log(`  NOTE: CardGridRenderer does NOT read _style_overrides (expected no visual change)`);
            }
        }

        // ============================================================
        // TEST 4: Present on cached tab (should be instant)
        // ============================================================
        console.log('\n========================================');
        console.log('=== TEST 4: Re-polish cached tab (should be fast) ===');
        console.log('========================================');

        // Go back to Conditions
        const condTab2 = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab2) {
            await condTab2.click();
            await page.waitForTimeout(2000);

            const present4 = await page.$('button.gen-link-btn:has-text("Present")');
            if (present4) {
                console.log('  Clicking Present on Conditions (should be cached)...');
                const startTime = Date.now();
                await present4.scrollIntoViewIfNeeded();
                await present4.click();

                for (let i = 0; i < 90; i++) {
                    await page.waitForTimeout(1000);
                    const r = await page.$('button:has-text("Reset")');
                    if (r && await r.isVisible()) {
                        const elapsed = Math.round((Date.now() - startTime) / 1000);
                        console.log(`  Cached polish returned in ${elapsed}s`);
                        break;
                    }
                    if (i % 10 === 9) console.log(`  Waiting... (${i+1}s)`);
                }
            }
        }

        console.log('\n=== ALL TESTS DONE ===');

    } catch (err) {
        console.error('ERROR:', err.message);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
