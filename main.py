# =============================================================================
# main.py — ExpatScore.de Sniper Coordinator + Page Generator
# Version: 3.0 | --force rebuild · Full CSV alignment · Zero-Slash Policy
# =============================================================================
#
# WHAT'S NEW IN v3.0
# ──────────────────
# 1. --force flag
#       python3 main.py --force
#    Bypasses ALL caching:
#      • Ignores built_pages.json (the slug registry)
#      • Ignores .html file mtimes (no "up to date" skipping)
#      • Deletes and rewrites every programmatic page in docs/
#    --force is safe to combine with --generator-only and --topic.
#
# 2. Complete CSV alignment
#    data/providers.csv is the single source of truth for every company button:
#      • _load_providers_csv()      reads the full dataset once per run
#      • _build_provider_url_map()  builds {slug → url} for O(1) lookup
#      • _inject_provider_urls()    patches href="#"/href="" before rendering
#    The providers list and map are also passed to the Jinja2 template context
#    so templates can look up URLs with {{ providers_map[item.slug] }}.
#    Every external link is post-processed by _fix_external_links() to carry
#    target="_blank" rel="nofollow", and _fix_internal_links() enforces the
#    Zero-Slash Policy (no leading "/" on internal hrefs).
#
# 3. Sitemap safety
#    regenerate_sitemap() filters out non-HTML file types and system/cache
#    files (.dedup_registry, .session_state, etc.) from the filesystem scan.
#    The CSV pass skips rows that lack a valid slug or category.
#
# ARGUMENT REFERENCE
# ──────────────────
#   --generator-only   Build pages then exit  (no workers)
#   --force            Bypass all caches, rebuild every page from CSV
#   --topic TITLE      Force-generate one AI article for TITLE (bypass JSON)
# =============================================================================

import csv
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
CSV_FILE      = DATA_DIR / "providers.csv"   # ← single source of truth for provider URLs
BUILT_FILE    = BASE_DIR / "built_pages.json"

# Domain used to distinguish internal vs external links during post-processing.
_SITE_DOMAIN = "expatscore.de"

# =============================================================================
# PROVIDER CSV — load · map · inject
# =============================================================================
#
# Expected CSV columns (header row required; column order does not matter):
#
#   name       Display name of the provider       e.g.  "N26"
#   slug       URL-safe identifier                e.g.  "n26"
#   url        Real outbound destination URL      e.g.  "https://n26.com/r/..."
#   category   Routing bucket for URL structure   e.g.  "banking" | "insurance"
#
# Any additional columns are forwarded unchanged to the Jinja2 template so you
# can add rating, description, badge, etc. without touching this file.
#
# The slug column is the universal join key used everywhere below.
# =============================================================================

def _load_providers_csv() -> list[dict]:
    """
    Read data/providers.csv and return every row as a dict.

    Skips rows where both slug and url are empty strings (blank trailer rows).
    Returns an empty list with a warning when the file is missing or unreadable
    so the rest of the pipeline degrades gracefully rather than crashing.
    """
    if not CSV_FILE.exists():
        log.warning(
            f"  ⚠  Providers CSV not found: {CSV_FILE}\n"
            f"     Company buttons will keep whatever URL is already in the JSON data."
        )
        return []
    try:
        with CSV_FILE.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = [
                r for r in reader
                if r.get("slug", "").strip() or r.get("url", "").strip()
            ]
        log.info(f"  📋 Loaded {len(rows)} provider row(s) from {CSV_FILE.name}")
        return rows
    except Exception as exc:
        log.error(f"  ✖ Failed to read providers CSV: {exc}")
        return []


def _build_provider_url_map(providers: list[dict]) -> dict[str, str]:
    """
    Return {slug: url} from the loaded provider rows.
    Rows with an empty slug or url are silently skipped.
    """
    return {
        p["slug"].strip(): p["url"].strip()
        for p in providers
        if p.get("slug", "").strip() and p.get("url", "").strip()
    }


