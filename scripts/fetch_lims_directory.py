"""
Fetch and preserve raw BIS LIMS directory pages with cryptographic provenance.
Covers:
- /home/bis_labs/ (BIS Owned)
- /home/empaneled_labs/ (Empanelled)
- /home/labs/ (Recognized)
"""

import urllib.request
import json
import hashlib
import time
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

BASE_URL = "https://lims.bis.gov.in"
OUTPUT_DIR = Path("data/raw/immutable/lims_directory")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fetch_page(url: str, timeout: int = 20) -> tuple[bytes, int]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.status

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []

    endpoints = [
        ("BIS_OWNED", "/home/bis_labs/", 1),
        ("BIS_EMPANELLED", "/home/empaneled_labs/", 10),
        ("BIS_RECOGNIZED", "/home/labs/", 30),
    ]

    total_pages = 0
    total_records = 0

    for category, path, max_pages in endpoints:
        print(f"\n--- Fetching {category} from {path} ---")
        page = 1
        while page <= max_pages:
            url = f"{BASE_URL}{path}" if page == 1 else f"{BASE_URL}{path}?page={page}"
            print(f"Fetching page {page}: {url}...")
            try:
                raw_bytes, status = fetch_page(url)
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                break

            # Parse table rows to check if page has content
            soup = BeautifulSoup(raw_bytes.decode("utf-8", errors="ignore"), "html.parser")
            table = soup.find("table")
            rows = table.find_all("tr")[1:] if table else []
            if not rows:
                print(f"Page {page} has 0 rows. Reached end of pagination.")
                break

            sha = sha256_bytes(raw_bytes)
            page_slug = f"{category.lower()}_page_{page}"
            page_dir = OUTPUT_DIR / page_slug
            page_dir.mkdir(parents=True, exist_ok=True)

            (page_dir / "original.html").write_bytes(raw_bytes)

            meta = {
                "category": category,
                "endpoint": path,
                "page": page,
                "source_url": url,
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "http_status": status,
                "sha256": sha,
                "rows_found": len(rows)
            }
            (page_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

            manifest.append(meta)
            total_pages += 1
            total_records += len(rows)
            print(f"  -> Saved {len(rows)} rows (SHA: {sha[:12]}...)")

            # Check if there is a next page or if this was the last page
            if category == "BIS_OWNED":
                break  # Only 1 page

            page += 1
            time.sleep(0.3)  # Respectful pacing

    manifest_file = OUTPUT_DIR / "directory_manifest.json"
    manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nCompleted fetching {total_pages} directory pages with {total_records} total rows.")
    print(f"Manifest written to {manifest_file}")

if __name__ == "__main__":
    main()
