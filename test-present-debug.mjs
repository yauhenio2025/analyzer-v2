import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-debug';
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
for (const f of fs.readdirSync(SCREENSHOTS_DIR)) fs.unlinkSync(path.join(SCREENSHOTS_DIR, f));

let stepNum = 0;
async function screenshot(page, name) {
    stepNum++;
    const filepath = path.join(SCREENSHOTS_DIR, `${String(stepNum).padStart(2, '0')}-${name}.png`);
    await page.screenshot({ path: filepath });
    console.log(`  [Screenshot ${stepNum}] ${name}`);
}

async function main() {
    const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
    const page = await context.newPage();

    // Track ALL console messages
    page.on('console', msg => {
        console.log(`  [console.${msg.type()}] ${msg.text().substring(0, 400)}`);
    });

    // Track ALL requests to analyzer-v2
    page.on('request', req => {
        if (req.url().includes('analyzer-v2')) {
            console.log(`  [REQ] ${req.method()} ${req.url()} body=${req.postData()?.substring(0, 200)}`);
        }
    });
    page.on('response', resp => {
        if (resp.url().includes('analyzer-v2')) {
            console.log(`  [RESP] ${resp.status()} ${resp.url()} (${resp.headers()['content-length'] || '?'} bytes)`);
        }
    });
    page.on('requestfailed', req => {
        if (req.url().includes('analyzer-v2') || req.url().includes('polish')) {
            console.log(`  [FAIL] ${req.url()} ${req.failure()?.errorText}`);
        }
    });

    try {
        console.log('\n=== Navigate ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-benanav-001/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 60000
        });
        await page.waitForTimeout(5000);

        // Check ANALYZER_V2_URL
        const envCheck = await page.evaluate(() => {
            // Check what URL the frontend would use
            const scripts = document.querySelectorAll('script');
            // Check env vars embedded in the page
            const envMeta = document.querySelector('meta[name="analyzer-v2-url"]');
            return {
                locationOrigin: window.location.origin,
                envMeta: envMeta?.getAttribute('content') || null,
            };
        });
        console.log('  Env check:', JSON.stringify(envCheck));

        // Check if V2 data is loaded
        const bodyText = await page.textContent('body');
        const hasV2 = bodyText.includes('V2_presentation') || bodyText.includes('V2 ORCHESTRATOR');
        console.log(`  V2 loaded: ${hasV2}`);

        if (!hasV2) {
            // Click on Previous Analyses item
            const prevItem = await page.$('text=V2_presentation');
            if (prevItem) {
                console.log('  Clicking V2_presentation in Previous Analyses...');
                await prevItem.click();
                await page.waitForTimeout(3000);
            } else {
                // Try import
                console.log('  No previous V2 data. Importing...');
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
                            const t = await page.textContent('body');
                            if (t.includes('Present') || t.includes('V2 ORCHESTRATOR')) {
                                console.log(`  Import done (~${(i+1)*2}s)`);
                                break;
                            }
                            if (t.includes('Import failed')) { console.log('  Import failed'); break; }
                            if (i % 15 === 14) console.log(`  Importing... (${(i+1)*2}s)`);
                        }
                    }
                }
            }
        }

        // Verify V2 is now loaded
        const postText = await page.textContent('body');
        if (!postText.includes('Present')) {
            console.log('  NO Present button found after data load');
            await screenshot(page, 'no-present-debug');
            return;
        }

        // Scroll to the Present button area
        await page.evaluate(() => {
            const h = [...document.querySelectorAll('h2,h3')].find(el => el.textContent.includes('Analysis Results'));
            if (h) { h.scrollIntoView({ block: 'start' }); window.scrollBy(0, -30); }
        });
        await page.waitForTimeout(1000);

        // Inspect the Present button
        const presentBtn = await page.$('button:has-text("Present"), .gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            console.log('  Present button element not found');
            return;
        }

        await presentBtn.scrollIntoViewIfNeeded();
        await screenshot(page, 'BEFORE-present');

        // Click Present and watch carefully
        console.log('\n=== Clicking Present - monitoring all events ===');

        // Also intercept the fetch response in the page context
        const polishPromise = page.evaluate(async () => {
            return new Promise((resolve) => {
                const originalFetch = window.fetch;
                window.fetch = async function(...args) {
                    const url = typeof args[0] === 'string' ? args[0] : args[0].url;
                    if (url.includes('polish')) {
                        console.log('[FETCH SPY] Polish request to: ' + url);
                        const startTime = Date.now();
                        try {
                            const resp = await originalFetch.apply(this, args);
                            const elapsed = Date.now() - startTime;
                            console.log('[FETCH SPY] Polish response: ' + resp.status + ' in ' + elapsed + 'ms');
                            const clone = resp.clone();
                            const body = await clone.text();
                            console.log('[FETCH SPY] Body length: ' + body.length + ', preview: ' + body.substring(0, 200));
                            resolve({ status: resp.status, elapsed, bodyLength: body.length });
                            return resp;
                        } catch (e) {
                            const elapsed = Date.now() - startTime;
                            console.log('[FETCH SPY] Polish fetch ERROR: ' + e.message + ' after ' + elapsed + 'ms');
                            resolve({ error: e.message, elapsed });
                            throw e;
                        }
                    }
                    return originalFetch.apply(this, args);
                };
                setTimeout(() => resolve({ error: 'spy timeout', elapsed: 120000 }), 120000);
            });
        });

        await presentBtn.click();
        console.log('  Present clicked, waiting for fetch spy result...');

        // Wait for the polish promise
        const spyResult = await polishPromise;
        console.log('  Fetch spy result:', JSON.stringify(spyResult));

        await page.waitForTimeout(2000);

        // Check final state
        const finalText = await page.textContent('body');
        const hasReset = finalText.includes('Reset');
        const hasPolishError = finalText.includes('Polish failed');
        console.log(`  Has Reset: ${hasReset}`);
        console.log(`  Has error: ${hasPolishError}`);

        if (hasReset) {
            await screenshot(page, 'AFTER-present-SUCCESS');
            const info = await page.$$eval('span', els =>
                els.filter(el => el.textContent?.includes('cached') || el.textContent?.match(/\d+\.\d+s/))
                    .filter(el => el.textContent.length < 100)
                    .map(el => el.textContent.trim())
            );
            console.log('  Style info:', info);

            // Scroll down to see polished content
            await page.evaluate(() => window.scrollBy(0, 300));
            await page.waitForTimeout(300);
            await screenshot(page, 'AFTER-content');

            // Reset test
            const resetBtn = await page.$('button:has-text("Reset")');
            if (resetBtn) {
                await resetBtn.click();
                await page.waitForTimeout(2000);
                await screenshot(page, 'AFTER-reset');
            }
        } else if (hasPolishError) {
            const errSpan = await page.$('span:has-text("Polish failed")');
            if (errSpan) console.log('  Error:', await errSpan.textContent());
            await screenshot(page, 'AFTER-present-ERROR');
        } else {
            console.log('  Neither Reset nor error found -- polishing may still be in progress');
            await screenshot(page, 'AFTER-present-UNKNOWN');
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
