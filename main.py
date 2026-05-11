# =============================================================================
# main.py — ExpatScore.de Sniper Coordinator + Page Generator
# Version: 2.8 | AI prompt enforces CSS classes & relative links
# =============================================================================

import threading
import logging
import time
import sys
import os
import json
import re
import math
import argparse
from datetime import datetime, date
from pathlib import Path

# =============================================================================
# LOAD .env FIRST
# =============================================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[Coordinator] ✅ .env loaded")
except ImportError:
    print("[Coordinator] ⚠  python-dotenv not installed — using system env vars")

# =============================================================================
# SHARED LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("expatscorebot.log", encoding="utf-8"),
    ],
)

log = logging.getLogger("Coordinator")

# =============================================================================
# PATHS
# =============================================================================

BASE_DIR      = Path(__file__).parent.resolve()
DOCS_DIR      = BASE_DIR / "docs"
BLOG_DIR      = DOCS_DIR / "blog"
TEMPLATE_FILE = BASE_DIR / "templates" / "blog_template.html"
DATA_DIR      = BASE_DIR / "data"
BUILT_FILE    = BASE_DIR / "built_pages.json"

# =============================================================================
# AI CONTENT GENERATION (Groq / LLaMA 3.3)
# =============================================================================

def _call_groq_for_article(topic: str) -> dict:
    """
    Send a prompt to Groq API to generate a full blog article.
    The prompt enforces:
      - Only HTML tags that match the existing CSS (h2, h3, p, ul, li, etc.)
      - Relative internal links (starting with /)
      - No inline styles, no header/footer duplication
    Returns a dict with keys: content_html, summary, meta_description, keywords.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        log.warning("  ⚠  GROQ_API_KEY not set – cannot generate AI article")
        return None

    try:
        import groq
    except ImportError:
        log.warning("  ⚠  groq library not installed. Run: pip install groq")
        return None

    client = groq.Groq(api_key=api_key)

    # Updated prompt to enforce CSS class compatibility
    prompt = f"""You are a professional financial writer for expats in Germany. Write a detailed, SEO‑optimized blog article about: "{topic}"

CRITICAL REQUIREMENTS:
- Length: 800–1000 words.
- Target audience: English‑speaking expats living in Germany.
- Tone: authoritative, helpful, trustworthy (like a financial advisor).
- Use ONLY the following HTML tags: <h2>, <h3>, <p>, <ul>, <li>, <strong>, <em>, <a>, <blockquote>. Do NOT use inline styles, divs, or custom classes.
- Headings: <h2> for main sections, <h3> for subsections.
- Internal links: use relative paths starting with "/". Example: <a href="/schufa-simulator">Free SCHUFA simulator</a>.
- Do NOT include any header, navigation, footer, or hero section – only the article body content.
- Do NOT include any markdown or code blocks – only pure HTML.

Structure:
- Start with a short introductory paragraph (no heading).
- Then use <h2> for each major point.
- Use <ul> or <li> for lists where appropriate.
- End with a conclusion or call‑to‑action paragraph.

Output format (exactly as shown):
<SUMMARY>One or two sentences summarizing the article.</SUMMARY>
<CONTENT>
Full HTML article content (using only allowed tags, no extra markup).
</CONTENT>
<META>Meta description under 155 characters.</META>
<KEYWORDS>keyword1, keyword2, keyword3, ...</KEYWORDS>
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2500,
        )
        raw = response.choices[0].message.content

        # Parse the response
        summary_match = re.search(r'<SUMMARY>(.*?)</SUMMARY>', raw, re.DOTALL)
        content_match = re.search(r'<CONTENT>(.*?)</CONTENT>', raw, re.DOTALL)
        meta_match = re.search(r'<META>(.*?)</META>', raw, re.DOTALL)
        keywords_match = re.search(r'<KEYWORDS>(.*?)</KEYWORDS>', raw, re.DOTALL)

        summary = summary_match.group(1).strip() if summary_match else f"Complete guide to {topic} for expats in Germany."
        content_html = content_match.group(1).strip() if content_match else f"<p>AI content could not be generated for '{topic}'. Please try again later.</p>"
        meta_description = meta_match.group(1).strip() if meta_match else (summary[:152] + "…" if len(summary) > 155 else summary)
        keywords = keywords_match.group(1).strip() if keywords_match else f"{topic}, expat Germany, guide"

        # Truncate meta description to 155 chars
        if len(meta_description) > 155:
            meta_description = meta_description[:152] + "…"

        return {
            "content_html": content_html,
            "summary": summary,
            "meta_description": meta_description,
            "keywords": keywords,
        }
    except Exception as e:
        log.error(f"  ✖ Groq API error: {e}")
        return None

# =============================================================================
# HELPER FUNCTIONS (estimates, dates, enrichment)
# =============================================================================

