# =============================================================================
# main.py — ExpatScore.de Sniper Coordinator + Page Generator
# Version: 2.3 | Reddit worker disabled (commented), template path fixed
#
# Changes from 2.2:
#   - Commented out reddit_worker.main() call to prevent AttributeError
#   - Template path explicitly set to /templates/blog_template.html
#   - All other SEO logic (155‑char meta, absolute URLs) intact
# =============================================================================

import threading
import logging
import time
import sys
import os
import json
import re
import math
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
# PATHS — HARDCODED template inside /templates folder
# =============================================================================

BASE_DIR      = Path(__file__).parent.resolve()
DOCS_DIR      = BASE_DIR / "docs"
BLOG_DIR      = DOCS_DIR / "blog"
TEMPLATE_FILE = BASE_DIR / "templates" / "blog_template.html"   # ✅ Strict path
DATA_DIR      = BASE_DIR / "data"
BUILT_FILE    = BASE_DIR / "built_pages.json"

# =============================================================================
# PAGE GENERATOR — renders JSON post data into production HTML
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

    # Dates
    post.setdefault('date', date.today().strftime('%B %d, %Y'))
    post['date_iso']          = _to_iso_date(post.get('date_iso', post['date']))
    post['date_modified_iso'] = _to_iso_date(
        post.get('date_modified_iso', post.get('date_modified', post['date_iso']))
    )

    # Reading time + word count
    content = post.get('content_html', post.get('content', ''))
    post.setdefault('read_minutes', _estimate_read_minutes(content))
    post.setdefault('word_count',   _estimate_word_count(content))

    if 'content_html' not in post and 'content' in post:
        post['content_html'] = post['content']

    # Meta description – HARD 155-CHAR LIMIT
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

    # FAQs
    faqs = post.get('faqs', [])
    if isinstance(faqs, list) and all(
        isinstance(f, dict) and 'question' in f and 'answer' in f
        for f in faqs
    ):
        post['faqs'] = faqs
    else:
        post['faqs'] = []

    # Affiliate card validation
    card = post.get('affiliate_card')
    if card and isinstance(card, dict):
        required_keys = {'name', 'category', 'url', 'description'}
        if not required_keys.issubset(card.keys()):
            log.warning(f"  ⚠  affiliate_card for '{post.get('slug')}' missing keys "
                        f"{required_keys - card.keys()} — card suppressed")
            post['affiliate_card'] = None
    else:
        post['affiliate_card'] = None

    # Related slugs
    related = post.get('related_slugs', [])
    if isinstance(related, list) and all(
        isinstance(r, dict) and 'slug' in r and 'title' in r
        for r in related
    ):
        post['related_slugs'] = related
    else:
        post['related_slugs'] = []

    return post

def generate_blog_pages(data_glob: str = "*.json") -> list[str]:
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
# IMPORT WORKERS
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
        # ❌ REDDIT WORKER DISABLED (commented out to prevent AttributeError)
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

def main():
    log.info("=" * 65)
    log.info("🚀 ExpatScore Coordinator v2.3 — Reddit worker disabled")
    log.info("=" * 65)

    log.info("\n📐 Running page generator...")
    newly_built = generate_blog_pages()
    if newly_built:
        regenerate_sitemap()
    else:
        log.info("  ✅ All pages up to date")

    if os.getenv("GENERATOR_ONLY"):
        log.info("✅ GENERATOR_ONLY mode — exiting.")
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

    # Reddit thread is still started but its inner call is commented out
    reddit_thread = make_thread(run_reddit, "RedditWorker")
    reddit_thread.start()
    time.sleep(15)

    youtube_thread = make_thread(run_youtube, "YouTubeWorker")
    youtube_thread.start()

    log.info("✅ YouTube worker only is active. Reddit worker is disabled.")
    log.info("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(300)
            if not reddit_thread.is_alive():
                log.critical("🟠 [Watchdog] Reddit thread dead — RESTARTING (but still disabled)")
                reddit_thread = make_thread(run_reddit, "RedditWorker")
                reddit_thread.start()
            if not youtube_thread.is_alive():
                log.critical("🔴 [Watchdog] YouTube thread dead — RESTARTING")
                youtube_thread = make_thread(run_youtube, "YouTubeWorker")
                youtube_thread.start()
    except KeyboardInterrupt:
        log.info("🔴 Shutting down. Goodbye.")
        sys.exit(0)

if __name__ == "__main__":
    main()