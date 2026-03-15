#!/usr/bin/env python3
"""
agent.py – Static site generator for ExpatScore.de
Reads article data from a CSV, generates HTML pages using Jinja2 templates,
creates hub pages and a root index, and finally generates a sitemap.xml.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime  # added for sitemap date

import pandas as pd
from jinja2 import Environment, FileSystemLoader
import markdown

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
PUBLISH_THRESHORDS_WORDS = 1               # minimum word count to publish an article (set to 1 for testing)
DEFAULT_DATA_PATH = Path("data.csv")       # now directly in the project root
DEFAULT_OUTPUT_DIR = Path("docs")
DEFAULT_TEMPLATES_DIR = Path("templates")
RAW_CONTENT_DIR = Path("raw_content")      # folder containing Markdown files

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# ContentAgent class
# ----------------------------------------------------------------------
class ContentAgent:
    """Generates static HTML pages for articles, category hubs, and the root index."""

    def __init__(self, data_path: Path, output_dir: Path, templates_dir: Path):
        self.data_path = data_path
        self.output_dir = output_dir
        self.templates_dir = templates_dir

        # Load Jinja2 environment and templates
        self.env = Environment(loader=FileSystemLoader(templates_dir))
        self.article_template = self.env.get_template("article.html")
        self.hub_template = self.env.get_template("hub.html")

        # Data containers
        self.df = None
        self.articles_by_category = {}

        # Track generated pages for sitemap
        self.generated_articles = []   # list of (category, slug)
        self.generated_hubs = []        # list of category names

    def _load_data(self) -> None:
        """Read the CSV, validate required columns, and group articles by category."""
        if not self.data_path.exists():
            logger.error(f"Data file not found: {self.data_path}")
            sys.exit(1)

        self.df = pd.read_csv(self.data_path)
        required_cols = {"slug", "category", "title", "meta_description", "h1", "subheadline"}
        if not required_cols.issubset(self.df.columns):
            missing = required_cols - set(self.df.columns)
            logger.error(f"Missing columns in CSV: {missing}")
            sys.exit(1)

        # Group by category for hub pages
        self.articles_by_category = {
            cat: group.to_dict(orient="records")
            for cat, group in self.df.groupby("category")
        }
        logger.info(f"Loaded {len(self.df)} articles in {len(self.articles_by_category)} categories.")

    @staticmethod
    def _word_count(html: str) -> int:
        """Return the number of words in HTML content (simple tag stripping)."""
        import re
        text = re.sub(r"<[^>]+>", "", html)          # remove HTML tags
        words = re.findall(r"\b\w+\b", text)
        return len(words)

    @staticmethod
    def _wrap_tables_in_div(html: str) -> str:
        """Wrap all <table> elements in a <div class="table-responsive">."""
        import re
        return re.sub(r"(<table.*?</table>)", r'<div class="table-responsive">\1</div>', html, flags=re.DOTALL)

    def _get_base_path(self, output_path: Path) -> str:
        """
        Return the relative path prefix needed to reach the root directory
        from the directory containing `output_path`.
        - If output_path is in the root (e.g., 'index.html') -> returns ''
        - If output_path is one level deep (e.g., 'versicherung/index.html') -> returns '../'
        - Deeper levels return more '../' as needed.
        """
        rel_dir = output_path.parent.relative_to(self.output_dir)
        if rel_dir == Path('.'):
            return ''
        depth = len(rel_dir.parts)
        return '../' * depth

    def _get_related_posts(self, row: pd.Series, limit: int = 3) -> list:
        """Return a list of related articles from the same category (excluding current)."""
        category = row['category']
        current_slug = row['slug']
        articles_in_cat = self.articles_by_category.get(category, [])
        related = [
            {"title": a['title'], "url": f"{a['slug']}.html", "description": a['meta_description']}
            for a in articles_in_cat if a['slug'] != current_slug
        ]
        return related[:limit]

    def generate_article_html(self, row: pd.Series, content_html: str) -> None:
        """Generate a single article HTML file."""
        slug = row['slug']
        category = row['category']
        filename = f"{slug}.html"
        folder = Path(self.output_dir) / category
        folder.mkdir(parents=True, exist_ok=True)
        output_path = folder / filename

        # Check word count threshold
        final_words = self._word_count(content_html)
        if final_words < PUBLISH_THRESHORDS_WORDS:
            logger.warning(
                f"Content for {slug} has only {final_words} words "
                f"(<{PUBLISH_THRESHORDS_WORDS}). Skipping HTML generation."
            )
            return

        # Table responsiveness: ensure all tables are wrapped
        content_html = self._wrap_tables_in_div(content_html)

        # NEW: Wrap the entire article content in a div with class "content-article"
        # This enables the modern desktop layout (centered, max-width) from style.css
        content_html = f'<div class="content-article">\n{content_html}\n</div>'

        reading_time = max(1, final_words // 200)

        breadcrumbs = [
            {"name": "Home", "url": f"{self._get_base_path(output_path)}index.html"},
            {"name": category.capitalize(), "url": f"./index.html"},
            {"name": row['title'], "url": None}
        ]

        # Basic JSON‑LD for article (you can extend this)
        json_ld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": row['title'],
            "description": row['meta_description'],
            "url": f"https://www.expatscore.de/{category}/{slug}.html"
        }

        related = self._get_related_posts(row)

        context = {
            "base_path": self._get_base_path(output_path),
            "title": row['title'],
            "meta_description": row['meta_description'],
            "h1": row['h1'] if row['h1'] else row['title'],
            "subheadline": row['subheadline'],
            "content": content_html,
            "category": category,
            "filename": filename,
            "related_posts": related,
            "reading_time": reading_time,
            "breadcrumbs": breadcrumbs,
            "json_ld": json_ld,
        }

        try:
            html = self.article_template.render(**context)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info(f"GENERATED: {category}/{filename} ({final_words} words)")
            self.generated_articles.append((category, slug))  # track for sitemap
        except Exception as e:
            logger.error(f"Template error for {slug}: {e}")

    def generate_hub_pages(self) -> None:
        """Generate an index.html for each category (hub page)."""
        for category, articles in self.articles_by_category.items():
            folder = Path(self.output_dir) / category
            folder.mkdir(parents=True, exist_ok=True)
            output_path = folder / "index.html"

            hub_articles = [{
                "title": a['title'],
                "url": f"{a['slug']}.html",          # same folder
                "description": a['meta_description']
            } for a in articles]

            context = {
                "base_path": self._get_base_path(output_path),
                "category": category,
                "articles": hub_articles,
                "title": f"{category.capitalize()} · ExpatScore.de",
                "meta_description": f"Alle Artikel zum Thema {category} – Bankkonten, Versicherungen, Schufa-Guides.",
            }
            try:
                html = self.hub_template.render(**context)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info(f"Generated hub: {category}/index.html")
                self.generated_hubs.append(category)  # track for sitemap
            except Exception as e:
                logger.error(f"Hub template error for {category}: {e}")

    def generate_root_index(self) -> None:
        """
        Generate the root index.html (homepage) listing all articles across categories.
        Uses hub_template with base_path="" and full URLs to articles.
        """
        output_path = Path(self.output_dir) / "index.html"
        all_articles = []
        for category, articles in self.articles_by_category.items():
            for a in articles:
                all_articles.append({
                    "title": a['title'],
                    "url": f"{category}/{a['slug']}.html",   # full relative path from root
                    "description": a['meta_description']
                })

        context = {
            "base_path": "",                                 # root
            "category": "Startseite",                        # used in section‑title
            "articles": all_articles,
            "title": "ExpatScore.de – Ihr Guide für Banking, Versicherungen & SCHUFA",
            "meta_description": (
                "Praktische Ratgeber für Expats in Deutschland: "
                "Bankkonten, Versicherungen, SCHUFA-Aufbau und mehr."
            ),
        }
        try:
            html = self.hub_template.render(**context)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Generated root index.html")
        except Exception as e:
            logger.error(f"Root index generation error: {e}")

    def generate_sitemap(self) -> None:
        """
        Generate sitemap.xml in the output directory.
        Includes homepage, all generated hub pages, and all generated articles.
        Uses current date for <lastmod>.
        """
        sitemap_path = self.output_dir / "sitemap.xml"
        base_url = "https://www.expatscore.de"
        today = datetime.now().date().isoformat()

        # Prepare list of URLs
        urls = []

        # Homepage
        urls.append(f"{base_url}/index.html")

        # Hub pages
        for category in self.generated_hubs:
            urls.append(f"{base_url}/{category}/index.html")

        # Article pages
        for category, slug in self.generated_articles:
            urls.append(f"{base_url}/{category}/{slug}.html")

        # Build XML
        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        ]
        for url in urls:
            xml_lines.append('  <url>')
            xml_lines.append(f'    <loc>{url}</loc>')
            xml_lines.append(f'    <lastmod>{today}</lastmod>')
            xml_lines.append('  </url>')
        xml_lines.append('</urlset>')

        try:
            with open(sitemap_path, "w", encoding="utf-8") as f:
                f.write("\n".join(xml_lines))
            logger.info(f"Generated sitemap with {len(urls)} entries: {sitemap_path}")
        except Exception as e:
            logger.error(f"Sitemap generation error: {e}")

    def run(self) -> None:
        """Main orchestration: load data, generate articles, hubs, root index, and sitemap."""
        self._load_data()

        # For each article, generate its HTML from Markdown source or fallback.
        for _, row in self.df.iterrows():
            slug = row['slug']

            # --- SMART FILE DISCOVERY (recursive search) ---
            # Find the first .md file matching the slug anywhere under RAW_CONTENT_DIR
            md_files = list(Path(RAW_CONTENT_DIR).rglob(f"{slug}.md"))
            if md_files:
                md_path = md_files[0]  # take the first match (should be unique)
                try:
                    with open(md_path, "r", encoding="utf-8") as f:
                        md_content = f.read()
                    content_html = markdown.markdown(
                        md_content,
                        extensions=['tables', 'fenced_code']
                    )
                    logger.debug(f"Loaded Markdown for {slug} from {md_path}")
                except Exception as e:
                    logger.error(f"Error reading {md_path}: {e}")
                    continue  # skip this article if something went wrong
            else:
                # Fallback: use meta_description as a paragraph
                content_html = f"<p>{row['meta_description']}</p>"
                logger.warning(f"Markdown file not found for {slug} (searched recursively), using meta_description as fallback")

            self.generate_article_html(row, content_html)

        self.generate_hub_pages()
        self.generate_root_index()
        self.generate_sitemap()   # added sitemap generation at the end
        logger.info("✅ All eligible pages generated.")


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # You can override paths via command line arguments
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATA_PATH
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT_DIR
    templates = Path(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_TEMPLATES_DIR

    agent = ContentAgent(data, out, templates)
    agent.run()