def _inject_provider_urls(raw_post: dict, url_map: dict[str, str]) -> dict:
    """
    Patch placeholder destination URLs before a post is enriched and rendered.

    Targets two locations inside raw_post:
      • raw_post["providers"]      — list of company/button objects
      • raw_post["affiliate_card"] — single CTA card dict

    An entry is patched when its url field equals "#", "" or "placeholder".
    The real URL is looked up from url_map by the entry's slug field.

    Returns a *shallow copy* of raw_post — the original dict is never mutated.
    """
    if not url_map:
        return raw_post

    post = dict(raw_post)

    # ── Patch providers list ──────────────────────────────────────────────
    if isinstance(post.get("providers"), list):
        patched = []
        for item in post["providers"]:
            item        = dict(item)
            slug        = item.get("slug", "").strip()
            current_url = item.get("url", "#").strip()
            if current_url in ("#", "", "placeholder") and slug in url_map:
                item["url"] = url_map[slug]
                log.debug(f"    🔗 Injected URL for provider '{slug}'")
            patched.append(item)
        post["providers"] = patched

    # ── Patch affiliate_card CTA url ──────────────────────────────────────
    card = post.get("affiliate_card")
    if isinstance(card, dict):
        card        = dict(card)
        slug        = card.get("slug", "").strip()
        current_url = card.get("url", "#").strip()
        if current_url in ("#", "", "placeholder") and slug in url_map:
            card["url"] = url_map[slug]
            log.debug(f"    🔗 Injected URL for affiliate_card '{slug}'")
        post["affiliate_card"] = card

    return post


# =============================================================================
# HTML POST-PROCESSING — SEO external attrs · Zero-Slash internal links
# =============================================================================

def _fix_external_links(html: str) -> str:
    """
    SEO hardening pass — runs on every rendered HTML page.

    Every <a> tag whose href points outside _SITE_DOMAIN is rewritten to carry:
        target="_blank" rel="nofollow"

    Any pre-existing target or rel attributes are stripped first so the output
    never contains duplicates or conflicting values, regardless of what the
    Jinja2 template or the AI model emitted.

    Patterns left completely untouched:
      - Same-domain absolute URLs    https://expatscore.de/...
      - Relative internal paths      blog/slug, schufa-guide, …
      - Anchor-only hrefs            #section
      - Non-http protocols           mailto:  tel:  data:
    """
    def _patch(m: re.Match) -> str:
        original = m.group(0)
        href_m   = re.search(r'\bhref=(["\'])([^"\']*)\1', original, re.I)
        if not href_m:
            return original
        href = href_m.group(2).strip()
        if not re.match(r'^https?://', href, re.I):
            return original
        if _SITE_DOMAIN in href:
            return original  # same-domain absolute URL — leave alone
        # Strip stale target / rel
        patched = re.sub(r'\s+target=(["\'])[^"\']*\1', "", original, flags=re.I)
        patched = re.sub(r'\s+rel=(["\'])[^"\']*\1',    "", patched,  flags=re.I)
        # Re-attach as the final attributes before the closing >
        if patched.endswith("/>"):
            patched = patched[:-2].rstrip() + ' target="_blank" rel="nofollow" />'
        else:
            patched = patched[:-1].rstrip() + ' target="_blank" rel="nofollow">'
        return patched

    return re.sub(r"<a\b[^>]*>", _patch, html, flags=re.I)


