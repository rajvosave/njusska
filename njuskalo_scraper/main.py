#!/usr/bin/env python3
"""
Njuskalo Auto Scraper Runner

This script scrapes vehicle listings from njuskalo.hr auto-oglasi category
and saves the data to a JSON file.

Usage:
    python main.py                                          # Scrape default URL (auti)
    python main.py https://www.njuskalo.hr/auti             # Scrape specific URL
    python main.py https://example.com/listings             # Scrape any URL
"""

import sys
from scraper import main
import asyncio

if __name__ == "__main__":
    # Get URL from command-line argument if provided
    url = None
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    asyncio.run(main(url))
