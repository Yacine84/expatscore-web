#!/usr/bin/env python3
"""
pSEO Metadata Controller — Mixed-File Environment
=================================================
Inventory-driven, idempotent DOM-aware updater for .html and .txt (HTML-content) files.

Architecture:
    seo_inventory.json ──▶ update_meta.py ──▶ docs/*.html | docs/*.txt
                              │
                              ├──▶ .backups/ (timestamped)
                              ├──▶ stdout (dry-run preview)
                              └──▶ stderr (errors / missing)

Author: pSEO Automation Layer
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_DOCS_DIR = Path("docs")
DEFAULT_INVENTORY = Path("seo_inventory.json")
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%H:%M:%S"


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass(frozen=True)
class PageMeta:
    """Immutable metadata payload for a single page."""
    title: str
    meta_description: str
    h1: Optional[str] = None

    def __post_init__(self):
        # Frozen dataclass workaround for derived defaults
        object.__setattr__(
            self, "_h1_resolved", self.h1 if self.h1 and self.h1.strip() else self.title
        )

    @property
    def h1_resolved(self) -> str:
        return getattr(self, "_h1_resolved", self.title)


@dataclass
class ProcessingResult:
    """Outcome of a single file operation."""
    filename: str
    status: str  # 'updated', 'skipped', 'missing', 'error'
    changes: List[str] = field(default_factory=list)
    error_message: Optional[str] = None


# =============================================================================
# CORE CONTROLLER
# =============================================================================

class MetadataController:
    """
    Surgical DOM updater for HTML and HTML-in-.txt files.
    
    Guarantees:
        - Idempotent: re-running produces identical output, no redundant writes.
        - Non-destructive: backups before mutation, dry-run for preview.
        - Extension-agnostic: .html and .txt treated identically for parsing.
    """

    def __init__(
        self,
        docs_dir: Path,
        dry_run: bool = False,
        backup_dir: Optional[Path] = None,
    ):
        self.docs_dir = docs_dir.resolve()
        self.dry_run = dry_run
        self.backup_dir = (backup_dir or self.docs_dir / ".backups").resolve()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._ensure_backup_dir()

    # -------------------------------------------------------------------------
    # Inventory Loading
    # -------------------------------------------------------------------------

    def load_inventory(self, path: Path) -> Dict[str, PageMeta]:
        """Load and validate the JSON inventory."""
        if not path.exists():
            self.logger.error("Inventory file not found: %s", path)
            sys.exit(1)

        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in inventory: %s", e)
            sys.exit(1)

        inventory: Dict[str, PageMeta] = {}
        for filename, data in raw.items():
            if not isinstance(data, dict):
                self.logger.error("Entry for '%s' must be an object, got %s", filename, type(data).__name__)
                sys.exit(1)

            try:
                inventory[filename] = PageMeta(**data)
            except TypeError as e:
                self.logger.error("Schema error for '%s': %s", filename, e)
                sys.exit(1)

        self.logger.info("Loaded inventory: %d page(s)", len(inventory))
        return inventory

    # -------------------------------------------------------------------------
    # File Resolution
    # -------------------------------------------------------------------------

    def resolve_file(self, filename: str) -> Optional[Path]:
        """
        Resolve a filename from inventory to an actual filesystem path.
        Supports both .html and .txt extensions as provided.
        """
        candidate = self.docs_dir / filename
        if candidate.exists():
            return candidate

        # If the inventory key lacks extension, try common variants
        # (defensive, though inventory should be explicit)
        for ext in (".html", ".txt"):
            candidate = self.docs_dir / (filename + ext)
            if candidate.exists():
                return candidate

        return None

    # -------------------------------------------------------------------------
    # Backup System
    # -------------------------------------------------------------------------

    def _ensure_backup_dir(self) -> None:
        if not self.dry_run:
            self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _create_backup(self, source: Path) -> Path:
        """Create a timestamped backup: filename.ext.YYYYMMDD_HHMMSS.bak"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{source.name}.{timestamp}.bak"
        backup_path = self.backup_dir / backup_name
        shutil.copy2(source, backup_path)
        return backup_path

    # -------------------------------------------------------------------------
    # DOM Surgery
    # -------------------------------------------------------------------------

    def _update_title(self, soup: BeautifulSoup, title_text: str) -> bool:
        """Update or inject <title>. Returns True if changed."""
        title_tag = soup.find("title")
        if title_tag:
            current = (title_tag.string or "").strip()
            if current == title_text.strip():
                return False
            title_tag.string = title_text
            return True

        # Inject into <head> if missing
        head = soup.find("head")
        if head:
            new_title = Tag(name="title")
            new_title.string = title_text
            head.insert(0, new_title)
            return True

        return False  # No <head> found — caller logs warning

    def _update_meta_description(self, soup: BeautifulSoup, description: str) -> bool:
        """Update or inject <meta name='description'>. Returns True if changed."""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            current = (meta_tag.get("content") or "").strip()
            if current == description.strip():
                return False
            meta_tag["content"] = description
            return True

        head = soup.find("head")
        if head:
            new_meta = Tag(name="meta")
            new_meta.attrs = {"name": "description", "content": description}
            head.append(new_meta)
            return True

        return False

    def _update_h1(self, soup: BeautifulSoup, h1_text: str) -> bool:
        """Update first <h1>. Returns True if changed."""
        h1_tag = soup.find("h1")
        if not h1_tag:
            return False  # Caller logs warning

        current = h1_tag.get_text(strip=True)
        if current == h1_text.strip():
            return False

        h1_tag.clear()
        h1_tag.append(h1_text)
        return True

    # -------------------------------------------------------------------------
    # File Processing
    # -------------------------------------------------------------------------

    def process_file(self, filename: str, meta: PageMeta) -> ProcessingResult:
        """
        Main entry for a single file. Handles all error states and returns
        a structured result for summary reporting.
        """
        filepath = self.resolve_file(filename)
        if not filepath:
            self.logger.error("MISSING: %s not found in %s", filename, self.docs_dir)
            return ProcessingResult(filename, "missing", error_message="File not found")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                original_content = f.read()
        except UnicodeDecodeError as e:
            self.logger.error("ENCODING ERROR: %s — %s", filename, e)
            return ProcessingResult(filename, "error", error_message=f"Encoding error: {e}")
        except OSError as e:
            self.logger.error("READ ERROR: %s — %s", filename, e)
            return ProcessingResult(filename, "error", error_message=f"Read error: {e}")

        # Parse with html.parser — tolerant of mixed/loose markup
        soup = BeautifulSoup(original_content, "html.parser")

        changes: List[str] = []

        # --- Execute updates ---
        try:
            if self._update_title(soup, meta.title):
                changes.append("title")

            if self._update_meta_description(soup, meta.meta_description):
                changes.append("meta_description")

            h1_changed = self._update_h1(soup, meta.h1_resolved)
            if h1_changed:
                changes.append("h1")
            elif not soup.find("h1"):
                self.logger.warning("NO <H1>: %s has no <h1> tag to update", filename)

        except Exception as e:
            self.logger.error("DOM ERROR: %s — %s", filename, e)
            return ProcessingResult(filename, "error", error_message=f"DOM mutation error: {e}")

        # --- Idempotency check ---
        if not changes:
            self.logger.info("SKIP: %s (already correct)", filename)
            return ProcessingResult(filename, "skipped")

        # --- Dry-run preview ---
        if self.dry_run:
            self.logger.info("DRY-RUN: %s → would update: %s", filename, ", ".join(changes))
            return ProcessingResult(filename, "dry-run", changes=changes)

        # --- Persist with backup ---
        try:
            backup_path = self._create_backup(filepath)
            rendered = str(soup)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(rendered)

            self.logger.info(
                "UPDATED: %s (%s) [backup: %s]",
                filename,
                ", ".join(changes),
                backup_path.name,
            )
            return ProcessingResult(filename, "updated", changes=changes)

        except OSError as e:
            self.logger.error("WRITE ERROR: %s — %s", filename, e)
            return ProcessingResult(filename, "error", error_message=f"Write error: {e}")

    # -------------------------------------------------------------------------
    # Orchestration
    # -------------------------------------------------------------------------

    def run(self, inventory: Dict[str, PageMeta]) -> List[ProcessingResult]:
        """Process entire inventory and return all results."""
        results: List[ProcessingResult] = []

        for filename, meta in inventory.items():
            result = self.process_file(filename, meta)
            results.append(result)

        return results

    def print_summary(self, results: List[ProcessingResult]) -> None:
        """Emit a clean, scannable summary table."""
        counts: Dict[str, int] = {
            "updated": 0,
            "skipped": 0,
            "missing": 0,
            "error": 0,
            "dry-run": 0,
        }

        for r in results:
            counts[r.status] = counts.get(r.status, 0) + 1

        print()
        print("=" * 58)
        print("  pSEO METADATA UPDATE SUMMARY")
        print("=" * 58)
        print(f"  {'Updated:':<12} {counts['updated'] + counts['dry-run']:<6} {'(dry-run previewed)' if self.dry_run else ''}")
        print(f"  {'Skipped:':<12} {counts['skipped']:<6}  (already correct)")
        print(f"  {'Missing:':<12} {counts['missing']:<6}  (not found in docs/)")
        print(f"  {'Errors:':<12} {counts['error']:<6}  (encoding/DOM/write failures)")
        print("=" * 58)

        if counts["error"] > 0:
            print("\n  Error Details:")
            for r in results:
                if r.status == "error":
                    print(f"    • {r.filename}: {r.error_message}")


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="pSEO Metadata Controller — Update <title>, <h1>, and <meta name='description'> across .html and .txt files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --dry-run                          Preview all changes
  %(prog)s --inventory ./data/seo.json        Use custom inventory path
  %(prog)s --docs ./content --dry-run         Target custom docs directory
        """,
    )
    parser.add_argument(
        "--inventory",
        type=Path,
        default=DEFAULT_INVENTORY,
        help=f"Path to seo_inventory.json (default: {DEFAULT_INVENTORY})",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=DEFAULT_DOCS_DIR,
        help=f"Target directory containing .html and .txt files (default: {DEFAULT_DOCS_DIR})",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=None,
        help="Custom backup directory (default: <docs>/.backups/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes in terminal without writing to disk",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format=LOG_FORMAT, datefmt=DATE_FORMAT)

    controller = MetadataController(
        docs_dir=args.docs,
        dry_run=args.dry_run,
        backup_dir=args.backup_dir,
    )

    inventory = controller.load_inventory(args.inventory)
    results = controller.run(inventory)
    controller.print_summary(results)

    # Exit non-zero if any files were missing or errored
    error_count = sum(1 for r in results if r.status in ("missing", "error"))
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())