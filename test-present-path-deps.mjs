import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-path-deps';
fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
for (const f of fs.readdirSync(SCREENSHOTS_DIR)) fs.unlinkSync(path.join(SCREENSHOTS_DIR, f));

let stepNum = 0;
async function screenshot(page, name, opts = {}) {
    stepNum++;
    const filepath = path.join(SCREENSHOTS_DIR, `${String(stepNum).padStart(2, '0')}-${name}.png`);
    await page.screenshot({ path: filepath, ...opts });
    console.log(`  [Screenshot ${stepNum}] ${name} -> ${filepath}`);
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

    // Listen for polish API responses
    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            try {
                const body = await resp.text();
                const parsed = JSON.parse(body);
                console.log(`  [POLISH API] status=${resp.status()} | school=${parsed.style_school} | cached=${parsed.cached} | time=${parsed.execution_time_ms}ms`);
                const overrides = parsed.polished_payload?.style_overrides;
                if (overrides) {
                    console.log(`  [POLISH API] override keys: ${Object.keys(overrides).join(', ')}`);
                    if (overrides.items_container) {
                        console.log(`  [POLISH API] items_container: ${JSON.stringify(overrides.items_container)}`);
                    }
                    if (overrides.card) {
                        console.log(`  [POLISH API] card: ${JSON.stringify(overrides.card)}`);
                    }
                    if (overrides.mini_card) {
                        console.log(`  [POLISH API] mini_card: ${JSON.stringify(overrides.mini_card)}`);
                    }
                }
            } catch {}
        }
    });

    try {
        // =====================================================
        // Step 1: Navigate to the genealogy page
        // =====================================================
        console.log('\n========================================');
        console.log('Step 1: Navigate to morozov-on-varoufakis');
        console.log('========================================');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 90000
        });
        await page.waitForTimeout(8000);

        let bodyText = await page.textContent('body');
        await screenshot(page, 'initial-load');
        console.log(`  Page loaded. Has "Present": ${bodyText.includes('Present')}`);
        console.log(`  Has "Previous Analyses": ${bodyText.includes('Previous Analyses')}`);
        console.log(`  Has "V2_presentation": ${bodyText.includes('V2_presentation')}`);

        // =====================================================
        // Step 2: Check for V2 results and load one
        // =====================================================
        console.log('\n========================================');
        console.log('Step 2: Load V2 results');
        console.log('========================================');

        // Check if there are V2 results already loaded
        if (!bodyText.includes('Present')) {
            console.log('  Present button not visible. Looking for V2 results...');

            // Look for Previous Analyses section
            const prevAnalyses = await page.$('text=Previous Analyses');
            if (prevAnalyses) {
                console.log('  Found "Previous Analyses" section');
                await prevAnalyses.scrollIntoViewIfNeeded();
                await page.waitForTimeout(1000);
                await screenshot(page, 'previous-analyses');
            }

            // Look for V2_presentation entries
            const v2Entries = await page.$$('text=/V2_presentation|v2_presentation/i');
            console.log(`  Found ${v2Entries.length} V2_presentation entries`);
            if (v2Entries.length > 0) {
                await v2Entries[0].click();
                console.log('  Clicked first V2_presentation entry');
                await page.waitForTimeout(5000);
                bodyText = await page.textContent('body');
                console.log(`  After click - Has "Present": ${bodyText.includes('Present')}`);
            }

            // If still no Present, try scrolling to bottom to find import section
            if (!bodyText.includes('Present')) {
                console.log('  Scrolling to look for import section...');
                await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
                await page.waitForTimeout(2000);
                await screenshot(page, 'scroll-bottom');

                // Try importing job
                const input = await page.$('input[placeholder*="job"]');
                if (input) {
                    console.log('  Found job input, importing...');
                    await input.fill('job-7d32be316d06');
                    const importBtn = await page.$('button:has-text("Import from v2")');
                    if (importBtn) {
                        await importBtn.click();
                        for (let i = 0; i < 150; i++) {
                            await page.waitForTimeout(2000);
                            bodyText = await page.textContent('body');
                            if (bodyText.includes('Present')) {
                                console.log(`  Import completed after ~${(i+1)*2}s`);
                                break;
                            }
                            if (i % 15 === 14) console.log(`  Still importing... (${(i+1)*2}s)`);
                        }
                    }
                }
            }
        } else {
            console.log('  Present button already visible - V2 data loaded');
        }

        await screenshot(page, 'after-v2-load');

        // =====================================================
        // Step 3: Navigate to Conditions of Possibility tab
        // =====================================================
        console.log('\n========================================');
        console.log('Step 3: Navigate to Conditions of Possibility');
        console.log('========================================');

        const condTab = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab) {
            await condTab.click();
            await page.waitForTimeout(2000);
            console.log('  Switched to Conditions of Possibility tab');
        } else {
            console.log('  WARNING: Conditions of Possibility tab not found');
            // List available tabs
            const tabs = await page.$$eval('button', buttons =>
                buttons.filter(b => b.textContent.length < 50)
                    .map(b => b.textContent.trim())
                    .filter(t => t.length > 0)
            );
            console.log(`  Available buttons: ${tabs.join(' | ')}`);
        }
        await screenshot(page, 'conditions-tab');

        // =====================================================
        // Step 4: Expand Path Dependencies section BEFORE Present
        // =====================================================
        console.log('\n========================================');
        console.log('Step 4: Expand Path Dependencies BEFORE Present');
        console.log('========================================');

        // Find and click the Path Dependencies section header
        const allHeaders = await page.$$('.gen-conditions-tab h3, .gen-conditions-section h3');
        let pathDepsHeader = null;
        for (const h of allHeaders) {
            const text = await h.textContent();
            if (text.includes('Path Dependencies') || text.includes('Path Depend')) {
                pathDepsHeader = h;
                console.log(`  Found "Path Dependencies" header: "${text.trim()}"`);
                break;
            }
        }

        if (!pathDepsHeader) {
            // Try broader search
            const h3s = await page.$$('h3');
            for (const h of h3s) {
                const text = await h.textContent();
                console.log(`  h3: "${text.trim().substring(0, 50)}"`);
            }
            // Try clicking by text
            pathDepsHeader = await page.$('h3:has-text("Path")');
        }

        if (pathDepsHeader) {
            await pathDepsHeader.scrollIntoViewIfNeeded();
            await pathDepsHeader.click();
            await page.waitForTimeout(800);
            console.log('  Clicked Path Dependencies to expand');
        } else {
            console.log('  WARNING: Could not find Path Dependencies header');
            // Try to expand all sections
            const sections = await page.$$('.gen-conditions-section h3');
            console.log(`  Found ${sections.length} section headers`);
            for (let i = 0; i < sections.length; i++) {
                const t = await sections[i].textContent();
                console.log(`  Section ${i}: "${t.trim().substring(0, 60)}"`);
            }
        }

        // Measure content dimensions BEFORE
        const beforeMetrics = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };

            const sections = tab.querySelectorAll('.gen-conditions-section');
            const results = [];
            for (const sec of sections) {
                const h3 = sec.querySelector('h3');
                const content = sec.querySelector('.gen-section-content');
                const items = content?.querySelectorAll('.gen-mini-card, .gen-card, [class*="item"], [class*="card"]');
                results.push({
                    title: h3?.textContent?.trim()?.substring(0, 40) || 'unknown',
                    expanded: !!content,
                    contentHeight: content?.scrollHeight || 0,
                    itemCount: items?.length || 0,
                    containerStyle: content?.style?.cssText || '',
                    containerClass: content?.className || '',
                });
            }
            return { sections: results, tabHeight: tab.scrollHeight };
        });
        console.log('  BEFORE metrics:');
        console.log(`    Tab total height: ${beforeMetrics.tabHeight}px`);
        for (const s of (beforeMetrics.sections || [])) {
            console.log(`    ${s.title}: expanded=${s.expanded} height=${s.contentHeight}px items=${s.itemCount}`);
        }

        // Scroll to show Path Dependencies content
        await page.evaluate(() => {
            const pathSection = Array.from(document.querySelectorAll('.gen-conditions-section')).find(s =>
                s.querySelector('h3')?.textContent?.includes('Path')
            );
            if (pathSection) pathSection.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(500);

        // BEFORE screenshot - Path Dependencies expanded
        await screenshot(page, 'BEFORE-path-deps-expanded');
        await page.evaluate(() => window.scrollBy(0, 500));
        await page.waitForTimeout(300);
        await screenshot(page, 'BEFORE-path-deps-scrolled-down');

        // =====================================================
        // Step 5: Click Present and wait for completion
        // =====================================================
        console.log('\n========================================');
        console.log('Step 5: Click Present button');
        console.log('========================================');

        // Scroll back to top to find Present button
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(500);

        const presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            console.log('  ERROR: Present button not found!');
            await screenshot(page, 'no-present-button', { fullPage: true });
            return;
        }

        await presentBtn.scrollIntoViewIfNeeded();
        await page.waitForTimeout(300);
        await presentBtn.click();
        console.log('  Present button clicked. Waiting for polish...');

        const startTime = Date.now();
        let polished = false;
        for (let i = 0; i < 180; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                console.log(`  Polish completed in ${elapsed}s`);
                polished = true;
                break;
            }
            const errSpan = await page.$('.gen-polish-error, span:has-text("Polish failed"), span:has-text("Error")');
            if (errSpan && await errSpan.isVisible()) {
                const errText = await errSpan.textContent();
                console.log(`  Polish FAILED: ${errText}`);
                await screenshot(page, 'polish-error');
                break;
            }
            if (i % 20 === 19) console.log(`  Still polishing... (${i+1}s)`);
        }

        if (!polished) {
            console.log('  Polish did not complete in 180s');
            await screenshot(page, 'polish-timeout', { fullPage: true });
            return;
        }

        await page.waitForTimeout(1500);

        // =====================================================
        // Step 6: Switch to Conditions of Possibility tab again (if needed)
        // =====================================================
        console.log('\n========================================');
        console.log('Step 6: Switch to Conditions of Possibility (post-polish)');
        console.log('========================================');

        const condTab2 = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab2) {
            await condTab2.click();
            await page.waitForTimeout(2000);
            console.log('  Switched to Conditions of Possibility');
        }
        await screenshot(page, 'conditions-after-polish');

        // =====================================================
        // Step 7: Expand Path Dependencies AFTER Present
        // =====================================================
        console.log('\n========================================');
        console.log('Step 7: Expand Path Dependencies AFTER Present');
        console.log('========================================');

        // Find Path Dependencies header again
        const allHeaders2 = await page.$$('.gen-conditions-tab h3, .gen-conditions-section h3');
        let pathDepsAfter = null;
        for (const h of allHeaders2) {
            const text = await h.textContent();
            if (text.includes('Path Dependencies') || text.includes('Path Depend')) {
                pathDepsAfter = h;
                break;
            }
        }

        if (!pathDepsAfter) {
            pathDepsAfter = await page.$('h3:has-text("Path")');
        }

        if (pathDepsAfter) {
            // Check if already expanded
            const isExpanded = await page.evaluate(el => {
                const section = el.closest('.gen-conditions-section') || el.parentElement;
                return !!section?.querySelector('.gen-section-content');
            }, pathDepsAfter);

            if (!isExpanded) {
                await pathDepsAfter.click();
                await page.waitForTimeout(800);
                console.log('  Expanded Path Dependencies after polish');
            } else {
                console.log('  Path Dependencies already expanded');
            }

            await pathDepsAfter.scrollIntoViewIfNeeded();
            await page.waitForTimeout(500);
        }

        // Scroll to Path Dependencies
        await page.evaluate(() => {
            const pathSection = Array.from(document.querySelectorAll('.gen-conditions-section')).find(s =>
                s.querySelector('h3')?.textContent?.includes('Path')
            );
            if (pathSection) pathSection.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(500);

        // AFTER screenshot - Path Dependencies
        await screenshot(page, 'AFTER-path-deps-expanded');
        await page.evaluate(() => window.scrollBy(0, 500));
        await page.waitForTimeout(300);
        await screenshot(page, 'AFTER-path-deps-scrolled-down');

        // Measure content dimensions AFTER
        const afterMetrics = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };

            const sections = tab.querySelectorAll('.gen-conditions-section');
            const results = [];
            for (const sec of sections) {
                const h3 = sec.querySelector('h3');
                const content = sec.querySelector('.gen-section-content');
                const items = content?.querySelectorAll('.gen-mini-card, .gen-card, [class*="item"], [class*="card"]');

                // Check for grid layout
                const containerCS = content ? window.getComputedStyle(content) : null;

                results.push({
                    title: h3?.textContent?.trim()?.substring(0, 40) || 'unknown',
                    expanded: !!content,
                    contentHeight: content?.scrollHeight || 0,
                    itemCount: items?.length || 0,
                    containerStyle: content?.style?.cssText || '',
                    containerClass: content?.className || '',
                    display: containerCS?.display || '',
                    gridTemplateColumns: containerCS?.gridTemplateColumns || '',
                    gap: containerCS?.gap || '',
                });
            }
            return { sections: results, tabHeight: tab.scrollHeight };
        });
        console.log('  AFTER metrics:');
        console.log(`    Tab total height: ${afterMetrics.tabHeight}px`);
        for (const s of (afterMetrics.sections || [])) {
            console.log(`    ${s.title}: expanded=${s.expanded} height=${s.contentHeight}px items=${s.itemCount} display=${s.display} grid=${s.gridTemplateColumns}`);
        }

        // Height comparison
        if (beforeMetrics.tabHeight && afterMetrics.tabHeight) {
            const reduction = Math.round((1 - afterMetrics.tabHeight / beforeMetrics.tabHeight) * 100);
            console.log(`\n  HEIGHT COMPARISON: ${beforeMetrics.tabHeight}px -> ${afterMetrics.tabHeight}px (${reduction}% ${reduction > 0 ? 'reduction' : 'increase'})`);
        }

        // =====================================================
        // Step 8: Also check Unacknowledged Debts section
        // =====================================================
        console.log('\n========================================');
        console.log('Step 8: Expand Unacknowledged Debts AFTER Present');
        console.log('========================================');

        const allHeaders3 = await page.$$('.gen-conditions-tab h3, .gen-conditions-section h3');
        let unackHeader = null;
        for (const h of allHeaders3) {
            const text = await h.textContent();
            if (text.includes('Unacknowledged') || text.includes('Debts')) {
                unackHeader = h;
                console.log(`  Found "Unacknowledged Debts" header: "${text.trim()}"`);
                break;
            }
        }

        if (unackHeader) {
            const isExpanded = await page.evaluate(el => {
                const section = el.closest('.gen-conditions-section') || el.parentElement;
                return !!section?.querySelector('.gen-section-content');
            }, unackHeader);

            if (!isExpanded) {
                await unackHeader.click();
                await page.waitForTimeout(800);
                console.log('  Expanded Unacknowledged Debts');
            }

            await unackHeader.scrollIntoViewIfNeeded();
            await page.waitForTimeout(500);

            // Check grid layout for Unacknowledged Debts
            const unackMetrics = await page.evaluate(el => {
                const section = el.closest('.gen-conditions-section') || el.parentElement;
                const content = section?.querySelector('.gen-section-content');
                if (!content) return { error: 'no content' };
                const cs = window.getComputedStyle(content);
                const items = content.querySelectorAll('.gen-mini-card, .gen-card, [class*="item"], [class*="card"]');
                return {
                    display: cs.display,
                    gridTemplateColumns: cs.gridTemplateColumns,
                    gap: cs.gap,
                    containerStyle: content.style.cssText,
                    contentHeight: content.scrollHeight,
                    itemCount: items.length,
                };
            }, unackHeader);
            console.log('  Unacknowledged Debts metrics:', JSON.stringify(unackMetrics, null, 2));
        }

        await screenshot(page, 'AFTER-unack-debts-expanded');
        await page.evaluate(() => window.scrollBy(0, 500));
        await page.waitForTimeout(300);
        await screenshot(page, 'AFTER-unack-debts-scrolled-down');

        // =====================================================
        // Step 9: Detailed inline style inspection
        // =====================================================
        console.log('\n========================================');
        console.log('Step 9: Detailed inline style inspection');
        console.log('========================================');

        const styleDetails = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };

            const results = [];
            // Find all elements with inline styles
            const all = tab.querySelectorAll('*');
            for (const el of all) {
                const css = el.style?.cssText || '';
                if (css.includes('grid') || css.includes('column') || css.includes('gap')) {
                    results.push({
                        tag: el.tagName,
                        cls: (el.className?.toString() || '').substring(0, 60),
                        style: css.substring(0, 300),
                        childCount: el.children?.length || 0,
                    });
                }
            }
            return { gridElements: results };
        });
        console.log('  Elements with grid/column styles:');
        for (const el of (styleDetails.gridElements || [])) {
            console.log(`    <${el.tag} .${el.cls}> children=${el.childCount} style="${el.style}"`);
        }

        // =====================================================
        // Step 10: Full page screenshot for overall comparison
        // =====================================================
        console.log('\n========================================');
        console.log('Step 10: Full page screenshots');
        console.log('========================================');

        // Scroll to top of conditions tab
        await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (tab) tab.scrollIntoView({ block: 'start' });
        });
        await page.waitForTimeout(300);
        await screenshot(page, 'AFTER-full-conditions-top');

        // Expand all sections for full view
        const allSectionHeaders = await page.$$('.gen-conditions-tab h3, .gen-conditions-section h3');
        for (const h of allSectionHeaders) {
            const isExpanded = await page.evaluate(el => {
                const section = el.closest('.gen-conditions-section') || el.parentElement;
                return !!section?.querySelector('.gen-section-content');
            }, h);
            if (!isExpanded) {
                await h.click();
                await page.waitForTimeout(300);
            }
        }
        await page.waitForTimeout(500);

        // Full page screenshot with all expanded
        await screenshot(page, 'AFTER-all-sections-expanded', { fullPage: true });

        console.log('\n========================================');
        console.log('ALL TESTS COMPLETE');
        console.log('========================================');

    } catch (err) {
        console.error('ERROR:', err.message, err.stack);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
