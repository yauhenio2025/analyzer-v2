import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-state';
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

    page.on('request', req => {
        if (req.url().includes('polish') || req.url().includes('analyzer-v2')) {
            console.log(`  [REQ] ${req.method()} ${req.url()}`);
        }
    });
    page.on('response', resp => {
        if (resp.url().includes('polish') || resp.url().includes('analyzer-v2')) {
            console.log(`  [RESP] ${resp.status()} ${resp.url()}`);
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
        const hasV2 = bodyText.includes('V2 ORCHESTRATOR') || bodyText.includes('Idea Evolution');
        console.log(`  V2 loaded: ${hasV2}`);

        if (!hasV2) {
            // Try clicking on a Previous Analyses V2 entry
            const prevItem = await page.$('text=V2_presentation');
            if (prevItem) {
                console.log('  Found V2_presentation in Previous Analyses, clicking...');
                await prevItem.click();
                await page.waitForTimeout(3000);
            } else {
                // Import
                console.log('  No V2 data found. Importing...');
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
        }

        // Wait for any rendering
        await page.waitForTimeout(2000);

        // === KEY DIAGNOSTIC: Inject logging into V2TabContent ===
        // We'll inspect the React component tree to get the presentation object
        console.log('\n=== Inspect V2 presentation state ===');

        // Method 1: Find __reactFiber or __reactInternalInstance on the V2 results container
        const v2State = await page.evaluate(() => {
            // Look for the V2 results container
            const v2Container = document.querySelector('.gen-v2-results');
            if (!v2Container) return { error: 'No .gen-v2-results container found' };

            // Try to find React fiber
            const fiberKey = Object.keys(v2Container).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
            if (!fiberKey) return { error: 'No React fiber found on container' };

            // Walk up the fiber tree to find V2TabContent's state
            let fiber = v2Container[fiberKey];
            let depth = 0;
            const findings = [];
            while (fiber && depth < 50) {
                if (fiber.memoizedProps) {
                    const props = fiber.memoizedProps;
                    if (props.presentation) {
                        findings.push({
                            depth,
                            type: fiber.type?.name || fiber.type?.displayName || String(fiber.type),
                            job_id: props.presentation.job_id,
                            plan_id: props.presentation.plan_id,
                            view_count: props.presentation.view_count,
                            activeTab: props.activeTab,
                            views: (props.presentation.views || []).map(v => v.view_key),
                        });
                    }
                }
                if (fiber.memoizedState) {
                    // Check for polish state in hooks
                    let hookState = fiber.memoizedState;
                    let hookIdx = 0;
                    while (hookState && hookIdx < 20) {
                        if (hookState.queue && hookState.memoizedState !== undefined) {
                            // This is a useState hook
                        }
                        hookState = hookState.next;
                        hookIdx++;
                    }
                }
                fiber = fiber.return;
                depth++;
            }

            return { fiberKey, findings };
        });

        console.log('  V2 state inspection:', JSON.stringify(v2State, null, 2));

        // Method 2: Check what ANALYZER_V2_URL is set to
        const envCheck = await page.evaluate(() => {
            // Search for ANALYZER_V2_URL in all script sources
            const scripts = document.querySelectorAll('script[src]');
            const inlineScripts = document.querySelectorAll('script:not([src])');
            let found = null;

            for (const s of inlineScripts) {
                if (s.textContent.includes('ANALYZER_V2_URL') || s.textContent.includes('analyzer-v2')) {
                    found = s.textContent.substring(0, 500);
                    break;
                }
            }

            return {
                scriptCount: scripts.length,
                inlineScriptCount: inlineScripts.length,
                analyzerV2Found: found,
            };
        });
        console.log('  Env check:', JSON.stringify(envCheck, null, 2));

        // Now try to find the Present button and inspect its onclick handler
        console.log('\n=== Inspect Present button ===');

        // Scroll to Analysis Results
        await page.evaluate(() => {
            const h = [...document.querySelectorAll('h2,h3')].find(el => el.textContent.includes('Analysis Results'));
            if (h) { h.scrollIntoView({ block: 'start' }); window.scrollBy(0, -30); }
        });
        await page.waitForTimeout(1000);

        const presentBtnInfo = await page.evaluate(() => {
            const btns = [...document.querySelectorAll('button')].filter(b =>
                b.textContent.trim() === 'Present' && b.offsetParent !== null
            );
            if (btns.length === 0) return { error: 'No Present button found' };

            return btns.map(btn => {
                // Check if it has an onClick handler via React fiber
                const fiberKey = Object.keys(btn).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance') || k.startsWith('__reactProps'));
                let reactProps = null;
                if (fiberKey) {
                    const fiber = btn[fiberKey];
                    if (fiber && fiber.onClick) {
                        reactProps = { hasOnClick: true, onClickType: typeof fiber.onClick };
                    } else if (fiber && fiber.memoizedProps) {
                        reactProps = {
                            hasOnClick: !!fiber.memoizedProps.onClick,
                            disabled: fiber.memoizedProps.disabled,
                            className: fiber.memoizedProps.className,
                        };
                    }
                }

                return {
                    text: btn.textContent.trim(),
                    className: btn.className,
                    disabled: btn.disabled,
                    fiberKey,
                    reactProps,
                    parentClasses: btn.parentElement?.className || '',
                    isVisible: btn.offsetParent !== null,
                    rect: btn.getBoundingClientRect(),
                };
            });
        });
        console.log('  Present button info:', JSON.stringify(presentBtnInfo, null, 2));

        await screenshot(page, 'state-inspection');

        // Method 3: Intercept handlePolish call directly
        // Override the button click to log what happens
        console.log('\n=== Click Present with detailed logging ===');

        // Inject a click event spy on all Present buttons
        await page.evaluate(() => {
            const btns = [...document.querySelectorAll('button')].filter(b =>
                b.textContent.trim() === 'Present' && b.offsetParent !== null
            );
            btns.forEach((btn, i) => {
                const original = btn.onclick;
                btn.addEventListener('click', (e) => {
                    console.log(`[STATE] Present button ${i} clicked! Target: ${e.target.textContent}, disabled: ${btn.disabled}`);
                    console.log(`[STATE] Button classes: ${btn.className}`);
                    console.log(`[STATE] Event bubbles: ${e.bubbles}, cancelable: ${e.cancelable}`);
                }, true); // capture phase
            });
            console.log(`[STATE] Attached click spies to ${btns.length} Present buttons`);
        });

        // Also intercept fetch
        await page.evaluate(() => {
            const origFetch = window.fetch;
            window.fetch = function(...args) {
                const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
                console.log(`[POLISH] fetch called: ${url}`);
                if (url && url.includes('polish')) {
                    console.log(`[POLISH] Body: ${JSON.stringify(args[1]?.body || '').substring(0, 300)}`);
                }
                return origFetch.apply(this, args);
            };
            console.log('[STATE] Fetch spy installed');
        });

        // Click the Present button
        const presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            console.log('  Present button not found for click test');
            // Try alternative selector
            const allPresent = await page.$$('button');
            for (const btn of allPresent) {
                const text = await btn.textContent();
                if (text.trim() === 'Present' && await btn.isVisible()) {
                    console.log('  Found Present button with alternative search');
                    await btn.scrollIntoViewIfNeeded();
                    await btn.click();
                    console.log('  Clicked!');
                    break;
                }
            }
        } else {
            await presentBtn.scrollIntoViewIfNeeded();
            console.log('  Clicking Present button...');
            await presentBtn.click();
            console.log('  Clicked!');
        }

        // Wait and check state
        await page.waitForTimeout(3000);
        await screenshot(page, 'after-click');

        // Check if polishing state changed
        const afterState = await page.evaluate(() => {
            const btns = [...document.querySelectorAll('button')].filter(b =>
                b.offsetParent !== null &&
                (b.textContent.includes('Polishing') || b.textContent.includes('Reset') || b.textContent.includes('Present'))
            );
            return btns.map(b => ({
                text: b.textContent.trim(),
                disabled: b.disabled,
                className: b.className,
            }));
        });
        console.log('  After click button state:', JSON.stringify(afterState));

        // Wait longer for polish response
        let resetFound = false;
        for (let i = 0; i < 60; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                console.log(`  Reset appeared after ${i+4}s`);
                resetFound = true;
                break;
            }
            const errSpan = await page.$('span:has-text("Polish failed")');
            if (errSpan) {
                const errText = await errSpan.textContent();
                console.log(`  Polish error: ${errText}`);
                break;
            }
            if (i % 10 === 9) console.log(`  Waiting... (${i+4}s)`);
        }

        await screenshot(page, 'final-state');

        if (resetFound) {
            console.log('  SUCCESS: Polish completed');
        } else {
            console.log('  FAILURE: Polish did not complete');
        }

        console.log('\n=== DONE ===');

    } catch (err) {
        console.error('ERROR:', err.message);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
