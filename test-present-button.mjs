import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-button';
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

// Clean previous screenshots
for (const f of fs.readdirSync(SCREENSHOTS_DIR)) {
    fs.unlinkSync(path.join(SCREENSHOTS_DIR, f));
}

let stepNum = 0;
async function screenshot(page, name, fullPage = false) {
    stepNum++;
    const filepath = path.join(SCREENSHOTS_DIR, `${String(stepNum).padStart(2, '0')}-${name}.png`);
    await page.screenshot({ path: filepath, fullPage });
    console.log(`  [Screenshot ${stepNum}] ${name}`);
    return filepath;
}

async function main() {
    const browser = await chromium.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const context = await browser.newContext({
        viewport: { width: 1440, height: 900 }
    });

    const page = await context.newPage();

    const consoleLogs = [];
    page.on('console', msg => {
        const text = msg.text();
        consoleLogs.push({ type: msg.type(), text });
        const lower = text.toLowerCase();
        if (lower.includes('present') || lower.includes('polish') || lower.includes('import') ||
            lower.includes('job-') || lower.includes('v2') || msg.type() === 'error') {
            console.log(`  [console.${msg.type()}] ${text.substring(0, 300)}`);
        }
    });

    page.on('request', req => {
        const url = req.url();
        if (url.includes('analyzer-v2') || url.includes('polish') || url.includes('import-v2') || url.includes('genealogy/jobs') || url.includes('refresh-v2')) {
            console.log(`  [NET ->] ${req.method()} ${url}`);
        }
    });
    page.on('response', resp => {
        const url = resp.url();
        if (url.includes('analyzer-v2') || url.includes('polish') || url.includes('import-v2') || url.includes('genealogy/jobs') || url.includes('refresh-v2')) {
            console.log(`  [NET <-] ${resp.status()} ${url}`);
        }
    });

    try {
        // ============================================================
        // STEP 1: Navigate to Genealogy page
        // ============================================================
        console.log('\n=== STEP 1: Navigate to Genealogy page ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-benanav-001/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await page.waitForTimeout(5000);
        await screenshot(page, 'genealogy-page');

        // ============================================================
        // STEP 2: Inject V2 presentation data directly
        // ============================================================
        console.log('\n=== STEP 2: Fetch page presentation from analyzer-v2 and inject ===');

        // Strategy: Fetch the page presentation from analyzer-v2 directly,
        // then inject it into the React state via the frontend's import mechanism.
        // The refresh-v2 endpoint on the-critic backend already works.
        // We'll call it from the page context.

        console.log('  Calling refresh-v2 endpoint from page context...');
        const refreshResult = await page.evaluate(async () => {
            const API_BASE = window.location.origin.replace('-1.onrender.com', '.onrender.com') + '/api';
            // First create an in-memory job by POSTing to import-v2
            // but we know this times out. Instead, use refresh-v2 which is lighter.
            // However refresh-v2 needs an existing job. Let's try a different approach.

            // Direct approach: Fetch from analyzer-v2 and set React state
            try {
                const pageResp = await fetch('https://analyzer-v2.onrender.com/v1/presenter/page/job-7d32be316d06', {
                    signal: AbortSignal.timeout(120000),
                });
                if (!pageResp.ok) {
                    return { error: `Page API returned ${pageResp.status}` };
                }
                const presentation = await pageResp.json();
                return {
                    ok: true,
                    viewCount: presentation.views?.length || 0,
                    jobId: presentation.job_id,
                    keys: Object.keys(presentation),
                };
            } catch (e) {
                return { error: e.message };
            }
        });
        console.log('  Refresh result:', JSON.stringify(refreshResult));

        if (!refreshResult.ok) {
            console.log('  Failed to fetch presentation, trying import-v2 instead...');
        }

        // Now inject the presentation into React state by simulating the import flow
        console.log('  Injecting presentation into React state...');
        const injectResult = await page.evaluate(async () => {
            // Fetch the full presentation
            const pageResp = await fetch('https://analyzer-v2.onrender.com/v1/presenter/page/job-7d32be316d06', {
                signal: AbortSignal.timeout(120000),
            });
            if (!pageResp.ok) return { error: 'Failed to fetch presentation' };
            const presentation = await pageResp.json();

            // Find the React fiber for the GenealogyPage component
            // We can access React state through the DOM fiber
            const rootEl = document.getElementById('root');
            if (!rootEl || !rootEl._reactRootContainer) {
                // React 18+ with createRoot doesn't use _reactRootContainer
                // Try a different approach: simulate what the import does
                // by calling the API endpoint that creates an in-memory job

                // Actually, let's just call the Critic backend's import but handle it
                // by first creating the job directly
                const API_BASE = (() => {
                    // The Critic frontend's API_BASE
                    const url = new URL(window.location.href);
                    return `${url.protocol}//the-critic.onrender.com/api`;
                })();

                // Use refresh-v2 but first we need to create the job in memory.
                // We can't do that without the import endpoint.
                // Let's try a different approach: reload the page with the data available.
                return {
                    error: 'Cannot inject directly into React state. Need to use import flow.',
                    apiBase: API_BASE
                };
            }
            return { error: 'Unexpected DOM structure' };
        });
        console.log('  Inject result:', JSON.stringify(injectResult));

        // ============================================================
        // STEP 3: Use the actual import flow but with longer timeout
        // ============================================================
        console.log('\n=== STEP 3: Use import flow with retry ===');

        // Scroll to import section
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await page.waitForTimeout(500);

        const jobInput = await page.$('input[placeholder*="job"]');
        if (jobInput) {
            await jobInput.fill('job-7d32be316d06');
            await page.waitForTimeout(300);

            // Click Import
            const importBtn = await page.$('button:has-text("Import from v2")');
            if (importBtn && !(await importBtn.isDisabled())) {
                console.log('  Clicking Import from v2...');
                await importBtn.click();

                // Wait longer this time -- the compose pipeline may need 3+ minutes
                console.log('  Waiting for import (up to 5 minutes)...');
                let importSuccess = false;
                for (let i = 0; i < 150; i++) {
                    await page.waitForTimeout(2000);
                    const bodyText = await page.textContent('body');

                    if (bodyText.includes('Present') || bodyText.includes('Idea Evolution') || bodyText.includes('Close V2')) {
                        console.log(`  Import completed after ~${(i + 1) * 2}s!`);
                        importSuccess = true;
                        break;
                    }

                    if (bodyText.includes('Import failed') || bodyText.includes('timed out')) {
                        console.log(`  Import failed after ~${(i + 1) * 2}s`);
                        // Dismiss the error and try again
                        const dismissBtn = await page.$('button:has-text("Dismiss")');
                        if (dismissBtn) {
                            await dismissBtn.click();
                            await page.waitForTimeout(500);
                        }

                        // Try one more time
                        if (i < 20) {
                            console.log('  Retrying import...');
                            await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
                            await page.waitForTimeout(500);
                            const input2 = await page.$('input[placeholder*="job"]');
                            if (input2) {
                                await input2.fill('job-7d32be316d06');
                                const btn2 = await page.$('button:has-text("Import from v2")');
                                if (btn2 && !(await btn2.isDisabled())) {
                                    await btn2.click();
                                    continue;
                                }
                            }
                        }
                        break;
                    }

                    if (i % 15 === 14) {
                        console.log(`  Still waiting... (${(i + 1) * 2}s)`);
                        await screenshot(page, `import-waiting-${(i+1)*2}s`);
                    }
                }

                if (!importSuccess) {
                    console.log('  Import did not complete within timeout');
                    await screenshot(page, 'import-timeout');
                }
            }
        }

        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(1000);
        await screenshot(page, 'after-import-attempt');

        // ============================================================
        // STEP 4: Check for Present button and test it
        // ============================================================
        console.log('\n=== STEP 4: Check for Present button ===');

        const bodyText = await page.textContent('body');
        const hasPresent = bodyText.includes('Present');
        const hasV2Views = bodyText.includes('Idea Evolution') || bodyText.includes('Close V2');
        console.log(`  Has Present: ${hasPresent}`);
        console.log(`  Has V2 Views: ${hasV2Views}`);

        if (hasPresent) {
            // Find Present button
            let presentBtn = await page.$('button:has-text("Present")');

            // It might be nested in V2TabContent - scroll to find it
            if (!presentBtn) {
                for (let s = 0; s < 10; s++) {
                    await page.evaluate(y => window.scrollTo(0, y), s * 300);
                    await page.waitForTimeout(300);
                    presentBtn = await page.$('button:has-text("Present"):visible');
                    if (presentBtn) break;
                }
            }

            if (presentBtn) {
                await presentBtn.scrollIntoViewIfNeeded();
                console.log('\n  *** TESTING Present BUTTON ***');

                // BEFORE screenshot
                await screenshot(page, 'BEFORE-present');
                await screenshot(page, 'BEFORE-present-full', true);

                // Click Present
                console.log('  Clicking Present...');
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
                        console.log(`  Polish failed after ~${(i+1)*2}s`);
                        const errSpan = await page.$('span:has-text("Polish failed")');
                        if (errSpan) {
                            const errText = await errSpan.textContent();
                            console.log(`  Error: ${errText}`);
                        }
                        break;
                    }
                    if (i % 5 === 4) console.log(`  Polishing... (${(i+1)*2}s)`);
                }

                await page.waitForTimeout(1000);

                // AFTER screenshot
                await screenshot(page, 'AFTER-present');
                await screenshot(page, 'AFTER-present-full', true);

                // Style info
                const styleSpans = await page.$$eval('span', els =>
                    els.filter(el => {
                        const t = el.textContent;
                        return t?.includes('cached') || t?.includes('s)') || t?.includes('school');
                    }).map(el => el.textContent.trim())
                );
                console.log('  Style info:', styleSpans);

                // Test Reset
                const resetBtn = await page.$('button:has-text("Reset")');
                if (resetBtn) {
                    console.log('\n  *** TESTING Reset BUTTON ***');
                    await resetBtn.scrollIntoViewIfNeeded();
                    await resetBtn.click();
                    await page.waitForTimeout(2000);
                    await screenshot(page, 'AFTER-reset');

                    const afterReset = await page.textContent('body');
                    console.log(`  Present button restored: ${afterReset.includes('Present')}`);
                    console.log(`  Reset button gone: ${!afterReset.includes('Reset')}`);
                }
            }
        } else {
            console.log('  No Present button found. V2 data was not loaded.');
            await screenshot(page, 'NO-present-button', true);
        }

        // Final console
        console.log('\n=== Console Errors ===');
        consoleLogs.filter(l => l.type === 'error').forEach(l => {
            console.log(`  ${l.text.substring(0, 300)}`);
        });

        console.log('\n=== TEST COMPLETE ===');

    } catch (err) {
        console.error('ERROR:', err.message);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
