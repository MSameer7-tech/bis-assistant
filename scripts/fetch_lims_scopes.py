"""
Concurrent scope fetcher for discoverable BIS LIMS laboratories.
Fetches https://lims.bis.gov.in/home_lab_scope/<internal_id>/
Preserves raw HTML and cryptographic metadata in data/raw/immutable/lims_scope/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import urllib.request
import json
import hashlib
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

from ai.lims.extractor import LimsExtractor
from ai.lims.models import LabCategory

BASE_URL = "https://lims.bis.gov.in"
DIRECTORY_DIR = Path("data/raw/immutable/lims_directory")
SCOPE_DIR = Path("data/raw/immutable/lims_scope")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fetch_single_scope(lab_info: dict) -> dict:
    internal_id = lab_info["internal_id"]
    lab_code = lab_info["lab_code"]
    lab_name = lab_info["lab_name"]
    category = lab_info["category"]

    target_dir = SCOPE_DIR / f"lab_{internal_id}"
    meta_file = target_dir / "metadata.json"
    html_file = target_dir / "original.html"

    url = f"{BASE_URL}/home_lab_scope/{internal_id}/"

    # If already cached, read from disk
    if meta_file.exists() and html_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            html_bytes = html_file.read_bytes()
            soup = BeautifulSoup(html_bytes.decode("utf-8", errors="ignore"), "html.parser")
            table = soup.find("table", {"id": "review_lab_list"}) or soup.find("table", class_="table-bordered")
            rows = table.find_all("tr")[1:] if table else []
            scope_status = "SCOPE_AVAILABLE" if len(rows) > 0 else "SCOPE_EMPTY"
            return {
                "internal_id": internal_id,
                "lab_code": lab_code,
                "lab_name": lab_name,
                "category": category,
                "scope_status": scope_status,
                "scope_rows": len(rows),
                "cached": True,
                "error": None
            }
        except Exception as e:
            pass  # Re-fetch if cache corrupt

    # Fetch over network
    req = urllib.request.Request(url, headers=HEADERS)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            status = resp.status
            sha = sha256_bytes(data)

            # Analyze scope table
            soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
            table = soup.find("table", {"id": "review_lab_list"}) or soup.find("table", class_="table-bordered")
            rows = table.find_all("tr")[1:] if table else []
            scope_status = "SCOPE_AVAILABLE" if len(rows) > 0 else "SCOPE_EMPTY"

            target_dir.mkdir(parents=True, exist_ok=True)
            html_file.write_bytes(data)

            meta = {
                "internal_id": internal_id,
                "lab_code": lab_code,
                "lab_name": lab_name,
                "category": category,
                "source_url": url,
                "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
                "http_status": status,
                "sha256": sha,
                "scope_rows": len(rows),
                "scope_status": scope_status
            }
            meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

            return {
                "internal_id": internal_id,
                "lab_code": lab_code,
                "lab_name": lab_name,
                "category": category,
                "scope_status": scope_status,
                "scope_rows": len(rows),
                "cached": False,
                "error": None
            }
    except Exception as e:
        return {
            "internal_id": internal_id,
            "lab_code": lab_code,
            "lab_name": lab_name,
            "category": category,
            "scope_status": "SCOPE_REQUEST_FAILED",
            "scope_rows": 0,
            "cached": False,
            "error": str(e)
        }

def main():
    SCOPE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_file = DIRECTORY_DIR / "directory_manifest.json"
    if not manifest_file.exists():
        print(f"Error: {manifest_file} not found. Run fetch_lims_directory.py first.")
        return

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

    # Extract all discovered directory labs
    all_labs = []
    for entry in manifest:
        cat = LabCategory(entry["category"])
        page_dir = DIRECTORY_DIR / f"{entry['category'].lower()}_page_{entry['page']}"
        html = (page_dir / "original.html").read_text(encoding="utf-8", errors="ignore")
        labs = LimsExtractor.extract_labs_from_directory_html(html, cat, entry["source_url"])
        for l in labs:
            all_labs.append({
                "internal_id": l.internal_id,
                "lab_code": l.lab_code,
                "lab_name": l.lab_name,
                "category": l.category
            })

    print(f"Loaded {len(all_labs)} laboratories from directory manifest.")
    print(f"Starting concurrent scope retrieval with 8 workers...")

    results = []
    available_count = 0
    empty_count = 0
    failed_count = 0
    total_scope_rows = 0

    t_start = time.time()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_single_scope, lab): lab for lab in all_labs}
        done_count = 0
        for fut in as_completed(futures):
            res = fut.result()
            results.append(res)
            done_count += 1
            st = res["scope_status"]
            if st == "SCOPE_AVAILABLE":
                available_count += 1
                total_scope_rows += res["scope_rows"]
            elif st == "SCOPE_EMPTY":
                empty_count += 1
            else:
                failed_count += 1

            if done_count % 50 == 0 or done_count == len(all_labs):
                elapsed = time.time() - t_start
                print(f"Progress: {done_count}/{len(all_labs)} ({elapsed:.1f}s) | Available: {available_count} | Empty: {empty_count} | Failed: {failed_count} | Rows: {total_scope_rows}")

    scope_manifest_file = SCOPE_DIR / "scope_acquisition_manifest.json"
    scope_manifest_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nFinished scope acquisition in {time.time() - t_start:.1f}s.")
    print(f"Manifest written to {scope_manifest_file}")
    print(f"Summary: Available: {available_count}, Empty: {empty_count}, Failed: {failed_count}, Total Scope Rows: {total_scope_rows}")

if __name__ == "__main__":
    main()
