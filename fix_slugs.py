#!/usr/bin/env python3
"""
ExpatScore.de — URL Slug Fixer + Vercel Redirect Generator
===========================================================

What it does:
  1. Scans /docs/ for HTML files with broken German slugs (umlauts stripped,
     not transliterated — e.g. 'einlsen-fr' should be 'einloesen-fuer').
  2. Previews proposed renames. NO changes on first run without --apply.
  3. On --apply: renames files, rewrites all internal links site-wide,
     updates canonical/og:url tags in affected files, and emits a
     vercel-redirects.json snippet for 301s from old → new URLs.

Safety:
  - Dry-run is the default. You must explicitly pass --apply.
  - Creates a timestamped backup of /docs/ before any write.
  - Logs every action to slug_fix_report.txt.

Usage:
  python3 fix_slugs.py                    # preview only
  python3 fix_slugs.py --apply            # execute
  python3 fix_slugs.py --docs ./docs      # custom docs path
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# TRANSLITERATION: German → ASCII-safe URL form
# Applied to ORIGINAL German text. On already-broken slugs we
# use a dictionary of known broken→correct mappings (below).
# ─────────────────────────────────────────────────────────────
UMLAUT_MAP = {
    'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
    'Ä': 'ae', 'Ö': 'oe', 'Ü': 'ue',
    'ß': 'ss',
}

# ─────────────────────────────────────────────────────────────
# BROKEN-SLUG PATTERN REPAIRS  (word-boundary-safe)
#
# Slugs use '-' as word separator. We ONLY repair patterns that
# are bounded by '-' or string start/end, so we never mangle
# legitimate English words like "free" or "fresh".
#
# Each entry: broken_token  →  corrected_token
# These are whole slug-words (between dashes), not substrings.
# ─────────────────────────────────────────────────────────────
BROKEN_SLUG_TOKENS = {
    # 'für' stripped → 'fr'
    'fr':         'fuer',

    # 'für' variants embedded with following word (dash → glued)
    # These arise when the slugger removed the umlaut AND the dash
    # e.g. 'einlösen-für-ice' → 'einlsen-fr-ice' still has dashes,
    # so individual tokens handle it. But 'einlösen' → 'einlsen'
    # is a single corrupted token:
    'einlsen':    'einloesen',     # einlösen
    'einlsung':   'einloesung',
    'einlsungen': 'einloesungen',

    # Other umlaut-stripped German tokens commonly appearing in expat slugs
    'brgeramt':   'buergeramt',    # Bürgeramt
    'brger':      'buerger',
    'bros':       'bueros',
    'grn':        'gruen',
    'knnen':      'koennen',
    'mglich':     'moeglich',
    'mssen':      'muessen',
    'berweisung': 'ueberweisung',
    'gltig':      'gueltig',
    'tglich':     'taeglich',
    'whrend':     'waehrend',
    'whrung':     'waehrung',
    'hnlich':     'aehnlich',
    'knnte':      'koennte',
    'trglich':    'traeglich',
}


def detect_broken_slug(slug: str) -> str | None:
    """
    Return repaired slug if any token (between dashes) matches a broken
    pattern, else None. Word-boundary safe — won't touch 'free' or 'fresh'.
    """
    tokens = slug.split('-')
    changed = False
    for i, tok in enumerate(tokens):
        if tok in BROKEN_SLUG_TOKENS:
            tokens[i] = BROKEN_SLUG_TOKENS[tok]
            changed = True
    if changed:
        return '-'.join(tokens)
    return None


def find_html_files(docs_path: Path) -> list[Path]:
    """All .html files under /docs/, excluding /docs/blog/ index if present."""
    return sorted(docs_path.rglob('*.html'))


def build_rename_plan(docs_path: Path) -> list[dict]:
    """
    Scan all HTML files, identify ones whose slug (filename stem) contains
    broken-umlaut patterns, return a list of planned renames.
    """
    plan = []
    for html_file in find_html_files(docs_path):
        stem = html_file.stem
        repaired = detect_broken_slug(stem.lower())
        if repaired and repaired != stem.lower():
            new_name = repaired + html_file.suffix
            new_path = html_file.with_name(new_name)
            # Old URL path relative to /docs/
            old_url = '/' + str(html_file.relative_to(docs_path)).replace('\\', '/')
            old_url = old_url.replace('.html', '')
            new_url = '/' + str(new_path.relative_to(docs_path)).replace('\\', '/')
            new_url = new_url.replace('.html', '')
            plan.append({
                'old_path': html_file,
                'new_path': new_path,
                'old_slug': stem,
                'new_slug': repaired,
                'old_url':  old_url,
                'new_url':  new_url,
            })
    return plan


def build_link_rewrite_map(plan: list[dict]) -> dict[str, str]:
    """
    Map of all string substitutions to apply across HTML/JS/XML/TXT files.
    We rewrite:
      - href="old-slug.html"   → href="new-slug.html"
      - href="/old-slug"       → href="/new-slug"
      - href="blog/old-slug"   → href="blog/new-slug"
      - canonical/og:url ending in /old-slug → /new-slug
      - .txt marketing file references (same stem)
    """
    mapping = {}
    for item in plan:
        old_stem = item['old_slug']
        new_stem = item['new_slug']
        # Relative file references
        mapping[f'{old_stem}.html'] = f'{new_stem}.html'
        # Absolute URL tail matches (leading slash or end of string boundary)
        # We handle these with whole-token replacement on href/content attrs
        mapping[f'/{old_stem}"']    = f'/{new_stem}"'
        mapping[f'/{old_stem}<']    = f'/{new_stem}<'
        mapping[f'/{old_stem} ']    = f'/{new_stem} '
        # Marketing companion file (same stem, different extension)
        mapping[f'{old_stem}_marketing.txt'] = f'{new_stem}_marketing.txt'
    return mapping


def rewrite_file_content(path: Path, mapping: dict[str, str]) -> tuple[bool, int]:
    """Apply all mapping substitutions to one file. Returns (changed, count)."""
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return False, 0
    original = text
    count = 0
    for old, new in mapping.items():
        if old in text:
            occurrences = text.count(old)
            text = text.replace(old, new)
            count += occurrences
    if text != original:
        path.write_text(text, encoding='utf-8')
        return True, count
    return False, 0


def build_vercel_redirects(plan: list[dict]) -> list[dict]:
    """
    Generate 301 redirects. Vercel syntax:
      { "source": "/old-url", "destination": "/new-url", "permanent": true }
    We also emit .html variants in case anyone links with the extension.
    """
    redirects = []
    for item in plan:
        redirects.append({
            'source':      item['old_url'],
            'destination': item['new_url'],
            'permanent':   True,
        })
        # Also redirect .html variant if someone linked with extension
        redirects.append({
            'source':      item['old_url'] + '.html',
            'destination': item['new_url'],
            'permanent':   True,
        })
    return redirects


def print_preview(plan: list[dict]) -> None:
    if not plan:
        print("\n✅ No broken slugs found. Your URL slugs are clean.")
        return
    print(f"\n🔍 Found {len(plan)} broken slug(s):\n")
    print(f"{'OLD SLUG':<60} → NEW SLUG")
    print('─' * 120)
    for item in plan:
        print(f"{item['old_slug']:<60} → {item['new_slug']}")
    print()
    print("This will:")
    print(f"  • Rename {len(plan)} HTML file(s) + companion _marketing.txt files")
    print(f"  • Rewrite internal links across ALL files in /docs/")
    print(f"  • Generate {len(plan) * 2} vercel.json redirect rules (301)")
    print("\nRe-run with --apply to execute.")


def write_report(log_lines: list[str], docs_path: Path) -> None:
    report_path = docs_path.parent / 'slug_fix_report.txt'
    header = f"ExpatScore slug fix — {datetime.now().isoformat()}\n{'=' * 60}\n\n"
    report_path.write_text(header + '\n'.join(log_lines), encoding='utf-8')
    print(f"\n📝 Report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Fix broken German slugs in ExpatScore /docs/")
    parser.add_argument('--docs', default='./docs', help='Path to docs/ folder (default: ./docs)')
    parser.add_argument('--apply', action='store_true', help='Execute the plan (default: dry-run)')
    parser.add_argument('--no-backup', action='store_true', help='Skip backup step (not recommended)')
    args = parser.parse_args()

    docs_path = Path(args.docs).resolve()
    if not docs_path.exists():
        print(f"❌ docs path not found: {docs_path}")
        sys.exit(1)

    print(f"📂 Scanning: {docs_path}")
    plan = build_rename_plan(docs_path)
    print_preview(plan)

    if not plan:
        sys.exit(0)
    if not args.apply:
        sys.exit(0)

    # ── EXECUTION ───────────────────────────────────────────
    log = []

    # 1. Backup
    if not args.no_backup:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = docs_path.parent / f'docs_backup_{timestamp}'
        shutil.copytree(docs_path, backup_path)
        msg = f"✅ Backup created: {backup_path}"
        print(msg); log.append(msg)

    # 2. Rename .html files + companion _marketing.txt files
    print("\n🔧 Renaming files...")
    for item in plan:
        old = item['old_path']
        new = item['new_path']
        if new.exists():
            msg = f"⚠️  SKIP (target exists): {new.name}"
            print(msg); log.append(msg)
            continue
        old.rename(new)
        msg = f"  {old.name}  →  {new.name}"
        print(msg); log.append(msg)
        # Companion _marketing.txt can live in EITHER the same folder
        # as the html OR in /docs/ root (your tree has both patterns).
        # Search both locations.
        txt_candidates = [
            old.with_name(item['old_slug'] + '_marketing.txt'),
            docs_path / (item['old_slug'] + '_marketing.txt'),
        ]
        for old_txt in txt_candidates:
            if old_txt.exists():
                new_txt = old_txt.with_name(item['new_slug'] + '_marketing.txt')
                if new_txt.exists():
                    msg = f"  ⚠️  SKIP txt (target exists): {new_txt.name}"
                    print(msg); log.append(msg)
                else:
                    old_txt.rename(new_txt)
                    msg = f"  {old_txt.name}  →  {new_txt.name}"
                    print(msg); log.append(msg)
                break  # only rename one companion

    # 3. Rewrite links across the project
    print("\n🔗 Rewriting internal links...")
    mapping = build_link_rewrite_map(plan)
    # Scan wider than /docs/ — also root-level .js, .json, .xml may reference URLs
    scan_roots = [docs_path, docs_path.parent]
    scanned = set()
    for root in scan_roots:
        for ext in ('*.html', '*.js', '*.xml', '*.json', '*.txt', '*.css'):
            for file_path in root.rglob(ext):
                # Skip node_modules, venv, backups
                parts_lower = [p.lower() for p in file_path.parts]
                if any(skip in parts_lower for skip in ('node_modules', 'venv', '__pycache__', '.git')):
                    continue
                if 'docs_backup_' in str(file_path):
                    continue
                if file_path in scanned:
                    continue
                scanned.add(file_path)
                changed, count = rewrite_file_content(file_path, mapping)
                if changed:
                    msg = f"  edited ({count} repl): {file_path.relative_to(docs_path.parent)}"
                    print(msg); log.append(msg)

    # 4. Emit vercel-redirects.json snippet
    redirects = build_vercel_redirects(plan)
    snippet_path = docs_path.parent / 'vercel-redirects.snippet.json'
    snippet = {'redirects': redirects}
    snippet_path.write_text(json.dumps(snippet, indent=2, ensure_ascii=False), encoding='utf-8')
    msg = f"\n📄 Vercel redirect snippet: {snippet_path}"
    print(msg); log.append(msg)
    print(f"   Merge the 'redirects' array into your existing vercel.json.")

    # 5. Write report
    write_report(log, docs_path)
    print("\n✅ Done. Next step: merge redirects into vercel.json, commit, deploy.")


if __name__ == '__main__':
    main()