def _fix_internal_links(html: str) -> str:
    """
    Zero-Slash Policy pass — runs on every rendered HTML page.

    Strips the leading "/" from every internal href value so paths are
    always pure-relative (e.g. "blog/slug" never "/blog/slug").
    This prevents incorrect redirections under Vercel / Cloudflare cleanUrls.

    Skipped patterns (left untouched):
        https?://   external URLs handled by _fix_external_links
        //          protocol-relative URLs
        #           in-page anchors
        mailto:     e-mail links
        tel:        phone links
        data:       data URIs
    """
    result, cursor = [], 0
    for m in re.finditer(r'\bhref=(["\'])([^"\']*)\1', html, re.I):
        quote = m.group(1)
        href  = m.group(2)
        result.append(html[cursor : m.start()])
        if re.match(r'^(https?://|//|#|mailto:|tel:|data:)', href, re.I):
            result.append(m.group(0))                        # external / special
        elif href.startswith("/"):
            result.append(f"href={quote}{href[1:]}{quote}")  # strip leading /
        else:
            result.append(m.group(0))                        # already relative
        cursor = m.end()
    result.append(html[cursor:])
    return "".join(result)


# =============================================================================
# AI CONTENT GENERATION (Groq / LLaMA 3.3)
# =============================================================================

def _call_groq_for_article(topic: str) -> dict | None:
    """
    Request a full blog article from the Groq API.

    The prompt enforces:
      • Only CSS-compatible HTML tags (h2, h3, p, ul, li, …)
      • Internal links without a leading slash  (Zero-Slash Policy)
      • External links with target="_blank" rel="nofollow"
      • No inline styles, no header/footer markup

    Returns a dict with keys: content_html, summary, meta_description, keywords,
    or None if the API call fails or the key is missing.
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

    prompt = f"""You are a professional financial writer for expats in Germany. \
Write a detailed, SEO-optimised blog article about: "{topic}"

CRITICAL REQUIREMENTS:
- Length: 800-1000 words.
- Target audience: English-speaking expats living in Germany.
- Tone: authoritative, helpful, trustworthy (like a financial advisor).
- Use ONLY these HTML tags: <h2> <h3> <p> <ul> <li> <strong> <em> <a> <blockquote>.
  Do NOT use inline styles, divs, spans, or custom classes.
- Headings: <h2> for main sections, <h3> for subsections.
- Internal links: MUST use relative paths WITHOUT a leading slash.
  Correct:   <a href="schufa-simulator">Free SCHUFA simulator</a>
  WRONG:     <a href="/schufa-simulator">...</a>   ← leading slash BREAKS routing.
- External links: MUST always include target="_blank" rel="nofollow".
  Example:   <a href="https://example.com" target="_blank" rel="nofollow">Text</a>
- Do NOT include any header, navigation, footer, or hero section — body content only.
- Do NOT output markdown or code fences — pure HTML only.

Structure:
- Short intro paragraph (no heading).
- <h2> for each major section.
- <ul>/<li> for lists where suitable.
- Concluding paragraph with a call to action.

Output exactly in this format (no text outside the tags):
<SUMMARY>One or two sentences summarising the article.</SUMMARY>
<CONTENT>
Full HTML article body (allowed tags only, no extra markup).
</CONTENT>
<META>Meta description, max 155 characters.</META>
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

        summary_m  = re.search(r'<SUMMARY>(.*?)</SUMMARY>',   raw, re.DOTALL)
        content_m  = re.search(r'<CONTENT>(.*?)</CONTENT>',   raw, re.DOTALL)
        meta_m     = re.search(r'<META>(.*?)</META>',         raw, re.DOTALL)
        keywords_m = re.search(r'<KEYWORDS>(.*?)</KEYWORDS>', raw, re.DOTALL)

        summary      = summary_m.group(1).strip()  if summary_m  else f"Complete guide to {topic} for expats in Germany."
        content_html = content_m.group(1).strip()  if content_m  else f"<p>AI content for '{topic}' could not be generated. Please try again.</p>"
        meta_desc    = meta_m.group(1).strip()     if meta_m     else (summary[:152] + "…" if len(summary) > 155 else summary)
        keywords     = keywords_m.group(1).strip() if keywords_m else f"{topic}, expat Germany, guide"

        if len(meta_desc) > 155:
            meta_desc = meta_desc[:152] + "…"

        return {
            "content_html":     content_html,
            "summary":          summary,
            "meta_description": meta_desc,
            "keywords":         keywords,
        }
    except Exception as exc:
        log.error(f"  ✖ Groq API error: {exc}")
        return None


