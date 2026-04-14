#!/usr/bin/env python3
"""
ExpatScore.de — Production URL Verification Sweep
===================================================

Verifies every URL in docs/sitemap.xml against production. Catches:
  • 404s, 500s, non-200 responses
  • Redirect chains (1 hop = OK, 2+ = suspicious)
  • Canonical mismatches (page canonical ≠ sitemap URL = Google-confusing)
  • Old-slug 308 redirects still work
  • robots.txt sanity (not blocking /)
  • GSC verification file still serves

No writes, no destructive ops. Read-only against production.

Usage:
  python3 verify_urls.py                    # check sitemap URLs + extras
  python3 verify_urls.py --sitemap PATH     # custom sitemap path
  python3 verify_urls.py --delay 2.0        # seconds between requests
"""

import argparse
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from xml.etree import ElementTree as ET

# ──────────────────────────────────────────────────────────────
# Bypass SSL certificate verification (fix for macOS CERTIFICATE_VERIFY_FAILED)
# ──────────────────────────────────────────────────────────────
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

SITE_BASE = 'https://expatscore.de'

# Extra URLs to verify beyond the sitemap
REDIRECT_CHECKS = [
    # (old_url, expected_final_url, description)
    (
        f'{SITE_BASE}/blog/bahnbonus-punkte-einlsen-fr-ice-tickets',
        f'{SITE_BASE}/blog/bahnbonus-punkte-einloesen-fuer-ice-tickets',
        'Old umlaut slug → new slug (Task B)',
    ),
]

STATIC_ASSETS = [
    (f'{SITE_BASE}/robots.txt',          'robots.txt'),
    (f'{SITE_BASE}/google9536a7cd025919e5.html', 'GSC verification file'),
]

UA = 'ExpatScore-VerifyBot/1.0 (+https://expatscore.de)'


# ──────────────────────────────────────────────────────────────
# HTTP — minimal stdlib implementation, follows redirects manually
# so we can count hops and see each Location header.
# ──────────────────────────────────────────────────────────────
class RedirectTrackingOpener(urllib.request.OpenerDirector):
    pass


def fetch(url: str, follow_redirects: bool = True, max_hops: int = 5,
          timeout: int = 10) -> dict:
    """
    Returns:
      {
        'final_url': str,
        'status': int,
        'hops': int,
        'chain': [(status, url), ...],
        'body': str | None,          # only set on 200 responses
        'error': str | None,
      }
    """
    chain = []
    current = url
    for hop in range(max_hops + 1):
        req = urllib.request.Request(
            current,
            headers={'User-Agent': UA, 'Accept': 'text/html,*/*'},
            method='GET',
        )
        try:
            # Disable automatic redirect following — we track manually
            opener = urllib.request.build_opener(NoRedirect())
            resp = opener.open(req, timeout=timeout)
            status = resp.getcode()
            chain.append((status, current))
            if status == 200:
                body = resp.read(500_000).decode('utf-8', errors='replace')
                return {
                    'final_url': current, 'status': 200, 'hops': hop,
                    'chain': chain, 'body': body, 'error': None,
                }
            # Non-redirect, non-200 (shouldn't reach here w/ NoRedirect)
            return {
                'final_url': current, 'status': status, 'hops': hop,
                'chain': chain, 'body': None, 'error': None,
            }
        except RedirectCaught as rc:
            chain.append((rc.status, current))
            if not follow_redirects or hop >= max_hops:
                return {
                    'final_url': current, 'status': rc.status, 'hops': hop,
                    'chain': chain, 'body': None,
                    'error': 'redirect-limit' if hop >= max_hops else None,
                }
            current = rc.location
            continue
        except urllib.error.HTTPError as e:
            chain.append((e.code, current))
            return {
                'final_url': current, 'status': e.code, 'hops': hop,
                'chain': chain, 'body': None, 'error': None,
            }
        except Exception as e:
            return {
                'final_url': current, 'status': 0, 'hops': hop,
                'chain': chain, 'body': None, 'error': str(e),
            }
    return {
        'final_url': current, 'status': 0, 'hops': max_hops,
        'chain': chain, 'body': None, 'error': 'max hops exceeded',
    }


class RedirectCaught(Exception):
    def __init__(self, status, location):
        self.status = status
        self.location = location


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Intercept redirects instead of following them automatically."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RedirectCaught(code, newurl)


# ──────────────────────────────────────────────────────────────
# HTML INSPECTION — canonical extraction (same regex as sitemap gen)
# ──────────────────────────────────────────────────────────────
CANONICAL_RE_A = re.compile(
    r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']',
    re.IGNORECASE
)
CANONICAL_RE_B = re.compile(
    r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']',
    re.IGNORECASE
)


