#!/usr/bin/env python3
"""
ExpatScore.de — Sitemap Regenerator  v3.0
==========================================

WHAT'S NEW IN v3.0
──────────────────
• Strict file-type guard: only files with a .html extension are ever scanned.
  This automatically excludes system/cache artefacts such as:
    .dedup_registry   .session_state   built_pages.json   *.bak   *.log
  without needing them to be listed explicitly.

• Expanded EXCLUDE_STEMS set covers every known cache/system filename stem
  so accidental .html wrappers around state files are also caught.

• CSV rows are validated before entry: a row must have a non-empty slug AND
  a non-empty category to be included. Blank trailer rows and header-only
  artefacts are silently skipped.

• SOURCE column in the preview table clearly labels whether each URL came
  from a canonical tag, filesystem path derivation, or the CSV.

• --csv flag lets you point at any CSV without editing the script.

WHAT IT DOES (unchanged behaviour)
───────────────────────────────────
1.  Scans /docs/ recursively for .html files.
2.  For each file: extracts canonical URL from <link rel="canonical">.
    Falls back to filesystem path + Vercel cleanUrls derivation.
3.  Skips noindex pages, excluded stems, and non-.html files.
4.  Assigns priority + changefreq based on URL pattern (PRIORITY_RULES).
5.  Uses each file's mtime for <lastmod>.
6.  Reads providers.csv and adds one entry per valid (slug, category) row
    not already present from the filesystem scan.
7.  Deduplicates on full URL — filesystem beats CSV on collision.
8.  Outputs docs/sitemap.xml, diffs against the old version.

SAFETY
──────
Dry-run by default.  Backs up the old sitemap before overwriting.

USAGE
─────
  python3 generate_sitemap.py                                  # preview
  python3 generate_sitemap.py --apply                          # write
  python3 generate_sitemap.py --apply --csv path/to/file.csv  # custom CSV
  python3 generate_sitemap.py --apply --verbose                # verbose
"""

import argparse
import csv
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────
SITE_BASE = "https://expatscore.de"    # strictly non-www

# Default CSV path (overridable via --csv).
DEFAULT_CSV_PATH = Path(__file__).parent / "data" / "providers.csv"

# URL pattern for programmatic provider pages derived from CSV rows:
#   /{category}/{slug}  →  https://expatscore.de/banking/n26
PROGRAMMATIC_URL_TEMPLATE = "/{category}/{slug}"

# ── Files / stems to exclude from the sitemap ────────────────────────────────
#
# EXCLUDE_FILES  — exact filenames (with extension) that must be skipped.
EXCLUDE_FILES: set[str] = {
    "google9536a7cd025919e5.html",   # GSC verification file
}

# EXCLUDE_STEMS  — filename stems (no extension) that must be skipped.
# This catches both .html files and any non-.html artefacts that slip through.
EXCLUDE_STEMS: set[str] = {
    # System / cache files
    "dedup_registry",
    "session_state",
    "built_pages",
    # Legal / utility pages (low-value, yearly)
    # These are NOT excluded from the sitemap — they get priority 0.3.
    # Add stems here only for pages you want COMPLETELY absent from sitemap.xml.
    "404",
    # Google / verification files (stems only; full filenames also in EXCLUDE_FILES)
    "google9536a7cd025919e5",
}

# EXCLUDE_STEM_PREFIXES — stems starting with these strings are always excluded.
EXCLUDE_STEM_PREFIXES: tuple[str, ...] = (
    "google",   # any GSC / Google tag manager verification file
    "_",        # private / partial template fragments
)

