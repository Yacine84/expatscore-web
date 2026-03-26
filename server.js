// server.js — ExpatScore Lead Hunter & Signal Dashboard
// Run: npm install express axios groq-sdk && node server.js

const express = require('express');
const axios   = require('axios');
const { Groq } = require('groq-sdk');

const app  = express();
const port = 3000;

let lastHuntData = null;
const groq = new Groq(); // reads GROQ_API_KEY from env

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ─── Reddit scraper ────────────────────────────────────────────────────────

async function scrapeReddit(subreddit, limit = 10) {
  const url = 'https://www.reddit.com/r/' + subreddit + '/hot.json?limit=' + limit;
  try {
    const { data } = await axios.get(url, {
      headers: { 'User-Agent': 'ExpatScore/1.0 (content-research-bot)' }
    });
    return data.data.children.map(child => {
      const d = child.data;
      return {
        id:        d.id,
        title:     d.title,
        body:      d.selftext || '',
        subreddit: d.subreddit,
        author:    d.author,
        upvotes:   d.score,
        url:       'https://reddit.com' + d.permalink,
        created:   d.created_utc
      };
    });
  } catch (err) {
    console.error('Reddit scrape error:', err.message);
    return [];
  }
}

// ─── Groq analysis ─────────────────────────────────────────────────────────
// Returns structured JSON: seo_blueprint + video_hook for each post.
// NOTE: Draft generation for *manual* posting is kept as a separate
//       on-demand endpoint (/api/generate-draft) — not automated.

async function analysePost(post) {
  const userPrompt = [
    'You are a growth analyst for ExpatScore.de — a tool helping expats in Germany',
    'navigate SCHUFA, banking, tax, and bureaucracy.',
    '',
    'Analyse this Reddit post and return ONLY a valid JSON object, no markdown fences.',
    '',
    'POST TITLE: ' + post.title,
    'POST BODY: ' + (post.body || '').substring(0, 600),
    'SUBREDDIT: ' + post.subreddit,
    '',
    'Return exactly this shape:',
    '{',
    '  "seo_blueprint": {',
    '    "title": "<SEO article title, 50-60 chars>",',
    '    "slug": "<url-friendly-slug>",',
    '    "meta_description": "<155 char meta description>",',
    '    "primary_keyword": "<main long-tail keyword>",',
    '    "secondary_keywords": ["<kw2>", "<kw3>", "<kw4>"],',
    '    "h2_headers": ["<H2 one>", "<H2 two>", "<H2 three>", "<H2 four>"]',
    '  },',
    '  "video_hook": "<one punchy TikTok/Reels opening line, under 15 words>",',
    '  "pain_summary": "<one sentence describing the core expat pain point>",',
    '  "partner_category": "<neobank|tax_advisor|relocation|insurance|language_school|none>"',
    '}'
  ].join('\n');

  try {
    const completion = await groq.chat.completions.create({
      messages: [{ role: 'user', content: userPrompt }],
      model: 'llama-3.3-70b-versatile',
      temperature: 0.4,
      response_format: { type: 'json_object' }
    });
    const content = completion.choices[0]?.message?.content || '{}';
    return JSON.parse(content);
  } catch (err) {
    console.error('Groq analysis error for post', post.id, ':', err.message);
    return null;
  }
}

// ─── Hunt runner ───────────────────────────────────────────────────────────

async function runHunt(subreddit, limit) {
  const posts   = await scrapeReddit(subreddit, limit);
  const results = [];

  for (const post of posts) {
    console.log('  Analysing:', post.title.substring(0, 60));
    const analysis = await analysePost(post);
    results.push({ ...post, analysis: analysis || {} });
    await new Promise(r => setTimeout(r, 400)); // rate-limit Groq
  }

  return results;
}

// ─── Routes ────────────────────────────────────────────────────────────────

