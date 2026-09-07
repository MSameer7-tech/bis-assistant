#!/usr/bin/env python3
"""
Phase F3 Step 5B: Controlled Bulk Geocoding CLI Script.

Executes controlled bulk geocoding of the authoritative BIS LIMS catalog (580 laboratories)
into the isolated geographic metadata cache.

Usage:
    python scripts/phase_f3_bulk_geocoder.py --dry-run
    python scripts/phase_f3_bulk_geocoder.py --live
    python scripts/phase_f3_bulk_geocoder.py --verify-only
"""

import sys
import argparse
import logging
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.geo.bulk_geocoder import (
    ControlledBulkGeocoder,
    DEFAULT_CATALOG_FILE,
    DEFAULT_CACHE_FILE,
    DEFAULT_CHECKPOINT_FILE,
)
from ai.services.geocoding_service import load_env_if_missing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("phase_f3_bulk_geocoder")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase F3 Step 5B: Controlled Bulk Geocoding CLI"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute live Geoapify API calls for uncached laboratories."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without making live provider calls."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Perform 14-point quality validation on existing cache without geocoding."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Conservative delay in seconds between provider calls (default: 0.25s)."
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=None,
        help="Limit number of records to process (for testing)."
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force re-geocoding even if valid cached entry exists."
    )
    parser.add_argument(
        "--retry-transient",
        action="store_true",
        help="Retry entries that previously failed due to network or rate limit errors."
    )
    return parser.parse_args()


def progress_callback(current: int, total: int, info: dict):
    provider_tag = "LIVE_CALL" if info.get("provider_called") else "CACHE_HIT"
    if current % 10 == 0 or current == total:
        print(
            f"[{current:03d}/{total:03d}] Lab ID {info['internal_id']} "
            f"({info['lab_code']}): {info['status']} [{provider_tag}]"
        )


def main():
    args = parse_args()
    load_env_if_missing()

    geocoder = ControlledBulkGeocoder(
        delay_seconds=args.delay,
        on_progress=progress_callback
    )

    if args.verify_only:
        print("Running 14-point quality validation on geographic cache...")
        val = geocoder.validate_cache()
        print(f"Validation Passed: {val['validation_passed']}")
        print(f"Checked Laboratories: {val['total_laboratories_checked']}")
        print(f"Cached Laboratories: {val['cached_laboratories_count']}")
        print(f"Valid Coordinates Count: {val['valid_coordinates_count']}")
        print(f"Null Coordinates Count: {val['null_coordinates_count']}")
        print(f"Issues Count: {val['issues_count']}")
        if val["issues"]:
            print("Issues encountered:")
            for iss in val["issues"]:
                print(f"  - {iss}")
        return 0 if val["validation_passed"] else 1

    if not args.live and not args.dry_run:
        print("ERROR: Must specify either --live or --dry-run (or --verify-only).")
        return 1

    print("==================================================")
    print("PHASE F3 STEP 5B: CONTROLLED BULK GEOCODING")
    print(f"Mode: {'LIVE (GEOAPIFY)' if args.live else 'DRY RUN'}")
    print(f"Catalog: {DEFAULT_CATALOG_FILE}")
    print(f"Cache: {DEFAULT_CACHE_FILE}")
    print(f"Checkpoint: {DEFAULT_CHECKPOINT_FILE}")
    print(f"Pacing Delay: {args.delay}s")
    print("==================================================")

    summary = geocoder.run_batch(
        force_refresh=args.force_refresh,
        retry_transient=args.retry_transient,
        max_records=args.max_records,
        dry_run=args.dry_run
    )

    print("\n==================================================")
    print("BATCH ACCOUNTING SUMMARY")
    print("==================================================")
    print(f"Total laboratories:          {summary.total_laboratories}")
    print(f"Processed:                   {summary.processed}")
    print(f"Cache hits:                  {summary.cache_hits}")
    print(f"Provider calls:              {summary.provider_calls}")
    print(f"SUCCESS:                     {summary.success}")
    print(f"ZERO_RESULTS:                {summary.zero_results}")
    print(f"MISSING_ADDRESS:             {summary.missing_address}")
    print(f"MISSING_API_KEY:             {summary.missing_api_key}")
    print(f"RATE_LIMITED:                {summary.rate_limited}")
    print(f"API_ERROR:                   {summary.api_error}")
    print(f"NETWORK_ERROR:               {summary.network_error}")
    print(f"Coordinates available:       {summary.coordinates_available}")
    print(f"Coordinates unavailable:     {summary.coordinates_unavailable}")
    print(f"Failures:                    {summary.failures}")
    print("--------------------------------------------------")
    print(f"BIS-owned geocoded:          {summary.bis_owned_geocoded} (with coords: {summary.bis_owned_with_coords})")
    print(f"Recognized geocoded:         {summary.recognized_geocoded} (with coords: {summary.recognized_with_coords})")
    print(f"Empanelled geocoded:         {summary.empanelled_geocoded} (with coords: {summary.empanelled_with_coords})")
    print(f"Empty-scope geocoded:        {summary.empty_scope_geocoded}")
    print(f"Empty-scope with coords:     {summary.empty_scope_with_coords}")
    print(f"Empty-scope without coords:  {summary.empty_scope_without_coords}")
    print(f"Exact reconciliation valid:  {summary.reconcile()}")
    print("==================================================")

    # Run validation
    print("\nRunning post-batch 14-point cache validation...")
    val = geocoder.validate_cache()
    print(f"Validation Passed:           {val['validation_passed']}")
    print(f"Issues Count:                {val['issues_count']}")
    if val["issues"]:
        for iss in val["issues"]:
            print(f"  - {iss}")

    return 0 if (summary.reconcile() and val["validation_passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
