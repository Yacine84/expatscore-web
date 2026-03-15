#!/usr/bin/env python3
"""
generate_pages.py – Production static site generator for ExpatScore.de
Reads data.csv from root, outputs into docs/ folder (for GitHub Pages / static hosting).
Now generates homepage, static pages, and uses dynamic base_path for correct asset linking.
"""

import csv
import os
import shutil
import re
import random
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
import xml.etree.ElementTree as ET

# ---------- Configuration ----------
DATA_FILE = "data.csv"
TEMPLATES_DIR = "templates"
OUTPUT_DIR = "docs"                     # output root

# Static pages that are mentioned in the sitemap (not necessarily generated here)
STATIC_PAGES = [
    "index.html",
    "banking.html",
    "schufa-guide.html",
]

# Configuration for generating static pages from templates
# Each entry: {'output': relative output path (inside OUTPUT_DIR), 'template': template name}
STATIC_PAGES_CONFIG = [
    {'output': 'index.html',                'template': 'index.html'},
    {'output': 'impressum.html',             'template': 'impressum.html'},
    {'output': 'datenschutz.html',           'template': 'datenschutz.html'},
    {'output': 'affiliate-hinweis.html',     'template': 'affiliate-hinweis.html'},
    {'output': 'ueber-uns.html',              'template': 'ueber-uns.html'},
    {'output': 'guides/schufa-guide.html',   'template': 'schufa-guide.html'},   # in subfolder
]

# ---------- Setup Jinja2 ----------
env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
article_template = env.get_template("article.html")
hub_template = env.get_template("hub.html")
index_template = env.get_template("index.html")   # for homepage
# Static page templates will be loaded dynamically

# ---------- Helper Functions ----------

def calculate_base_path(output_file_path, output_root=OUTPUT_DIR):
    """
    Return a relative path prefix (e.g. "", "../", "../../") that,
    when prepended to asset paths, correctly points to the root
    of the site (where 'assets/' lives).

    :param output_file_path: full path to the generated HTML file
    :param output_root: root directory of the site (default: 'docs')
    :return: string like "", "../", "../../", etc.
    """
    # Get the directory of the output file relative to output_root
    rel_dir = os.path.dirname(os.path.relpath(output_file_path, output_root))
    if rel_dir == ".":
        return ""                     # file is directly in output_root
    # Count the number of directory levels to go up
    depth = rel_dir.count(os.sep) + 1
    return "../" * depth

def read_data():
    """Read CSV, return list of dicts and dict grouped by category."""
    rows = []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Basic validation
            if not row.get("title") or not row.get("slug") or not row.get("category"):
                print(f"Warning: Skipping row missing title/slug/category: {row}")
                continue
            rows.append(row)
    # Group by category
    grouped = {}
    for row in rows:
        cat = row["category"]
        grouped.setdefault(cat, []).append(row)
    return rows, grouped

def clean_category_folders(categories):
    """Remove all category folders for the given categories inside OUTPUT_DIR."""
    for cat in categories:
        folder = os.path.join(OUTPUT_DIR, cat)
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  Removed {folder}")

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def write_html(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def generate_sitemap(articles, static_pages, categories):
    """Write sitemap.xml to OUTPUT_DIR."""
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    today = datetime.now().date().isoformat()

    for page in static_pages:
        url = ET.SubElement(root, "url")
        ET.SubElement(url, "loc").text = f"https://expatscore.de/{page}"
        ET.SubElement(url, "lastmod").text = today
        ET.SubElement(url, "changefreq").text = "monthly"
        ET.SubElement(url, "priority").text = "0.8"

    for art in articles:
        url = ET.SubElement(root, "url")
        loc = f"https://expatscore.de/{art['category']}/{art['slug']}.html"
        ET.SubElement(url, "loc").text = loc
        ET.SubElement(url, "lastmod").text = today
        ET.SubElement(url, "changefreq").text = "monthly"
        ET.SubElement(url, "priority").text = "0.6"

    for cat in categories:
        url = ET.SubElement(root, "url")
        loc = f"https://expatscore.de/{cat}/index.html"
        ET.SubElement(url, "loc").text = loc
        ET.SubElement(url, "lastmod").text = today
        ET.SubElement(url, "changefreq").text = "weekly"
        ET.SubElement(url, "priority").text = "0.7"

    tree = ET.ElementTree(root)
    tree.write(os.path.join(OUTPUT_DIR, "sitemap.xml"), encoding="utf-8", xml_declaration=True)

def copy_assets():
    """
    Copy static assets to OUTPUT_DIR.
    Copies the entire assets/ folder and also individual root files if present.
    Prints success message if assets folder copied, otherwise warns.
    """
    assets_dir_src = os.path.join(".", "assets")
    assets_dir_dst = os.path.join(OUTPUT_DIR, "assets")

    # Remove old assets folder if it exists
    if os.path.exists(assets_dir_dst):
        shutil.rmtree(assets_dir_dst)
        print(f"  Removed old {assets_dir_dst}")

    # Copy the entire assets/ folder
    if os.path.isdir(assets_dir_src):
        shutil.copytree(assets_dir_src, assets_dir_dst)
        print(f"  ✅ Successfully copied assets/ folder to {assets_dir_dst}")
    else:
        print(f"  ⚠️ Warning: assets/ folder not found, skipping asset copy.")

    # Copy individual root files (if they exist)
    root_files = ["favicon.ico", "sitemap.xml", "og-image.jpg"]
    for filename in root_files:
        src = os.path.join(".", filename)
        dst = os.path.join(OUTPUT_DIR, filename)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"  Copied {filename}")
        else:
            print(f"  ⚠️ Warning: {filename} not found, skipping.")