// Dashboard (pure HTML string concatenation — no nested backticks)
app.get('/hunt', (req, res) => {
  const rows = (lastHuntData || []).map(post => {
    const seo  = post.analysis?.seo_blueprint || {};
    const hook = post.analysis?.video_hook    || '—';
    const pain = post.analysis?.pain_summary  || '—';
    return '<tr>'
      + '<td><a href="' + post.url + '" target="_blank">' + escHtml(post.title) + '</a></td>'
      + '<td>' + post.upvotes + '</td>'
      + '<td>' + escHtml(seo.primary_keyword || '—') + '</td>'
      + '<td>' + escHtml(hook) + '</td>'
      + '<td>' + escHtml(pain) + '</td>'
      + '</tr>';
  }).join('');

  const html = '<!DOCTYPE html><html lang="en"><head>'
    + '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    + '<title>ExpatScore Lead Hunter</title>'
    + '<style>'
    + 'body{background:#0a0a0a;color:#e0e0e0;font-family:system-ui,sans-serif;padding:2rem}'
    + 'h1{color:#d4af37}form{margin:1.5rem 0;display:flex;gap:1rem;flex-wrap:wrap;align-items:flex-end}'
    + 'label{display:block;font-size:.85rem;color:#d4af37;margin-bottom:.3rem}'
    + 'input{background:#1e1e1e;border:1px solid #444;color:#fff;padding:.5rem .75rem;border-radius:6px}'
    + 'button{background:#d4af37;color:#0a0a0a;border:none;padding:.6rem 1.4rem;border-radius:6px;font-weight:600;cursor:pointer}'
    + 'table{width:100%;border-collapse:collapse;margin-top:1.5rem}'
    + 'th{background:#1a1a1a;color:#d4af37;padding:.6rem;text-align:left;font-size:.8rem;text-transform:uppercase}'
    + 'td{padding:.6rem;border-bottom:1px solid #222;font-size:.85rem;vertical-align:top}'
    + 'td a{color:#d4af37;text-decoration:none}'
    + '.empty{color:#666;margin:3rem 0;text-align:center}'
    + '</style>'
    + '</head><body>'
    + '<h1>ExpatScore Lead Hunter</h1>'
    + '<form action="/hunt-scrape" method="get">'
    + '<div><label>Subreddit</label><input name="subreddit" value="germany" placeholder="germany"></div>'
    + '<div><label>Posts</label><input name="num" type="number" value="10" min="1" max="25" style="width:80px"></div>'
    + '<button type="submit">Hunt</button>'
    + '</form>'
    + (lastHuntData
      ? '<p style="color:#888">' + lastHuntData.length + ' posts loaded — '
        + '<a href="/hunt/json" style="color:#d4af37">view raw JSON</a></p>'
        + '<table><thead><tr><th>Title</th><th>Upvotes</th><th>Primary keyword</th>'
        + '<th>Video hook</th><th>Pain summary</th></tr></thead><tbody>'
        + rows + '</tbody></table>'
      : '<div class="empty">No data yet. Click Hunt to start.</div>')
    + '</body></html>';

  res.send(html);
});

// Trigger scrape + analysis, then redirect to dashboard
app.get('/hunt-scrape', async (req, res) => {
  const subreddit = req.query.subreddit || 'germany';
  const limit     = Math.min(parseInt(req.query.num) || 10, 25);
  console.log('Starting hunt: r/' + subreddit + ' (' + limit + ' posts)');
  try {
    lastHuntData = await runHunt(subreddit, limit);
    console.log('Hunt complete:', lastHuntData.length, 'posts');
    res.redirect('/hunt');
  } catch (err) {
    console.error('Hunt failed:', err.message);
    res.status(500).send('Hunt failed: ' + err.message);
  }
});

// JSON endpoint for signal_engine.py
app.get('/hunt/json', (req, res) => {
  if (!lastHuntData) {
    return res.status(404).json({
      error: 'No hunt data yet. Visit /hunt-scrape?subreddit=germany&num=10 first.'
    });
  }
  res.json(lastHuntData);
});

// On-demand draft endpoint for MANUAL use only (human copies & posts)
app.post('/api/generate-draft', async (req, res) => {
  const { title, body } = req.body;
  if (!title) return res.status(400).json({ error: 'title required' });

  const prompt = 'You are a tired but helpful expat who moved to Germany in 2021.'
    + ' Write a casual, empathetic Reddit reply (no bullet points, no AI vibes) to this post.\n\n'
    + 'Title: ' + title + '\nContent: ' + (body || '').substring(0, 600);

  try {
    const completion = await groq.chat.completions.create({
      messages: [{ role: 'user', content: prompt }],
      model: 'llama-3.3-70b-versatile',
      temperature: 0.75,
      max_tokens: 300
    });
    res.json({ draft: completion.choices[0]?.message?.content || '' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ─── Helpers ───────────────────────────────────────────────────────────────

function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─── Start ─────────────────────────────────────────────────────────────────

app.listen(port, () => {
  console.log('ExpatScore Lead Hunter running at http://localhost:' + port);
  console.log('  Dashboard : http://localhost:' + port + '/hunt');
  console.log('  JSON API  : http://localhost:' + port + '/hunt/json');
});