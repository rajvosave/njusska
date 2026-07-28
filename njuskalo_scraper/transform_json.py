#!/usr/bin/env python3
"""Transform existing JSON to add mileage and flatten listings."""

import json
import re
from pathlib import Path

def extract_mileage(text):
    """Extract mileage from listing text using 'Rabljeno vozilo' pattern."""
    # Look for "Rabljeno vozilo, {number} km" pattern
    mileage_match = re.search(r'Rabljeno vozilo[,:]?\s*([\d.]+)\s*km\b', text, re.IGNORECASE)
    if mileage_match:
        return f"{mileage_match.group(1)} km"
    return ""

def transform_listings():
    """Transform the JSON file with new structure."""
    json_path = Path("njuskalo_auto_listings.json")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Flatten all listings from all pages and add mileage
    all_listings = []
    seen_urls = set()
    
    for page in data.get("pages", []):
        for listing in page.get("extracted_listings", []):
            url = listing.get("url")
            if url and url not in seen_urls:
                # Add mileage from title and other text
                title = listing.get("title", "")
                mileage = extract_mileage(title)
                
                listing_copy = listing.copy()
                listing_copy["mileage"] = mileage
                
                all_listings.append(listing_copy)
                seen_urls.add(url)
    
    # Clean up pages - remove extracted_listings_sample and extracted_listings
    cleaned_pages = []
    for page in data.get("pages", []):
        cleaned_page = {
            k: v for k, v in page.items() 
            if k not in ["extracted_listings_sample", "extracted_listings"]
        }
        cleaned_pages.append(cleaned_page)
    
    # Create new output structure
    output = {
        "scrape_metadata": {
            "timestamp": data["scrape_metadata"]["timestamp"],
            "total_pages_scraped": len(data.get("pages", [])),
            "listings_count": len(all_listings),
        },
        "pages": cleaned_pages,
        "listings": all_listings,
    }
    
    # Save the transformed JSON
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Transformed JSON file")
    print(f"  - Added 'mileage' field using 'Rabljeno vozilo' pattern")
    print(f"  - Successfully extracted mileage: {len([l for l in all_listings if l.get('mileage')])}/{len(all_listings)} listings")

if __name__ == "__main__":
    transform_listings()