# =============================================================================
# HELPER FUNCTIONS — estimates · dates · enrichment
# =============================================================================

def _estimate_read_minutes(html_or_text: str) -> int:
    text  = re.sub(r'<[^>]+>', ' ', html_or_text)
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
    """
    Derive and attach SEO/meta fields that the template expects.
    Never modifies the original dict — always works on a copy.
    """
    post = dict(post)

    post.setdefault("date", date.today().strftime("%B %d, %Y"))
    post["date_iso"]          = _to_iso_date(post.get("date_iso", post["date"]))
    post["date_modified_iso"] = _to_iso_date(
        post.get("date_modified_iso", post.get("date_modified", post["date_iso"]))
    )

    content = post.get("content_html", post.get("content", ""))
    post.setdefault("read_minutes", _estimate_read_minutes(content))
    post.setdefault("word_count",   _estimate_word_count(content))

    if "content_html" not in post and "content" in post:
        post["content_html"] = post["content"]

    if not post.get("meta_description"):
        raw = post.get("summary", "")[:155]
        post["meta_description"] = raw + ("…" if len(raw) == 155 else "")
    elif len(post["meta_description"]) > 155:
        post["meta_description"] = post["meta_description"][:152] + "…"

    post.setdefault("keywords", "expat Germany, SCHUFA, banking, credit score, expat finance")
    post.setdefault("lang", "en")

    has_affiliate = (
        bool(post.get("affiliate_card"))
        or bool(post.get("has_affiliate_links"))
        or "affiliate"  in content.lower()
        or "sponsored"  in content.lower()
    )
    post.setdefault("has_affiliate_links", has_affiliate)

    faqs = post.get("faqs", [])
    post["faqs"] = (
        faqs
        if isinstance(faqs, list)
        and all(isinstance(f, dict) and "question" in f and "answer" in f for f in faqs)
        else []
    )

    card = post.get("affiliate_card")
    if isinstance(card, dict):
        required = {"name", "category", "url", "description"}
        if not required.issubset(card.keys()):
            log.warning(
                f"  ⚠  affiliate_card for '{post.get('slug')}' missing keys "
                f"{required - card.keys()} — card suppressed"
            )
            post["affiliate_card"] = None
    else:
        post["affiliate_card"] = None

    related = post.get("related_slugs", [])
    post["related_slugs"] = (
        related
        if isinstance(related, list)
        and all(isinstance(r, dict) and "slug" in r and "title" in r for r in related)
        else []
    )

    return post


# =============================================================================
# PAGE GENERATOR
# =============================================================================