def extract_canonical(html: str) -> str | None:
    m = CANONICAL_RE_A.search(html) or CANONICAL_RE_B.search(html)
    return m.group(1).strip() if m else None


# ──────────────────────────────────────────────────────────────
# SITEMAP LOADING
# ──────────────────────────────────────────────────────────────
def load_sitemap_urls(sitemap_path: Path) -> list[str]:
    tree = ET.parse(sitemap_path)
    root = tree.getroot()
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    return [u.find('sm:loc', ns).text.strip()
            for u in root.findall('sm:url', ns)]


# ──────────────────────────────────────────────────────────────
# CHECKS
# ──────────────────────────────────────────────────────────────
def check_sitemap_url(url: str) -> dict:
    """Fetch URL, verify 200, verify canonical matches URL."""
    r = fetch(url, follow_redirects=True)
    issues = []
    status_label = 'OK'

    if r['error']:
        issues.append(f"network error: {r['error']}")
        status_label = 'ERROR'
    elif r['status'] != 200:
        issues.append(f"HTTP {r['status']}")
        status_label = 'FAIL'
    else:
        # 200 reached. Check hop count — more than 1 redirect is a smell.
        if r['hops'] > 1:
            chain_str = ' → '.join(f"{s}:{u}" for s, u in r['chain'])
            issues.append(f"redirect chain ({r['hops']} hops): {chain_str}")
            status_label = 'WARN'
        elif r['hops'] == 1:
            # Single redirect is acceptable (e.g. www canonicalization), but
            # if sitemap URL redirects, it's wrong — sitemap should hold the
            # CANONICAL URL, not a redirecting one.
            issues.append(f"sitemap URL redirects (should be final URL in sitemap): {r['chain'][0][1]} → {r['final_url']}")
            status_label = 'WARN'

        # Canonical check
        if r['body']:
            canonical = extract_canonical(r['body'])
            if canonical is None:
                issues.append('no <link rel="canonical"> in page')
                if status_label == 'OK':
                    status_label = 'WARN'
            else:
                # Normalise both sides for comparison
                norm_canonical = canonical.rstrip('/')
                norm_sitemap = url.rstrip('/')
                # Allow trailing-slash homepage variants
                if norm_canonical == '' or norm_canonical == SITE_BASE:
                    norm_canonical = SITE_BASE
                if norm_sitemap == '' or norm_sitemap == SITE_BASE:
                    norm_sitemap = SITE_BASE
                if norm_canonical != norm_sitemap:
                    issues.append(
                        f'canonical mismatch: page says "{canonical}", '
                        f'sitemap says "{url}"'
                    )
                    status_label = 'FAIL'

    return {
        'url':    url,
        'status': status_label,
        'http':   r['status'],
        'hops':   r['hops'],
        'issues': issues,
    }


def check_redirect(old_url: str, expected_final: str, description: str) -> dict:
    """Verify old URL redirects (308/301) to expected destination."""
    r = fetch(old_url, follow_redirects=True)
    issues = []
    status_label = 'OK'

    if r['error']:
        issues.append(f"network error: {r['error']}")
        status_label = 'ERROR'
    elif r['status'] != 200:
        issues.append(f"final HTTP {r['status']} — redirect broken")
        status_label = 'FAIL'
    else:
        if r['hops'] == 0:
            issues.append('URL returned 200 directly (no redirect happened)')
            status_label = 'FAIL'
        else:
            # Redirect happened. Check destination.
            if r['final_url'].rstrip('/') != expected_final.rstrip('/'):
                issues.append(
                    f'redirected to "{r["final_url"]}" but expected "{expected_final}"'
                )
                status_label = 'FAIL'
            # Check redirect code — want 301 or 308 (permanent)
            first_hop_status = r['chain'][0][0]
            if first_hop_status not in (301, 308):
                issues.append(
                    f'redirect is {first_hop_status} (not permanent — should be 301 or 308)'
                )
                if status_label == 'OK':
                    status_label = 'WARN'
    return {
        'url':    f'{old_url}  →  (expected) {expected_final}',
        'description': description,
        'status': status_label,
        'http':   r['status'],
        'hops':   r['hops'],
        'issues': issues,
    }


def check_static_asset(url: str, label: str) -> dict:
    r = fetch(url, follow_redirects=True)
    issues = []
    status_label = 'OK'
    if r['error']:
        issues.append(f"network error: {r['error']}")
        status_label = 'ERROR'
    elif r['status'] != 200:
        issues.append(f"HTTP {r['status']}")
        status_label = 'FAIL'
    else:
        # robots.txt sanity — must not blanket-disallow /
        if url.endswith('robots.txt') and r['body']:
            txt = r['body'].lower()
            # Parse simplistically: any "user-agent: *" block with "disallow: /"
            # on its own line is a full-site block.
            lines = [l.strip() for l in txt.splitlines()]
            in_star_block = False
            for line in lines:
                if line.startswith('#') or not line:
                    continue
                if line.startswith('user-agent:'):
                    in_star_block = (line.split(':', 1)[1].strip() == '*')
                elif in_star_block and line == 'disallow: /':
                    issues.append('robots.txt blocks entire site! (Disallow: /)')
                    status_label = 'FAIL'
    return {
        'url': url, 'status': status_label, 'http': r['status'],
        'hops': r['hops'], 'issues': issues, 'label': label,
    }


