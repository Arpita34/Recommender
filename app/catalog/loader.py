import json
import os

def load_catalog(path: str) -> dict:
    """Loads the scraped JSON catalog from disk."""
    if not os.path.exists(path):
        print(f"Warning: Catalog not found at {path}")
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
