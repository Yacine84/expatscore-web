// redditScraper.js
// Puppeteer-based scraper for Reddit (new Shreddit UI)

const puppeteer = require('puppeteer');

/**
 * Sleep for a random duration between min and max milliseconds.
 */
function randomDelay(min = 1000, max = 3000) {
    return new Promise(resolve => setTimeout(resolve, Math.floor(Math.random() * (max - min + 1) + min)));
}

/**
 * Attempt to close any modal or overlay that might appear (login popup, etc.)
 */
async function closePopup(page) {
    const closeSelectors = [
        'button[aria-label="Close"]',
        'button.close',
        'button[data-testid="close-button"]',
        'div[role="dialog"] button:first-child',
        'button[aria-label="Dismiss"]'
    ];
    for (const selector of closeSelectors) {
        const closeBtn = await page.$(selector);
        if (closeBtn) {
            try {
                await closeBtn.click();
                console.log('Closed popup with selector:', selector);
                await randomDelay(500, 1000);
                return true;
            } catch (e) {
                // ignore, try next selector
            }
        }
    }
    return false;
}

/**
 * Scrape Reddit posts from a given subreddit (newest first).
 * @param {string} subreddit - Name of the subreddit (without r/).
 * @param {number} numPosts - Number of posts to scrape.
 * @returns {Promise<Array>} Array of post objects.
 */
async function scrapeReddit(subreddit, numPosts) {
    console.log(`[scraper] Starting scrape for r/${subreddit}, target ${numPosts} posts`);

    const browser = await puppeteer.launch({
        executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 800 });
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    const url = `https://www.reddit.com/r/${subreddit}/new/`;
    console.log(`[scraper] Navigating to ${url}`);
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

    // Wait for the first post to appear
    await page.waitForSelector('shreddit-post', { timeout: 15000 }).catch(() => {
        console.warn('[scraper] No shreddit-post found after timeout – page might be different');
    });

    // Close any initial popup
    await closePopup(page);

    let previousCount = 0;
    let sameCountAttempts = 0;
    const maxSameCountAttempts = 5;

    // Scroll until we have enough posts or no new posts load
    while (true) {
        const currentCount = await page.$$eval('shreddit-post', els => els.length);
        console.log(`[scraper] Found ${currentCount} posts so far`);

        if (currentCount >= numPosts) {
            console.log(`[scraper] Reached target (${numPosts})`);
            break;
        }

        if (currentCount === previousCount) {
            sameCountAttempts++;
            console.log(`[scraper] No new posts (attempt ${sameCountAttempts}/${maxSameCountAttempts})`);
            if (sameCountAttempts >= maxSameCountAttempts) {
                console.log('[scraper] Stopping – no more posts loading');
                break;
            }
        } else {
            sameCountAttempts = 0;
        }

        previousCount = currentCount;

        // Scroll to bottom
        console.log('[scraper] Scrolling...');
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await randomDelay(2000, 4000);
        await closePopup(page);
    }

    // Extract data from the first numPosts posts (or all if fewer)
    const posts = await page.$$eval('shreddit-post', (elements, limit) => {
        return elements.slice(0, limit).map(el => {
            // Title
            const titleEl = el.querySelector('a[slot="title"]');
            const title = titleEl ? titleEl.textContent.trim() : 'N/A';

            // Author
            const authorEl = el.querySelector('a[slot="author"]');
            const author = authorEl ? authorEl.textContent.trim() : 'N/A';

            // Score (attribute on shreddit-post)
            const score = el.getAttribute('score') || '0';

            // URL – build absolute
            let url = '#';
            if (titleEl) {
                const href = titleEl.getAttribute('href');
                if (href) {
                    if (href.startsWith('http')) {
                        url = href;
                    } else {
                        url = 'https://www.reddit.com' + href;
                    }
                }
            }

            // Description / body text
            let description = '';
            const bodySlot = el.querySelector('div[slot="text-body"]');
            if (bodySlot) {
                // Try to get paragraphs or just the text
                const paragraphs = bodySlot.querySelectorAll('p');
                if (paragraphs.length) {
                    description = Array.from(paragraphs).map(p => p.textContent.trim()).join('\n');
                } else {
                    description = bodySlot.textContent.trim();
                }
            }

            return { title, author, score, url, description };
        });
    }, numPosts); // pass the limit

    console.log(`[scraper] Extracted ${posts.length} posts`);
    await browser.close();
    return posts;
}

module.exports = { scrapeReddit };