# URL pattern → (priority, changefreq).
# Rules are checked top-to-bottom; first match wins.
# URL is the root-relative clean path (e.g. "/banking/n26", "/blog/foo").
PRIORITY_RULES: list[tuple[str, str, str]] = [
    # pattern                                           priority  changefreq
    (r"^/$",                                            "1.0",    "weekly"),
    (r"^/blog$",                                        "0.8",    "weekly"),
    (r"^/schufa-simulator$",                            "0.9",    "weekly"),
    (r"^/blue-card-tool$",                              "0.9",    "weekly"),
    (r"^/(banking|insurance)$",                         "0.8",    "weekly"),
    # Programmatic provider pages  ← must precede the /blog/ rule
    (r"^/(banking|insurance)/[^/]+$",                   "0.75",   "monthly"),
    (r"^/schufa-guide$",                                "0.85",   "monthly"),
    (r"^/how-to-get-schufa-germany$",                   "0.85",   "monthly"),
    (r"^/blog/",                                        "0.7",    "monthly"),
    (r"^/about$",                                       "0.5",    "monthly"),
    (r"^/(impressum|datenschutz|affiliate-hinweis)$",   "0.3",    "yearly"),
]
DEFAULT_PRIORITY   = "0.6"
DEFAULT_CHANGEFREQ = "monthly"


