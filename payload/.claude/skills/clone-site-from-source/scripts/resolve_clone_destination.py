#!/usr/bin/env python3
"""Resolve <workspace>/크롤링/<SiteName> without creating the site project."""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


INVALID_PATH_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
SEPARATORS = re.compile(r"[\s_]+")


def sanitize_site_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().strip(".")
    normalized = INVALID_PATH_CHARS.sub("-", normalized)
    normalized = SEPARATORS.sub("", normalized)
    normalized = re.sub(r"-+", "-", normalized).strip("-.")
    if not normalized or normalized in {".", ".."}:
        raise ValueError("site name is empty after sanitization")
    if len(normalized) > 80:
        normalized = normalized[:80].rstrip("-.")
    return normalized


def infer_site_name(source_url: str) -> str:
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URL must be an absolute http(s) URL")
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    first_label = host.split(".")[0]
    parts = [part for part in re.split(r"[-_]", first_label) if part]
    return sanitize_site_name("".join(part.capitalize() for part in parts))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--site-name")
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="allow a destination directory that already contains files",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.expanduser().resolve()
    if not workspace_root.is_dir():
        raise SystemExit(f"workspace root does not exist: {workspace_root}")

    try:
        site_name = sanitize_site_name(args.site_name) if args.site_name else infer_site_name(args.source_url)
    except ValueError as error:
        raise SystemExit(str(error)) from error

    crawl_root = (workspace_root / "크롤링").resolve()
    destination = (crawl_root / site_name).resolve()
    try:
        destination.relative_to(crawl_root)
    except ValueError as error:
        raise SystemExit("resolved destination escaped the crawling root") from error

    if destination.exists() and any(destination.iterdir()) and not args.allow_existing:
        raise SystemExit(f"destination already contains files: {destination}")

    crawl_root.mkdir(parents=True, exist_ok=True)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
