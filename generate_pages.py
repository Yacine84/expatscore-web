#!/usr/bin/env python3
"""
generate_pages.py — ExpatScore.de V3.2 Gold Standard Generator
═══════════════════════════════════════════════════════════════════

Architecture:
  - Reads article data from data.csv
  - Optionally reads long-form Markdown content from raw_content/
  - Outputs ALL pages to docs/ FLAT ROOT (no subfolders)
  - NEVER overwrites handcrafted "gold" pages
  - Generates sitemap.xml with clean URLs (no .html extensions)
  - Copies style.css, script.js, vercel.json to docs/

This is the ONLY generator. agent.py and consolidate.py are obsolete.
"""

import csv
import os
import re
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

try:
    import markdown
    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

# ──────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────
DATA_FILE       = "data.csv"
TEMPLATES_DIR   = "templates"
OUTPUT_DIR      = "docs"
RAW_CONTENT_DIR = "raw_content"
DOMAIN          = "https://www.expatscore.de"
TODAY           = datetime.now().date().isoformat()

# Category slug → display label + hub page filename (flat root)
CATEGORY_MAP = {
    "banking":   {"label": "Banking",      "hub": "banking"},
    "insurance": {"label": "Versicherung", "hub": "insurance"},
    "guides":    {"label": "SCHUFA Guide", "hub": "schufa-guide"},
    "legal":     {"label": "Legal",        "hub": "about"},
    "tools":     {"label": "Tools",        "hub": "schufa-simulator"},
}

# Handcrafted "gold" pages — NEVER overwrite these.
# These are your manually polished pages with interactive tools, simulators, etc.
PROTECTED_FILES = {
    "index.html",
    "banking.html",
    "insurance.html",
    "schufa-guide.html",
    "schufa-simulator.html",
    "n26-bank-erfahrungen.html",
    "blocked-account-germany.html",
    "konto-ohne-anmeldung.html",
    "blue-card-tool.html",
    "about.html",
    "datenschutz.html",
    "affiliate-hinweis.html",
    "impressum.html",
    "tk-health-insurance.html",
    "steuer-id-guide.html",
    "anmeldung-germany.html",
    "style.css",
    "script.js",
    "vercel.json",
    "sitemap.xml",
}

# All pages for sitemap (handcrafted + generated).
# Handcrafted pages are always included. Generated ones are added dynamically.
SITEMAP_STATIC = [
    ("/",                     "1.0",  "weekly"),
    ("/banking",              "0.8",  "weekly"),
    ("/insurance",            "0.8",  "weekly"),
    ("/schufa-guide",         "0.85", "monthly"),
    ("/schufa-simulator",     "0.85", "monthly"),
    ("/n26-bank-erfahrungen", "0.8",  "monthly"),
    ("/blocked-account-germany","0.8","monthly"),
    ("/konto-ohne-anmeldung", "0.8",  "monthly"),
    ("/blue-card-tool",       "0.75", "monthly"),
    ("/tk-health-insurance",  "0.75", "monthly"),
    ("/anmeldung-germany",    "0.75", "monthly"),
    ("/steuer-id-guide",      "0.75", "monthly"),
    ("/about",                "0.5",  "monthly"),
    ("/impressum",            "0.3",  "yearly"),
    ("/datenschutz",          "0.3",  "yearly"),
    ("/affiliate-hinweis",    "0.3",  "yearly"),
]

# ──────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("generator")


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────
def word_count(html: str) -> int:
    """Count words in HTML (strips tags)."""
    text = re.sub(r"<[^>]+>", "", html)
    return len(text.split())


