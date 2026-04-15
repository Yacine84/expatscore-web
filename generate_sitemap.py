#!/usr/bin/env python3
"""
ExpatScore.de — Sitemap Regenerator
====================================

What it does:
  1. Scans /docs/ for all .html files.
  2. For each file: extracts canonical URL from <link rel="canonical">.
     If missing, derives URL from filesystem path + cleanUrls rules.
  3. Skips noindex pages, GSC verification file, and any file in a
     configurable EXCLUDE list.
  4. Assigns priority + changefreq based on URL pattern (see PRIORITY_RULES).
  5. Uses each file's mtime for <lastmod> (real modification date, not today).
  6. Outputs a valid sitemap.xml to /docs/sitemap.xml.
  7. Diffs old vs new and reports what changed.

Safety:
  Dry-run default. Backs up old sitemap before overwriting.

Usage:
  python3 regenerate_sitemap.py                   # preview diff + proposed XML
  python3 regenerate_sitemap.py --apply           # write new sitemap
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
SITE_BASE = 'https://expatscore.de'          # NO 'www' – strictly non-www

# Files to exclude from sitemap even if they exist as .html
EXCLUDE_FILES = {
    'google9536a7cd025919e5.html',  # GSC verification
    # Add future exclusions here
}

# Exclude anything whose stem STARTS with these prefixes
EXCLUDE_PREFIXES = (
    'google',  # Any Google verification file
    '_',       # Partials / private files
)

# URL pattern → (priority, changefreq)
# Rules checked in order; first match wins.
# URL is the final clean URL (e.g. '/schufa-guide', '/blog/foo').
PRIORITY_RULES = [
    # (regex_pattern,                      priority, changefreq)
    (r'^/$',                               '1.0',   'weekly'),
    (r'^/blog$',                           '0.8',   'weekly'),           # blog index
    (r'^/blog/',                           '0.7',   'monthly'),          # individual posts
    (r'^/schufa-simulator$',               '0.9',   'weekly'),
    (r'^/blue-card-tool$',                 '0.9',   'weekly'),
    (r'^/(banking|insurance)$',            '0.8',   'weekly'),
    (r'^/schufa-guide$',                   '0.85',  'monthly'),
    (r'^/how-to-get-schufa-germany$',      '0.85',  'monthly'),
    (r'^/about$',                          '0.5',   'monthly'),
    (r'^/(impressum|datenschutz|affiliate-hinweis)$', '0.3', 'yearly'),
]
# Fallback for anything not matched above
DEFAULT_PRIORITY   = '0.6'
DEFAULT_CHANGEFREQ = 'monthly'


# ─────────────────────────────────────────────────────────────
# HTML INSPECTION
# ─────────────────────────────────────────────────────────────
CANONICAL_RE = re.compile(
    r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE
)
CANONICAL_RE_REVERSED = re.compile(
    r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
    re.IGNORECASE
)
NOINDEX_RE = re.compile(
    r'<meta\s+[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex',
    re.IGNORECASE
)


def extract_canonical(html: str) -> str | None:
    """Return canonical URL if declared in <head>, else None."""
    # Try rel-first order then href-first order (either is valid HTML)
    m = CANONICAL_RE.search(html) or CANONICAL_RE_REVERSED.search(html)
    return m.group(1).strip() if m else None


def is_noindex(html: str) -> bool:
    return bool(NOINDEX_RE.search(html))


# ─────────────────────────────────────────────────────────────
# URL DERIVATION
# ─────────────────────────────────────────────────────────────
def derive_url_from_path(html_file: Path, docs_path: Path) -> str:
    """
    Derive the public clean URL for a file that has no canonical declared.
    Matches Vercel's cleanUrls + /blog/:slug rewrite:
      docs/schufa-guide.html        → /schufa-guide
      docs/blog/foo.html            → /blog/foo
      docs/index.html               → /
    """
    rel = html_file.relative_to(docs_path)
    parts = rel.parts
    stem = html_file.stem  # filename without .html

    if stem == 'index' and len(parts) == 1:
        return '/'

    # Everything else: /<path-without-extension>
    # Vercel cleanUrls strips .html regardless of depth
    path_no_ext = '/'.join(parts[:-1] + (stem,))
    return '/' + path_no_ext


def is_absolute_url(url: str) -> bool:
    return url.startswith('http://') or url.startswith('https://')


def to_absolute(url: str) -> str:
    """Canonical may be absolute OR root-relative. Normalise to absolute."""
    if is_absolute_url(url):
        return url
    if url.startswith('/'):
        return SITE_BASE + url
    # Relative URL in a canonical is bad practice but handle it
    return SITE_BASE + '/' + url


# ─────────────────────────────────────────────────────────────
# PRIORITY / CHANGEFREQ RESOLUTION
# ─────────────────────────────────────────────────────────────
def resolve_priority_freq(path_url: str) -> tuple[str, str]:
    """path_url is the root-relative URL like '/schufa-guide'."""
    for pattern, priority, freq in PRIORITY_RULES:
        if re.match(pattern, path_url):
            return priority, freq
    return DEFAULT_PRIORITY, DEFAULT_CHANGEFREQ


# ─────────────────────────────────────────────────────────────
# FILE WALK + ENTRY BUILD
# ─────────────────────────────────────────────────────────────
def should_exclude(html_file: Path, docs_path: Path) -> tuple[bool, str]:
    """Returns (excluded, reason)."""
    if html_file.name in EXCLUDE_FILES:
        return True, 'in EXCLUDE_FILES'
    if any(html_file.stem.startswith(p) for p in EXCLUDE_PREFIXES):
        return True, f'stem starts with excluded prefix'
    # Skip files directly inside /docs/blog/ that are intentionally left out
    # (none currently, but hook is here if needed)
    return False, ''


def build_sitemap_entries(docs_path: Path, verbose: bool = False) -> list[dict]:
    """
    Walk /docs/, produce one entry per indexable .html file.
    Entry keys: loc, lastmod, changefreq, priority, source_file, source_canonical
    """
    entries = []
    skipped = []

    for html_file in sorted(docs_path.rglob('*.html')):
        rel = html_file.relative_to(docs_path)

        excluded, reason = should_exclude(html_file, docs_path)
        if excluded:
            skipped.append((rel, reason))
            continue

        try:
            html = html_file.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            skipped.append((rel, 'non-utf8 file'))
            continue

        if is_noindex(html):
            skipped.append((rel, 'noindex meta'))
            continue

        # Canonical is the source of truth
        canonical = extract_canonical(html)
        if canonical:
            loc = to_absolute(canonical)
            source = 'canonical'
        else:
            loc = SITE_BASE + derive_url_from_path(html_file, docs_path)
            source = 'filesystem'

        # Resolve priority/freq from the PATH portion of the URL
        path_portion = loc.replace(SITE_BASE, '') or '/'
        priority, changefreq = resolve_priority_freq(path_portion)

        # Real modification date from filesystem
        mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
        lastmod = mtime.strftime('%Y-%m-%d')

        entries.append({
            'loc':        loc,
            'lastmod':    lastmod,
            'changefreq': changefreq,
            'priority':   priority,
            'source_file':      str(rel),
            'source_canonical': source,
        })

    return entries, skipped


# ─────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────
def deduplicate_entries(entries: list[dict]) -> tuple[list[dict], list[tuple]]:
    """
    If two files declare the same canonical (e.g. blog.html at root +
    /blog → /docs/blog.html rewrite), keep one entry, flag the dup.
    """
    seen = {}
    dups = []
    for e in entries:
        key = e['loc'].rstrip('/')
        if key in seen:
            dups.append((seen[key]['source_file'], e['source_file'], e['loc']))
        else:
            seen[key] = e
    return list(seen.values()), dups


# ─────────────────────────────────────────────────────────────
# XML GENERATION
# ─────────────────────────────────────────────────────────────
def generate_sitemap_xml(entries: list[dict]) -> str:
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # Sort by priority desc, then loc asc for determinism + readability
    entries_sorted = sorted(entries,
                            key=lambda e: (-float(e['priority']), e['loc']))
    for e in entries_sorted:
        lines.extend([
            '  <url>',
            f'    <loc>{escape(e["loc"])}</loc>',
            f'    <lastmod>{e["lastmod"]}</lastmod>',
            f'    <changefreq>{e["changefreq"]}</changefreq>',
            f'    <priority>{e["priority"]}</priority>',
            '  </url>',
        ])
    lines.append('</urlset>')
    return '\n'.join(lines) + '\n'


# ─────────────────────────────────────────────────────────────
# DIFF REPORTING
# ─────────────────────────────────────────────────────────────
def parse_existing_sitemap(sitemap_path: Path) -> set[str]:
    if not sitemap_path.exists():
        return set()
    text = sitemap_path.read_text(encoding='utf-8')
    return set(re.findall(r'<loc>([^<]+)</loc>', text))


def print_diff(old_urls: set[str], new_entries: list[dict]) -> None:
    new_urls = {e['loc'] for e in new_entries}
    added   = sorted(new_urls - old_urls)
    removed = sorted(old_urls - new_urls)
    kept    = sorted(new_urls & old_urls)

    print(f"\n📊 DIFF vs current sitemap:")
    print(f"   {len(kept):>3} unchanged")
    print(f"   {len(added):>3} added    (not in current sitemap — Google hasn't seen these!)")
    print(f"   {len(removed):>3} removed  (in current sitemap but no longer on disk)")

    if added:
        print(f"\n   ➕ NEW URLS:")
        for url in added:
            print(f"      {url}")
    if removed:
        print(f"\n   ➖ REMOVED URLS:")
        for url in removed:
            print(f"      {url}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--docs', default='./docs')
    p.add_argument('--apply', action='store_true', help='Write the new sitemap')
    p.add_argument('--verbose', action='store_true')
    args = p.parse_args()

    docs_path = Path(args.docs).resolve()
    if not docs_path.exists():
        print(f"❌ docs path not found: {docs_path}")
        sys.exit(1)

    sitemap_path = docs_path / 'sitemap.xml'
    print(f"📂 Scanning: {docs_path}")
    print(f"📄 Target:   {sitemap_path}\n")

    entries, skipped = build_sitemap_entries(docs_path, verbose=args.verbose)
    entries, dups = deduplicate_entries(entries)

    if skipped:
        print(f"⏭️  Skipped {len(skipped)} file(s):")
        for rel, reason in skipped:
            print(f"   {rel}  ({reason})")
        print()

    if dups:
        print(f"⚠️  {len(dups)} duplicate canonical(s) detected:")
        for file_a, file_b, loc in dups:
            print(f"   {file_a} ↔ {file_b}  →  {loc}")
        print("   Kept first occurrence. Review canonicals if unintended.\n")

    # Preview sample
    print(f"✅ {len(entries)} URL(s) will be in sitemap:\n")
    print(f"   {'PRIORITY':<10}{'FREQ':<12}URL")
    print(f"   {'─' * 80}")
    for e in sorted(entries, key=lambda x: (-float(x['priority']), x['loc'])):
        print(f"   {e['priority']:<10}{e['changefreq']:<12}{e['loc']}")
    print()

    # Diff vs current
    old_urls = parse_existing_sitemap(sitemap_path)
    print_diff(old_urls, entries)

    new_xml = generate_sitemap_xml(entries)

    if not args.apply:
        print("\n📄 Proposed sitemap.xml (first 40 lines):")
        print('   ' + '\n   '.join(new_xml.split('\n')[:40]))
        if len(new_xml.split('\n')) > 40:
            print(f"   ... ({len(new_xml.split(chr(10)))} total lines)")
        print("\nRe-run with --apply to write the new sitemap.")
        return

    # ── APPLY ────────────────────────────────────────
    if sitemap_path.exists():
        backup = sitemap_path.with_suffix(
            f'.xml.bak.{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        shutil.copy2(sitemap_path, backup)
        print(f"\n💾 Backup: {backup}")

    sitemap_path.write_text(new_xml, encoding='utf-8')
    print(f"✅ Wrote: {sitemap_path}")
    print(f"   {len(entries)} URLs")
    print("\nNext steps:")
    print("  1. git add docs/sitemap.xml && git commit -m 'chore: regenerate sitemap'")
    print("  2. git push  (Vercel deploys)")
    print("  3. Google Search Console → Sitemaps → resubmit https://expatscore.de/sitemap.xml")


if __name__ == '__main__':
    main()