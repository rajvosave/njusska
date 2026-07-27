import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NjuskaloAutoScraper:
    """Scraper for njuskalo.hr auto-oglasi (vehicle listings)."""
    
    def __init__(self, output_file: str = "listings.json"):
        """Initialize the scraper with output file configuration.
        
        Args:
            output_file: Path to save JSON output
        """
        self.output_file = output_file
        self.listings: List[Dict[str, Any]] = []
        
    async def scrape(self, url: str) -> bool:
        """Scrape a njuskalo.hr auto listings page.
        
        Args:
            url: URL to scrape (e.g., https://www.njuskalo.hr/auto-oglasi)
            
        Returns:
            True if successful, False otherwise
        """
        # Configure browser with anti-bot measures
        browser_config = BrowserConfig(
            headless=False,  # Set to False to see the browser window
            verbose=True,    # Enable verbose logging
        )
        
        # Configure crawl parameters
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # Don't use cache
            wait_for="document.readyState == 'complete'",  # Wait for full page load
            wait_for_images=True,  # Wait for images to load
            simulate_user=True,  # Simulate human-like behavior
            delay_before_return_html=3,  # Increase delay to let JS run
            css_selector=".entity_container, .listingItem, [data-listing], .listing",  # Try multiple selectors
            page_timeout=90000,  # Increase page timeout
        )
        
        try:
            logger.info(f"Starting crawl of {url}")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)
                
                if not result.success:
                    logger.error(f"Crawl failed: {result.status_code}")
                    return False
                
                logger.info(f"Successfully crawled page. Status: {result.status_code}")
                
                # Parse listings from markdown/HTML content
                self._parse_listings(result)
                
                return True
                
        except Exception as e:
            logger.error(f"Error during crawl: {e}", exc_info=True)
            return False
    
    def _parse_listings(self, result: Any) -> None:
        """Extract listing data from crawl result.
        
        Args:
            result: CrawlResult object from crawl4ai
        """
        # Extract metadata
        metadata = {
            "url": result.url,
            "title": result.metadata.get("title", "N/A"),
            "description": result.metadata.get("description", ""),
            "scraped_at": datetime.now().isoformat(),
            "success": result.success,
            "status_code": result.status_code,
        }
        
        # Debug output
        logger.info(f"Page title: {metadata['title']}")
        logger.info(f"HTTP Status: {result.status_code}")
        logger.info(f"Markdown length: {len(result.markdown) if result.markdown else 0} chars")
        logger.info(f"HTML length: {len(result.html) if result.html else 0} chars")
        
        # Store the raw markdown content for analysis
        # In a production setup, you would parse the HTML more intelligently
        # For now, we'll store the page metadata and raw content
        listing = {
            "metadata": metadata,
            "raw_content_preview": result.markdown[:500] if result.markdown else "",
            "raw_html_length": len(result.html) if result.html else 0,
            "raw_html": result.html[:2000] if result.html else "",  # Store first 2KB for debugging
        }
        
        # If we have extracted markdown, try to identify individual listings
        if result.markdown:
            listings_text = result.markdown
            # Try to identify listing entries (this is a basic approach)
            # In production, you'd parse the DOM more carefully
            lines = listings_text.split('\n')
            
            listing["extracted_content"] = {
                "lines_count": len(lines),
                "content_preview": '\n'.join(lines[:20])
            }
        
        self.listings.append(listing)
        logger.info(f"Parsed page listing. Total listings: {len(self.listings)}")
    
    def save_output(self) -> str:
        """Save scraped listings to JSON file.
        
        Returns:
            Path to the output file
        """
        output_path = Path(self.output_file)
        
        # Create output structure
        output_data = {
            "scrape_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_pages_scraped": len(self.listings),
                "listings_count": len(self.listings),
            },
            "listings": self.listings
        }
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Output saved to {output_path}")
            
            # Also save raw HTML for debugging if available
            if self.listings and len(self.listings) > 0:
                first_listing = self.listings[0]
                if "raw_html" in first_listing and first_listing["raw_html"]:
                    html_file = output_path.parent / "debug_raw.html"
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(first_listing["raw_html"])
                    logger.info(f"Raw HTML saved to {html_file} for debugging")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error saving output: {e}", exc_info=True)
            raise


async def main(url: str = None):
    """Main entry point for the scraper.
    
    Args:
        url: URL to scrape. Defaults to njuskalo.hr auto listings if not provided.
    """
    # URL for njuskalo.hr auto listings (default)
    if url is None:
        url = "https://www.njuskalo.hr/auto-oglasi"
    
    # Initialize scraper
    scraper = NjuskaloAutoScraper(output_file="njuskalo_auto_listings.json")
    
    # Run the scrape
    logger.info("=" * 60)
    logger.info("Starting Njuskalo Auto Listings Scraper")
    logger.info("=" * 60)
    
    success = await scraper.scrape(url)
    
    if success:
        output_file = scraper.save_output()
        logger.info(f"Scrape completed successfully. Results saved to: {output_file}")
    else:
        logger.error("Scrape failed. Please check the logs above.")
        return False
    
    logger.info("=" * 60)
    logger.info("Scraper finished")
    logger.info("=" * 60)
    
    return True


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
