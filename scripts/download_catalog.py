"""
Download Official SHL Catalog
Fetches the official SHL product catalog from the SHL API endpoint,
normalizes it to our app's format, and saves it as data/catalog.json.

This replaces the web-scraped catalog with official, accurate data.
Run this script once to get the best possible catalog.
"""
import httpx
import json
import os
import re

CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"

# Fix URL prefix: the API uses /products/ but live site uses /solutions/products/
OLD_PREFIX = "https://www.shl.com/products/product-catalog/view/"
NEW_PREFIX = "https://www.shl.com/solutions/products/product-catalog/view/"

# Full mapping of all 8 keys to single-letter test type codes
KEYS_TO_TYPE = {
    "Knowledge & Skills":             "K",
    "Personality & Behavior":         "P",
    "Ability & Aptitude":             "A",
    "Biodata & Situational Judgment": "B",
    "Competencies":                   "C",
    "Simulations":                    "S",
    "Assessment Exercises":           "E",
    "Development & 360":              "D",
}

def keys_to_test_type(keys: list) -> str:
    codes = []
    for key in keys:
        code = KEYS_TO_TYPE.get(key)
        if code and code not in codes:
            codes.append(code)
    return ",".join(codes) if codes else "K"

def parse_duration(duration_str: str) -> int:
    """Extract minutes from duration string like '30 minutes'."""
    if not duration_str:
        return 0
    nums = re.findall(r"\d+", str(duration_str))
    return int(nums[0]) if nums else 0

def normalize_entry(item: dict) -> dict:
    """Convert one raw API entry to our app's catalog format."""
    url = item.get("link", "")
    # Fix URL prefix
    if url.startswith(OLD_PREFIX):
        url = url.replace(OLD_PREFIX, NEW_PREFIX, 1)

    keys = item.get("keys", [])
    test_type = keys_to_test_type(keys)

    return {
        "name":             item.get("name", ""),
        "url":              url,
        "description":      item.get("description", ""),
        "test_type":        test_type,
        "keys":             keys,
        "job_levels":       item.get("job_levels", []),
        "languages":        item.get("languages", []),
        "duration_minutes": parse_duration(item.get("duration", "")),
        "remote_testing":   item.get("remote", "no") == "yes",
        "adaptive":         item.get("adaptive", "no") == "yes",
        "competencies":     [],  # Not in API — populated from description/keys heuristics
    }

def download_catalog():
    print(f"Downloading official SHL catalog from:\n  {CATALOG_URL}\n")
    
    try:
        resp = httpx.get(CATALOG_URL, timeout=30.0)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Failed to download catalog: {e}")
        return

    # The API response sometimes contains raw control characters inside strings.
    # Parse with strict=False to allow them, then clean up.
    try:
        raw_data = json.loads(resp.content, strict=False)
    except Exception:
        # Last resort: strip control characters and retry
        cleaned = re.sub(r'[\x00-\x1f\x7f](?<![\n\r\t])', '', resp.text)
        raw_data = json.loads(cleaned)
    print(f"✅ Downloaded {len(raw_data)} raw entries.")

    # Normalize all entries
    catalog = {}
    skipped = 0
    for item in raw_data:
        name = item.get("name", "").strip()
        if not name:
            skipped += 1
            continue
        
        # Skip entries with bad status
        if item.get("status", "ok") != "ok":
            skipped += 1
            continue

        normalized = normalize_entry(item)
        catalog[name] = normalized

    print(f"✅ Normalized {len(catalog)} entries ({skipped} skipped).")

    # Show breakdown by test type
    from collections import Counter
    type_counts = Counter()
    for entry in catalog.values():
        for code in entry["test_type"].split(","):
            type_counts[code.strip()] += 1
    print("\n📊 Breakdown by test type:")
    for code, count in sorted(type_counts.items()):
        label = {v: k for k, v in KEYS_TO_TYPE.items()}.get(code, code)
        print(f"  {code}: {count:3d}  ({label})")

    # Save
    os.makedirs("data", exist_ok=True)
    out_path = "data/catalog.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Saved to {out_path}")
    print("\nNext step: run  python scripts/build_index.py  to rebuild FAISS index.")

if __name__ == "__main__":
    download_catalog()
