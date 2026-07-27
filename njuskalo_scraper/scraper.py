import asyncio
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _path_parts(path: str) -> List[str]:
    """Return non-empty URL path segments."""
    return [part for part in path.split("/") if part]


class NjuskaloAutoScraper:
    """Scraper for njuskalo.hr auto-oglasi (vehicle listings)."""
    
    def __init__(
        self,
        output_file: str = "listings.json",
        headless: bool = False,
        fallback_visible_on_block: bool = False,
    ):
        """Initialize the scraper with output file configuration.
        
        Args:
            output_file: Path to save JSON output
            headless: Whether to run browser in headless mode
            fallback_visible_on_block: Retry blocked pages in visible browser mode
        """
        self.output_file = output_file
        self.headless = headless
        self.fallback_visible_on_block = fallback_visible_on_block
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
            headless=self.headless,
            verbose=True,    # Enable verbose logging
        )
        
        # Configure crawl parameters
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,  # Don't use cache
            wait_until="domcontentloaded",
            wait_for="js:() => document.querySelectorAll('article, [class*=\"EntityList\"], [class*=\"listing\"], [data-testid*=\"listing\"]').length > 0",  # Wait for listing-like nodes
            wait_for_timeout=45000,
            page_timeout=120000,
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
            start_url = self._normalize_url(url)
            if start_url != url:
                logger.info(f"Normalized URL: {start_url}")
            
            async with AsyncWebCrawler(config=browser_config) as crawler:
                queue = [start_url]
                crawled = set()
                max_pages = 100

                while queue and len(crawled) < max_pages:
                    current_url = queue.pop(0)
                    if current_url in crawled:
                        continue

                    logger.info(f"Crawling page {len(crawled) + 1}: {current_url}")
                    result = await crawler.arun(url=current_url, config=run_config)

                    if not result.success:
                        logger.warning(f"Retrying failed page with relaxed config: {current_url}")
                        retry_config = CrawlerRunConfig(
                            cache_mode=CacheMode.BYPASS,
                            wait_until="domcontentloaded",
                            page_timeout=120000,
                            wait_for_timeout=60000,
                            simulate_user=True,
                            delay_before_return_html=3,
                            word_count_threshold=1,
                            remove_consent_popups=True,
                            remove_overlay_elements=True,
                        )
                        result = await crawler.arun(url=current_url, config=retry_config)

                    if not result.success:
                        logger.warning(f"Page crawl failed ({current_url}): {result.status_code}")
                        crawled.add(current_url)
                        continue

                    if self._is_block_page(result):
                        logger.warning(f"Blocked by anti-bot/captcha on page: {current_url}")
                        if self.headless and self.fallback_visible_on_block:
                            logger.warning("Retrying blocked page in visible browser mode.")
                            fallback_result = await self._retry_visible_mode(current_url, run_config)
                            if fallback_result and fallback_result.success and not self._is_block_page(fallback_result):
                                result = fallback_result
                            else:
                                logger.warning("Visible-mode retry still blocked or failed.")
                                crawled.add(current_url)
                                continue
                        else:
                            if self.headless:
                                logger.warning("Try running with --no-headless or --fallback-visible-on-block.")
                            crawled.add(current_url)
                            continue

                    logger.info(f"Successfully crawled page. Status: {result.status_code}")

                    # Parse listings from markdown/HTML content
                    self._parse_listings(result)
                    crawled.add(current_url)

                    # Discover additional pagination URLs and enqueue unseen pages.
                    page_urls = self._extract_pagination_urls(result.html, result.url)
                    for page_url in page_urls:
                        if page_url not in crawled and page_url not in queue:
                            queue.append(page_url)

                if not self.listings:
                    logger.error("No pages were successfully scraped.")
                    return False

                logger.info(f"Pagination crawl completed. Pages scraped: {len(self.listings)}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error during crawl: {e}", exc_info=True)
            return False

    def _is_block_page(self, result: Any) -> bool:
        """Return True when crawl result appears to be a captcha/anti-bot page."""
        title = (result.metadata.get("title") or "").lower()
        indicators = ["shieldsquare captcha", "captcha"]
        return any(ind in title for ind in indicators)

    async def _retry_visible_mode(self, url: str, run_config: CrawlerRunConfig) -> Any:
        """Retry a blocked URL using a visible browser instance."""
        browser_config = BrowserConfig(
            headless=False,
            verbose=True,
        )
        try:
            async with AsyncWebCrawler(config=browser_config) as crawler:
                return await crawler.arun(url=url, config=run_config)
        except Exception as exc:
            logger.warning(f"Visible-mode retry failed: {exc}")
            return None

    def _normalize_url(self, raw_url: str) -> str:
        """Normalize URL by preserving query parameters via standard encoding."""
        parsed = urlparse(raw_url)
        query_items = parse_qsl(parsed.query, keep_blank_values=True)
        normalized_query = urlencode(query_items, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, normalized_query, parsed.fragment))

    def _extract_pagination_urls(self, html: str, current_url: str) -> List[str]:
        """Extract pagination URLs from a result page.

        Returns URLs on the same path with numeric page query params.
        """
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        parsed_current = urlparse(current_url)
        current_path = parsed_current.path
        current_q = dict(parse_qsl(parsed_current.query, keep_blank_values=True))

        pages = set()
        current_page = int(current_q.get("page", "1")) if current_q.get("page", "1").isdigit() else 1
        pages.add(current_page)

        for link in soup.find_all("a", href=True):
            absolute = urljoin(current_url, link["href"].strip())
            parsed = urlparse(absolute)

            if parsed.path != current_path:
                continue

            q = dict(parse_qsl(parsed.query, keep_blank_values=True))
            page_value = q.get("page")
            if not page_value or not page_value.isdigit():
                continue

            pages.add(int(page_value))

        # Njuskalo embeds total page count in a JSON blob, use it when present.
        total_pages_match = re.search(r'"totalPageCount"\s*:\s*(\d+)', html)
        if total_pages_match:
            total_pages = int(total_pages_match.group(1))
            if total_pages > 1:
                pages.update(range(1, total_pages + 1))

        if len(pages) <= 1:
            return []

        discovered: List[str] = []
        for page_num in sorted(pages):
            q = dict(current_q)
            if page_num == 1:
                q.pop("page", None)
            else:
                q["page"] = str(page_num)

            query = urlencode(q)
            page_url = urlunparse((parsed_current.scheme, parsed_current.netloc, current_path, "", query, ""))
            if page_url != current_url:
                discovered.append(page_url)

        return discovered
    
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
            "extracted_listings": listing_items,
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
        scope = self._build_listing_scope(base_url)

        listing_cards = self._find_listing_cards(soup)
        for card in listing_cards:
            link = card.find("a", href=True)
            if link is None:
                continue

            href = link.get("href", "").strip()
            if "-oglas-" not in href:
                continue

            full_url = urljoin(base_url, href)
            if full_url in seen_urls:
                continue
            if not self._is_relevant_listing_url(full_url, scope):
                continue

            title = link.get_text(" ", strip=True)
            if not title:
                title = (link.get("title") or "").strip()
            if not title:
                continue

            card_text = " ".join(card.get_text(" ", strip=True).split())
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

    def _find_listing_cards(self, soup: BeautifulSoup) -> List[Any]:
        """Return article nodes from the main search result list only."""
        sections = soup.select("section.EntityList--ListItemRegularAd")
        cards: List[Any] = []
        for section in sections:
            cards.extend(section.select("li.EntityList-item article"))

        if cards:
            return cards

        return list(soup.find_all("article"))

    def _build_listing_scope(self, base_url: str) -> Dict[str, str]:
        """Build category/model scope from the requested page URL."""
        parsed = urlparse(base_url)
        parts = _path_parts(parsed.path)
        category = parts[0] if parts else ""
        slug = parts[-1] if parts else ""
        canonical_category = "auti" if category == "rabljeni-auti" else category
        return {
            "netloc": parsed.netloc.lower(),
            "category": canonical_category,
            "requested_category": category,
            "slug": slug,
        }

    def _is_relevant_listing_url(self, listing_url: str, scope: Dict[str, str]) -> bool:
        """Return True if listing URL belongs to the active category/model scope."""
        parsed = urlparse(listing_url)
        if scope["netloc"] and parsed.netloc.lower() != scope["netloc"]:
            return False

        parts = _path_parts(parsed.path)
        if len(parts) < 2:
            return False

        category = scope.get("category", "")
        if category and parts[0] != category:
            return False

        slug = scope.get("slug", "")
        requested_category = scope.get("requested_category", "")
        if slug and requested_category == "auti" and not parts[1].startswith(f"{slug}-"):
            return False

        return True

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

        all_listings: List[Dict[str, Any]] = []
        seen_urls = set()
        for page in self.listings:
            for item in page.get("extracted_listings", []):
                url = item.get("url")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                all_listings.append(item)
        
        # Create output structure
        output_data = {
            "scrape_metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_pages_scraped": len(self.listings),
                "listings_count": len(all_listings),
            },
            "pages": self.listings,
            "listings": all_listings,
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


async def main(
    url: str = None,
    headless: bool = False,
    fallback_visible_on_block: bool = False,
):
    """Main entry point for the scraper.
    
    Args:
        url: URL to scrape. Defaults to njuskalo.hr auto listings if not provided.
        headless: Whether to run browser in headless mode.
        fallback_visible_on_block: Retry blocked pages in visible browser mode.
    """
    # URL for njuskalo.hr auto listings (default)
    if url is None:
        url = "https://www.njuskalo.hr/auti"
    
    # Initialize scraper
    scraper = NjuskaloAutoScraper(
        output_file="njuskalo_auto_listings.json",
        headless=headless,
        fallback_visible_on_block=fallback_visible_on_block,
    )
    
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
