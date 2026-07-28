#!/usr/bin/env python3
"""
Njuskalo Auto Scraper Runner

This script scrapes vehicle listings from njuskalo.hr auto-oglasi category
and saves the data to a JSON file.

Usage:
    python main.py                                          # Scrape default URL (auti), visible browser
    python main.py --no-headless                            # Scrape with visible browser
    python main.py --fallback-visible-on-block "URL"       # Headless first, then visible fallback if blocked
    python main.py --max-pages 3 "URL"                      # Scrape only first 3 pages
    python main.py https://www.njuskalo.hr/auti             # Scrape specific URL
    python main.py https://example.com/listings --headless  # Scrape any URL with explicit headless
"""

import argparse
from scraper import main
import asyncio


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Scrape njuskalo listings with crawl4AI")
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="URL to scrape (defaults to https://www.njuskalo.hr/auti)",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=False,
        help="Run browser without UI",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run browser with visible UI",
    )
    parser.add_argument(
        "--fallback-visible-on-block",
        action="store_true",
        help="When blocked in headless mode, retry that page once in visible mode",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=100,
        help="Maximum number of pages to scrape from pagination (default: 100)",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    ok = asyncio.run(
        main(
            args.url,
            headless=args.headless,
            fallback_visible_on_block=args.fallback_visible_on_block,
            max_pages=args.max_pages,
        )
    )
    raise SystemExit(0 if ok else 1)