def reading_time(html: str) -> int:
    """Estimate reading time in minutes (200 wpm)."""
    return max(1, word_count(html) // 200)


def wrap_tables(html: str) -> str:
    """Wrap <table> elements in responsive div."""
    return re.sub(
        r"(<table.*?</table>)",
        r'<div class="table-responsive">\1</div>',
        html, flags=re.DOTALL
    )


def load_markdown_content(slug: str) -> str | None:
    """Search raw_content/ recursively for {slug}.md and return HTML."""
    if not HAS_MARKDOWN:
        return None
    raw_dir = Path(RAW_CONTENT_DIR)
    if not raw_dir.exists():
        return None
    matches = list(raw_dir.rglob(f"{slug}.md"))
    if not matches:
        return None
    with open(matches[0], "r", encoding="utf-8") as f:
        md = f.read()
    return markdown.markdown(md, extensions=["tables", "fenced_code"])


def get_related_posts(article: dict, all_articles: list, limit: int = 3) -> list:
    """Get related articles from the same category."""
    same_cat = [a for a in all_articles if a["category"] == article["category"] and a["slug"] != article["slug"]]
    related = same_cat[:limit]
    return [
        {"title": r["title"], "url": f"{r['slug']}.html", "description": r["meta_description"]}
        for r in related
    ]


# ──────────────────────────────────────────────────────────────────
# Main Generator
# ──────────────────────────────────────────────────────────────────
def main():
    log.info("═══ ExpatScore.de V3.2 Generator ═══")

    # ── 1. Setup ──
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    article_tpl = env.get_template("article.html")

    # ── 2. Read data ──
    articles = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if not row.get("slug") or not row.get("title"):
                log.warning(f"Skipping row with missing slug/title: {row}")
                continue
            articles.append(row)
    log.info(f"Loaded {len(articles)} articles from {DATA_FILE}")

    generated_slugs = []

    # ── 3. Generate articles ──
    for article in articles:
        slug = article["slug"]
        filename = f"{slug}.html"
        output_path = os.path.join(OUTPUT_DIR, filename)

        # NEVER overwrite handcrafted pages
        if filename in PROTECTED_FILES:
            if os.path.exists(output_path):
                log.info(f"SKIP (protected): {filename} — handcrafted gold page exists")
                continue
            else:
                log.info(f"GENERATE (protected but missing): {filename}")

        # Content: try Markdown file first, then CSV content field, then meta_description fallback
        content_html = load_markdown_content(slug)
        if content_html:
            log.info(f"  Content source: raw_content/{slug}.md")
        elif article.get("content"):
            content_html = article["content"]
            log.info(f"  Content source: data.csv content column")
        else:
            content_html = f"<p>{article['meta_description']}</p>"
            log.warning(f"  Content source: meta_description fallback (no .md or content)")

        # Process content
        content_html = wrap_tables(content_html)

        # Category mapping
        cat_key = article.get("category", "guides")
        cat_info = CATEGORY_MAP.get(cat_key, {"label": cat_key.capitalize(), "hub": "index"})

        # Build template context
        context = {
            "title": article["title"],
            "meta_description": article["meta_description"],
            "slug": slug,
            "h1": article.get("h1") or article["title"],
            "subheadline": article.get("subheadline", ""),
            "content": content_html,
            "category": cat_key,
            "category_label": cat_info["label"],
            "category_hub": cat_info["hub"],
            "reading_time": reading_time(content_html),
            "related_posts": get_related_posts(article, articles),
            "date_published": "2026-01-15",
            "date_modified": TODAY,
        }

        try:
            html = article_tpl.render(**context)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            generated_slugs.append(slug)
            log.info(f"  ✓ GENERATED: {filename} ({word_count(content_html)} words)")
        except Exception as e:
            log.error(f"  ✗ Template error for {slug}: {e}")

    # ── 4. Generate sitemap.xml ──
    log.info("Generating sitemap.xml...")
    sitemap_entries = list(SITEMAP_STATIC)

    # Add generated articles that aren't already in the static list
    static_paths = {entry[0] for entry in SITEMAP_STATIC}
    for slug in generated_slugs:
        path = f"/{slug}"
        if path not in static_paths:
            sitemap_entries.append((path, "0.6", "monthly"))

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    ]
    for path, priority, freq in sitemap_entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{DOMAIN}{path}</loc>")
        lines.append(f"    <lastmod>{TODAY}</lastmod>")
        lines.append(f"    <changefreq>{freq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    with open(os.path.join(OUTPUT_DIR, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info(f"  ✓ sitemap.xml — {len(sitemap_entries)} URLs")

    # ── 5. Copy root assets ──
    log.info("Copying root assets...")
    root_assets = ["style.css", "script.js", "vercel.json", "og-image.jpg", "favicon.ico"]
    for asset in root_assets:
        src = os.path.join(".", asset)
        dst = os.path.join(OUTPUT_DIR, asset)
        if os.path.isfile(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            log.info(f"  Copied {asset}")

    # Copy assets/img/ directory if it exists
    assets_src = os.path.join(".", "assets", "img")
    assets_dst = os.path.join(OUTPUT_DIR, "assets", "img")
    if os.path.isdir(assets_src):
        os.makedirs(assets_dst, exist_ok=True)
        for f in os.listdir(assets_src):
            src = os.path.join(assets_src, f)
            dst_file = os.path.join(assets_dst, f)
            if os.path.isfile(src) and not os.path.exists(dst_file):
                shutil.copy2(src, dst_file)
        log.info(f"  Copied assets/img/")

    # ── 6. Clean up old subfolder artifacts ──
    old_folders = ["banking", "insurance", "guides", "legal", "tools",
                   "wenn-du-dauerhaft-ins-minus-rutschst-und-rückzahlungen-ausbleiben-wer-sein-konto-sauber-führt"]
    for folder in old_folders:
        path = os.path.join(OUTPUT_DIR, folder)
        if os.path.isdir(path):
            shutil.rmtree(path)
            log.info(f"  🗑 Removed old subfolder: docs/{folder}/")

    # ── Done ──
    total = len(generated_slugs)
    protected = len(PROTECTED_FILES) - 3  # minus css/js/json
    log.info(f"")
    log.info(f"═══ BUILD COMPLETE ═══")
    log.info(f"  Generated:  {total} new article(s)")
    log.info(f"  Protected:  {protected} handcrafted gold pages")
    log.info(f"  Sitemap:    {len(sitemap_entries)} URLs")
    log.info(f"  Output:     {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
