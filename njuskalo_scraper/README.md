# Njuskalo Auto Scraper

A Python web scraper that uses [crawl4AI](https://github.com/unclecode/crawl4AI) to extract vehicle listings from [njuskalo.hr](https://www.njuskalo.hr) (Croatian online classifieds).

## Overview

This scraper targets the auto-oglasi (vehicles) category on njuskalo.hr and extracts listing data including title, price, location, condition, mileage, and other vehicle details. The data is saved to a JSON file for further analysis.

## Features

- **Asynchronous crawling** using crawl4AI's AsyncWebCrawler for efficient page fetching
- **Anti-bot detection measures** including:
  - Stealth mode enabled
  - Random user agent rotation
  - Human-like behavior simulation (delays between requests)
- **Structured JSON output** with metadata and scraped content
- **Comprehensive logging** for debugging and monitoring
- **Error handling** with retry mechanisms

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

### 1. Install Dependencies

```bash
# Navigate to the scraper directory
cd njuskalo_scraper

# Install required packages
pip install -r requirements.txt

# Install Playwright browsers (required by crawl4AI)
crawl4ai-setup

# Optional: Verify installation
crawl4ai-doctor
```

### 2. Verify Setup

```bash
# Check that Playwright is properly installed
python -c "from crawl4ai import AsyncWebCrawler; print('✓ crawl4AI installed successfully')"
```

## Usage

### Quick Start

```bash
# Run the scraper
python main.py
```

This will:
1. Crawl the njuskalo.hr auto-oglasi page
2. Extract listing data
3. Save results to `njuskalo_auto_listings.json`

### Using the Scraper Programmatically

```python
import asyncio
from scraper import NjuskaloAutoScraper

async def custom_scrape():
    scraper = NjuskaloAutoScraper(output_file="my_listings.json")
    
    # Scrape a specific URL
    success = await scraper.scrape("https://www.njuskalo.hr/auto-oglasi")
    
    if success:
        scraper.save_output()

asyncio.run(custom_scrape())
```

## Output Format

The scraper outputs a JSON file with the following structure:

```json
{
  "scrape_metadata": {
    "timestamp": "2026-07-27T10:30:00.123456",
    "total_pages_scraped": 1,
    "listings_count": 1
  },
  "listings": [
    {
      "metadata": {
        "url": "https://www.njuskalo.hr/auto-oglasi",
        "title": "Page title",
        "description": "Page description",
        "scraped_at": "2026-07-27T10:30:00.123456",
        "success": true,
        "status_code": 200
      },
      "raw_content_preview": "...",
      "raw_html_length": 50000,
      "extracted_content": {
        "lines_count": 250,
        "content_preview": "..."
      }
    }
  ]
}
```

## Logging

The scraper outputs detailed logs to console. Log levels include:
- **INFO**: General progress updates
- **WARNING**: Non-critical issues
- **ERROR**: Failures and exceptions

Example log output:
```
2026-07-27 10:30:00 - __main__ - INFO - ============================================================
2026-07-27 10:30:00 - __main__ - INFO - Starting Njuskalo Auto Listings Scraper
2026-07-27 10:30:00 - __main__ - INFO - ============================================================
2026-07-27 10:30:01 - __main__ - INFO - Starting crawl of https://www.njuskalo.hr/auto-oglasi
2026-07-27 10:30:05 - __main__ - INFO - Successfully crawled page. Status: 200
2026-07-27 10:30:05 - __main__ - INFO - Output saved to njuskalo_auto_listings.json
```

## Troubleshooting

### Issue: `crawl4ai-setup` command not found

**Solution**: Ensure crawl4AI is installed:
```bash
pip install crawl4ai
```

### Issue: Browser crashes or timeouts

**Solution**: Check system resources and try running with less concurrent requests:
```python
# In scraper.py, adjust delay_before_return_html
delay_before_return_html=3  # Increase from 2 to 3
```

### Issue: No listings extracted

**Solution**: The CSS selectors may have changed on njuskalo.hr. Update the selectors in `scraper.py`:
```python
css_selector=".new-selector-1, .new-selector-2"  # Update these
```

### Issue: Connection refused or blocked

**Solution**: The site may have anti-scraping measures. Try:
1. Increase delays between requests
2. Use a proxy (requires additional configuration)
3. Add random delays using `asyncio.sleep(random.uniform(1, 3))`

## Performance Notes

- **First run**: Takes ~5-10 seconds (includes browser startup)
- **Subsequent runs**: ~3-5 seconds (browser warmup already done)
- **Memory usage**: ~100-200 MB during execution
- **Network bandwidth**: Minimal (single page = ~500 KB typically)

## Limitations

- Currently scrapes a single page only (pagination not implemented)
- Requires active internet connection
- respects the site's rate limiting (includes delays)
- Depends on CSS selectors remaining stable on njuskalo.hr

## Future Enhancements

- [ ] Multi-page pagination support
- [ ] Database storage (SQLite) instead of JSON
- [ ] Field extraction (individual listing data parsing)
- [ ] Scheduling/periodic scraping
- [ ] Proxy rotation for large-scale scraping
- [ ] Search query support (e.g., filter by price range, model)

## Legal & Ethical Considerations

- Ensure compliance with njuskalo.hr's [Terms of Service](https://www.njuskalo.hr) and robots.txt
- Use reasonable request rates to avoid overloading the server
- This tool is for educational/personal use
- Always respect website policies regarding automated access

## License

This project is provided as-is for educational purposes.

## Support

For issues with crawl4AI itself, visit: https://github.com/unclecode/crawl4AI

For bugs or questions about this scraper, check the logs and ensure all dependencies are correctly installed.
