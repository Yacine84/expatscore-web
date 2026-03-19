// run_hunt.js
// This script runs the Reddit scraper on multiple subreddits and prints a summary of posts.

const { scrapeReddit } = require('./redditScraper');

// List of subreddits to scrape
const subreddits = ['germany', 'berlin', 'AskAGerman', 'Munich', 'ExpatFinanceGermany'];
const numPosts = 10; // number of latest posts from each subreddit

(async () => {
  console.log('🚀 Starting Reddit hunt...\n');

  for (const subreddit of subreddits) {
    console.log(`🔍 Scraping r/${subreddit} (latest ${numPosts} posts)...`);

    try {
      const posts = await scrapeReddit(subreddit, numPosts);

      if (!posts || posts.length === 0) {
        console.log(`⚠️  No posts found for r/${subreddit}\n`);
        continue;
      }

      posts.forEach((post, index) => {
        console.log(`\n--- r/${subreddit} - Post #${index + 1} ---`);
        console.log(`Title: ${post.title}`);
        console.log(`URL: ${post.url}`);
        console.log(`Score: ${post.score}`);
      });

      console.log(`\n✅ Finished r/${subreddit} – found ${posts.length} posts.\n`);
    } catch (error) {
      console.error(`❌ Error scraping r/${subreddit}:`, error.message);
      console.log('Continuing to next subreddit...\n');
    }
  }

  console.log('🏁 Hunt completed. Check the output above for posts related to "Schufa" or "Bank".');
})();