def _estimate_read_minutes(html_or_text: str) -> int:
    text = re.sub(r'<[^>]+>', ' ', html_or_text)
    words = len(text.split())
    return max(1, math.ceil(words / 200))

def _estimate_word_count(html_or_text: str) -> int:
    text = re.sub(r'<[^>]+>', ' ', html_or_text)
    return len(text.split())

def _to_iso_date(date_str: str) -> str:
    if not date_str:
        return date.today().isoformat()
    if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return date_str[:10]
    for fmt in ('%B %d, %Y', '%d %B %Y', '%d.%m.%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    log.warning(f"  ⚠  Could not parse date '{date_str}' — using today")
    return date.today().isoformat()

def _enrich_post(post: dict) -> dict:
    """Adds derived SEO fields. Enforces 155‑char limit for meta_description."""
    post = dict(post)

    post.setdefault('date', date.today().strftime('%B %d, %Y'))
    post['date_iso']          = _to_iso_date(post.get('date_iso', post['date']))
    post['date_modified_iso'] = _to_iso_date(
        post.get('date_modified_iso', post.get('date_modified', post['date_iso']))
    )

    content = post.get('content_html', post.get('content', ''))
    post.setdefault('read_minutes', _estimate_read_minutes(content))
    post.setdefault('word_count',   _estimate_word_count(content))

    if 'content_html' not in post and 'content' in post:
        post['content_html'] = post['content']

    if 'meta_description' not in post or not post['meta_description']:
        raw_desc = post.get('summary', '')[:155]
        post['meta_description'] = raw_desc + ('…' if len(raw_desc) == 155 else '')
    else:
        if len(post['meta_description']) > 155:
            post['meta_description'] = post['meta_description'][:152] + '…'

    post.setdefault('keywords', 'expat Germany, SCHUFA, banking, credit score, expat finance')
    post.setdefault('lang', 'en')

    has_affiliate = bool(post.get('affiliate_card')) or \
                    bool(post.get('has_affiliate_links')) or \
                    'affiliate' in content.lower() or \
                    'sponsored' in content.lower()
    post.setdefault('has_affiliate_links', has_affiliate)

    faqs = post.get('faqs', [])
    if isinstance(faqs, list) and all(
        isinstance(f, dict) and 'question' in f and 'answer' in f
        for f in faqs
    ):
        post['faqs'] = faqs
    else:
        post['faqs'] = []

    card = post.get('affiliate_card')
    if card and isinstance(card, dict):
        required_keys = {'name', 'category', 'url', 'description'}
        if not required_keys.issubset(card.keys()):
            log.warning(f"  ⚠  affiliate_card for '{post.get('slug')}' missing keys "
                        f"{required_keys - card.keys()} — card suppressed")
            post['affiliate_card'] = None
    else:
        post['affiliate_card'] = None

    related = post.get('related_slugs', [])
    if isinstance(related, list) and all(
        isinstance(r, dict) and 'slug' in r and 'title' in r
        for r in related
    ):
        post['related_slugs'] = related
    else:
        post['related_slugs'] = []

    return post

# =============================================================================
# PAGE GENERATOR (with AI support for forced topics)
# =============================================================================

def generate_blog_pages(data_glob: str = "*.json", force_topic_title: str = None) -> list[str]:
    """
    Generate blog pages from JSON data.
    If force_topic_title is provided, generate an AI article (bypass JSON).
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        log.critical("❌ jinja2 not installed. Run: pip install jinja2")
        return []

    if not TEMPLATE_FILE.exists():
        log.critical(f"❌ Template not found: {TEMPLATE_FILE}")
        return []

    BLOG_DIR.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_FILE.parent)),
        autoescape=select_autoescape(['html']),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("blog_template.html")

    built = []
    if BUILT_FILE.exists():
        try:
            built = json.loads(BUILT_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            built = []

    newly_built = []

    # ─────────────────────────────────────────────────────────────────────
    # FORCED TOPIC MODE: generate AI article (bypass any existing JSON)
    # ─────────────────────────────────────────────────────────────────────
    if force_topic_title:
        log.info(f"  🔥 Force topic mode: '{force_topic_title}'")
        forced_slug = re.sub(r'[^a-z0-9]+', '-', force_topic_title.lower()).strip('-')

        # Generate AI content
        log.info("  🤖 Requesting AI article from Groq (llama-3.3-70b-versatile) – this may take 10–20 seconds...")
        ai_data = _call_groq_for_article(force_topic_title)
        if ai_data:
            content_html = ai_data["content_html"]
            summary = ai_data["summary"]
            meta_desc = ai_data["meta_description"]
            keywords = ai_data["keywords"]
            log.info("  ✅ AI content received")
        else:
            # Fallback placeholder
            content_html = f"<p>Full article about {force_topic_title} will be generated soon. Check back later.</p>"
            summary = f"Complete guide to {force_topic_title} for expats in Germany."
            meta_desc = summary[:155]
            keywords = f"{force_topic_title}, expat Germany, guide"
            log.warning("  ⚠  Using placeholder content (AI failed)")

        # Build the post dictionary
        post_dict = {
            "slug": forced_slug,
            "title": force_topic_title,
            "summary": summary,
            "content_html": content_html,
            "meta_description": meta_desc,
            "keywords": keywords,
            "category": "Guide",
            "date": date.today().strftime('%B %d, %Y'),
            "date_iso": date.today().isoformat(),
        }

        # Enrich and render
        enriched = _enrich_post(post_dict)
        enriched['slug'] = forced_slug
        out_path = BLOG_DIR / f"{forced_slug}.html"

        try:
            html = template.render(post=enriched, year=datetime.now().year)
            out_path.write_text(html, encoding='utf-8')
            wordcount = enriched.get('word_count', 0)
            log.info(f"  ✅ Built (forced AI): blog/{forced_slug}.html ({wordcount} words)")
            newly_built.append(forced_slug)
        except Exception as e:
            log.error(f"  ✖ Render failed for forced topic: {e}", exc_info=True)
            return []

        # Update registry
        if forced_slug not in built:
            built.append(forced_slug)
        BUILT_FILE.write_text(json.dumps(sorted(built), indent=2, ensure_ascii=False), encoding='utf-8')
        return newly_built

    # ─────────────────────────────────────────────────────────────────────
    # NORMAL MODE (no --topic) – process all JSON files as before
    # ─────────────────────────────────────────────────────────────────────
    data_files = sorted(DATA_DIR.glob(data_glob)) if DATA_DIR.exists() else []
    if not data_files:
        log.warning(f"  ⚠  No JSON data files found in {DATA_DIR}")
        return []

    log.info(f"  📄 Found {len(data_files)} post file(s) in {DATA_DIR}")

    for data_file in data_files:
        if data_file.name.startswith('.'):
            log.info(f"  ⏭  Skipping dot-file: {data_file.name}")
            continue

        try:
            raw_post = json.loads(data_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"  ✖ Failed to read {data_file.name}: {e}")
            continue

        if isinstance(raw_post, list):
            if len(raw_post) == 0:
                log.warning(f"  ⚠  {data_file.name} contains an empty list — skipping")
                continue
            raw_post = raw_post[0]
            log.info(f"  🔄 {data_file.name} was a list — using first element as post")

        if not isinstance(raw_post, dict):
            log.warning(f"  ⚠  {data_file.name} does not contain a valid post object — skipping")
            continue

        slug = raw_post.get('slug') or data_file.stem
        if not slug:
            log.warning(f"  ⚠  No slug in {data_file.name} — skipping")
            continue

        out_path = BLOG_DIR / f"{slug}.html"

        if slug in built and out_path.exists():
            data_mtime = data_file.stat().st_mtime
            out_mtime  = out_path.stat().st_mtime
            if data_mtime <= out_mtime:
                log.info(f"  ⏭  {slug} — up to date, skipping")
                continue

        post = _enrich_post(raw_post)
        post['slug'] = slug

        try:
            html = template.render(post=post, year=datetime.now().year)
            out_path.write_text(html, encoding='utf-8')
            log.info(f"  ✅ Built: blog/{slug}.html "
                     f"({post['word_count']} words · {post['read_minutes']} min read)")
            newly_built.append(slug)
        except Exception as e:
            log.error(f"  ✖ Render failed for {slug}: {e}", exc_info=True)

    all_built = sorted(set(built + newly_built))
    BUILT_FILE.write_text(json.dumps(all_built, indent=2, ensure_ascii=False), encoding='utf-8')
    log.info(f"  📊 Generator summary: {len(newly_built)} built, {len(all_built)} total tracked")
    return newly_built

def regenerate_sitemap(base_url: str = "https://expatscore.de") -> None:
    sitemap_path = DOCS_DIR / "sitemap.xml"
    today = date.today().isoformat()

    PRIORITIES = {
        '':                  ('1.0', 'weekly'),
        'schufa-simulator':  ('0.9', 'weekly'),
        'schufa-guide':      ('0.85', 'monthly'),
        'banking':           ('0.8', 'weekly'),
        'insurance':         ('0.8', 'weekly'),
        'blue-card-tool':    ('0.9', 'weekly'),
        'blog/':             ('0.7', 'weekly'),
    }

    urls = []
    for html_file in sorted(DOCS_DIR.rglob('*.html')):
        rel = html_file.relative_to(DOCS_DIR)
        parts = list(rel.parts)
        if parts[-1] == 'index.html':
            parts[-1] = ''
        else:
            parts[-1] = parts[-1].replace('.html', '')
        url_path = '/'.join(parts).strip('/')

        skip_patterns = ['impressum', 'datenschutz', 'affiliate-hinweis', '404']
        if any(p in url_path for p in skip_patterns):
            priority, changefreq = '0.3', 'yearly'
        elif url_path.startswith('blog/') and url_path != 'blog/':
            priority, changefreq = '0.6', 'monthly'
        else:
            priority, changefreq = PRIORITIES.get(url_path, ('0.6', 'monthly'))

        full_url = f"{base_url}/{url_path}" if url_path else base_url + '/'
        urls.append((full_url, today, changefreq, priority))

    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for full_url, lastmod, changefreq, priority in urls:
        lines += [
            '  <url>',
            f'    <loc>{full_url}</loc>',
            f'    <lastmod>{lastmod}</lastmod>',
            f'    <changefreq>{changefreq}</changefreq>',
            f'    <priority>{priority}</priority>',
            '  </url>',
        ]
    lines.append('</urlset>')

    sitemap_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    log.info(f"  🗺  Sitemap regenerated: {len(urls)} URLs → {sitemap_path}")

# =============================================================================
# WORKER IMPORTS
# =============================================================================

try:
    import reddit_worker
    import youtube_worker
    WORKERS_AVAILABLE = True
except ImportError as e:
    log.warning(f"⚠  Worker import failed ({e}) — sniper mode unavailable")
    WORKERS_AVAILABLE = False

def make_thread(target_fn, name: str) -> threading.Thread:
    return threading.Thread(target=target_fn, name=name, daemon=True)

def run_reddit():
    log.info("🟠 [Reddit Worker] Thread started.")
    try:
        # REDDIT WORKER DISABLED
        # reddit_worker.main()
        log.info("🟠 [Reddit Worker] Skipped (disabled in configuration).")
    except Exception as e:
        log.critical(f"💥 [Reddit Worker] Fatal crash: {e}", exc_info=True)

def run_youtube():
    log.info("🔴 [YouTube Worker] Thread started.")
    try:
        youtube_worker.main()
    except Exception as e:
        log.critical(f"💥 [YouTube Worker] Fatal crash: {e}", exc_info=True)

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="ExpatScore Coordinator")
    parser.add_argument("--generator-only", action="store_true",
                        help="Only generate pages, then exit (no workers)")
    parser.add_argument("--topic", type=str,
                        help="Force generate a full AI article for this topic (ignores JSON)")
    args = parser.parse_args()

    log.info("=" * 65)
    log.info("🚀 ExpatScore Coordinator v2.8 — AI prompt ensures CSS compatibility")
    log.info("=" * 65)

    log.info("\n📐 Running page generator...")
    newly_built = generate_blog_pages(force_topic_title=args.topic)

    if newly_built:
        regenerate_sitemap()
    else:
        log.info("  ✅ No new pages built (no force topic and no changed JSON).")

    if args.generator_only:
        log.info("✅ --generator-only mode — exiting.")
        sys.exit(0)

    if not WORKERS_AVAILABLE:
        log.warning("⚠  Worker modules not available — sniper mode disabled.")
        sys.exit(0)

    missing_critical = []
    if not os.getenv("N8N_WEBHOOK_URL"):
        missing_critical.append("N8N_WEBHOOK_URL")
    if not os.getenv("YOUTUBE_API_KEY"):
        missing_critical.append("YOUTUBE_API_KEY")
    if missing_critical:
        log.critical(f"🚫 Missing required .env variables: {missing_critical}")
        sys.exit(1)

    youtube_enabled = os.getenv("YOUTUBE_WORKER_ENABLED", "true").lower() == "true"

    reddit_thread = make_thread(run_reddit, "RedditWorker")
    reddit_thread.start()
    log.info("🟠 Reddit worker thread started (disabled internally).")

    time.sleep(15)

    if youtube_enabled:
        youtube_thread = make_thread(run_youtube, "YouTubeWorker")
        youtube_thread.start()
        log.info("🔴 YouTube worker started.")
    else:
        log.info("🔴 YouTube worker disabled by YOUTUBE_WORKER_ENABLED=false")
        youtube_thread = None

    log.info("✅ Workers initialised. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(300)
            if not reddit_thread.is_alive():
                log.critical("🟠 [Watchdog] Reddit thread dead — RESTARTING")
                reddit_thread = make_thread(run_reddit, "RedditWorker")
                reddit_thread.start()
            if youtube_enabled and (youtube_thread is None or not youtube_thread.is_alive()):
                log.critical("🔴 [Watchdog] YouTube thread dead — RESTARTING")
                youtube_thread = make_thread(run_youtube, "YouTubeWorker")
                youtube_thread.start()
    except KeyboardInterrupt:
        log.info("🔴 Shutting down. Goodbye.")
        sys.exit(0)

if __name__ == "__main__":
    main()