# ─────────────────────────────────────────────────────────────
# HTML INSPECTION
# ─────────────────────────────────────────────────────────────
_CANONICAL_RE = re.compile(
    r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_CANONICAL_REV = re.compile(
    r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
    re.IGNORECASE,
)
_NOINDEX_RE = re.compile(
    r'<meta\s+[^>]*name=["\']robots["\'][^>]*content=["\'][^"\']*noindex',
    re.IGNORECASE,
)


def extract_canonical(html: str) -> str | None:
    """Return the canonical URL declared in <head>, or None if absent."""
    m = _CANONICAL_RE.search(html) or _CANONICAL_REV.search(html)
    return m.group(1).strip() if m else None


def is_noindex(html: str) -> bool:
    return bool(_NOINDEX_RE.search(html))


# ─────────────────────────────────────────────────────────────
# URL DERIVATION
# ─────────────────────────────────────────────────────────────
def derive_url_from_path(html_file: Path, docs_path: Path) -> str:
    """
    Derive the public clean URL for a file that carries no canonical tag.
    Mirrors Vercel cleanUrls + /blog/:slug rewrite:
      docs/schufa-guide.html   →   /schufa-guide
      docs/blog/foo.html       →   /blog/foo
      docs/index.html          →   /
    """
    rel  = html_file.relative_to(docs_path)
    parts = rel.parts
    stem  = html_file.stem

    if stem == "index" and len(parts) == 1:
        return "/"

    path_no_ext = "/".join(parts[:-1] + (stem,))
    return "/" + path_no_ext


def to_absolute(url: str) -> str:
    """Normalise a canonical URL (absolute or root-relative) to absolute."""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("/"):
        return SITE_BASE + url
    return SITE_BASE + "/" + url


# ─────────────────────────────────────────────────────────────
# PRIORITY / CHANGEFREQ
# ─────────────────────────────────────────────────────────────
def resolve_priority_freq(path_url: str) -> tuple[str, str]:
    """
    path_url is the root-relative URL (e.g. '/schufa-guide', '/banking/n26').
    Returns (priority, changefreq).
    """
    for pattern, priority, freq in PRIORITY_RULES:
        if re.match(pattern, path_url):
            return priority, freq
    return DEFAULT_PRIORITY, DEFAULT_CHANGEFREQ


# ─────────────────────────────────────────────────────────────
# EXCLUSION CHECK
# ─────────────────────────────────────────────────────────────
def should_exclude(html_file: Path) -> tuple[bool, str]:
    """
    Return (True, reason) if this file must not appear in sitemap.xml.

    Checks (in order):
      1. File extension is NOT .html           → excluded (non-html artefact)
      2. Exact filename is in EXCLUDE_FILES    → excluded
      3. Stem is in EXCLUDE_STEMS              → excluded (system/cache file)
      4. Stem starts with an excluded prefix   → excluded
    """
    # Guard 1 — extension
    if html_file.suffix.lower() != ".html":
        return True, f"non-html suffix ({html_file.suffix!r})"

    stem = html_file.stem.lower()

    # Guard 2 — exact filename
    if html_file.name in EXCLUDE_FILES:
        return True, "in EXCLUDE_FILES"

    # Guard 3 — known system/cache stem
    if stem in EXCLUDE_STEMS:
        return True, "excluded system/cache stem"

    # Guard 4 — excluded prefix
    if any(stem.startswith(pfx) for pfx in EXCLUDE_STEM_PREFIXES):
        return True, "excluded stem prefix"

    return False, ""


# ─────────────────────────────────────────────────────────────
# FILESYSTEM WALK
# ─────────────────────────────────────────────────────────────
def build_filesystem_entries(
    docs_path: Path,
    verbose: bool = False,
) -> tuple[list[dict], list[tuple]]:
    """
    Walk docs_path recursively and return one sitemap entry per indexable page.

    Entry keys: loc, lastmod, changefreq, priority, source_file, source_canonical
    """
    entries: list[dict] = []
    skipped: list[tuple] = []

    # rglob("*") instead of rglob("*.html") so the exclusion check can log
    # non-html artefacts that would otherwise be silently invisible.
    for path in sorted(docs_path.rglob("*")):
        if path.is_dir():
            continue

        rel = path.relative_to(docs_path)
        excluded, reason = should_exclude(path)
        if excluded:
            skipped.append((rel, reason))
            continue

        try:
            html = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skipped.append((rel, "non-utf8 content"))
            continue

        if is_noindex(html):
            skipped.append((rel, "noindex meta tag"))
            continue

        canonical = extract_canonical(html)
        if canonical:
            loc    = to_absolute(canonical)
            source = "canonical"
        else:
            loc    = SITE_BASE + derive_url_from_path(path, docs_path)
            source = "filesystem"

        path_portion = loc.replace(SITE_BASE, "") or "/"
        priority, changefreq = resolve_priority_freq(path_portion)

        mtime   = datetime.fromtimestamp(path.stat().st_mtime)
        lastmod = mtime.strftime("%Y-%m-%d")

        entries.append(
            {
                "loc":              loc,
                "lastmod":          lastmod,
                "changefreq":       changefreq,
                "priority":         priority,
                "source_file":      str(rel),
                "source_canonical": source,
            }
        )

        if verbose:
            print(f"   + {rel}  [{source}]  →  {loc}")

    return entries, skipped


# ─────────────────────────────────────────────────────────────
# CSV INTEGRATION
# ─────────────────────────────────────────────────────────────
def load_csv_providers(csv_path: Path) -> list[dict]:
    """
    Load provider rows from the CSV.

    Expected columns (header row required; column order does not matter):
        name      display name,         e.g. "N26"
        slug      URL-safe identifier,  e.g. "n26"
        url       destination URL,      e.g. "https://n26.com/r/..."
        category  routing bucket,       e.g. "banking" | "insurance"

    Rows missing both slug and category are treated as blank/trailer rows and
    silently skipped.  Returns [] with a warning if the file is absent.
    """
    if not csv_path.exists():
        print(f"⚠️  CSV not found: {csv_path}")
        print("   Sitemap will only contain pages already on disk.")
        return []
    try:
        with csv_path.open(encoding="utf-8", newline="") as fh:
            rows = [
                r
                for r in csv.DictReader(fh)
                if r.get("slug", "").strip() or r.get("category", "").strip()
            ]
        print(f"📋 Loaded {len(rows)} provider row(s) from {csv_path.name}")
        return rows
    except Exception as exc:
        print(f"⚠️  Could not read CSV ({exc}) — CSV entries omitted.")
        return []


def build_csv_entries(providers: list[dict], today: str) -> list[dict]:
    """
    Generate one sitemap entry per valid CSV row.

    A row is valid when it has a non-empty slug AND a non-empty category.
    Invalid / incomplete rows are silently skipped so a partially-filled CSV
    never causes a crash or a malformed sitemap entry.

    URL pattern:  /{category}/{slug}
    e.g.  /banking/n26  →  https://expatscore.de/banking/n26
    """
    entries: list[dict] = []
    skipped_rows = 0
    for p in providers:
        slug     = p.get("slug",     "").strip()
        category = p.get("category", "").strip().lower()
        if not slug or not category:
            skipped_rows += 1
            continue

        path_url = PROGRAMMATIC_URL_TEMPLATE.format(category=category, slug=slug)
        loc      = SITE_BASE + path_url
        priority, changefreq = resolve_priority_freq(path_url)

        entries.append(
            {
                "loc":              loc,
                "lastmod":          today,
                "changefreq":       changefreq,
                "priority":         priority,
                "source_file":      f"csv:{category}/{slug}",
                "source_canonical": "csv",
            }
        )

    if skipped_rows:
        print(f"⚠️  {skipped_rows} CSV row(s) skipped (missing slug or category)")

    return entries


# ─────────────────────────────────────────────────────────────
# DEDUPLICATION
# ─────────────────────────────────────────────────────────────
def deduplicate_entries(
    entries: list[dict],
) -> tuple[list[dict], list[tuple]]:
    """
    Remove duplicate URLs, keeping the first occurrence.
    Since filesystem entries are prepended before CSV entries, the real HTML
    file (with its accurate mtime lastmod) always wins over a CSV-only entry.
    """
    seen: dict[str, dict] = {}
    dups: list[tuple]     = []
    for e in entries:
        key = e["loc"].rstrip("/")
        if key in seen:
            dups.append((seen[key]["source_file"], e["source_file"], e["loc"]))
        else:
            seen[key] = e
    return list(seen.values()), dups


# ─────────────────────────────────────────────────────────────
# XML GENERATION
# ─────────────────────────────────────────────────────────────
def generate_sitemap_xml(entries: list[dict]) -> str:
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    # Priority descending, then URL ascending — deterministic and readable
    for e in sorted(entries, key=lambda e: (-float(e["priority"]), e["loc"])):
        lines.extend(
            [
                "  <url>",
                f'    <loc>{escape(e["loc"])}</loc>',
                f'    <lastmod>{e["lastmod"]}</lastmod>',
                f'    <changefreq>{e["changefreq"]}</changefreq>',
                f'    <priority>{e["priority"]}</priority>',
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


# ─────────────────────────────────────────────────────────────
# DIFF REPORTING
# ─────────────────────────────────────────────────────────────
def parse_existing_sitemap(sitemap_path: Path) -> set[str]:
    if not sitemap_path.exists():
        return set()
    return set(re.findall(r"<loc>([^<]+)</loc>", sitemap_path.read_text(encoding="utf-8")))


def print_diff(old_urls: set[str], new_entries: list[dict]) -> None:
    new_urls = {e["loc"] for e in new_entries}
    added    = sorted(new_urls - old_urls)
    removed  = sorted(old_urls - new_urls)
    kept     = sorted(new_urls & old_urls)

    print(f"\n📊 DIFF vs current sitemap:")
    print(f"   {len(kept):>4} unchanged")
    print(f"   {len(added):>4} added    ← Google hasn't seen these yet!")
    print(f"   {len(removed):>4} removed  ← in old sitemap but no longer present")

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
def main() -> None:
    p = argparse.ArgumentParser(
        description="ExpatScore sitemap regenerator v3.0 — filesystem + CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 generate_sitemap.py                          # dry-run preview
  python3 generate_sitemap.py --apply                  # write sitemap.xml
  python3 generate_sitemap.py --apply --verbose        # verbose output
  python3 generate_sitemap.py --apply --csv /path/to/providers.csv
""",
    )
    p.add_argument(
        "--docs",    default="./docs",
        help="Path to the docs/ directory (default: ./docs)",
    )
    p.add_argument(
        "--csv",     default=str(DEFAULT_CSV_PATH),
        help="Path to providers.csv (default: data/providers.csv)",
    )
    p.add_argument(
        "--apply",   action="store_true",
        help="Write the new sitemap.xml (default: dry-run preview only)",
    )
    p.add_argument(
        "--verbose", action="store_true",
        help="Print each discovered file and its resolved URL during the scan",
    )
    args = p.parse_args()

    docs_path = Path(args.docs).resolve()
    csv_path  = Path(args.csv).resolve()

    if not docs_path.exists():
        print(f"❌ docs path not found: {docs_path}")
        sys.exit(1)

    sitemap_path = docs_path / "sitemap.xml"
    today        = datetime.now().strftime("%Y-%m-%d")

    print(f"📂 Scanning:  {docs_path}")
    print(f"📋 CSV:       {csv_path}")
    print(f"📄 Target:    {sitemap_path}\n")

    # ── Source 1: filesystem ──────────────────────────────────────────────
    fs_entries, skipped = build_filesystem_entries(docs_path, verbose=args.verbose)

    if skipped:
        # Only report skipped files that are NOT merely non-html artefacts;
        # those are too noisy and expected (node_modules, etc.)
        meaningful = [
            (r, reason)
            for r, reason in skipped
            if "non-html suffix" not in reason
        ]
        if meaningful:
            print(f"⏭️  Skipped {len(meaningful)} file(s) (non-html excluded separately):")
            for rel, reason in meaningful:
                print(f"   {rel}  ({reason})")
            print()

        non_html = sum(1 for _, r in skipped if "non-html suffix" in r)
        if non_html:
            print(f"🛡  Blocked {non_html} non-html artefact(s) from sitemap "
                  f"(.dedup_registry, .session_state, etc.)\n")

    # ── Source 2: CSV ─────────────────────────────────────────────────────
    providers   = load_csv_providers(csv_path)
    csv_entries = build_csv_entries(providers, today)

    if csv_entries:
        print(f"📋 {len(csv_entries)} programmatic URL(s) generated from CSV\n")

    # ── Merge: filesystem first so its lastmod/canonical wins on collision ─
    all_entries, dups = deduplicate_entries(fs_entries + csv_entries)

    if dups:
        print(f"⚠️  {len(dups)} duplicate URL(s) found (first occurrence kept):")
        for file_a, file_b, loc in dups:
            print(f"   {file_a}  ↔  {file_b}  →  {loc}")
        print("   Check canonical tags if this is unexpected.\n")

    # ── Preview table ─────────────────────────────────────────────────────
    print(f"✅ {len(all_entries)} URL(s) will be in sitemap:\n")
    print(f"   {'PRIO':<7}{'FREQ':<12}{'SOURCE':<12}URL")
    print(f"   {'─' * 88}")
    for e in sorted(all_entries, key=lambda x: (-float(x["priority"]), x["loc"])):
        print(
            f"   {e['priority']:<7}{e['changefreq']:<12}"
            f"{e['source_canonical']:<12}{e['loc']}"
        )
    print()

    # ── Diff ──────────────────────────────────────────────────────────────
    old_urls = parse_existing_sitemap(sitemap_path)
    print_diff(old_urls, all_entries)

    new_xml = generate_sitemap_xml(all_entries)

    if not args.apply:
        print("\n📄 Proposed sitemap.xml (first 50 lines):")
        lines = new_xml.split("\n")
        print("   " + "\n   ".join(lines[:50]))
        if len(lines) > 50:
            print(f"   … ({len(lines)} total lines)")
        print("\nRe-run with --apply to write the new sitemap.")
        return

    # ── Write ─────────────────────────────────────────────────────────────
    if sitemap_path.exists():
        backup = sitemap_path.with_suffix(
            f".xml.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        shutil.copy2(sitemap_path, backup)
        print(f"\n💾 Backup: {backup}")

    sitemap_path.write_text(new_xml, encoding="utf-8")
    print(f"✅ Wrote: {sitemap_path}")
    print(
        f"   {len(all_entries)} URLs total  "
        f"({len(fs_entries)} from filesystem · "
        f"{len(csv_entries)} from CSV · "
        f"{len(dups)} duplicate(s) dropped)"
    )
    print("\nNext steps:")
    print("  1. git add docs/sitemap.xml && git commit -m 'chore: regenerate sitemap'")
    print("  2. git push  (Vercel/Cloudflare deploys automatically)")
    print("  3. Google Search Console → Sitemaps → resubmit https://expatscore.de/sitemap.xml")


if __name__ == "__main__":
    main()