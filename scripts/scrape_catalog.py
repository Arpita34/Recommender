"""
Improved SHL Catalog Scraper
Uses SHL's internal API endpoint that powers their product catalog table.
This fetches ALL assessments across all pages instead of just what's visible
in the static HTML.
"""
import httpx
import json
import time
import os
from typing import Optional
from bs4 import BeautifulSoup

BASE_URL = "https://www.shl.com"

# SHL's internal API endpoint for the catalog table (paginated)
# start=0 means first page, &type=1 filters to Individual Test Solutions
CATALOG_API = "https://www.shl.com/solutions/products/product-catalog/?start={start}&type=1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def scrape_all_links():
    """Paginate through the SHL catalog and collect all product page URLs."""
    all_links = []
    start = 0
    page_size = 12  # SHL loads 12 items per page

    print("Collecting all product links via pagination...")
    while True:
        url = CATALOG_API.format(start=start)
        print(f"  Fetching page at start={start}: {url}")
        
        try:
            resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20.0)
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            print(f"  Error fetching page: {e}")
            break

        # Find product links on this page
        page_links = []
        for a in soup.select('a[href*="/view/"]'):
            href = a['href']
            if not href.startswith('http'):
                href = BASE_URL + href
            if href not in all_links and href not in page_links:
                page_links.append(href)

        if not page_links:
            print(f"  No more links found at start={start}. Done paginating.")
            break

        print(f"  Found {len(page_links)} links on this page.")
        all_links.extend(page_links)
        start += page_size
        time.sleep(1.5)  # Be polite

    print(f"\nTotal product links collected: {len(all_links)}")
    return all_links


def parse_product_page(html: str, url: str) -> Optional[dict]:
    """Parse a single product page and extract assessment metadata."""
    soup = BeautifulSoup(html, 'html.parser')

    # 1. Extract Name (h1)
    name_tag = soup.find('h1')
    if not name_tag:
        return None
    name = name_tag.text.strip()

    # 2. Description — prefer meta description tag
    description = ""
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        description = meta_desc['content'].strip()
    if not description:
        for p in soup.find_all('p'):
            if p.text.strip() and len(p.text.strip()) > 50:
                description = p.text.strip()
                break

    text_content_lower = soup.get_text().lower()

    # 3. Determine test_type based on keywords
    test_type = "K"  # Default to Knowledge
    type_keywords = {
        'P': ['personality', 'behaviour', 'opq'],
        'A': ['ability', 'aptitude', 'numerical reasoning', 'verbal reasoning', 'inductive reasoning'],
        'B': ['situational judgement', 'sjt'],
        'S': ['skill', 'microsoft office', 'typing', 'data entry'],
        'C': ['competency'],
        'K': ['knowledge', 'programming', 'language test', 'technical']
    }
    for t_code, keywords in type_keywords.items():
        if any(kw in text_content_lower for kw in keywords):
            test_type = t_code
            break

    # 4. Job levels
    job_levels = []
    level_map = {
        'Director': 'Director',
        'Executive': 'Executive',
        'Manager': 'Manager',
        'Professional': 'Professional',
        'Graduate': 'Graduate',
        'Entry-Level': 'Entry-Level',
        'Apprentice': 'Apprentice',
    }
    for label, val in level_map.items():
        if label.lower() in text_content_lower:
            job_levels.append(val)

    # 5. Competencies
    competencies = []
    comp_map = {
        'Programming': ['programming', 'coding', 'developer'],
        'Problem Solving': ['problem solving'],
        'Leadership': ['leadership', 'management'],
        'Communication': ['communication', 'verbal'],
        'Numerical': ['numerical', 'arithmetic', 'math'],
        'Customer Service': ['customer service', 'customer support'],
    }
    for comp, keywords in comp_map.items():
        if any(kw in text_content_lower for kw in keywords):
            competencies.append(comp)

    # CRITICAL: Filter out Pre-packaged Job Solutions.
    # Individual Test Solutions are identified by NOT having "job solution" in their
    # page content, or by having "/view/" style URLs that are NOT pre-packaged bundles.
    # Job Solutions typically have "pre-packaged" or end with "solution" describing a bundle.
    job_solution_signals = [
        'pre-packaged job solution',
        'this solution is a combination',
        'bundle of assessments',
        'multiple assessments for',
    ]
    if any(signal in text_content_lower for signal in job_solution_signals):
        return None  # Skip Job Solutions

    return {
        "name": name,
        "url": url,
        "description": description,
        "test_type": test_type,
        "job_levels": job_levels,
        "competencies": competencies,
        "duration_minutes": 30,
        "remote_testing": True
    }


def scrape_catalog():
    product_links = scrape_all_links()

    catalog = {}
    for i, url in enumerate(product_links):
        print(f"Scraping [{i+1}/{len(product_links)}]: {url}")
        time.sleep(1.2)
        try:
            page = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20.0)
            item = parse_product_page(page.text, url)
            if item:
                catalog[item['name']] = item
        except Exception as e:
            print(f"  Error: {e}")

    os.makedirs('data', exist_ok=True)
    with open('data/catalog.json', 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Scraped {len(catalog)} assessments into data/catalog.json")


if __name__ == '__main__':
    scrape_catalog()
