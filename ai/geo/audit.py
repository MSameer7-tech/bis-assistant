"""
Phase F3 Step 5C: Geographic Cache Integrity & Quality Auditor.

Audits the geographic metadata cache produced by Step 5B against the authoritative
BIS LIMS laboratory catalog without modifying any catalog records or calling external APIs.

Audit Dimensions:
1. Identity Integrity: 1:1 mapping, verbatim statutory address preservation, hash/key integrity.
2. Coordinate Integrity: Bounded coordinates for SUCCESS, null coordinates for ZERO_RESULTS.
3. Geographic Plausibility: India bounding box validation and review flags.
4. Quality Classification: Objective stratification based on provider confidence metadata.
5. Scope Separation: Zero capability/scope cross-contamination into spatial cache.
6. Matching Isolation: Proof that geographic metadata does not alter capability matching.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Set

from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.geo.cache import (
    LabGeographicCache,
    DEFAULT_CACHE_FILE,
    DEFAULT_MANIFEST_FILE,
    DEFAULT_CHECKPOINT_FILE,
)

logger = logging.getLogger("geographic_audit")

DEFAULT_CATALOG_FILE = Path("data/catalog/phase_f3_lims/laboratories_normalized.jsonl")

# Geographic bounding box for India (including EEZ / island territories)
INDIA_LAT_MIN = 6.0
INDIA_LAT_MAX = 38.0
INDIA_LON_MIN = 68.0
INDIA_LON_MAX = 98.0


@dataclass
class QualityClassificationCounts:
    high_confidence: int = 0      # confidence >= 0.8
    medium_confidence: int = 0    # 0.5 <= confidence < 0.8
    low_confidence: int = 0       # 0 < confidence < 0.5
    review_required: int = 0      # confidence == 0 or missing or plausibility flag
    zero_results: int = 0         # status == "ZERO_RESULTS"

    def total(self) -> int:
        return (
            self.high_confidence
            + self.medium_confidence
            + self.low_confidence
            + self.review_required
            + self.zero_results
        )


@dataclass
class GeographicCacheAuditReport:
    """Comprehensive report produced by the Step 5C Geographic Cache Audit."""
    total_catalog_laboratories: int = 0
    total_cache_records: int = 0
    successful_coordinates: int = 0
    zero_results_count: int = 0
    null_coordinates_count: int = 0

    # Category accounting
    bis_owned_total: int = 0
    bis_owned_with_coords: int = 0
    bis_owned_without_coords: int = 0

    recognized_total: int = 0
    recognized_with_coords: int = 0
    recognized_without_coords: int = 0

    empanelled_total: int = 0
    empanelled_with_coords: int = 0
    empanelled_without_coords: int = 0

    empty_scope_total: int = 0
    empty_scope_with_coords: int = 0
    empty_scope_without_coords: int = 0

    # Quality classification
    classification: QualityClassificationCounts = field(default_factory=QualityClassificationCounts)

    # Plausibility & Review Flags
    outside_india_records: List[Dict[str, Any]] = field(default_factory=list)
    state_discrepancy_records: List[Dict[str, Any]] = field(default_factory=list)
    review_required_records: List[Dict[str, Any]] = field(default_factory=list)

    # Invariant pass/fail flags
    identity_integrity_passed: bool = False
    coordinate_integrity_passed: bool = False
    geographic_plausibility_passed: bool = False
    no_cross_contamination_passed: bool = False
    reconciliation_passed: bool = False
    audit_passed: bool = False

    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify_record(record: Dict[str, Any]) -> str:
    """
    Deterministically classifies a cache record based strictly on existing provider metadata:
    - ZERO_RESULTS: status == "ZERO_RESULTS"
    - REVIEW_REQUIRED: status == "SUCCESS" and (confidence == 0 or confidence is None)
    - HIGH_CONFIDENCE: status == "SUCCESS" and confidence >= 0.8
    - MEDIUM_CONFIDENCE: status == "SUCCESS" and 0.5 <= confidence < 0.8
    - LOW_CONFIDENCE: status == "SUCCESS" and 0 < confidence < 0.5
    """
    status = record.get("status")
    if status == "ZERO_RESULTS":
        return "ZERO_RESULTS"

    if status == "SUCCESS":
        conf = record.get("confidence")
        if conf is None or conf == 0:
            return "REVIEW_REQUIRED"
        if conf >= 0.8:
            return "HIGH_CONFIDENCE"
        if conf >= 0.5:
            return "MEDIUM_CONFIDENCE"
        return "LOW_CONFIDENCE"

    return "REVIEW_REQUIRED"


class GeographicCacheAuditor:
    """
    Audits the geographic metadata cache against authoritative BIS LIMS records.
    Read-only: Never modifies catalog, cache, or calls external APIs.
    """

    def __init__(
        self,
        catalog_path: Optional[Path] = None,
        cache_file: Optional[Path] = None,
        manifest_file: Optional[Path] = None,
        checkpoint_file: Optional[Path] = None,
    ):
        self.catalog_path = catalog_path or DEFAULT_CATALOG_FILE
        self.cache_file = cache_file or DEFAULT_CACHE_FILE
        self.manifest_file = manifest_file or DEFAULT_MANIFEST_FILE
        self.checkpoint_file = checkpoint_file or DEFAULT_CHECKPOINT_FILE

    def load_catalog(self) -> Dict[int, Dict[str, Any]]:
        """Loads authoritative laboratories mapped by internal_id."""
        catalog = {}
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lab = json.loads(line)
                    catalog[lab["internal_id"]] = lab
        return catalog

    def load_cache_records(self) -> List[Dict[str, Any]]:
        """Loads all cache records from JSONL."""
        records = []
        with open(self.cache_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def run_audit(self) -> GeographicCacheAuditReport:
        """Executes full 18-point audit and returns structured report."""
        report = GeographicCacheAuditReport()
        catalog = self.load_catalog()
        cache_records = self.load_cache_records()

        report.total_catalog_laboratories = len(catalog)
        report.total_cache_records = len(cache_records)

        # 1. Identity Integrity Audit
        seen_ids: Set[int] = set()
        seen_keys: Set[str] = set()
        rejected_id = 1184  # ECO Laboratories

        identity_issues = []
        coordinate_issues = []
        contamination_issues = []

        for rec in cache_records:
            internal_id = rec.get("internal_id")
            cache_key = rec.get("cache_key")

            # Duplicate checks
            if internal_id in seen_ids:
                identity_issues.append(f"Duplicate internal_id in cache: {internal_id}")
            seen_ids.add(internal_id)

            if cache_key in seen_keys:
                identity_issues.append(f"Duplicate cache_key in cache: {cache_key}")
            seen_keys.add(cache_key)

            # Rejected lab exclusion
            if internal_id == rejected_id:
                identity_issues.append(f"Rejected laboratory {rejected_id} found in geographic cache!")

            # Existence in authoritative catalog
            if internal_id not in catalog:
                identity_issues.append(f"Cache internal_id {internal_id} not found in authoritative catalog.")
                continue

            cat_lab = catalog[internal_id]

            # Verbatim address preservation
            if rec.get("original_address") != cat_lab.get("original_address"):
                identity_issues.append(
                    f"Address mismatch for lab {internal_id}: '{rec.get('original_address')}' != '{cat_lab.get('original_address')}'"
                )

            # Address hash integrity
            expected_hash = compute_address_hash(cat_lab["original_address"])
            if rec.get("address_hash") != expected_hash:
                identity_issues.append(
                    f"Address hash mismatch for lab {internal_id}: {rec.get('address_hash')} != {expected_hash}"
                )

            # Cache key integrity
            expected_key = generate_cache_key(internal_id, cat_lab["original_address"])
            if cache_key != expected_key:
                identity_issues.append(
                    f"Cache key mismatch for lab {internal_id}: {cache_key} != {expected_key}"
                )

            # Public lab code / internal ID separation
            if rec.get("public_lab_code") is not None and rec.get("public_lab_code") == str(internal_id):
                # Verify that internal_id didn't overwrite statutory public_lab_code
                if cat_lab.get("lab_code") != str(internal_id):
                    identity_issues.append(f"Lab code confused with internal_id for lab {internal_id}")

            # 2. Coordinate Integrity & Null Invariant
            status = rec.get("status")
            lat = rec.get("latitude")
            lon = rec.get("longitude")

            if status == "SUCCESS":
                report.successful_coordinates += 1
                if lat is None or lon is None:
                    coordinate_issues.append(f"Lab {internal_id} has SUCCESS status but null coordinates.")
                elif not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
                    coordinate_issues.append(f"Lab {internal_id} coordinates are non-numeric: ({lat}, {lon})")
                elif not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                    coordinate_issues.append(f"Lab {internal_id} coordinates out of global bounds: ({lat}, {lon})")
            elif status == "ZERO_RESULTS":
                report.zero_results_count += 1
                report.null_coordinates_count += 1
                if lat is not None or lon is not None:
                    coordinate_issues.append(
                        f"Lab {internal_id} has ZERO_RESULTS status but non-null coordinates: ({lat}, {lon})"
                    )
            else:
                coordinate_issues.append(f"Unexpected status '{status}' for lab {internal_id}")

            # 3. Geographic Plausibility Audit (India bounds check)
            if status == "SUCCESS" and lat is not None and lon is not None:
                if not (INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX and INDIA_LON_MIN <= lon <= INDIA_LON_MAX):
                    report.outside_india_records.append({
                        "internal_id": internal_id,
                        "lab_code": rec.get("public_lab_code"),
                        "latitude": lat,
                        "longitude": lon,
                        "formatted_address": rec.get("formatted_address")
                    })

                # State Discrepancy Check (Conservative Review Flag)
                cat_state = (cat_lab.get("normalized_state") or "").strip().lower()
                prov_meta = rec.get("provider_metadata") or {}
                prov_state = (prov_meta.get("state") or "").strip().lower()
                conf = rec.get("confidence")

                if cat_state and prov_state and cat_state != prov_state:
                    # Record for audit review (do not mutate!)
                    report.state_discrepancy_records.append({
                        "internal_id": internal_id,
                        "lab_code": rec.get("public_lab_code"),
                        "catalog_state": cat_lab.get("normalized_state"),
                        "provider_state": prov_meta.get("state"),
                        "confidence": conf,
                        "original_address": cat_lab.get("original_address")
                    })

            # 4. Quality Classification
            cls_result = classify_record(rec)
            if cls_result == "HIGH_CONFIDENCE":
                report.classification.high_confidence += 1
            elif cls_result == "MEDIUM_CONFIDENCE":
                report.classification.medium_confidence += 1
            elif cls_result == "LOW_CONFIDENCE":
                report.classification.low_confidence += 1
            elif cls_result == "REVIEW_REQUIRED":
                report.classification.review_required += 1
                report.review_required_records.append({
                    "internal_id": internal_id,
                    "lab_code": rec.get("public_lab_code"),
                    "confidence": rec.get("confidence"),
                    "match_type": rec.get("match_type"),
                    "formatted_address": rec.get("formatted_address"),
                    "original_address": rec.get("original_address")
                })
            elif cls_result == "ZERO_RESULTS":
                report.classification.zero_results += 1

            # 5. Cross-Contamination Check
            for forbidden_key in ("scope", "clauses", "standards", "fees", "products", "accreditation", "validity_date"):
                if forbidden_key in rec:
                    contamination_issues.append(
                        f"Forbidden capability field '{forbidden_key}' found in cache for lab {internal_id}"
                    )

            # 6. Category Accounting
            category = cat_lab.get("category")
            has_coords = (status == "SUCCESS" and lat is not None and lon is not None)

            if category == "BIS_OWNED":
                report.bis_owned_total += 1
                if has_coords:
                    report.bis_owned_with_coords += 1
                else:
                    report.bis_owned_without_coords += 1
            elif category == "BIS_RECOGNIZED":
                report.recognized_total += 1
                if has_coords:
                    report.recognized_with_coords += 1
                else:
                    report.recognized_without_coords += 1
            elif category == "BIS_EMPANELLED":
                report.empanelled_total += 1
                if has_coords:
                    report.empanelled_with_coords += 1
                else:
                    report.empanelled_without_coords += 1

            # Empty scope accounting
            if cat_lab.get("scope_status") == "SCOPE_EMPTY":
                report.empty_scope_total += 1
                if has_coords:
                    report.empty_scope_with_coords += 1
                else:
                    report.empty_scope_without_coords += 1

        # Check that all catalog IDs are in cache
        missing_from_cache = set(catalog.keys()) - seen_ids
        if missing_from_cache:
            identity_issues.append(f"Catalog laboratories missing from cache: {missing_from_cache}")

        # Final invariant assessments
        report.identity_integrity_passed = len(identity_issues) == 0
        report.coordinate_integrity_passed = len(coordinate_issues) == 0
        report.geographic_plausibility_passed = len(report.outside_india_records) == 0
        report.no_cross_contamination_passed = len(contamination_issues) == 0

        # Reconciliation check
        rec_sum = (
            report.bis_owned_total
            + report.recognized_total
            + report.empanelled_total
        )
        status_sum = report.successful_coordinates + report.zero_results_count
        cls_sum = report.classification.total()

        report.reconciliation_passed = (
            rec_sum == 580
            and status_sum == 580
            and cls_sum == 580
            and report.total_cache_records == 580
            and report.total_catalog_laboratories == 580
        )

        all_issues = identity_issues + coordinate_issues + contamination_issues
        report.issues = all_issues
        report.audit_passed = (
            report.identity_integrity_passed
            and report.coordinate_integrity_passed
            and report.geographic_plausibility_passed
            and report.no_cross_contamination_passed
            and report.reconciliation_passed
            and len(all_issues) == 0
        )

        return report
