import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-final-v2';
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

    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            try {
                const body = await resp.text();
                const parsed = JSON.parse(body);
                console.log(`  [POLISH] ${resp.status()} | school: ${parsed.style_school} | cached: ${parsed.cached} | time: ${parsed.execution_time_ms}ms`);
                const overrides = parsed.polished_payload?.style_overrides;
                if (overrides) {
                    console.log(`  [POLISH] override keys: ${Object.keys(overrides).join(', ')}`);
                    // Show one sample override
                    if (overrides.section_header) {
                        console.log(`  [POLISH] section_header override: ${JSON.stringify(overrides.section_header)}`);
                    }
                    if (overrides.card) {
                        console.log(`  [POLISH] card override: ${JSON.stringify(overrides.card)}`);
                    }
                }
            } catch {}
        }
    });

    try {
        // Step 1: Navigate and ensure V2 data
        console.log('\n=== Step 1: Navigate ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-benanav-001/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await page.waitForTimeout(5000);

        let bodyText = await page.textContent('body');
        if (!bodyText.includes('Present')) {
            console.log('  V2 data not loaded. Importing...');
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
                        if (bodyText.includes('Present')) { console.log(`  Import done (~${(i+1)*2}s)`); break; }
                        if (bodyText.includes('Import failed')) { console.log('  Import failed'); break; }
                        if (i % 15 === 14) console.log(`  Importing... (${(i+1)*2}s)`);
                    }
                }
            }
        } else {
            console.log('  V2 data already loaded');
        }

        // Step 2: Switch to Conditions of Possibility tab
        console.log('\n=== Step 2: Switch to Conditions of Possibility ===');
        const condTab = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab) {
            await condTab.click();
            await page.waitForTimeout(2000);
        }

        // Step 3: Expand first accordion section BEFORE polishing
        console.log('\n=== Step 3: Expand accordion sections BEFORE ===');
        // Click the first h3 header to expand
        const firstHeader = await page.$('.gen-conditions-tab h3');
        if (firstHeader) {
            await firstHeader.click();
            await page.waitForTimeout(500);
            console.log('  Expanded first section');
        }

        // Scroll to see the expanded content
        await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (tab) tab.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(500);

        // BEFORE screenshot with expanded section
        await screenshot(page, 'conditions-expanded-BEFORE');
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'conditions-expanded-BEFORE-scrolled');

        // Count inline styles BEFORE
        const before = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'No tab', count: 0, chars: 0, samples: [] };
            const all = tab.querySelectorAll('*');
            let count = 0;
            let chars = 0;
            const samples = [];
            for (const el of all) {
                const css = el.style?.cssText || '';
                if (css.length > 10) {
                    count++;
                    chars += css.length;
                    if (samples.length < 5) {
                        samples.push({
                            tag: el.tagName,
                            cls: (el.className?.toString() || '').substring(0, 40),
                            style: css.substring(0, 150),
                        });
                    }
                }
            }
            return { count, chars, total: all.length, samples };
        });
        console.log(`  BEFORE: ${before.count} styled elements / ${before.total} total (${before.chars} chars)`);
        before.samples.forEach(s => console.log(`    <${s.tag} .${s.cls}> ${s.style}`));

        // Step 4: Click Present
        console.log('\n=== Step 4: Click Present ===');
        // Scroll back to toolbar
        await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (tab) tab.scrollIntoView({ block: 'start' });
            window.scrollBy(0, -80);
        });
        await page.waitForTimeout(300);

        const presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            console.log('  ERROR: Present button not found');
            await screenshot(page, 'no-present', { fullPage: true });
            return;
        }

        await presentBtn.scrollIntoViewIfNeeded();
        await presentBtn.click();
        console.log('  Present clicked, waiting for polish response...');

        // Wait for Reset button
        let polished = false;
        for (let i = 0; i < 120; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                console.log(`  Polish completed in ${i+1}s`);
                polished = true;
                break;
            }
            const errSpan = await page.$('span:has-text("Polish failed")');
            if (errSpan) {
                console.log(`  Polish FAILED: ${await errSpan.textContent()}`);
                await screenshot(page, 'polish-error');
                break;
            }
            if (i % 15 === 14) console.log(`  Polishing... (${i+1}s)`);
        }

        if (!polished) {
            console.log('  Polish did not complete in 120s');
            await screenshot(page, 'polish-timeout');
            return;
        }

        // Step 5: Expand first section AFTER polishing
        console.log('\n=== Step 5: Inspect polished state ===');
        await page.waitForTimeout(1000);

        // The accordion may have re-rendered with sections collapsed.
        // Expand the first section again.
        const firstHeaderAfter = await page.$('.gen-conditions-tab h3');
        if (firstHeaderAfter) {
            // Check if already expanded (look for section-content sibling)
            const isExpanded = await page.evaluate(() => {
                const h3 = document.querySelector('.gen-conditions-tab h3');
                const section = h3?.closest('.gen-conditions-section');
                return !!section?.querySelector('.gen-section-content');
            });
            if (!isExpanded) {
                await firstHeaderAfter.click();
                await page.waitForTimeout(500);
                console.log('  Re-expanded first section after polish');
            } else {
                console.log('  First section already expanded');
            }
        }

        // Scroll to content
        await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (tab) tab.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(500);

        // AFTER screenshot with expanded section
        await screenshot(page, 'conditions-expanded-AFTER');
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'conditions-expanded-AFTER-scrolled');

        // Count inline styles AFTER
        const after = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'No tab', count: 0, chars: 0, samples: [] };
            const all = tab.querySelectorAll('*');
            let count = 0;
            let chars = 0;
            const samples = [];
            for (const el of all) {
                const css = el.style?.cssText || '';
                if (css.length > 10) {
                    count++;
                    chars += css.length;
                    if (samples.length < 10) {
                        samples.push({
                            tag: el.tagName,
                            cls: (el.className?.toString() || '').substring(0, 40),
                            style: css.substring(0, 200),
                        });
                    }
                }
            }
            return { count, chars, total: all.length, samples };
        });
        console.log(`  AFTER: ${after.count} styled elements / ${after.total} total (${after.chars} chars)`);
        console.log(`  DIFF: +${after.count - before.count} elements, +${after.chars - before.chars} chars`);
        after.samples.forEach(s => console.log(`    <${s.tag} .${s.cls}> ${s.style}`));

        // Check for _style_overrides in React component props
        const overrideCheck = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };

            const fiberKey = Object.keys(tab).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return { error: 'no fiber' };

            let fiber = tab[fiberKey];
            // Walk up to find the component that has _style_overrides in config
            let depth = 0;
            while (fiber && depth < 30) {
                const props = fiber.memoizedProps;
                if (props?.config?._style_overrides) {
                    return {
                        found: true,
                        depth,
                        component: fiber.type?.name || 'unknown',
                        keys: Object.keys(props.config._style_overrides),
                    };
                }
                fiber = fiber.return;
                depth++;
            }
            return { found: false, searchedDepth: depth };
        });
        console.log('  Style overrides in React:', JSON.stringify(overrideCheck));

        // Step 6: Test Reset
        console.log('\n=== Step 6: Reset ===');
        const resetBtn = await page.$('button:has-text("Reset")');
        if (resetBtn) {
            await resetBtn.click();
            await page.waitForTimeout(1500);

            // Expand section after reset
            const h3Reset = await page.$('.gen-conditions-tab h3');
            if (h3Reset) {
                await h3Reset.click();
                await page.waitForTimeout(500);
            }

            await page.evaluate(() => {
                const tab = document.querySelector('.gen-conditions-tab');
                if (tab) tab.scrollIntoView({ block: 'start' });
            });
            await page.waitForTimeout(300);
            await screenshot(page, 'conditions-expanded-AFTER-reset');

            const resetCheck = await page.evaluate(() => {
                const tab = document.querySelector('.gen-conditions-tab');
                if (!tab) return { count: 0 };
                const all = tab.querySelectorAll('*');
                let count = 0;
                for (const el of all) {
                    if (el.style?.cssText?.length > 10) count++;
                }
                return { count };
            });
            console.log(`  AFTER RESET: ${resetCheck.count} styled elements`);
            console.log(`  Present button visible: ${!!(await page.$('button.gen-link-btn:has-text("Present")'))}`);
        }

        // Step 7: Re-polish (should be cached and faster)
        console.log('\n=== Step 7: Re-polish (cached) ===');
        const present2 = await page.$('button.gen-link-btn:has-text("Present")');
        if (present2) {
            const start = Date.now();
            await present2.click();
            for (let i = 0; i < 90; i++) {
                await page.waitForTimeout(1000);
                const r = await page.$('button:has-text("Reset")');
                if (r && await r.isVisible()) {
                    const elapsed = Math.round((Date.now() - start) / 1000);
                    console.log(`  Cached polish completed in ${elapsed}s`);
                    break;
                }
                if (i % 15 === 14) console.log(`  Waiting... (${i+1}s)`);
            }
        }

        console.log('\n=== ALL TESTS COMPLETE ===');

    } catch (err) {
        console.error('ERROR:', err.message);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