# ──────────────────────────────────────────────────────────────
# REPORTING
# ──────────────────────────────────────────────────────────────
SYMBOL = {'OK': '✅', 'WARN': '⚠️ ', 'FAIL': '❌', 'ERROR': '💥'}


def print_row(result: dict, short_url: bool = True) -> None:
    sym = SYMBOL.get(result['status'], '?')
    url = result['url']
    if short_url and url.startswith(SITE_BASE):
        url = url.replace(SITE_BASE, '')
    hops_str = f"{result['hops']}h" if result['hops'] else ' -'
    print(f"  {sym} {result['http']:>3} {hops_str:>3}  {url}")
    for issue in result['issues']:
        print(f"         └─ {issue}")


def summarize(all_results: list[dict]) -> tuple[int, int, int, int]:
    ok = sum(1 for r in all_results if r['status'] == 'OK')
    warn = sum(1 for r in all_results if r['status'] == 'WARN')
    fail = sum(1 for r in all_results if r['status'] == 'FAIL')
    err = sum(1 for r in all_results if r['status'] == 'ERROR')
    return ok, warn, fail, err


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sitemap', default='./docs/sitemap.xml')
    p.add_argument('--delay', type=float, default=1.0,
                   help='Seconds between requests (default: 1.0)')
    p.add_argument('--skip-sitemap', action='store_true',
                   help='Skip sitemap URLs, only check redirects + assets')
    args = p.parse_args()

    sitemap_path = Path(args.sitemap).resolve()
    if not sitemap_path.exists() and not args.skip_sitemap:
        print(f"❌ Sitemap not found: {sitemap_path}")
        sys.exit(1)

    all_results = []

    # ── Sitemap URLs ────────────────────────────────────────
    if not args.skip_sitemap:
        urls = load_sitemap_urls(sitemap_path)
        print(f"🔍 Checking {len(urls)} URLs from {sitemap_path.name}\n")
        print(f"  {'sym':<4}{'HTTP':<5}{'hops':<5} URL")
        print(f"  {'─' * 70}")
        for url in urls:
            result = check_sitemap_url(url)
            all_results.append(result)
            print_row(result)
            time.sleep(args.delay)

    # ── Redirect integrity ──────────────────────────────────
    print(f"\n🔁 Checking {len(REDIRECT_CHECKS)} redirect(s):\n")
    for old_url, expected, desc in REDIRECT_CHECKS:
        result = check_redirect(old_url, expected, desc)
        all_results.append(result)
        sym = SYMBOL.get(result['status'], '?')
        short_old = old_url.replace(SITE_BASE, '')
        short_new = expected.replace(SITE_BASE, '')
        print(f"  {sym} {result['http']:>3} ({result['hops']}h)  {short_old}")
        print(f"         → expect: {short_new}")
        print(f"         ({result['description']})")
        for issue in result['issues']:
            print(f"         └─ {issue}")
        time.sleep(args.delay)

    # ── Static assets ───────────────────────────────────────
    print(f"\n📄 Checking static files:\n")
    for url, label in STATIC_ASSETS:
        result = check_static_asset(url, label)
        all_results.append(result)
        sym = SYMBOL.get(result['status'], '?')
        print(f"  {sym} {result['http']:>3}  {label}  ({url.replace(SITE_BASE, '')})")
        for issue in result['issues']:
            print(f"         └─ {issue}")
        time.sleep(args.delay)

    # ── Summary ─────────────────────────────────────────────
    ok, warn, fail, err = summarize(all_results)
    total = len(all_results)
    print(f"\n{'═' * 72}")
    print(f"  SUMMARY:  {ok} OK  ·  {warn} WARN  ·  {fail} FAIL  ·  {err} ERROR  (of {total})")
    print(f"{'═' * 72}")

    if fail or err:
        print("\n❌ Issues found. Fix these BEFORE Google crawls the sitemap.")
        sys.exit(1)
    elif warn:
        print("\n⚠️  Non-critical warnings. Review, but safe to proceed.")
        sys.exit(0)
    else:
        print("\n✅ All clean. Safe to let Google crawl.")
        sys.exit(0)


if __name__ == '__main__':
    main()