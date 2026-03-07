import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

const SCREENSHOTS_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/present-pathdeps-detail';
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

    try {
        // Navigate and load
        console.log('\n=== Navigate ===');
        await page.goto('https://the-critic-1.onrender.com/p/morozov-on-varoufakis/genealogy', {
            waitUntil: 'domcontentloaded',
            timeout: 90000
        });
        await page.waitForTimeout(8000);

        // Switch to CoP tab
        const condTab = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab) await condTab.click();
        await page.waitForTimeout(2000);

        // Click Present
        console.log('\n=== Click Present ===');
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(500);
        const presentBtn = await page.$('button.gen-link-btn:has-text("Present")');
        if (!presentBtn) { console.log('No Present button'); return; }
        await presentBtn.scrollIntoViewIfNeeded();
        await presentBtn.click();
        console.log('  Clicked, waiting...');

        for (let i = 0; i < 180; i++) {
            await page.waitForTimeout(1000);
            const reset = await page.$('button:has-text("Reset")');
            if (reset && await reset.isVisible()) { console.log(`  Done in ${i+1}s`); break; }
            if (i % 20 === 19) console.log(`  Waiting... (${i+1}s)`);
        }
        await page.waitForTimeout(1500);

        // Switch to CoP again
        const condTab2 = await page.$('button:has-text("Conditions of Possibility")');
        if (condTab2) await condTab2.click();
        await page.waitForTimeout(2000);

        // =====================================================
        // Deep inspection of Path Dependencies
        // =====================================================
        console.log('\n=== Deep inspection of Path Dependencies ===');

        // Expand Path Dependencies
        const pathH3 = await page.$('h3:has-text("Path Dependencies")');
        if (pathH3) {
            const isExp = await page.evaluate(el => {
                const sec = el.closest('.gen-conditions-section');
                return !!sec?.querySelector('.gen-section-content');
            }, pathH3);
            if (!isExp) {
                await pathH3.click();
                await page.waitForTimeout(800);
            }
        }

        // Deep DOM inspection of Path Dependencies section
        const pathDepsDetail = await page.evaluate(() => {
            const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
            let pathSection = null;
            for (const s of sections) {
                if (s.querySelector('h3')?.textContent?.includes('Path Dependencies')) {
                    pathSection = s;
                    break;
                }
            }
            if (!pathSection) return { error: 'no path deps section' };

            const content = pathSection.querySelector('.gen-section-content');
            if (!content) return { error: 'no content' };

            // Walk the full DOM tree
            function inspectElement(el, depth = 0) {
                const cs = window.getComputedStyle(el);
                const result = {
                    tag: el.tagName,
                    cls: (el.className?.toString() || '').substring(0, 60),
                    display: cs.display,
                    gridCols: cs.gridTemplateColumns !== 'none' ? cs.gridTemplateColumns : '',
                    overflow: cs.overflow !== 'visible' ? cs.overflow : '',
                    overflowX: cs.overflowX !== 'visible' ? cs.overflowX : '',
                    width: el.clientWidth,
                    scrollWidth: el.scrollWidth,
                    inlineStyle: (el.style?.cssText || '').substring(0, 200),
                    childCount: el.children.length,
                    depth,
                };
                const children = [];
                if (depth < 4) {
                    for (const child of el.children) {
                        children.push(inspectElement(child, depth + 1));
                    }
                }
                result.children = children;
                return result;
            }

            return inspectElement(content);
        });

        function printTree(node, indent = '') {
            const flags = [];
            if (node.display === 'grid') flags.push(`GRID(${node.gridCols?.substring(0, 60)})`);
            if (node.overflow) flags.push(`overflow:${node.overflow}`);
            if (node.overflowX) flags.push(`overflowX:${node.overflowX}`);
            if (node.scrollWidth > node.width + 5) flags.push(`OVERFLOW(w:${node.width} sw:${node.scrollWidth})`);
            if (node.inlineStyle) flags.push(`style="${node.inlineStyle.substring(0, 100)}"`);

            console.log(`${indent}<${node.tag} .${node.cls}> display=${node.display} w=${node.width} children=${node.childCount} ${flags.join(' ')}`);
            for (const child of (node.children || [])) {
                printTree(child, indent + '  ');
            }
        }

        console.log('\nPath Dependencies DOM tree:');
        printTree(pathDepsDetail);

        // Scroll to Path Dependencies and take close-up screenshot
        await page.evaluate(() => {
            const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
            for (const s of sections) {
                if (s.querySelector('h3')?.textContent?.includes('Path Dependencies')) {
                    s.scrollIntoView({ block: 'start' });
                    break;
                }
            }
        });
        await page.waitForTimeout(300);
        await screenshot(page, 'path-deps-closeup');

        // Scroll down within Path Dependencies
        await page.evaluate(() => window.scrollBy(0, 300));
        await page.waitForTimeout(200);
        await screenshot(page, 'path-deps-scrolled');

        // =====================================================
        // Also inspect Unacknowledged Debts closely
        // =====================================================
        console.log('\n=== Deep inspection of Unacknowledged Debts ===');

        const unackH3 = await page.$('h3:has-text("Unacknowledged")');
        if (unackH3) {
            const isExp = await page.evaluate(el => {
                const sec = el.closest('.gen-conditions-section');
                return !!sec?.querySelector('.gen-section-content');
            }, unackH3);
            if (!isExp) {
                await unackH3.click();
                await page.waitForTimeout(800);
            }
        }

        const unackDetail = await page.evaluate(() => {
            const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
            let section = null;
            for (const s of sections) {
                if (s.querySelector('h3')?.textContent?.includes('Unacknowledged')) {
                    section = s;
                    break;
                }
            }
            if (!section) return { error: 'no section' };

            const content = section.querySelector('.gen-section-content');
            if (!content) return { error: 'no content' };

            // Find grid container
            const gridEl = content.querySelector('div[style*="grid"]');
            if (!gridEl) return { error: 'no grid element', contentInline: content.style.cssText };

            const gridCS = window.getComputedStyle(gridEl);
            const items = Array.from(gridEl.children);

            return {
                gridDisplay: gridCS.display,
                gridCols: gridCS.gridTemplateColumns,
                gridGap: gridCS.gap,
                gridWidth: gridEl.clientWidth,
                gridScrollWidth: gridEl.scrollWidth,
                gridOverflow: gridCS.overflow,
                gridInlineStyle: gridEl.style.cssText,
                itemCount: items.length,
                items: items.map((item, i) => {
                    const cs = window.getComputedStyle(item);
                    return {
                        index: i,
                        tag: item.tagName,
                        width: item.clientWidth,
                        height: item.clientHeight,
                        display: cs.display,
                        inlineStyle: (item.style?.cssText || '').substring(0, 200),
                        textSnippet: item.textContent?.substring(0, 80),
                    };
                }),
            };
        });

        console.log('\nUnacknowledged Debts grid details:');
        console.log(`  Grid display: ${unackDetail.gridDisplay}`);
        console.log(`  Grid columns: ${unackDetail.gridCols}`);
        console.log(`  Grid gap: ${unackDetail.gridGap}`);
        console.log(`  Grid width: ${unackDetail.gridWidth} scrollWidth: ${unackDetail.gridScrollWidth}`);
        console.log(`  Grid overflow: ${unackDetail.gridOverflow}`);
        console.log(`  Grid inline: ${unackDetail.gridInlineStyle}`);
        console.log(`  Items: ${unackDetail.itemCount}`);
        for (const item of (unackDetail.items || [])) {
            console.log(`    [${item.index}] ${item.width}x${item.height}px "${item.textSnippet}..."`);
        }

        // Screenshot Unacknowledged Debts
        await page.evaluate(() => {
            const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
            for (const s of sections) {
                if (s.querySelector('h3')?.textContent?.includes('Unacknowledged')) {
                    s.scrollIntoView({ block: 'start' });
                    break;
                }
            }
        });
        await page.waitForTimeout(300);
        await screenshot(page, 'unack-debts-closeup');
        await page.evaluate(() => window.scrollBy(0, 500));
        await page.waitForTimeout(200);
        await screenshot(page, 'unack-debts-scrolled');
        await page.evaluate(() => window.scrollBy(0, 500));
        await page.waitForTimeout(200);
        await screenshot(page, 'unack-debts-scrolled-2');

        // =====================================================
        // Check if the grid is visually 2 columns in Path Dependencies
        // =====================================================
        console.log('\n=== Path Dependencies grid visual check ===');

        const pathGridVisual = await page.evaluate(() => {
            const sections = document.querySelectorAll('.gen-conditions-tab .gen-conditions-section');
            let section = null;
            for (const s of sections) {
                if (s.querySelector('h3')?.textContent?.includes('Path Dependencies')) {
                    section = s;
                    break;
                }
            }
            if (!section) return { error: 'no section' };

            const content = section.querySelector('.gen-section-content');
            if (!content) return { error: 'no content' };

            const gridEl = content.querySelector('div[style*="grid"]');
            if (!gridEl) return { error: 'no grid', contentChildren: content.children.length };

            const items = Array.from(gridEl.children);
            const positions = items.map((item, i) => {
                const rect = item.getBoundingClientRect();
                return {
                    index: i,
                    left: Math.round(rect.left),
                    top: Math.round(rect.top),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    tag: item.tagName,
                    textSnippet: item.textContent?.substring(0, 60),
                };
            });

            // Check if items are in 2 columns by checking x positions
            const uniqueLefts = [...new Set(positions.map(p => p.left))].sort((a, b) => a - b);

            return {
                gridWidth: gridEl.clientWidth,
                gridScrollWidth: gridEl.scrollWidth,
                gridComputedCols: window.getComputedStyle(gridEl).gridTemplateColumns,
                itemCount: items.length,
                positions,
                uniqueLeftPositions: uniqueLefts,
                is2Column: uniqueLefts.length === 2,
            };
        });

        console.log(`  Grid width: ${pathGridVisual.gridWidth} scrollWidth: ${pathGridVisual.gridScrollWidth}`);
        console.log(`  Computed cols: ${pathGridVisual.gridComputedCols}`);
        console.log(`  Items: ${pathGridVisual.itemCount}`);
        console.log(`  Unique left positions: ${pathGridVisual.uniqueLeftPositions?.join(', ')}`);
        console.log(`  Is 2-column: ${pathGridVisual.is2Column}`);
        for (const p of (pathGridVisual.positions || [])) {
            console.log(`    [${p.index}] left=${p.left} top=${p.top} size=${p.width}x${p.height} "${p.textSnippet}..."`);
        }

        console.log('\n=== COMPLETE ===');

    } catch (err) {
        console.error('ERROR:', err.message, err.stack);
        await screenshot(page, 'error');
    } finally {
        await browser.close();
    }
}

main().catch(console.error);