def reading_time_minutes(html_content):
    """
    Estimate reading time based on word count (200 words per minute).
    Strips HTML tags first.
    """
    text = re.sub(r'<[^>]+>', '', html_content)
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return minutes

def generate_breadcrumbs(category, title):
    """Return list of breadcrumb dicts."""
    return [
        {"name": "Home", "url": "/"},
        {"name": category.capitalize(), "url": f"/{category}/"},
        {"name": title, "url": None}   # current page
    ]

def generate_json_ld(article, filename, category):
    """Return Article schema.org dictionary."""
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "description": article["meta_description"],
        "author": {
            "@type": "Person",
            "name": "Yassine Chaikhi",
            "url": "https://expatscore.de/ueber-uns.html"
        },
        "publisher": {
            "@type": "Organization",
            "name": "ExpatScore.de",
            "logo": {
                "@type": "ImageObject",
                "url": "https://expatscore.de/assets/apple-touch-icon.png"
            }
        },
        "datePublished": datetime.now().isoformat(),   # ideally from CSV, fallback to now
        "dateModified": datetime.now().isoformat(),
        "mainEntityOfPage": f"https://expatscore.de/{category}/{filename}"
    }

def deterministic_shuffle(items, seed):
    """Shuffle a list deterministically based on a seed string."""
    r = random.Random(seed)
    shuffled = items[:]
    r.shuffle(shuffled)
    return shuffled

def get_related_posts(article, all_in_category):
    """
    Return up to 3 related posts from the same category, excluding the current article.
    Deterministic shuffle based on the current slug ensures variation across articles.
    """
    others = [a for a in all_in_category if a["slug"] != article["slug"]]
    shuffled = deterministic_shuffle(others, article["slug"])
    related = shuffled[:3]
    related_posts = []
    for r in related:
        related_posts.append({
            "title": r["title"],
            "url": f"./{r['slug']}.html",          # relative to the current article
            "description": r["meta_description"],
        })
    return related_posts

def get_latest_articles(all_articles, count=5):
    """
    Return the first 'count' articles from the list as 'latest'.
    (In a real scenario you might sort by date; here we simply take the first ones.)
    """
    return all_articles[:count]

