// server.js – Reddit Lead Hunter & Marketing Dashboard for ExpatScore.de
// Full version with authentic expat persona & 3‑stage funnel (Warm → Soft → Direct)
// Run: npm install express axios groq-sdk && node server.js

const express = require('express');
const axios = require('axios');
const Groq = require('groq-sdk');

// ==================== CONFIGURATION ====================
const GROQ_API_KEY = process.env.GROQ_API_KEY;
const groq = new Groq({ apiKey: GROQ_API_KEY });

const app = express();
app.use(express.urlencoded({ extended: true }));

// In‑memory store for the latest hunt results
let lastHuntData = null;

// ==================== HELPER FUNCTIONS ====================

/**
 * Fetch posts from a given subreddit
 */
async function scrapeReddit(subreddit, limit = 10) {
  try {
    const url = `https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}`;
    const { data } = await axios.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; ExpatBot/1.0)' }
    });
    return data.data.children.map(child => {
      const d = child.data;
      return {
        id: d.id,
        title: d.title,
        content: d.selftext || d.title,
        author: d.author,
        score: d.score,
        url: `https://reddit.com${d.permalink}`,
        created: d.created_utc
      };
    });
  } catch (err) {
    console.error('Reddit scrape error:', err.message);
    return [];
  }
}

/**
 * Generate three drafts for a single post using Groq
 * Returns { draft1, draft2, draft3 }
 */
async function generateDraftsForPost(post) {
  const systemPrompt = `You are a helpful, slightly tired expat who moved to Germany in 2021 with €800 and a dream. You write casual, empathetic Reddit replies that feel completely human. 

Style rules:
- Use mostly lowercase (low-caps) – it should read like a quick chat message.
- Use ellipses ... for hesitation.
- Mix in German words naturally: Termin, Mietvertrag, Bürgeramt, Schufa, Anmeldung, etc.
- Use phrases like "oof", "yikes", "this ^" to react.
- Use "i learned this the hard way..." to introduce advice.
- Never use bullet points or robotic lists.
- Be warm, relatable, and authentic.`;

  const userPrompt = `Here is a Reddit post:
Title: ${post.title}
Content: ${post.content}

Write three different reply drafts, each with a specific tone and goal:

Draft 1 (WARM – pure empathy + advice):
- No links, no website name.
- React with something like "oof", "yikes", or "this ^".
- Focus on shared struggle (e.g., "the Anmeldung nightmare").
- Give helpful advice from experience.
- Start with something like "i learned this the hard way..." when giving advice.

Draft 2 (SOFT PITCH – mention the concept of your tool):
- DO NOT include any URL or direct link.
- Mention you made something to help (e.g., "i actually made a little schufa simulator because i was tired of explaining this...").
- Tell them to "dm me" or "check my profile" if they want to see it.
- Keep it casual, no hard sell.

Draft 3 (DIRECT – include the link naturally):
- Include the full link https://expatscore.de.
- Frame it as a personal side‑project built out of frustration.
- The link should feel like a natural part of the advice.

Return a JSON object with keys "draft1", "draft2", "draft3". Each draft must be a single string (no extra keys).`;

  try {
    const completion = await groq.chat.completions.create({
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userPrompt }
      ],
      model: 'llama-3.3-70b-versatile',
      temperature: 0.7,
      response_format: { type: 'json_object' }
    });

    const content = completion.choices[0]?.message?.content;
    if (!content) throw new Error('Empty response');
    const parsed = JSON.parse(content);
    return {
      draft1: parsed.draft1 || 'Draft 1 not available',
      draft2: parsed.draft2 || 'Draft 2 not available',
      draft3: parsed.draft3 || 'Draft 3 not available'
    };
  } catch (err) {
    console.error('Groq generation error:', err.message);
    return {
      draft1: 'Sorry, AI draft could not be generated.',
      draft2: 'Sorry, AI draft could not be generated.',
      draft3: 'Sorry, AI draft could not be generated.'
    };
  }
}

