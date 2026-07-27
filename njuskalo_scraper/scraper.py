import asyncio
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
from urllib.parse import urljoin

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from bs4 import BeautifulSoup

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
        self.last_full_html: str = ""
        
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
            wait_until="networkidle",
            wait_for="js:() => document.querySelectorAll('article, [class*=\"EntityList\"], [class*=\"listing\"], [data-testid*=\"listing\"]').length > 0",  # Wait for listing-like nodes
            wait_for_timeout=45000,
            simulate_user=True,  # Simulate human-like behavior
            delay_before_return_html=2,  # Add delay to let JS finish
            word_count_threshold=10,  # Only extract if page has meaningful content
            remove_consent_popups=True,
            remove_overlay_elements=True,
            js_code_before_wait=[
                """
                (() => {
                    const selectors = [
                        'button[aria-label*="Prihvati i zatvori"]',
                        'button[aria-label*="Prihvati"]',
                        '#didomi-notice-agree-button',
                        'button[id*="agree"]'
                    ];
                    for (const sel of selectors) {
                        try {
                            const el = document.querySelector(sel);
                            if (el) {
                                el.click();
                                return true;
                            }
                        } catch (_) {
                            // Ignore invalid selectors and continue.
                        }
                    }

                    // Fallback by visible text content.
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const accept = buttons.find((btn) => /prihvati/i.test((btn.textContent || '').trim()));
                    if (accept) {
                        accept.click();
                        return true;
                    }
                    return false;
                })();
                """
            ],
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
        extracted_titles: List[str] = []
        if result.markdown:
            extracted_titles = self._extract_listing_titles_from_markdown(result.markdown)

        listing_items = self._extract_listing_items_from_html(result.html, result.url)
        self.last_full_html = result.html or ""

        listing = {
            "metadata": metadata,
            "raw_content_preview": result.markdown[:500] if result.markdown else "",
            "raw_html_length": len(result.html) if result.html else 0,
            "raw_html": result.html[:2000] if result.html else "",  # Store first 2KB for debugging
            "sample_listing_titles": extracted_titles[:20],
            "sample_listing_titles_count": len(extracted_titles),
            "extracted_listings_count": len(listing_items),
            "extracted_listings_sample": listing_items[:30],
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

    def _extract_listing_titles_from_markdown(self, markdown: str) -> List[str]:
        """Extract listing titles from markdown links that point to oglas pages."""
        # Typical listing links contain /oglas- in the URL.
        pattern = re.compile(r"\[(?P<title>[^\]]+)\]\((?P<url>https?://[^)]+/oglas-[^)]+)\)")
        titles: List[str] = []
        seen = set()
        for match in pattern.finditer(markdown):
            title = match.group("title").strip()
            if title and title not in seen:
                seen.add(title)
                titles.append(title)
        return titles

    def _extract_listing_items_from_html(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Extract listing links from HTML.

        This targets njuskalo ad URLs containing -oglas-.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        items: List[Dict[str, Any]] = []
        seen_urls = set()

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()
            if "-oglas-" not in href:
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue

            title = link.get_text(" ", strip=True)
            if not title:
                title = (link.get("title") or "").strip()
            if not title:
                continue

            # Find the listing card/container to extract structured fields.
            container = None
            node = link
            for _ in range(8):
                node = node.parent
                if node is None:
                    break
                if node.name == "article":
                    container = node
                    break

            if container is None:
                container = link.parent

            card_text = " ".join(container.get_text(" ", strip=True).split()) if container else ""
            year, location, price = self._extract_listing_details_from_text(card_text)

            seen_urls.add(full_url)
            items.append({
                "title": title,
                "url": full_url,
                "price": price,
                "location": location,
                "year": year,
            })

        return items

    def _extract_listing_details_from_text(self, text: str) -> tuple[Any, str, str]:
        """Extract year, location and price from listing card text."""
        year = None
        location = ""
        price = ""

        year_match = re.search(r"Godište automobila:\s*(\d{4})", text)
        if year_match:
            year = int(year_match.group(1))

        location_match = re.search(
            r"Lokacija vozila:\s*(.+?)(?:\s+Financiranje\b|\s+Objavljen:\b|\s+Prikaži na mapi\b|$)",
            text,
            flags=re.IGNORECASE,
        )
        if location_match:
            location = location_match.group(1).strip()

        # Prefer the highest euro amount in the card text, which is typically the main listing price.
        amount_matches = re.findall(r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?\s*€)", text)
        if amount_matches:
            best = max(amount_matches, key=self._price_sort_key)
            price = best.strip()

        return year, location, price

    def _price_sort_key(self, amount: str) -> float:
        """Convert localized euro amount to numeric sort key."""
        normalized = amount.replace("€", "").replace(".", "").replace(" ", "").replace(",", ".")
        try:
            return float(normalized)
        except ValueError:
            return 0.0
    
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
            if self.last_full_html:
                html_file = output_path.parent / "debug_raw.html"
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(self.last_full_html)
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
        url = "https://www.njuskalo.hr/auti"
    
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
