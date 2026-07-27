# Njuskalo Auto Scraper

Scrapes vehicle listings from Njuskalo using crawl4AI and exports structured JSON.

## Features

- Crawls all pagination pages for the provided URL.
- Extracts per-listing fields:
  - `title`
  - `url`
  - `price`
  - `location`
  - `year`
- Handles consent/overlay popups.
- Supports headless or visible browser mode.
- Produces both per-page data and flattened deduplicated listing output.

## Requirements

- Python 3.10+
- Virtual environment recommended

## Setup

```bash
cd njuskalo_scraper
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Usage

### Basic

```bash
python main.py
```

Uses default URL:

`https://www.njuskalo.hr/auti`

### Custom URL

```bash
python main.py "https://www.njuskalo.hr/auti/nissan-qashqai"
```

### Headless Toggle

```bash
# Visible browser (default)
python main.py --no-headless "https://www.njuskalo.hr/auti/nissan-qashqai"

# Headless
python main.py --headless "https://www.njuskalo.hr/auti/nissan-qashqai"

# Headless first, retry blocked pages in visible mode
python main.py --headless --fallback-visible-on-block "https://www.njuskalo.hr/auti/nissan-qashqai"
```

### CLI Help

```bash
python main.py --help
```

## Important (zsh)

If the URL contains query parameters, wrap it in quotes:

```bash
python main.py --headless "https://www.njuskalo.hr/auti/nissan-qashqai?page=1"
python main.py --headless "https://www.njuskalo.hr/auti/seat-ateca?yearManufactured[min]=2024"
```

Without quotes, zsh may throw `no matches found`.

Alternative (escaping):

```bash
python main.py --headless https://www.njuskalo.hr/auti/seat-ateca\?yearManufactured\[min\]=2024
```

## Output

The scraper writes `njuskalo_auto_listings.json` with:

- `scrape_metadata`
  - `timestamp`
  - `total_pages_scraped`
  - `listings_count`
- `pages`
  - Per-page crawl metadata and extracted records
- `listings`
  - Flattened deduplicated listing objects across all pages

Example listing object:

```json
{
  "title": "Nissan Qashqai 1,5 dCi",
  "url": "https://www.njuskalo.hr/auti/nissan-qashqai-1.5-dci-oglas-50655305",
  "price": "14.999 €",
  "location": "Varaždin, Jalkovečka",
  "year": 2018
}
```

## Notes

- Full multi-page crawling can take several minutes.
- If one page fails temporarily, the scraper continues with other pages.
- `debug_raw.html` stores the latest crawled page HTML for debugging.

## Disclaimer

Use responsibly and respect Njuskalo terms, robots rules, and local laws.
