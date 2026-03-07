import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-grid-audit';
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

    // Capture the polish API response
    let polishResponse = null;
    page.on('response', async resp => {
        if (resp.url().includes('polish')) {
            try {
                const body = await resp.text();
                polishResponse = JSON.parse(body);
            } catch {}
        }
    });

    try {
        // Navigate
        console.log('\n=== Navigate ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 90000
        });
        await page.waitForTimeout(8000);

        // Switch to Conditions of Possibility
        const condTab = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab) {
            await condTab.click();
            await page.waitForTimeout(2000);
        }

        // =====================================================
        // BEFORE: Expand ALL sections and measure
        // =====================================================
        console.log('\n=== BEFORE: Expand all sections ===');

        const beforeExpand = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };
            const sections = tab.querySelectorAll('.gen-conditions-section');
            const headers = [];
            for (const sec of sections) {
                const h3 = sec.querySelector('h3');
                if (h3) headers.push(h3.textContent.trim().substring(0, 50));
            }
            return { sectionCount: sections.length, headers };
        });
        console.log(`  Found ${beforeExpand.sectionCount} sections: ${beforeExpand.headers.join(' | ')}`);

        // Click all headers to expand
        const allH3Before = await page.$$('.gen-conditions-tab h3, .gen-conditions-section h3');
        for (const h of allH3Before) {
            const isCollapsed = await page.evaluate(el => {
                const section = el.closest('.gen-conditions-section') || el.parentElement;
                return !section?.querySelector('.gen-section-content');
            }, h);
            if (isCollapsed) {
                await h.click();
                await page.waitForTimeout(400);
            }
        }
        await page.waitForTimeout(500);

        // Measure every section BEFORE
        const beforeAll = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };
            const sections = tab.querySelectorAll('.gen-conditions-section');
            const data = [];
            for (const sec of sections) {
                const h3 = sec.querySelector('h3');
                const content = sec.querySelector('.gen-section-content');
                if (!content) {
                    data.push({ title: h3?.textContent?.trim()?.substring(0, 40), expanded: false });
                    continue;
                }
                // Count direct children that look like items
                const children = Array.from(content.children);
                const cs = window.getComputedStyle(content);

                // Find all items_container-like wrappers
                const itemContainers = content.querySelectorAll('[class*="items"], [class*="container"]');

                data.push({
                    title: h3?.textContent?.trim()?.substring(0, 40),
                    expanded: true,
                    contentHeight: content.scrollHeight,
                    contentWidth: content.clientWidth,
                    display: cs.display,
                    gridCols: cs.gridTemplateColumns,
                    directChildCount: children.length,
                    directChildTags: children.map(c => `${c.tagName}.${(c.className?.toString()||'').substring(0,30)}`).slice(0, 8),
                    itemContainerCount: itemContainers.length,
                });
            }
            return { sections: data, tabScrollHeight: tab.scrollHeight };
        });

        console.log(`\n  BEFORE - Tab total scroll height: ${beforeAll.tabScrollHeight}px`);
        for (const s of (beforeAll.sections || [])) {
            console.log(`  "${s.title}": expanded=${s.expanded} height=${s.contentHeight}px display=${s.display} grid=${s.gridCols} children=${s.directChildCount}`);
            if (s.directChildTags) console.log(`    child tags: ${s.directChildTags.join(', ')}`);
        }

        // Take per-section screenshots BEFORE
        for (let i = 0; i < (beforeAll.sections || []).length; i++) {
            const sec = beforeAll.sections[i];
            if (!sec.expanded) continue;
            await page.evaluate((idx) => {
                const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
                if (sections[idx]) sections[idx].scrollIntoView({ block: 'start' });
            }, i);
            await page.waitForTimeout(300);
            const safeName = sec.title.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 30);
            await screenshot(page, `BEFORE-section-${i}-${safeName}`);
        }

        // =====================================================
        // Click Present
        // =====================================================
        console.log('\n=== Click Present ===');
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(500);

        const presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) {
            console.log('  ERROR: No Present button');
            return;
        }
        await presentBtn.scrollIntoViewIfNeeded();
        await presentBtn.click();
        console.log('  Clicked Present, waiting...');

        let polished = false;
        for (let i = 0; i < 180; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) {
                console.log(`  Polish done in ${i+1}s`);
                polished = true;
                break;
            }
            if (i % 20 === 19) console.log(`  Waiting... (${i+1}s)`);
        }
        if (!polished) {
            console.log('  Polish timeout');
            return;
        }

        await page.waitForTimeout(1500);

        // Log the polish response
        if (polishResponse) {
            console.log('\n=== Polish API Response Analysis ===');
            console.log(`  school: ${polishResponse.style_school}`);
            console.log(`  cached: ${polishResponse.cached}`);
            const overrides = polishResponse.polished_payload?.style_overrides;
            if (overrides) {
                console.log(`  Override keys: ${Object.keys(overrides).join(', ')}`);
                for (const [key, val] of Object.entries(overrides)) {
                    console.log(`  ${key}: ${JSON.stringify(val)}`);
                }
            }
        }

        // Switch to CoP tab again
        const condTab2 = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab2) {
            await condTab2.click();
            await page.waitForTimeout(2000);
        }

        // =====================================================
        // AFTER: Expand ALL sections and measure
        // =====================================================
        console.log('\n=== AFTER: Expand all sections ===');

        const allH3After = await page.$$('.gen-conditions-tab h3, .gen-conditions-section h3');
        for (const h of allH3After) {
            const isCollapsed = await page.evaluate(el => {
                const section = el.closest('.gen-conditions-section') || el.parentElement;
                return !section?.querySelector('.gen-section-content');
            }, h);
            if (isCollapsed) {
                await h.click();
                await page.waitForTimeout(400);
            }
        }
        await page.waitForTimeout(500);

        // Measure every section AFTER
        const afterAll = await page.evaluate(() => {
            const tab = document.querySelector('.gen-conditions-tab');
            if (!tab) return { error: 'no tab' };
            const sections = tab.querySelectorAll('.gen-conditions-section');
            const data = [];
            for (const sec of sections) {
                const h3 = sec.querySelector('h3');
                const content = sec.querySelector('.gen-section-content');
                if (!content) {
                    data.push({ title: h3?.textContent?.trim()?.substring(0, 40), expanded: false });
                    continue;
                }
                const children = Array.from(content.children);
                const cs = window.getComputedStyle(content);

                // Check all descendants for grid
                const gridElements = [];
                const allEls = content.querySelectorAll('*');
                for (const el of allEls) {
                    const elCs = window.getComputedStyle(el);
                    if (elCs.display === 'grid') {
                        gridElements.push({
                            tag: el.tagName,
                            cls: (el.className?.toString() || '').substring(0, 40),
                            cols: elCs.gridTemplateColumns,
                            childCount: el.children.length,
                            inlineStyle: (el.style?.cssText || '').substring(0, 200),
                        });
                    }
                }

                data.push({
                    title: h3?.textContent?.trim()?.substring(0, 40),
                    expanded: true,
                    contentHeight: content.scrollHeight,
                    contentWidth: content.clientWidth,
                    display: cs.display,
                    gridCols: cs.gridTemplateColumns,
                    directChildCount: children.length,
                    directChildTags: children.map(c => `${c.tagName}.${(c.className?.toString()||'').substring(0,30)}`).slice(0, 8),
                    gridElements: gridElements,
                    inlineStyle: (content.style?.cssText || '').substring(0, 300),
                });
            }
            return { sections: data, tabScrollHeight: tab.scrollHeight };
        });

        console.log(`\n  AFTER - Tab total scroll height: ${afterAll.tabScrollHeight}px`);
        for (const s of (afterAll.sections || [])) {
            console.log(`\n  "${s.title}":`);
            console.log(`    expanded=${s.expanded} height=${s.contentHeight}px display=${s.display} grid=${s.gridCols}`);
            console.log(`    children=${s.directChildCount} tags: ${(s.directChildTags||[]).join(', ')}`);
            console.log(`    inline: "${s.inlineStyle}"`);
            if (s.gridElements?.length > 0) {
                console.log(`    GRID ELEMENTS FOUND (${s.gridElements.length}):`);
                for (const g of s.gridElements) {
                    console.log(`      <${g.tag} .${g.cls}> cols="${g.cols}" children=${g.childCount} inline="${g.inlineStyle}"`);
                }
            } else {
                console.log(`    NO grid elements found`);
            }
        }

        // Height comparison
        if (beforeAll.tabScrollHeight && afterAll.tabScrollHeight) {
            const diff = afterAll.tabScrollHeight - beforeAll.tabScrollHeight;
            const pct = Math.round((diff / beforeAll.tabScrollHeight) * 100);
            console.log(`\n  TOTAL HEIGHT: ${beforeAll.tabScrollHeight}px -> ${afterAll.tabScrollHeight}px (${pct > 0 ? '+' : ''}${pct}% | ${diff > 0 ? '+' : ''}${diff}px)`);
        }

        // Per-section height comparison
        console.log('\n  PER-SECTION HEIGHT COMPARISON:');
        for (let i = 0; i < (beforeAll.sections || []).length; i++) {
            const b = beforeAll.sections[i];
            const a = afterAll.sections?.[i];
            if (b?.expanded && a?.expanded) {
                const diff = a.contentHeight - b.contentHeight;
                const pct = b.contentHeight > 0 ? Math.round((diff / b.contentHeight) * 100) : 'N/A';
                const hasGrid = (a.gridElements?.length || 0) > 0;
                console.log(`  "${b.title}": ${b.contentHeight}px -> ${a.contentHeight}px (${typeof pct === 'number' ? (pct > 0 ? '+' : '') + pct + '%' : pct}) ${hasGrid ? '[HAS GRID]' : '[NO GRID]'}`);
            }
        }

        // Take per-section screenshots AFTER
        for (let i = 0; i < (afterAll.sections || []).length; i++) {
            const sec = afterAll.sections[i];
            if (!sec.expanded) continue;
            await page.evaluate((idx) => {
                const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
                if (sections[idx]) sections[idx].scrollIntoView({ block: 'start' });
            }, i);
            await page.waitForTimeout(300);
            const safeName = sec.title.replace(/[^a-zA-Z0-9]/g, '-').substring(0, 30);
            await screenshot(page, `AFTER-section-${i}-${safeName}`);
        }

        // Full page
        await screenshot(page, 'AFTER-all-expanded-fullpage', { fullPage: true });

        console.log('\n=== COMPLETE ===');

    } catch (err) {
        console.error('ERROR:', err.message, err.stack);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
