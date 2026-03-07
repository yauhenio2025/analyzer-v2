import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const SCREENSHOT_DIR = '/home/evgeny/projects/analyzer-v2/test-screenshots/polish-persistence';
const BASE_URL = 'https://the-critic-1.onrender.com';
const GENEALOGY_URL = `${BASE_URL}/p/morozov-benanav-001/genealogy`;

fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
// Clean old screenshots
for (const f of fs.readdirSync(SCREENSHOT_DIR)) {
    fs.unlinkSync(path.join(SCREENSHOT_DIR, f));
}

let stepNum = 1;
async function screenshot(page, name) {
    const num = String(stepNum++).padStart(2, '0');
    const filepath = path.join(SCREENSHOT_DIR, `${num}-${name}.png`);
    await page.screenshot({ path: filepath, fullPage: false });
    console.log(`  [SCREENSHOT] ${num}-${name}.png`);
    return filepath;
}

async function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
}

async function main() {
    console.log('=== FULL Polish Persistence Test ===\n');

    const browser = await puppeteer.connect({ browserURL: 'http://localhost:9222' });
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    const consoleMessages = [];
    page.on('console', msg => {
        consoleMessages.push({ type: msg.type(), text: msg.text().substring(0, 300) });
    });
    const pageErrors = [];
    page.on('pageerror', err => pageErrors.push(err.message.substring(0, 300)));

    try {
        // ============================
        // STEP 1: Navigate to genealogy page
        // ============================
        console.log('STEP 1: Navigate to genealogy page');
        await page.goto(GENEALOGY_URL, { waitUntil: 'networkidle2', timeout: 60000 });
        await sleep(3000);

        // Scroll to "Analysis Results" section
        await page.evaluate(() => {
            const h2s = document.querySelectorAll('h2');
            for (const h of h2s) {
                if (h.textContent.includes('Analysis Results')) {
                    h.scrollIntoView({ block: 'start' });
                    return;
                }
            }
        });
        await sleep(1000);
        await screenshot(page, 'analysis-results-top');

        // ============================
        // STEP 2: Identify current tab and find Present button
        // ============================
        console.log('\nSTEP 2: Identify tabs and Present button location');

        // Get the active tab and all tab names
        const tabInfo = await page.evaluate(() => {
            const tabBtns = document.querySelectorAll('.gen-tab-btn, [class*="gen-tab"] button, .gen-results-tabs button');
            const tabs = [];
            let activeTab = null;
            for (const btn of tabBtns) {
                const name = btn.textContent.trim();
                const isActive = btn.classList.contains('active');
                tabs.push({ name, active: isActive });
                if (isActive) activeTab = name;
            }
            // Fallback: look for buttons inside the tab area
            if (tabs.length === 0) {
                const allBtns = document.querySelectorAll('button');
                const tabNames = ['Relationship Landscape', 'Target Work Profile', 'Idea Evolution Map',
                    'Per-Work Scan Detail', 'Tactics & Strategies', 'Conditions of Possibility',
                    'Genealogical Portrait', 'Author Intellectual Profile'];
                for (const btn of allBtns) {
                    const text = btn.textContent.trim();
                    if (tabNames.includes(text)) {
                        const isActive = btn.classList.contains('active');
                        tabs.push({ name: text, active: isActive });
                        if (isActive) activeTab = text;
                    }
                }
            }
            return { tabs, activeTab };
        });
        console.log('  Tabs:', JSON.stringify(tabInfo.tabs.map(t => `${t.name}${t.active ? ' [ACTIVE]' : ''}`)));
        console.log('  Active tab:', tabInfo.activeTab);

        // Find Present/Re-polish button
        const presentBtnInfo = await page.evaluate(() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.trim();
                if (text === 'Present' || text === 'Re-polish' || text.includes('Present') && text.length < 20) {
                    const rect = btn.getBoundingClientRect();
                    return {
                        text,
                        class: btn.className,
                        visible: btn.offsetParent !== null,
                        rect: { top: rect.top, left: rect.left, width: rect.width, height: rect.height }
                    };
                }
            }
            return null;
        });
        console.log('  Present button:', JSON.stringify(presentBtnInfo));

        // ============================
        // STEP 3: Check for Reset button and reset if needed
        // ============================
        console.log('\nSTEP 3: Check for Reset button');

        const resetBtnInfo = await page.evaluate(() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.trim();
                if (text === 'Reset' || text === 'Reset Styling') {
                    return { text, visible: btn.offsetParent !== null, class: btn.className };
                }
            }
            return null;
        });
        console.log('  Reset button:', JSON.stringify(resetBtnInfo));

        if (resetBtnInfo && resetBtnInfo.visible) {
            console.log('  Clicking Reset to get clean state...');
            await page.evaluate(() => {
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.trim() === 'Reset' || btn.textContent.trim() === 'Reset Styling') {
                        btn.click();
                        return;
                    }
                }
            });
            await sleep(2000);
            console.log('  Reset clicked');
        }

        // ============================
        // STEP 4: Take BEFORE screenshot - scroll Present button into view
        // ============================
        console.log('\nSTEP 4: Take BEFORE screenshot');

        // Scroll the Present button into view
        await page.evaluate(() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.textContent.trim() === 'Present' || btn.textContent.trim() === 'Re-polish') {
                    btn.scrollIntoView({ block: 'center' });
                    return;
                }
            }
        });
        await sleep(500);
        await screenshot(page, 'BEFORE-present-button-area');

        // Also take a screenshot of the tab content area
        await page.evaluate(() => {
            const content = document.querySelector('.gen-tab-content, [class*="tab-content"], [class*="results"]');
            if (content) content.scrollIntoView({ block: 'start' });
        });
        await sleep(500);
        await screenshot(page, 'BEFORE-tab-content');

        // ============================
        // STEP 5: Click Present button and wait for polish API
        // ============================
        console.log('\nSTEP 5: Click Present button');

        // Clear console messages before clicking
        consoleMessages.length = 0;

        const presentBtnText = await page.evaluate(() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.trim();
                if (text === 'Present' || text === 'Re-polish') {
                    return text;
                }
            }
            return null;
        });

        if (!presentBtnText) {
            console.log('  ERROR: No Present/Re-polish button found!');
            await screenshot(page, 'ERROR-no-present-button');
            return;
        }

        console.log(`  Clicking "${presentBtnText}" button...`);
        await page.evaluate((targetText) => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                if (btn.textContent.trim() === targetText) {
                    btn.click();
                    return;
                }
            }
        }, presentBtnText);

        // Wait for the polish API to complete (5-15 seconds)
        console.log('  Waiting for polish API response...');

        // Take periodic screenshots while waiting
        for (let i = 0; i < 6; i++) {
            await sleep(3000);
            const polishState = await page.evaluate(() => {
                // Check if there's a loading indicator
                const loading = document.querySelector('[class*="loading"], [class*="spinner"], [class*="polishing"]');
                const acceptBtn = document.querySelector('button');
                let hasAccept = false;
                let hasReset = false;
                const allBtns = document.querySelectorAll('button');
                for (const btn of allBtns) {
                    const text = btn.textContent.trim();
                    if (text.includes('Accept')) hasAccept = true;
                    if (text === 'Reset') hasReset = true;
                }
                return {
                    hasLoading: !!loading,
                    hasAccept,
                    hasReset,
                    loadingText: loading ? loading.textContent.trim().substring(0, 50) : null
                };
            });
            console.log(`  [${(i+1)*3}s] State: ${JSON.stringify(polishState)}`);

            if (polishState.hasAccept) {
                console.log('  Polish complete - Accept button appeared!');
                break;
            }
        }

        await sleep(2000);
        await screenshot(page, 'AFTER-polish-complete');

        // Scroll to see the polished content
        await page.evaluate(() => {
            const content = document.querySelector('.gen-tab-content, [class*="tab-content"]');
            if (content) content.scrollIntoView({ block: 'start' });
        });
        await sleep(500);
        await screenshot(page, 'AFTER-polished-content');

        // ============================
        // STEP 6: Check for Accept Styling and Reset buttons
        // ============================
        console.log('\nSTEP 6: Verify Accept Styling and Reset buttons');

        const postPolishButtons = await page.evaluate(() => {
            const results = [];
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.trim();
                if (text.includes('Accept') || text === 'Reset' || text === 'Re-polish' || text === 'Present') {
                    results.push({
                        text,
                        class: btn.className,
                        visible: btn.offsetParent !== null
                    });
                }
            }
            return results;
        });
        console.log('  Post-polish buttons:', JSON.stringify(postPolishButtons, null, 2));

        // ============================
        // STEP 7: Click Accept Styling
        // ============================
        console.log('\nSTEP 7: Click Accept Styling');

        const acceptClicked = await page.evaluate(() => {
            const buttons = document.querySelectorAll('button');
            for (const btn of buttons) {
                const text = btn.textContent.trim();
                if (text.includes('Accept')) {
                    btn.click();
                    return text;
                }
            }
            return null;
        });

        if (acceptClicked) {
            console.log(`  Clicked: "${acceptClicked}"`);
            await sleep(2000);
            await screenshot(page, 'AFTER-accept-styling');

            // Check what buttons are now visible
            const postAcceptButtons = await page.evaluate(() => {
                const results = [];
                const buttons = document.querySelectorAll('button');
                for (const btn of buttons) {
                    const text = btn.textContent.trim();
                    if (text.includes('Accept') || text === 'Reset' || text === 'Re-polish' || text === 'Present') {
                        results.push({ text, visible: btn.offsetParent !== null });
                    }
                }
                return results;
            });
            console.log('  Post-accept buttons:', JSON.stringify(postAcceptButtons));
        } else {
            console.log('  WARNING: No Accept button found to click');
            await screenshot(page, 'WARNING-no-accept-button');
        }

        // ============================
        // STEP 8: Check localStorage for persisted polish data
        // ============================
        console.log('\nSTEP 8: Check localStorage for persisted data');

        const localStorageData = await page.evaluate(() => {
            const keys = [];
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key.includes('polish') || key.includes('Polish') || key.includes('style') ||
                    key.includes('Style') || key.includes('genealog') || key.includes('cache') ||
                    key.includes('present')) {
                    const value = localStorage.getItem(key);
                    keys.push({
                        key,
                        valueLength: value ? value.length : 0,
                        valuePreview: value ? value.substring(0, 100) : null
                    });
                }
            }
            // Also check all keys
            const allKeys = [];
            for (let i = 0; i < localStorage.length; i++) {
                allKeys.push(localStorage.key(i));
            }
            return { relevantKeys: keys, allKeys };
        });
        console.log('  All localStorage keys:', localStorageData.allKeys);
        console.log('  Relevant keys:', JSON.stringify(localStorageData.relevantKeys, null, 2));

        // ============================
        // STEP 9: CRITICAL TEST - Refresh the page
        // ============================
        console.log('\nSTEP 9: CRITICAL TEST - Page refresh persistence');

        const currentGenUrl = page.url();
        console.log(`  Refreshing: ${currentGenUrl}`);

        await page.goto(currentGenUrl, { waitUntil: 'networkidle2', timeout: 60000 });
        await sleep(5000);

        // Scroll to Analysis Results section
        await page.evaluate(() => {
            const h2s = document.querySelectorAll('h2');
            for (const h of h2s) {
                if (h.textContent.includes('Analysis Results')) {
                    h.scrollIntoView({ block: 'start' });
                    return;
                }
            }
        });
        await sleep(2000);
        await screenshot(page, 'AFTER-REFRESH-results-top');

        // Scroll to tab content
        await page.evaluate(() => {
            const content = document.querySelector('.gen-tab-content, [class*="tab-content"]');
            if (content) content.scrollIntoView({ block: 'start' });
        });
        await sleep(1000);
        await screenshot(page, 'AFTER-REFRESH-tab-content');

        // ============================
        // STEP 10: Verify polished styling persists
        // ============================
        console.log('\nSTEP 10: Verify polished styling persists after refresh');

        const postRefreshState = await page.evaluate(() => {
            const buttons = document.querySelectorAll('button');
            const btnTexts = [];
            for (const btn of buttons) {
                const text = btn.textContent.trim();
                if (text === 'Present' || text === 'Re-polish' || text === 'Reset' ||
                    text.includes('Accept') || text.includes('polish') || text.includes('Polish')) {
                    btnTexts.push({ text, visible: btn.offsetParent !== null });
                }
            }

            // Check if styled content is present (look for inline styles or class changes)
            const styledElements = document.querySelectorAll('[style*="background"], [style*="color"], [style*="border"], [class*="polished"], [class*="styled"]');

            // Check for specific polish indicators in the tab content
            const tabContent = document.querySelector('.gen-tab-content');
            const hasStyledContent = tabContent ?
                (tabContent.querySelector('[style]') !== null ||
                 tabContent.querySelector('[class*="polish"]') !== null ||
                 tabContent.innerHTML.includes('polished')) : false;

            return {
                polishButtons: btnTexts,
                styledElementCount: styledElements.length,
                hasStyledContent,
                tabContentPreview: tabContent ? tabContent.innerHTML.substring(0, 200) : null
            };
        });

        console.log('  Post-refresh buttons:', JSON.stringify(postRefreshState.polishButtons));
        console.log('  Styled element count:', postRefreshState.styledElementCount);
        console.log('  Has styled content:', postRefreshState.hasStyledContent);

        // Check if Re-polish button is present (indicates accepted state was persisted)
        const hasRepolish = postRefreshState.polishButtons.some(b => b.text === 'Re-polish' && b.visible);
        const hasPresent = postRefreshState.polishButtons.some(b => b.text === 'Present' && b.visible);
        const hasReset = postRefreshState.polishButtons.some(b => b.text === 'Reset' && b.visible);

        console.log('\n=== PERSISTENCE VERDICT ===');
        if (hasRepolish) {
            console.log('  PASS: "Re-polish" button present after refresh - styling was persisted!');
        } else if (hasPresent) {
            console.log('  FAIL: "Present" button shown instead of "Re-polish" - styling was NOT persisted');
        } else {
            console.log('  UNCLEAR: Neither Present nor Re-polish visible - check screenshots');
        }
        if (hasReset) {
            console.log('  PASS: "Reset" button present after refresh');
        }

        // Scroll down to see the content cards after refresh
        await page.evaluate(() => window.scrollBy(0, 500));
        await sleep(500);
        await screenshot(page, 'AFTER-REFRESH-content-cards');

        // ============================
        // Console log summary
        // ============================
        console.log('\n=== Console Messages (polish-related + errors) ===');
        const relevantLogs = consoleMessages.filter(m =>
            m.type === 'error' ||
            m.text.toLowerCase().includes('polish') ||
            m.text.toLowerCase().includes('cache') ||
            m.text.toLowerCase().includes('persist') ||
            m.text.toLowerCase().includes('localstorage') ||
            m.text.toLowerCase().includes('accept') ||
            m.text.toLowerCase().includes('style') ||
            m.text.toLowerCase().includes('present')
        );
        for (const msg of relevantLogs.slice(0, 30)) {
            console.log(`  [${msg.type}] ${msg.text}`);
        }

        if (pageErrors.length > 0) {
            console.log('\n=== Page Errors ===');
            for (const err of pageErrors) {
                console.log(`  ${err}`);
            }
        }

    } catch (error) {
        console.error('Test error:', error.message);
        console.error(error.stack);
        await screenshot(page, 'error-state');
    } finally {
        await page.close();
    }

    console.log('\n=== FULL TEST COMPLETE ===');
}

main().catch(console.error);