# ---------- Main Generation ----------
def main():
    print("Reading data.csv...")
    articles, grouped = read_data()
    categories = list(grouped.keys())

    print("Cleaning old category folders...")
    clean_category_folders(categories)

    # ------------------------------------------------------------------
    # 1. Generate Articles
    # ------------------------------------------------------------------
    print("Generating articles...")
    for article in articles:
        cat = article["category"]
        slug = article["slug"]
        filename = f"{slug}.html"
        folder = os.path.join(OUTPUT_DIR, cat)
        ensure_dir(folder)

        # Full output path for this article
        output_path = os.path.join(folder, filename)

        # Compute enhancements
        read_time = reading_time_minutes(article["content"])
        breadcrumbs = generate_breadcrumbs(cat, article["title"])
        json_ld = generate_json_ld(article, filename, cat)
        related_posts = get_related_posts(article, grouped[cat])

        # Calculate base_path dynamically
        base_path = calculate_base_path(output_path, output_root=OUTPUT_DIR)

        context = {
            "base_path": base_path,
            "title": article["title"],
            "meta_description": article["meta_description"],
            "h1": article["h1"],
            "subheadline": article["subheadline"],
            "content": article["content"],
            "category": cat,
            "filename": filename,
            "reading_time": read_time,
            "breadcrumbs": breadcrumbs,
            "json_ld": json_ld,
            "related_posts": related_posts,
        }

        html = article_template.render(**context)
        write_html(output_path, html)
        print(f"  Generated {cat}/{filename}")

    # ------------------------------------------------------------------
    # 2. Generate Category Hubs
    # ------------------------------------------------------------------
    print("Generating category hubs...")
    for cat, articles_in_cat in grouped.items():
        folder = os.path.join(OUTPUT_DIR, cat)
        ensure_dir(folder)

        output_path = os.path.join(folder, "index.html")

        hub_articles = []
        for a in articles_in_cat:
            hub_articles.append({
                "title": a["title"],
                "url": f"{a['slug']}.html",
                "description": a["meta_description"],
            })

        # Calculate base_path for the hub page (same depth as articles in that category)
        base_path = calculate_base_path(output_path, output_root=OUTPUT_DIR)

        context = {
            "base_path": base_path,
            "category": cat,
            "articles": hub_articles,
            "title": f"{cat.capitalize()} · ExpatScore.de",
            "meta_description": f"Alle Artikel zum Thema {cat} – Bankkonten, Versicherungen, Schufa-Guides.",
        }

        html = hub_template.render(**context)
        write_html(output_path, html)
        print(f"  Generated {cat}/index.html")

    # ------------------------------------------------------------------
    # 3. Generate Homepage (index.html)
    # ------------------------------------------------------------------
    print("Generating homepage...")
    homepage_output = os.path.join(OUTPUT_DIR, "index.html")
    base_path_home = calculate_base_path(homepage_output, output_root=OUTPUT_DIR)  # should be ""

    # Prepare context for homepage
    # Categories: list of dicts with name and url
    category_list = [{"name": cat.capitalize(), "url": f"{cat}/index.html"} for cat in categories]
    # Latest articles: get first 5 from overall articles list
    latest_articles = get_latest_articles(articles, count=5)
    latest_list = []
    for a in latest_articles:
        latest_list.append({
            "title": a["title"],
            "url": f"{a['category']}/{a['slug']}.html",
            "description": a["meta_description"],
        })

    context_home = {
        "base_path": base_path_home,
        "categories": category_list,
        "latest_articles": latest_list,
        "title": "ExpatScore.de – Finanzwissen für Expats in Deutschland",
        "meta_description": "Unabhängige Ratgeber zu Bankkonten, Versicherungen und Schufa für Expats in Deutschland."
    }

    html = index_template.render(**context_home)
    write_html(homepage_output, html)
    print("  Generated index.html")

    # ------------------------------------------------------------------
    # 4. Generate Static Pages (from templates)
    # ------------------------------------------------------------------
    print("Generating static pages...")
    for page_config in STATIC_PAGES_CONFIG:
        output_rel = page_config['output']
        template_name = page_config['template']
        output_path = os.path.join(OUTPUT_DIR, output_rel)

        # Ensure subdirectories exist (e.g., for guides/)
        ensure_dir(os.path.dirname(output_path))

        # Load template
        try:
            template = env.get_template(template_name)
        except Exception as e:
            print(f"  ⚠️ Warning: Could not load template '{template_name}': {e}")
            continue

        # Calculate base_path for this static page
        base_path = calculate_base_path(output_path, output_root=OUTPUT_DIR)

        # Basic context (can be extended if needed)
        context = {
            "base_path": base_path,
            "title": f"{os.path.splitext(os.path.basename(output_rel))[0].replace('-', ' ').title()} · ExpatScore.de",
            "meta_description": f"{os.path.splitext(os.path.basename(output_rel))[0].replace('-', ' ')} Seite auf ExpatScore.de",
        }

        html = template.render(**context)
        write_html(output_path, html)
        print(f"  Generated {output_rel}")

    # ------------------------------------------------------------------
    # 5. Generate Sitemap
    # ------------------------------------------------------------------
    print("Generating sitemap.xml...")
    generate_sitemap(articles, STATIC_PAGES, categories)

    # ------------------------------------------------------------------
    # 6. Copy Assets (with improved feedback)
    # ------------------------------------------------------------------
    print("Copying asset files to docs/...")
    copy_assets()

    print("\n✅ All done. Site generated in 'docs/' folder.")

if __name__ == "__main__":
    main()