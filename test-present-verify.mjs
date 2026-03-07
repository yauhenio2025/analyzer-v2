import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-verify';
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

async function countInlineStyles(page) {
    return page.evaluate(() => {
        // Search in gen-tab-content and gen-conditions-tab containers
        const containers = document.querySelectorAll('.gen-tab-content, .gen-conditions-tab');
        let withStyles = 0;
        let totalStyleLength = 0;
        const samples = [];
        for (const container of containers) {
            const all = container.querySelectorAll('*');
            for (const el of all) {
                if (el.style && el.style.cssText && el.style.cssText.length > 10) {
                    withStyles++;
                    totalStyleLength += el.style.cssText.length;
                    if (samples.length < 8) {
                        samples.push({
                            tag: el.tagName,
                            class: (el.className?.toString() || '').substring(0, 60),
                            style: el.style.cssText.substring(0, 300),
                        });
                    }
                }
            }
        }
        return { withStyles, totalStyleLength, samples };
    });
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
        if (text.includes('[POLISH]') || msg.type() === 'error') {
            console.log(`  [console.${msg.type()}] ${text.substring(0, 500)}`);
        }
    });

    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            try {
                const body = await resp.text();
                const parsed = JSON.parse(body);
                console.log(`  [POLISH] ${resp.status()} | school: ${parsed.style_school} | cached: ${parsed.cached} | overrides: ${Object.keys(parsed.polished_payload?.style_overrides || {}).join(', ')}`);
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
        if (!bodyText.includes('Present')) {
            console.log('  No V2 data loaded. Attempting import...');
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

        // ============================================================
        // TEST: Conditions of Possibility (accordion renderer -- supports style_overrides)
        // ============================================================
        console.log('\n========================================');
        console.log('=== Conditions of Possibility ===');
        console.log('========================================');

        // Click Conditions tab
        const condTab = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab) {
            await condTab.click();
            await page.waitForTimeout(2000);
        }

        // Scroll to content
        await page.evaluate(() => {
            const el = document.querySelector('.gen-conditions-tab') || document.querySelector('.gen-tab-content');
            if (el) el.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(500);

        // BEFORE measurements
        const before = await countInlineStyles(page);
        console.log(`  BEFORE: ${before.withStyles} elements with inline styles (${before.totalStyleLength} chars)`);
        if (before.samples.length > 0) {
            console.log('  BEFORE samples:');
            before.samples.forEach(s => console.log(`    <${s.tag} .${s.class}> style="${s.style}"`));
        }

        await screenshot(page, 'conditions-BEFORE');
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'conditions-BEFORE-scrolled');

        // Scroll back to Present
        await page.evaluate(() => {
            const el = document.querySelector('.gen-conditions-tab') || document.querySelector('.gen-tab-content');
            if (el) el.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(300);

        // Click Present
        console.log('  Clicking Present...');
        const presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            console.log('  ERROR: Present button not found');
            return;
        }
        await presentBtn.scrollIntoViewIfNeeded();
        await presentBtn.click();

        // Wait for polish
        for (let i = 0; i < 90; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                console.log(`  Polish completed in ${i+1}s`);
                break;
            }
            if (i % 15 === 14) console.log(`  Polishing... (${i+1}s)`);
        }

        await page.waitForTimeout(1000);

        // AFTER measurements
        const after = await countInlineStyles(page);
        console.log(`  AFTER: ${after.withStyles} elements with inline styles (${after.totalStyleLength} chars)`);
        console.log(`  DIFF: +${after.withStyles - before.withStyles} elements, +${after.totalStyleLength - before.totalStyleLength} chars`);
        if (after.samples.length > 0) {
            console.log('  AFTER samples:');
            after.samples.forEach(s => console.log(`    <${s.tag} .${s.class}> style="${s.style}"`));
        }

        // Scroll to content for AFTER screenshot
        await page.evaluate(() => {
            const el = document.querySelector('.gen-conditions-tab') || document.querySelector('.gen-tab-content');
            if (el) el.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(300);
        await screenshot(page, 'conditions-AFTER');
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'conditions-AFTER-scrolled');

        // Check the polished_renderer_config that was applied
        const polishState = await page.evaluate(() => {
            // Find the V2TabContent component via React fiber
            const container = document.querySelector('.gen-tab-content');
            if (!container) return { error: 'No gen-tab-content found' };

            const fiberKey = Object.keys(container).find(k => k.startsWith('__reactFiber'));
            if (!fiberKey) return { error: 'No React fiber' };

            let fiber = container[fiberKey];
            let depth = 0;
            const results = [];
            while (fiber && depth < 60) {
                const props = fiber.memoizedProps;
                if (props?.config?._style_overrides) {
                    results.push({
                        depth,
                        componentName: fiber.type?.name || fiber.type?.displayName || 'unknown',
                        overrideKeys: Object.keys(props.config._style_overrides),
                        sampleOverride: JSON.stringify(props.config._style_overrides.section_header || {}).substring(0, 200),
                    });
                }
                fiber = fiber.return;
                depth++;
            }

            // Also walk children
            fiber = container[fiberKey];
            const walkChildren = (f, d) => {
                if (!f || d > 30) return;
                if (f.memoizedProps?.config?._style_overrides) {
                    results.push({
                        depth: d,
                        componentName: f.type?.name || f.type?.displayName || 'unknown',
                        overrideKeys: Object.keys(f.memoizedProps.config._style_overrides),
                        direction: 'child',
                    });
                }
                if (f.child) walkChildren(f.child, d + 1);
                if (f.sibling) walkChildren(f.sibling, d);
            };
            walkChildren(fiber.child, 1);

            return { resultCount: results.length, results: results.slice(0, 10) };
        });
        console.log('  Polish state in React fiber:', JSON.stringify(polishState, null, 2));

        // Test Reset
        console.log('\n=== Test Reset ===');
        const resetBtn = await page.$('button:has-text("Reset")');
        if (resetBtn) {
            await resetBtn.click();
            await page.waitForTimeout(1500);

            const resetCount = await countInlineStyles(page);
            console.log(`  AFTER RESET: ${resetCount.withStyles} elements with inline styles`);

            await page.evaluate(() => {
                const el = document.querySelector('.gen-conditions-tab') || document.querySelector('.gen-tab-content');
                if (el) el.scrollIntoView({ block: 'start' });
            });
            await page.waitForTimeout(300);
            await screenshot(page, 'conditions-AFTER-reset');
            await page.evaluate(() => window.scrollBy(0, 400));
            await page.waitForTimeout(300);
            await screenshot(page, 'conditions-AFTER-reset-scrolled');

            const presentRestored = await page.$('button.gen-link-btn:has-text("Present")');
            console.log(`  Present button restored: ${!!presentRestored}`);
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
