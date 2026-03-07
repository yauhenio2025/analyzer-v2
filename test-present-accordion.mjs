import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-accordion';
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

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

    page.on('console', msg => {
        if (msg.type() === 'error') console.log(`  [error] ${msg.text().substring(0, 200)}`);
    });

    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            const body = await resp.text().catch(() => '');
            console.log(`  [POLISH] ${resp.status()} (${body.length} chars)`);
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
        let hasV2 = bodyText.includes('V2 ORCHESTRATOR') || bodyText.includes('V2_presentation');
        console.log(`  V2 loaded: ${hasV2}`);

        if (!hasV2) {
            console.log('  V2 data missing. Need to re-import...');

            // Check if there's a Previous Analyses section with V2 data
            const prevAnalysis = await page.$('text=V2_presentation');
            if (prevAnalysis) {
                console.log('  Found V2_presentation in Previous Analyses, clicking...');
                await prevAnalysis.click();
                await page.waitForTimeout(3000);
                hasV2 = (await page.textContent('body')).includes('V2 ORCHESTRATOR');
            }

            if (!hasV2) {
                // Do the import
                await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
                await page.waitForTimeout(1000);
                const input = await page.$('input[placeholder*="job"]');
                if (input) {
                    await input.fill('job-7d32be316d06');
                    await page.waitForTimeout(300);
                    const btn = await page.$('button:has-text("Import from v2")');
                    if (btn && !(await btn.isDisabled())) {
                        await btn.click();
                        for (let i = 0; i < 150; i++) {
                            await page.waitForTimeout(2000);
                            bodyText = await page.textContent('body');
                            if (bodyText.includes('Present') || bodyText.includes('V2 ORCHESTRATOR')) {
                                console.log(`  Import done (~${(i+1)*2}s)`);
                                break;
                            }
                            if (bodyText.includes('Import failed')) {
                                console.log('  Import failed');
                                const dismiss = await page.$('button:has-text("Dismiss")');
                                if (dismiss) await dismiss.click();
                                break;
                            }
                            if (i % 15 === 14) console.log(`  Importing... (${(i+1)*2}s)`);
                        }
                    }
                }
            }
        }

        // Check V2 state now
        bodyText = await page.textContent('body');
        hasV2 = bodyText.includes('V2 ORCHESTRATOR') || bodyText.includes('Present');
        if (!hasV2) {
            console.log('  STILL no V2 data. Aborting.');
            await screenshot(page, 'no-v2', { fullPage: true });
            return;
        }

        // Scroll to Analysis Results
        await page.evaluate(() => {
            const h = [...document.querySelectorAll('h2,h3')].find(el => el.textContent.includes('Analysis Results'));
            if (h) { h.scrollIntoView({ block: 'start' }); window.scrollBy(0, -30); }
        });
        await page.waitForTimeout(500);
        await screenshot(page, 'analysis-results');

        // List all V2 tabs
        console.log('\n=== List V2 tabs ===');
        const allTabs = await page.$$eval('.gen-tab-btn, .gen-results-tabs a, .gen-results-tabs button', els =>
            els.map(el => ({
                text: el.textContent.trim(),
                active: el.classList.contains('active'),
                class: el.className
            }))
        );
        console.log('  Tabs found:');
        allTabs.forEach(t => console.log(`    ${t.active ? '>> ' : '   '}[${t.text}] class="${t.class}"`));

        if (allTabs.length === 0) {
            console.log('  No tabs found! Looking for any clickable tab-like elements...');
            const allClickable = await page.$$eval('button, a', els =>
                els.filter(el => {
                    const cls = el.className || '';
                    const text = el.textContent.trim();
                    return el.offsetParent !== null && (cls.includes('tab') || text.includes('Map') || text.includes('Profile') || text.includes('Conditions'));
                }).map(el => ({ text: el.textContent.trim().substring(0, 60), class: el.className, tag: el.tagName }))
            );
            console.log('  Tab-like elements:');
            allClickable.forEach(e => console.log(`    <${e.tag}> [${e.text}] class="${e.class}"`));
        }

        // Test Present on the CURRENT tab (whichever is active)
        console.log('\n=== Test Present on current tab ===');
        const present = await page.$('button:has-text("Present"), .gen-link-btn:has-text("Present")');
        if (!present) {
            console.log('  Present button NOT found');
            // Debug
            const allBtns = await page.$$eval('button', els =>
                els.filter(el => el.offsetParent !== null).map(el => `[${el.textContent.trim().substring(0,40)}]`)
            );
            console.log('  Visible buttons:', allBtns.slice(0, 20).join(', '));
            await screenshot(page, 'debug', { fullPage: true });
            return;
        }

        await present.scrollIntoViewIfNeeded();
        await page.waitForTimeout(500);
        await screenshot(page, 'BEFORE-present');

        // Scroll down for more content
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'BEFORE-content-scrolled');

        // Click Present
        console.log('  Clicking Present...');
        await present.scrollIntoViewIfNeeded();
        await present.click();

        for (let i = 0; i < 90; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                console.log(`  Done in ${i+1}s`);
                break;
            }
            if (i % 10 === 9) console.log(`  Polishing... (${i+1}s)`);
        }

        await page.waitForTimeout(1000);
        await screenshot(page, 'AFTER-present');

        // Scroll to same content position
        await page.evaluate(() => window.scrollBy(0, 400));
        await page.waitForTimeout(300);
        await screenshot(page, 'AFTER-content-scrolled');

        // Style info
        const info = await page.$$eval('span', els =>
            els.filter(el => el.textContent?.includes('cached') || el.textContent?.match(/\(\d+\.\d+s\)/))
                .filter(el => el.textContent.length < 100)
                .map(el => el.textContent.trim())
        );
        console.log('  Style info:', info);

        // Check inline styles applied
        const styledElements = await page.evaluate(() => {
            const all = document.querySelectorAll('.gen-v2-results *');
            return Array.from(all)
                .filter(el => el.style.cssText.length > 30 &&
                    !el.style.cssText.includes('display: flex') &&
                    !el.style.cssText.includes('font-size: 0.8rem') &&
                    !el.style.cssText.includes('font-size: 0.72rem'))
                .slice(0, 20)
                .map(el => ({
                    tag: el.tagName,
                    class: (el.className?.toString() || '').substring(0, 60),
                    style: el.style.cssText.substring(0, 300)
                }));
        });
        console.log('  Styled elements:');
        styledElements.forEach(e => console.log(`    <${e.tag} .${e.class}> ${e.style}`));

        // Now try clicking on different tabs
        console.log('\n=== Try clicking tab links ===');
        // The tabs might just be <a> links in a nav
        const tabLinks = await page.$$('.gen-results-tabs a, .v2-tabs a, [class*="tab-btn"]');
        console.log(`  Found ${tabLinks.length} tab link elements`);

        if (tabLinks.length > 1) {
            // Reset first
            const resetBtn = await page.$('button:has-text("Reset")');
            if (resetBtn) {
                await resetBtn.click();
                await page.waitForTimeout(1000);
            }

            // Click second tab
            const secondTab = tabLinks[1];
            const tabText = await secondTab.textContent();
            console.log(`  Clicking second tab: "${tabText.trim()}"...`);
            await secondTab.click();
            await page.waitForTimeout(2000);
            await screenshot(page, 'second-tab');

            // Try Present on this tab
            const present2 = await page.$('button:has-text("Present"), .gen-link-btn:has-text("Present")');
            if (present2) {
                console.log('  Clicking Present on second tab...');
                await present2.scrollIntoViewIfNeeded();
                await screenshot(page, 'second-tab-BEFORE');
                await present2.click();

                for (let i = 0; i < 90; i++) {
                    await page.waitForTimeout(1000);
                    const r = await page.$('button:has-text("Reset")');
                    if (r && await r.isVisible()) {
                        console.log(`  Done in ${i+1}s`);
                        break;
                    }
                    if (i % 10 === 9) console.log(`  Polishing... (${i+1}s)`);
                }
                await page.waitForTimeout(1000);
                await screenshot(page, 'second-tab-AFTER');

                const info2 = await page.$$eval('span', els =>
                    els.filter(el => el.textContent?.includes('cached') || el.textContent?.match(/\(\d+\.\d+s\)/))
                        .filter(el => el.textContent.length < 100)
                        .map(el => el.textContent.trim())
                );
                console.log('  Style info (2nd tab):', info2);
            }
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
