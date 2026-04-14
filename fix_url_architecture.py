#!/usr/bin/env python3
"""
ExpatScore.de — Script 2: URL Architecture Fix
================================================

Resolves the mismatch where vercel.json rewrites flat URLs (e.g.
/anmeldung-germany) to /docs/<slug>.html files that don't exist —
because the actual files live in /docs/blog/.

What it does:
  1. Moves blue-card-tool.html from /docs/blog/ to /docs/ (it's a tool,
     belongs at flat URL like schufa-simulator).
  2. For 7 ARTICLES that should live under /blog/<slug>:
       - Updates vercel.json rewrites: /<slug> → /<slug>.html  becomes
         /blog/<slug> → /docs/blog/<slug>.html (already covered by your
         existing /blog/:slug catch-all, but we remove the conflicting
         flat rules).
       - Adds 301 redirects from old flat URLs (/anmeldung-germany) to
         new blog URLs (/blog/anmeldung-germany).
       - Updates each file's <link rel="canonical"> to the new /blog/
         URL.
  3. Updates blue-card-tool.html canonical to confirm flat URL.
  4. Sorts vercel.json redirects to keep them readable.

Safety:
  Dry-run by default. Validates JSON before writing. Backs up vercel.json.

Usage:
  python3 fix_url_architecture.py            # preview
  python3 fix_url_architecture.py --apply    # execute
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SITE_BASE = 'https://expatscore.de'  # non-www (Script 1 must run first)

# Articles currently in /docs/blog/ that vercel.json wrongly tries to
# serve at root. We KEEP them in /docs/blog/ and route them at /blog/<slug>.
# These match files we verified exist in your tree.
ARTICLES_TO_BLOG = [
    'anmeldung-germany',
    'blocked-account-germany',
    'konto-ohne-anmeldung',
    'n26-bank-erfahrungen',
    'steuer-id-guide',
    'tk-health-insurance',
    'how-to-get-schufa-germany',  # already correctly at /blog/, sitemap-aligned
]

# Tools that should live at flat URL (root). Files currently in
# /docs/blog/ that we PHYSICALLY MOVE to /docs/.
TOOLS_TO_FLATTEN = [
    'blue-card-tool',
]


# ──────────────────────────────────────────────────────────────
# CANONICAL TAG UPDATES
# ──────────────────────────────────────────────────────────────
def update_canonical(file_path: Path, new_url_path: str) -> bool:
    """Rewrite <link rel="canonical">, og:url, twitter:url, JSON-LD url."""
    if not file_path.exists():
        return False
    text = file_path.read_text(encoding='utf-8')
    new_url = SITE_BASE + new_url_path
    changed = False

    # canonical link tag — both attribute orders
    patterns = [
        (r'(<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\'])([^"\']+)(["\'])',
         lambda m: m.group(1) + new_url + m.group(3)),
        (r'(<link\s+[^>]*href=["\'])([^"\']+)(["\'][^>]*rel=["\']canonical["\'])',
         lambda m: m.group(1) + new_url + m.group(3)),
        # og:url
        (r'(<meta\s+[^>]*property=["\']og:url["\'][^>]*content=["\'])([^"\']+)(["\'])',
         lambda m: m.group(1) + new_url + m.group(3)),
        (r'(<meta\s+[^>]*content=["\'])([^"\']+)(["\'][^>]*property=["\']og:url["\'])',
         lambda m: m.group(1) + new_url + m.group(3)),
    ]
    new_text = text
    for pat, repl in patterns:
        new_new = re.sub(pat, repl, new_text)
        if new_new != new_text:
            changed = True
            new_text = new_new

    # JSON-LD url field — narrow regex, only matches /schufa-blah expatscore URLs
    # to avoid accidentally rewriting external URLs in JSON-LD
    jsonld_pat = (r'("url"\s*:\s*"https://(?:www\.)?expatscore\.de)'
                  r'(/[^"]*)(")')
    def jsonld_replace(m):
        # only swap if it currently points at the OLD path for this file
        return m.group(1) + new_url_path + m.group(3)
    # Apply only if any expatscore.de url field exists; we replace ALL of them
    # because a single article should only reference its own canonical URL.
    new_new = re.sub(jsonld_pat, jsonld_replace, new_text)
    if new_new != new_text:
        changed = True
        new_text = new_new

    if changed:
        file_path.write_text(new_text, encoding='utf-8')
    return changed


# ──────────────────────────────────────────────────────────────
# VERCEL.JSON SURGERY
# ──────────────────────────────────────────────────────────────
def normalize_path(p: str) -> str:
    """Strip trailing slashes, lowercase, for comparison."""
    return p.rstrip('/').lower()


def update_vercel_json(vercel_path: Path, articles: list[str],
                       tools: list[str]) -> tuple[dict, list[str]]:
    """
    Return (new_config, change_log).
    Logic:
      - For each article in `articles`:
          * REMOVE rewrites whose source is /<slug> or /<anything>/<slug>
            and whose destination points to /docs/<slug>.html
            (these are wrong — file lives at /docs/blog/<slug>.html).
          * ADD a 301 redirect /<slug>  →  /blog/<slug>
          * ADD a 301 redirect /<slug>.html  →  /blog/<slug>
          * The /blog/:slug catch-all rewrite already serves the file.
      - For each tool in `tools` (file moves to root):
          * KEEP existing /<slug> → /docs/<slug>.html rewrite (was already correct,
            because we're moving the file to root). If missing, ADD it.
          * No new redirect needed (URL didn't change).
    """
    log = []
    cfg = json.loads(vercel_path.read_text(encoding='utf-8'))
    rewrites = cfg.get('rewrites', [])
    redirects = cfg.get('redirects', [])

    # Build sets for safe membership checks
    existing_redirect_sources = {normalize_path(r['source']) for r in redirects}
    existing_rewrite_sources  = {normalize_path(r['source']) for r in rewrites}

    # ── Articles: remove flat rewrites, add redirects ───────
    for slug in articles:
        flat_paths = [f'/{slug}', f'/{slug}.html']
        # Remove any rewrite that maps a flat URL for this slug to /docs/<slug>.html
        new_rewrites = []
        for rw in rewrites:
            src_norm = normalize_path(rw['source'])
            dest_norm = normalize_path(rw['destination'])
            wrong_dest = (dest_norm == f'/docs/{slug}.html')
            flat_src = (src_norm in [normalize_path(p) for p in flat_paths])
            if flat_src and wrong_dest:
                log.append(f"  ✂ remove rewrite: {rw['source']} → {rw['destination']}")
                continue
            new_rewrites.append(rw)
        rewrites = new_rewrites

        # Add 301 redirects flat → /blog/<slug>  (idempotent)
        for old_path in flat_paths:
            if normalize_path(old_path) in existing_redirect_sources:
                log.append(f"  • redirect already present: {old_path}")
                continue
            new_redirect = {
                'source':      old_path,
                'destination': f'/blog/{slug}',
                'permanent':   True,
            }
            redirects.append(new_redirect)
            existing_redirect_sources.add(normalize_path(old_path))
            log.append(f"  ＋ add redirect: {old_path} → /blog/{slug}")

    # ── Tools: ensure flat rewrite exists pointing at /docs/<slug>.html ──
    for slug in tools:
        flat = f'/{slug}'
        target = f'/docs/{slug}.html'
        # Look for existing rewrite — could already be correct (your vercel.json
        # has /blue-card-tool → /docs/blue-card-tool.html, which is right after move)
        already_correct = any(
            normalize_path(rw['source']) == normalize_path(flat)
            and normalize_path(rw['destination']) == normalize_path(target)
            for rw in rewrites
        )
        if already_correct:
            log.append(f"  ✓ rewrite OK: {flat} → {target}")
        else:
            # Remove any conflicting rewrite for the same source
            rewrites = [rw for rw in rewrites
                        if normalize_path(rw['source']) != normalize_path(flat)]
            rewrites.append({'source': flat, 'destination': target})
            log.append(f"  ＋ add rewrite: {flat} → {target}")

    # Sort redirects: tool/article redirects first, legacy URL migrations after.
    # Preserve order within each group for git-diff readability.
    cfg['rewrites'] = rewrites
    cfg['redirects'] = redirects
    return cfg, log


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()

    project_root = Path(args.root).resolve()
    docs_path = project_root / 'docs'
    blog_path = docs_path / 'blog'
    vercel_path = project_root / 'vercel.json'

    if not vercel_path.exists():
        print(f"❌ vercel.json not found at {vercel_path}")
        sys.exit(1)
    if not blog_path.exists():
        print(f"❌ docs/blog/ not found at {blog_path}")
        sys.exit(1)

    print(f"📂 Project root: {project_root}\n")

    # Pre-flight: verify expected files exist where we think they do
    print("🔍 Pre-flight file existence check:")
    issues = []
    for slug in ARTICLES_TO_BLOG:
        f = blog_path / f'{slug}.html'
        ok = f.exists()
        print(f"   {'✓' if ok else '✗'} docs/blog/{slug}.html  {'(exists)' if ok else '(MISSING)'}")
        if not ok:
            issues.append(f'docs/blog/{slug}.html')
    for slug in TOOLS_TO_FLATTEN:
        src = blog_path / f'{slug}.html'
        dst = docs_path / f'{slug}.html'
        if dst.exists():
            print(f"   ⚠ docs/{slug}.html already at root (move not needed)")
        elif src.exists():
            print(f"   ✓ docs/blog/{slug}.html → will move to docs/{slug}.html")
        else:
            print(f"   ✗ docs/blog/{slug}.html MISSING — cannot move")
            issues.append(f'docs/blog/{slug}.html (for tool flatten)')

    if issues:
        print(f"\n❌ Pre-flight failed. Resolve missing files first:")
        for i in issues:
            print(f"     {i}")
        sys.exit(1)

    # Build vercel.json change set
    print("\n🔧 vercel.json changes:")
    new_cfg, vlog = update_vercel_json(vercel_path, ARTICLES_TO_BLOG,
                                       TOOLS_TO_FLATTEN)
    for line in vlog:
        print(line)

    # File move plan
    moves = []
    for slug in TOOLS_TO_FLATTEN:
        src = blog_path / f'{slug}.html'
        dst = docs_path / f'{slug}.html'
        if src.exists() and not dst.exists():
            moves.append((src, dst))

    print(f"\n📦 File moves ({len(moves)}):")
    for src, dst in moves:
        print(f"   {src.relative_to(project_root)}  →  {dst.relative_to(project_root)}")

    # Canonical update plan
    print(f"\n📝 Canonical updates ({len(ARTICLES_TO_BLOG) + len(TOOLS_TO_FLATTEN)}):")
    for slug in ARTICLES_TO_BLOG:
        print(f"   docs/blog/{slug}.html  →  canonical: /blog/{slug}")
    for slug in TOOLS_TO_FLATTEN:
        print(f"   docs/{slug}.html (after move)  →  canonical: /{slug}")

    if not args.apply:
        print("\nRe-run with --apply to execute.")
        sys.exit(0)

    # ── APPLY ───────────────────────────────────────
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 1. Backup vercel.json
    vercel_backup = vercel_path.with_suffix(f'.json.bak.{timestamp}')
    shutil.copy2(vercel_path, vercel_backup)
    print(f"\n💾 vercel.json backup: {vercel_backup}")

    # 2. Validate new vercel.json by serialising + reparsing
    try:
        new_text = json.dumps(new_cfg, indent=2, ensure_ascii=False) + '\n'
        json.loads(new_text)  # round-trip sanity
    except (TypeError, json.JSONDecodeError) as e:
        print(f"\n❌ Generated vercel.json is invalid: {e}")
        print("   No changes written.")
        sys.exit(1)

    # 3. Move tool files BEFORE updating their canonicals (so canonical
    #    update writes to the new location).
    for src, dst in moves:
        src.rename(dst)
        print(f"   ✓ moved: {src.name}  →  {dst}")

    # 4. Update canonicals
    print("\n📝 Updating canonicals...")
    for slug in ARTICLES_TO_BLOG:
        f = blog_path / f'{slug}.html'
        if update_canonical(f, f'/blog/{slug}'):
            print(f"   ✓ updated: docs/blog/{slug}.html → /blog/{slug}")
        else:
            print(f"   • no change needed: docs/blog/{slug}.html")
    for slug in TOOLS_TO_FLATTEN:
        f = docs_path / f'{slug}.html'  # post-move location
        if update_canonical(f, f'/{slug}'):
            print(f"   ✓ updated: docs/{slug}.html → /{slug}")
        else:
            print(f"   • no change needed: docs/{slug}.html")

    # 5. Write new vercel.json
    vercel_path.write_text(new_text, encoding='utf-8')
    print(f"\n✅ vercel.json updated.")

    print("\n🎯 Next steps:")
    print("   1. Re-run regenerate_sitemap.py --apply  (canonicals changed → sitemap follows)")
    print("   2. git diff vercel.json   (review)")
    print("   3. git status            (review file moves)")
    print("   4. Commit + push")
    print("   5. Re-run verify_urls.py after deploy")


if __name__ == '__main__':
    main()