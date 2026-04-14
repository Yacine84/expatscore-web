#!/usr/bin/env python3
"""
ExpatScore.de — Script 1: Domain Normalization (www → non-www)
================================================================

What it does:
  Replaces 'https://www.expatscore.de' with 'https://expatscore.de' in:
    - All HTML files under /docs/ (canonicals, og:url, twitter:url, JSON-LD)
    - regenerate_sitemap.py (so future sitemap regens use the right base)
  Leaves the .bak sitemap files alone (historical record).

Safety:
  Dry-run by default. Backs up every modified file as <file>.bak-domain
  on first --apply run.

Usage:
  python3 fix_domain.py            # preview
  python3 fix_domain.py --apply    # execute
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

OLD = 'https://www.expatscore.de'
NEW = 'https://expatscore.de'

# Files we explicitly target outside /docs/
EXTRA_TARGETS = [
    'regenerate_sitemap.py',  # update SITE_BASE constant for next regen
    'verify_urls.py',         # update SITE_BASE so future runs verify correct domain
]

# Skip patterns — never touch these
SKIP_PATTERNS = (
    'docs_backup_',     # slug-fix backups
    '.bak.',            # sitemap backups
    '.bak-domain',      # this script's own backups
    'node_modules',
    'venv',
    '__pycache__',
    '.git',
    'data/snapshots',   # SERP snapshots — historical, don't touch
)


def should_skip(path: Path) -> bool:
    s = str(path)
    return any(pat in s for pat in SKIP_PATTERNS)


def find_targets(project_root: Path, docs_path: Path) -> list[Path]:
    """All HTML files in /docs/ + the EXTRA_TARGETS at project root."""
    targets = []
    for html in docs_path.rglob('*.html'):
        if not should_skip(html):
            targets.append(html)
    for name in EXTRA_TARGETS:
        candidate = project_root / name
        if candidate.exists():
            targets.append(candidate)
    return sorted(targets)


def count_occurrences(path: Path) -> int:
    try:
        return path.read_text(encoding='utf-8').count(OLD)
    except (UnicodeDecodeError, PermissionError):
        return 0


def rewrite_file(path: Path, dry_run: bool, backup_dir: Path | None) -> int:
    """Replace OLD → NEW in file. Return number of replacements."""
    try:
        text = path.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return 0
    count = text.count(OLD)
    if count == 0:
        return 0
    if dry_run:
        return count
    # Backup
    if backup_dir:
        rel = path.name + '.bak-domain'
        backup_path = backup_dir / rel
        # Avoid name collisions across folders by including parent dir in name
        if backup_path.exists():
            backup_path = backup_dir / f"{path.parent.name}__{rel}"
        shutil.copy2(path, backup_path)
    path.write_text(text.replace(OLD, NEW), encoding='utf-8')
    return count


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='.')
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()

    project_root = Path(args.root).resolve()
    docs_path = project_root / 'docs'
    if not docs_path.exists():
        print(f"❌ docs/ not found in {project_root}")
        sys.exit(1)

    print(f"📂 Project root: {project_root}")
    print(f"🔄 Replacing:    {OLD}")
    print(f"          with:  {NEW}\n")

    targets = find_targets(project_root, docs_path)
    affected = []
    total_replacements = 0

    for path in targets:
        n = count_occurrences(path)
        if n > 0:
            rel = path.relative_to(project_root)
            affected.append((path, rel, n))
            total_replacements += n

    if not affected:
        print("✅ No occurrences of www domain found. Nothing to do.")
        sys.exit(0)

    print(f"📋 {len(affected)} file(s) contain '{OLD}' "
          f"({total_replacements} total occurrences):\n")
    for _, rel, n in affected:
        print(f"   {n:>4}  {rel}")

    if not args.apply:
        print("\nRe-run with --apply to execute.")
        sys.exit(0)

    # ── APPLY ───────────────────────────────────────
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = project_root / f'domain_fix_backups_{timestamp}'
    backup_dir.mkdir(exist_ok=True)
    print(f"\n💾 Backup dir: {backup_dir}")

    print("\n🔧 Rewriting files...")
    for path, rel, expected in affected:
        actual = rewrite_file(path, dry_run=False, backup_dir=backup_dir)
        status = '✓' if actual == expected else '⚠'
        print(f"   {status} {actual:>4} repl  {rel}")

    print(f"\n✅ Done. {total_replacements} replacements across {len(affected)} files.")
    print(f"   Rollback: rm -rf <files> && mv {backup_dir}/* docs/  (carefully)")
    print(f"   Better:   git diff  →  git checkout -- <file>  if anything looks wrong")


if __name__ == '__main__':
    main()