/**
 * Process a hunt: scrape and generate drafts for all posts
 */
async function runHunt(subreddit = 'germany', num = 5) {
  const posts = await scrapeReddit(subreddit, num);
  const results = [];
  for (const post of posts) {
    const drafts = await generateDraftsForPost(post);
    results.push({ ...post, ...drafts });
    // small delay to avoid flooding the API
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  return results;
}

// ==================== ROUTES ====================

// Home – redirect to hunt
app.get('/', (req, res) => {
  res.redirect('/hunt');
});

// Scrape and generate, then redirect to /hunt
app.get('/hunt-scrape', async (req, res) => {
  const subreddit = req.query.subreddit || 'germany';
  const num = parseInt(req.query.num) || 5;
  try {
    lastHuntData = await runHunt(subreddit, num);
    res.redirect('/hunt');
  } catch (err) {
    console.error('Hunt failed:', err);
    lastHuntData = null;
    res.redirect('/hunt?error=1');
  }
});

// Display the dashboard
app.get('/hunt', (req, res) => {
  const data = lastHuntData || [];
  const error = req.query.error ? 'Scraping failed. Please try again.' : '';

  // Embedded HTML with dark & gold theme
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ExpatScore · Reddit Lead Hunter</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    body { background: #0a0a0a; color: #e0e0e0; padding: 2rem; line-height: 1.6; }
    .container { max-width: 1600px; margin: 0 auto; }
    h1 { font-size: 2.5rem; font-weight: 600; margin-bottom: 0.5rem; background: linear-gradient(135deg, #f5e7b2 0%, #d4af37 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .subhead { color: #888; margin-bottom: 2rem; border-left: 4px solid #d4af37; padding-left: 1rem; }
    .error { background: #2a1a1a; border: 1px solid #b33; color: #f99; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1.5rem; }
    .search-form { background: #1a1a1a; padding: 1.5rem; border-radius: 1rem; margin-bottom: 2rem; border: 1px solid #333; display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end; }
    .form-group { display: flex; flex-direction: column; }
    .form-group label { font-size: 0.9rem; color: #d4af37; margin-bottom: 0.3rem; font-weight: 500; }
    .form-group input { background: #2a2a2a; border: 1px solid #444; color: #fff; padding: 0.6rem 1rem; border-radius: 0.5rem; font-size: 1rem; width: 200px; }
    .form-group input:focus { outline: none; border-color: #d4af37; }
    button { background: #d4af37; color: #0a0a0a; border: none; padding: 0.8rem 2rem; border-radius: 2rem; font-weight: 600; font-size: 1rem; cursor: pointer; transition: all 0.2s; border: 1px solid #d4af37; }
    button:hover { background: transparent; color: #d4af37; }
    .stats { color: #aaa; margin-bottom: 1rem; font-size: 0.95rem; }
    .stats span { color: #d4af37; font-weight: 600; }
    .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr)); gap: 1.8rem; }
    .card { background: #121212; border: 1px solid #2a2a2a; border-radius: 1.5rem; padding: 1.5rem; transition: border 0.2s; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
    .card:hover { border-color: #d4af37; }
    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; gap: 0.5rem; }
    .card-title { font-size: 1.3rem; font-weight: 600; }
    .card-title a { color: #fff; text-decoration: none; }
    .card-title a:hover { text-decoration: underline; color: #d4af37; }
    .card-meta { display: flex; gap: 1rem; color: #aaa; font-size: 0.9rem; }
    .card-meta .author { color: #d4af37; }
    .draft-row { margin-top: 1.2rem; border-top: 1px dashed #333; padding-top: 1.2rem; }
    .draft-label { font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px; color: #d4af37; margin-bottom: 0.4rem; font-weight: 500; }
    .draft-box { background: #1e1e1e; border: 1px solid #333; border-radius: 0.8rem; padding: 0.8rem; margin-bottom: 1rem; position: relative; }
    .draft-box textarea { width: 100%; background: transparent; border: none; color: #ddd; font-size: 0.95rem; resize: vertical; min-height: 100px; font-family: inherit; padding: 0; }
    .draft-box textarea:focus { outline: none; }
    .copy-btn { position: absolute; bottom: 0.8rem; right: 0.8rem; background: #2a2a2a; border: 1px solid #444; color: #d4af37; padding: 0.3rem 1rem; border-radius: 2rem; font-size: 0.8rem; cursor: pointer; transition: 0.2s; }
    .copy-btn:hover { background: #d4af37; color: #0a0a0a; border-color: #d4af37; }
    .footer { text-align: center; margin-top: 3rem; color: #666; }
  </style>
</head>
<body>
  <div class="container">
    <h1>⚡ ExpatScore · Lead Hunter</h1>
    <div class="subhead">Find expat pain points on Reddit & generate warm, soft & direct replies</div>

    ${error ? `<div class="error">⚠️ ${error}</div>` : ''}

    <div class="search-form">
      <div class="form-group">
        <label>Subreddit</label>
        <input type="text" id="subreddit" placeholder="e.g. germany" value="germany">
      </div>
      <div class="form-group">
        <label>Posts to fetch</label>
        <input type="number" id="num" min="1" max="20" value="5">
      </div>
      <button onclick="runHunt()">🚀 Hunt leads</button>
    </div>

    <div class="stats">
      <span>${data.length}</span> posts analyzed
    </div>

    <div class="card-grid" id="cardGrid">
      ${data.map(post => `
        <div class="card">
          <div class="card-header">
            <div class="card-title"><a href="${post.url}" target="_blank">${escapeHtml(post.title)}</a></div>
            <div class="card-meta">
              <span class="author">u/${escapeHtml(post.author)}</span>
              <span>⬆️ ${post.score}</span>
            </div>
          </div>
          <div class="draft-row">
            <div class="draft-label">WARM (empathy + advice)</div>
            <div class="draft-box">
              <textarea id="d1-${post.id}" readonly>${escapeHtml(post.draft1)}</textarea>
              <button class="copy-btn" onclick="copyText('d1-${post.id}')">Copy</button>
            </div>
          </div>
          <div class="draft-row">
            <div class="draft-label">SOFT PITCH (dm me / check profile)</div>
            <div class="draft-box">
              <textarea id="d2-${post.id}" readonly>${escapeHtml(post.draft2)}</textarea>
              <button class="copy-btn" onclick="copyText('d2-${post.id}')">Copy</button>
            </div>
          </div>
          <div class="draft-row">
            <div class="draft-label">DIRECT (with link)</div>
            <div class="draft-box">
              <textarea id="d3-${post.id}" readonly>${escapeHtml(post.draft3)}</textarea>
              <button class="copy-btn" onclick="copyText('d3-${post.id}')">Copy</button>
            </div>
          </div>
        </div>
      `).join('')}
    </div>

    ${data.length === 0 ? `
      <div style="text-align:center; margin: 5rem 0; color:#666;">
        No data yet. Use the form above to start hunting.
      </div>
    ` : ''}

    <div class="footer">
      ExpatScore.de — smart leads for the German expat market
    </div>
  </div>

  <script>
    function runHunt() {
      const sub = document.getElementById('subreddit').value;
      const num = document.getElementById('num').value;
      window.location.href = '/hunt-scrape?subreddit=' + encodeURIComponent(sub) + '&num=' + encodeURIComponent(num);
    }

    function copyText(elementId) {
      const textarea = document.getElementById(elementId);
      textarea.select();
      textarea.setSelectionRange(0, 99999);
      navigator.clipboard.writeText(textarea.value).then(() => {
        const btn = event.target;
        const original = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = original, 1500);
      }).catch(err => {
        alert('Copy failed: ' + err);
      });
    }
  </script>
</body>
</html>`;

  res.send(html);
});

// Simple HTML escape to prevent XSS
function escapeHtml(unsafe) {
  if (!unsafe) return '';
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ==================== START SERVER ====================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`✅ ExpatScore Lead Hunter running on http://localhost:${PORT}`);
});