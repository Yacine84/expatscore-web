#!/usr/bin/env python3
"""
sync_blog.py — Blog index generator for ExpatScore.de (Robust version)

Scans docs/blog/*.html (excluding system files), extracts metadata,
and updates docs/blog.html with sorted blog cards.

Usage:
    python sync_blog.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("❌ BeautifulSoup not installed. Run: pip install beautifulsoup4")
    sys.exit(1)


# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
BLOG_DIR = PROJECT_ROOT / "docs" / "blog"
BLOG_INDEX_FILE = PROJECT_ROOT / "docs" / "blog.html"

# Files to exclude (system / temporary)
EXCLUDED_FILENAMES = {
    "seen_urls.html",
    "seen_posts.html",
    "session_state.html",
    ".dedup_registry.html",
    ".session_state.html",
}


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------
def is_valid_article(file_path: Path) -> bool:
    """
    Return True if the file should be processed:
        - Not a dot-file
        - Basename not in EXCLUDED_FILENAMES
        - Contains an <h1> tag (real article)
    """
    if file_path.name.startswith("."):
        return False
    if file_path.name in EXCLUDED_FILENAMES:
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        return bool(soup.find("h1"))
    except Exception:
        return False


def extract_article_metadata(file_path: Path) -> Optional[Dict]:
    """
    Parse an HTML article file and extract:
        - title (from <h1>)
        - description (first <p> inside .article-body, or first <p> in body)
        - date (from .date span, or "📅" text, or file mtime)
    Returns dict or None if critical data missing.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
    except Exception as e:
        print(f"  ⚠  Could not read {file_path.name}: {e}")
        return None

    # Title (required)
    title_tag = soup.select_one(".hero-article h1") or soup.find("h1")
    if not title_tag:
        print(f"  ⏭  Skip {file_path.name}: no <h1> found")
        return None
    title = title_tag.get_text(strip=True)

    # Description: first <p> inside .article-body, else first <p> overall
    desc = ""
    article_body = soup.select_one(".article-body")
    if article_body:
        first_p = article_body.find("p")
        if first_p:
            desc = first_p.get_text(strip=True)[:200]
    if not desc:
        first_p = soup.find("p")
        if first_p:
            desc = first_p.get_text(strip=True)[:200]

    # Date: try .date span, then "📅" text, else mtime
    date_obj = None
    date_span = soup.select_one("span.date")
    if date_span:
        date_str = date_span.get_text(strip=True)
    else:
        # Look for the line with "📅"
        date_span = None
        for span in soup.find_all("span"):
            text = span.get_text(strip=True)
            if text.startswith("📅"):
                date_str = text.replace("📅", "").strip()
                break
        else:
            date_str = None

    if date_str:
        for fmt in ("%B %d, %Y", "%Y-%m-%d", "%d %B %Y", "%d.%m.%Y", "%m/%d/%Y"):
            try:
                date_obj = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue

    if not date_obj:
        date_obj = datetime.fromtimestamp(file_path.stat().st_mtime)

    return {
        "title": title,
        "description": desc if desc else title,
        "date_obj": date_obj,
        "date_str": date_obj.strftime("%Y-%m-%d"),
        "slug": file_path.stem,
        "url": f"blog/{file_path.name}",
    }


def generate_blog_card(article: Dict) -> str:
    """Return HTML string for a single blog card."""
    category = "GUIDE"  # Can be extended later
    return f'''<div class="blog-card">
  <span class="category">{category}</span>
  <h3>{article["title"]}</h3>
  <p>{article["description"]}</p>
  <span class="date">{article["date_str"]}</span>
  <a href="{article["url"]}">Read more →</a>
</div>'''


def ensure_blog_container(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Try to find <div id="blog-container">. If missing, look for
    common wrappers (.blog-grid, .card-grid, main, section) and
    insert the ID into the first suitable container.
    Returns the container element, or None if none found.
    """
    container = soup.find("div", id="blog-container")
    if container:
        return container

    # Fallback: look for typical blog card wrappers
    fallback_selectors = [
        ".blog-grid",           # common class
        ".card-grid",           # your existing grid class
        "main article",         # semantic HTML
        "section.blog-list",
        "div.blog-list",
        "div.content",          # generic but often used
    ]
    for selector in fallback_selectors:
        container = soup.select_one(selector)
        if container:
            # Inject an id to make future runs faster
            container["id"] = "blog-container"
            print(f"  ℹ  Injected id='blog-container' into <{container.name} class='{container.get('class', [''])[0]}'>")
            return container

    # Last resort: the entire <main> or <body>
    container = soup.find("main") or soup.find("body")
    if container:
        container["id"] = "blog-container"
        print(f"  ℹ  Injected id='blog-container' into <{container.name}>")
        return container

    return None


def update_blog_index(articles: List[Dict]):
    """
    Read blog.html, locate (or inject) the blog container,
    replace its contents with generated cards, and write back.
    """
    if not BLOG_INDEX_FILE.exists():
        print(f"❌ {BLOG_INDEX_FILE} not found. Please create it first.")
        return

    with open(BLOG_INDEX_FILE, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    container = ensure_blog_container(soup)
    if not container:
        print("❌ Could not find or create a suitable container for blog cards.")
        print("   Make sure your blog.html has a <div>, <main>, or <section> with a common class.")
        return

    # Clear existing cards
    container.clear()

    # Add new cards (already sorted)
    for article in articles:
        card_html = generate_blog_card(article)
        card_soup = BeautifulSoup(card_html, "html.parser")
        container.append(card_soup)

    # Write back
    with open(BLOG_INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify()))

    print(f"✅ Updated {BLOG_INDEX_FILE} with {len(articles)} cards.")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    print("🔍 Scanning blog articles...")
    if not BLOG_DIR.exists():
        print(f"❌ Blog directory not found: {BLOG_DIR}")
        sys.exit(1)

    articles = []
    for html_file in sorted(BLOG_DIR.glob("*.html")):
        if not is_valid_article(html_file):
            if html_file.name.startswith(".") or html_file.name in EXCLUDED_FILENAMES:
                print(f"  ⏭  Skipped system file: {html_file.name}")
            continue

        print(f"  📄 Processing: {html_file.name}")
        meta = extract_article_metadata(html_file)
        if meta:
            articles.append(meta)
        else:
            print(f"  ⚠  Could not extract metadata from {html_file.name}")

    if not articles:
        print("⚠  No valid articles found. Nothing to update.")
        return

    # Sort by date descending (newest first)
    articles.sort(key=lambda x: x["date_obj"], reverse=True)

    # Update the blog listing page
    update_blog_index(articles)


if __name__ == "__main__":
    main()