def generate_blog_pages(
    data_glob: str         = "*.json",
    force_topic_title: str = None,
    force_rebuild: bool    = False,
) -> list[str]:
    """
    Generate blog pages from JSON data files in DATA_DIR.

    Parameters
    ──────────
    data_glob         Glob pattern for JSON files (default "*.json").
    force_topic_title If set, generate a single AI article for this topic
                      and exit (bypasses JSON files entirely).
    force_rebuild     When True (--force flag):
                        • Skip the mtime / slug-registry cache checks
                        • Re-render every JSON file unconditionally
                        • The slug registry (built_pages.json) is fully
                          rewritten at the end of the run

    Pipeline per page
    ──────────────────
    1.  Load data/providers.csv → build {slug: url} map
    2.  For each JSON file:
          a. _inject_provider_urls()  — patch href="#" from CSV
          b. _enrich_post()           — derive SEO fields
          c. template.render()        — Jinja2 with providers context
          d. _fix_external_links()    — enforce target/_blank/nofollow
          e. _fix_internal_links()    — enforce Zero-Slash Policy
          f. write docs/blog/<slug>.html
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
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("blog_template.html")

    # ── Load slug registry (skip entirely when --force) ───────────────────
    built: list[str] = []
    if not force_rebuild and BUILT_FILE.exists():
        try:
            built = json.loads(BUILT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            built = []

    if force_rebuild:
        log.info("  🔥 --force mode: cache bypassed — ALL pages will be rebuilt")

    # ── Load providers CSV once for the whole run ─────────────────────────
    providers     = _load_providers_csv()
    url_map       = _build_provider_url_map(providers)
    providers_map = url_map.copy()   # alias for template context

    newly_built: list[str] = []

    # ─────────────────────────────────────────────────────────────────────
    # FORCED TOPIC MODE  — generate a single AI article, then exit
    # ─────────────────────────────────────────────────────────────────────
    if force_topic_title:
        log.info(f"  🔥 Force topic: '{force_topic_title}'")
        forced_slug = re.sub(r"[^a-z0-9]+", "-", force_topic_title.lower()).strip("-")

        log.info("  🤖 Requesting AI article from Groq (llama-3.3-70b-versatile)"
                 " – may take 10-20 s …")
        ai = _call_groq_for_article(force_topic_title)
        if ai:
            content_html = ai["content_html"]
            summary      = ai["summary"]
            meta_desc    = ai["meta_description"]
            keywords     = ai["keywords"]
            log.info("  ✅ AI content received")
        else:
            content_html = (
                f"<p>Full article about {force_topic_title} will be available soon.</p>"
            )
            summary   = f"Complete guide to {force_topic_title} for expats in Germany."
            meta_desc = summary[:155]
            keywords  = f"{force_topic_title}, expat Germany, guide"
            log.warning("  ⚠  Using placeholder (AI call failed)")

        post_dict = {
            "slug":             forced_slug,
            "title":            force_topic_title,
            "summary":          summary,
            "content_html":     content_html,
            "meta_description": meta_desc,
            "keywords":         keywords,
            "category":         "Guide",
            "date":             date.today().strftime("%B %d, %Y"),
            "date_iso":         date.today().isoformat(),
        }
        enriched         = _enrich_post(post_dict)
        enriched["slug"] = forced_slug
        out_path         = BLOG_DIR / f"{forced_slug}.html"

        try:
            html = template.render(
                post=enriched,
                providers_map=providers_map,
                providers=providers,
                year=datetime.now().year,
            )
            html = _fix_external_links(html)
            html = _fix_internal_links(html)
            out_path.write_text(html, encoding="utf-8")
            log.info(f"  ✅ Built (AI): blog/{forced_slug}.html "
                     f"({enriched.get('word_count', 0)} words)")
            newly_built.append(forced_slug)
        except Exception as exc:
            log.error(f"  ✖ Render failed for forced topic: {exc}", exc_info=True)
            return []

        # Update registry
        merged = sorted(set(built + newly_built)) if not force_rebuild else newly_built
        BUILT_FILE.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return newly_built

    # ─────────────────────────────────────────────────────────────────────
    # NORMAL MODE  — process every JSON file in DATA_DIR
    # ─────────────────────────────────────────────────────────────────────
    data_files = sorted(DATA_DIR.glob(data_glob)) if DATA_DIR.exists() else []
    if not data_files:
        log.warning(f"  ⚠  No JSON data files found in {DATA_DIR}")
        return []

    log.info(f"  📄 Found {len(data_files)} post file(s) in {DATA_DIR}")

    for data_file in data_files:
        if data_file.name.startswith("."):
            log.info(f"  ⏭  Skipping dot-file: {data_file.name}")
            continue

        try:
            raw_post = json.loads(data_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.error(f"  ✖ Failed to read {data_file.name}: {exc}")
            continue

        if isinstance(raw_post, list):
            if not raw_post:
                log.warning(f"  ⚠  {data_file.name} is an empty list — skipping")
                continue
            raw_post = raw_post[0]
            log.info(f"  🔄 {data_file.name} was a list — using first element")

        if not isinstance(raw_post, dict):
            log.warning(f"  ⚠  {data_file.name} is not a valid post object — skipping")
            continue

        slug = raw_post.get("slug") or data_file.stem
        if not slug:
            log.warning(f"  ⚠  No slug in {data_file.name} — skipping")
            continue

        out_path = BLOG_DIR / f"{slug}.html"

        # Cache check — skip when --force is active
        if not force_rebuild and slug in built and out_path.exists():
            if data_file.stat().st_mtime <= out_path.stat().st_mtime:
                log.info(f"  ⏭  {slug} — up to date, skipping")
                continue

        # ── Pipeline ──────────────────────────────────────────────────────
        raw_post      = _inject_provider_urls(raw_post, url_map)  # step a
        post          = _enrich_post(raw_post)                     # step b
        post["slug"]  = slug

        try:
            html = template.render(                                # step c
                post=post,
                providers_map=providers_map,
                providers=providers,
                year=datetime.now().year,
            )
            html = _fix_external_links(html)                       # step d
            html = _fix_internal_links(html)                       # step e
            out_path.write_text(html, encoding="utf-8")            # step f
            log.info(
                f"  ✅ Built: blog/{slug}.html "
                f"({post['word_count']} words · {post['read_minutes']} min read)"
            )
            newly_built.append(slug)
        except Exception as exc:
            log.error(f"  ✖ Render failed for {slug}: {exc}", exc_info=True)

    # ── Persist slug registry ─────────────────────────────────────────────
    # --force: rewrite the registry from scratch (only what was just built).
    # Normal: merge new slugs into the existing registry.
    if force_rebuild:
        all_built = sorted(newly_built)
    else:
        all_built = sorted(set(built + newly_built))

    BUILT_FILE.write_text(
        json.dumps(all_built, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info(
        f"  📊 Summary: {len(newly_built)} built"
        + (" (full force rebuild)" if force_rebuild else "")
        + f", {len(all_built)} total tracked"
    )
    return newly_built


# =============================================================================
# SITEMAP REGENERATOR
# =============================================================================

# System / cache file patterns that must never appear in sitemap.xml.
# These are matched against the file stem (filename without extension) and
# against the full filename with extension.
_SITEMAP_EXCLUDE_STEMS = {
    "dedup_registry",
    "session_state",
    "built_pages",
    "404",
    "impressum",
    "datenschutz",
    "affiliate-hinweis",
}
_SITEMAP_EXCLUDE_PREFIXES = (
    "google",   # GSC verification files (google9536….html, etc.)
    "_",        # Private / partial templates
    ".",        # Hidden dot-files
)

def _is_sitemap_excluded(html_file: Path) -> tuple[bool, str]:
    """
    Return (True, reason) if the file should be excluded from sitemap.xml,
    or (False, "") if it is a valid indexable page.

    Exclusion criteria:
      1. Stem matches a known system/cache name in _SITEMAP_EXCLUDE_STEMS
      2. Stem starts with a prefix in _SITEMAP_EXCLUDE_PREFIXES
      3. File suffix is NOT .html  (catches .dedup_registry, .session_state, etc.)
    """
    # Guard: only .html files are valid web pages
    if html_file.suffix.lower() != ".html":
        return True, f"non-html suffix ({html_file.suffix})"

    stem = html_file.stem.lower()

    if any(stem.startswith(pfx) for pfx in _SITEMAP_EXCLUDE_PREFIXES):
        return True, "excluded prefix"

    if stem in _SITEMAP_EXCLUDE_STEMS:
        return True, "excluded system/cache file"

    return False, ""


def regenerate_sitemap(base_url: str = "https://expatscore.de") -> None:
    """
    Regenerate docs/sitemap.xml with guaranteed coverage of all pages.

    Sources (merged and deduplicated by full URL):
      1. Filesystem scan of docs/**/*.html  — all already-rendered pages,
         filtered through _is_sitemap_excluded() to strip cache/system files.
      2. data/providers.csv                 — every valid (slug, category) row
         produces one URL entry so all 136 programmatic pages are present even
         before their HTML files have been written to disk.

    Merge rule: filesystem entry wins over CSV entry when both produce the
    same URL (the HTML file's real mtime is more accurate than today's date).

    URL pattern for programmatic (CSV-driven) pages:
        {base_url}/{category}/{slug}
    e.g.  https://expatscore.de/banking/n26
          https://expatscore.de/insurance/fintiba
    """
    sitemap_path = DOCS_DIR / "sitemap.xml"
    today        = date.today().isoformat()

    PRIORITIES: dict[str, tuple[str, str]] = {
        "":                 ("1.0",  "weekly"),
        "schufa-simulator": ("0.9",  "weekly"),
        "blue-card-tool":   ("0.9",  "weekly"),
        "schufa-guide":     ("0.85", "monthly"),
        "banking":          ("0.8",  "weekly"),
        "insurance":        ("0.8",  "weekly"),
        "blog/":            ("0.7",  "weekly"),
    }

    def _priority_for(url_path: str) -> tuple[str, str]:
        """Return (priority, changefreq) for a given URL path."""
        # Programmatic provider pages  /banking/n26  /insurance/fintiba
        if re.match(r'^(banking|insurance)/[^/]+$', url_path):
            return "0.75", "monthly"
        # Blog posts  (but not the blog index itself)
        if url_path.startswith("blog/") and url_path != "blog":
            return "0.6", "monthly"
        # Static legal/utility pages
        if any(url_path == p for p in ("impressum", "datenschutz", "affiliate-hinweis", "404")):
            return "0.3", "yearly"
        return PRIORITIES.get(url_path, ("0.6", "monthly"))

    # Keyed by full URL to deduplicate filesystem + CSV sources.
    # Tuple: (full_url, lastmod, changefreq, priority)
    seen: dict[str, tuple[str, str, str, str]] = {}

    # ── Source 1: filesystem scan ─────────────────────────────────────────
    fs_count = 0
    for html_file in sorted(DOCS_DIR.rglob("*")):
        excluded, reason = _is_sitemap_excluded(html_file)
        if excluded:
            if reason != f"non-html suffix ({html_file.suffix})":
                log.debug(f"  sitemap skip: {html_file.name} ({reason})")
            continue

        rel   = html_file.relative_to(DOCS_DIR)
        parts = list(rel.parts)
        if parts[-1] == "index.html":
            parts[-1] = ""
        else:
            parts[-1] = parts[-1][:-5]   # strip .html
        url_path = "/".join(parts).strip("/")

        priority, changefreq = _priority_for(url_path)
        full_url = f"{base_url}/{url_path}" if url_path else base_url + "/"
        seen[full_url] = (full_url, today, changefreq, priority)
        fs_count += 1

    # ── Source 2: CSV-driven programmatic pages ───────────────────────────
    providers  = _load_providers_csv()
    csv_added  = 0
    for p in providers:
        slug     = p.get("slug",     "").strip()
        category = p.get("category", "").strip().lower()
        if not slug or not category:
            continue   # skip incomplete / header-only rows
        full_url = f"{base_url}/{category}/{slug}"
        if full_url not in seen:
            priority, changefreq = _priority_for(f"{category}/{slug}")
            seen[full_url] = (full_url, today, changefreq, priority)
            csv_added += 1

    if csv_added:
        log.info(f"  📋 Added {csv_added} CSV-only programmatic URL(s) to sitemap")

    # ── Build XML ─────────────────────────────────────────────────────────
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for full_url, lastmod, changefreq, priority in sorted(
        seen.values(), key=lambda x: x[0]
    ):
        lines += [
            "  <url>",
            f"    <loc>{full_url}</loc>",
            f"    <lastmod>{lastmod}</lastmod>",
            f"    <changefreq>{changefreq}</changefreq>",
            f"    <priority>{priority}</priority>",
            "  </url>",
        ]
    lines.append("</urlset>")

    sitemap_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(
        f"  🗺  Sitemap written: {len(seen)} URLs "
        f"({fs_count} from disk · {csv_added} from CSV) → {sitemap_path}"
    )


# =============================================================================
# WORKER IMPORTS
# =============================================================================

try:
    import reddit_worker
    import youtube_worker
    WORKERS_AVAILABLE = True
except ImportError as exc:
    log.warning(f"⚠  Worker import failed ({exc}) — sniper mode unavailable")
    WORKERS_AVAILABLE = False


def make_thread(target_fn, name: str) -> threading.Thread:
    return threading.Thread(target=target_fn, name=name, daemon=True)


def run_reddit():
    log.info("🟠 [Reddit Worker] Thread started.")
    try:
        # REDDIT WORKER DISABLED
        # reddit_worker.main()
        log.info("🟠 [Reddit Worker] Skipped (disabled in configuration).")
    except Exception as exc:
        log.critical(f"💥 [Reddit Worker] Fatal crash: {exc}", exc_info=True)


def run_youtube():
    log.info("🔴 [YouTube Worker] Thread started.")
    try:
        youtube_worker.main()
    except Exception as exc:
        log.critical(f"💥 [YouTube Worker] Fatal crash: {exc}", exc_info=True)


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ExpatScore Coordinator v3.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py --generator-only          # build new/changed pages, then exit
  python3 main.py --generator-only --force  # rebuild ALL pages from CSV, then exit
  python3 main.py --topic "Best banks for students in Germany"  # AI article
  python3 main.py                           # full run: pages + workers
""",
    )
    parser.add_argument(
        "--generator-only", action="store_true",
        help="Build pages then exit (skip worker threads)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help=(
            "Bypass all caches and rebuild EVERY page from data/providers.csv. "
            "Ignores built_pages.json and file mtimes. "
            "Safe to combine with --generator-only."
        ),
    )
    parser.add_argument(
        "--topic", type=str, default=None,
        help="Force-generate a single AI article for TOPIC (bypasses JSON files)",
    )
    args = parser.parse_args()

    log.info("=" * 65)
    log.info("🚀 ExpatScore Coordinator v3.0 — --force · CSV alignment · Zero-Slash")
    log.info("=" * 65)

    if args.force:
        log.info("⚠  --force flag active: full cache bypass, all pages will be rebuilt")

    log.info("\n📐 Running page generator …")
    newly_built = generate_blog_pages(
        force_topic_title=args.topic,
        force_rebuild=args.force,
    )

    if newly_built or args.force:
        regenerate_sitemap()
    else:
        log.info("  ✅ No new pages built — sitemap unchanged.")

    if args.generator_only:
        log.info("✅ --generator-only mode — exiting.")
        sys.exit(0)

    if not WORKERS_AVAILABLE:
        log.warning("⚠  Worker modules not available — sniper mode disabled.")
        sys.exit(0)

    missing = []
    if not os.getenv("N8N_WEBHOOK_URL"):
        missing.append("N8N_WEBHOOK_URL")
    if not os.getenv("YOUTUBE_API_KEY"):
        missing.append("YOUTUBE_API_KEY")
    if missing:
        log.critical(f"🚫 Missing required .env variables: {missing}")
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
        log.info("🔴 YouTube worker disabled via YOUTUBE_WORKER_ENABLED=false")
        youtube_thread = None

    log.info("✅ Workers initialised. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(300)
            if not reddit_thread.is_alive():
                log.critical("🟠 [Watchdog] Reddit thread dead — RESTARTING")
                reddit_thread = make_thread(run_reddit, "RedditWorker")
                reddit_thread.start()
            if youtube_enabled and (
                youtube_thread is None or not youtube_thread.is_alive()
            ):
                log.critical("🔴 [Watchdog] YouTube thread dead — RESTARTING")
                youtube_thread = make_thread(run_youtube, "YouTubeWorker")
                youtube_thread.start()
    except KeyboardInterrupt:
        log.info("🔴 Shutting down. Goodbye.")
        sys.exit(0)


if __name__ == "__main__":
    main()