"""
Phase F3 Step 5C: Comprehensive Geographic Cache Integrity & Quality Audit Tests.

Tests all 18 audit criteria:
1. cache-to-catalog identity reconciliation
2. duplicate detection
3. rejected laboratory exclusion
4. address preservation
5. address hash integrity
6. cache-key integrity
7. coordinate bounds
8. null coordinate invariant
9. geographic plausibility detection
10. provider metadata preservation
11. quality classification
12. empty-scope geographic separation
13. category reconciliation
14. persistence roundtrip
15. stale-address detection
16. cross-contamination detection
17. matching isolation
18. deterministic audit results
"""

import json
from pathlib import Path
import pytest

from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.geo.cache import LabGeographicCache
from ai.geo.audit import (
    GeographicCacheAuditor,
    GeographicCacheAuditReport,
    QualityClassificationCounts,
    classify_record,
    INDIA_LAT_MIN,
    INDIA_LAT_MAX,
    INDIA_LON_MIN,
    INDIA_LON_MAX,
)
from ai.lims.matching_engine import LimsMatchingEngine
from ai.lims.matching_models import LabMatchingRequest, MatchStatus


@pytest.fixture(scope="module")
def audit_report():
    """Runs the audit once against the production cache and catalog."""
    auditor = GeographicCacheAuditor()
    return auditor.run_audit()


@pytest.fixture(scope="module")
def cache_records():
    auditor = GeographicCacheAuditor()
    return auditor.load_cache_records()


@pytest.fixture(scope="module")
def catalog_labs():
    auditor = GeographicCacheAuditor()
    return auditor.load_catalog()


def test_01_cache_to_catalog_identity_reconciliation(audit_report, catalog_labs, cache_records):
    """Criterion 1: Exactly one cache record per validated BIS internal_id; 580 total."""
    assert audit_report.total_catalog_laboratories == 580
    assert audit_report.total_cache_records == 580
    assert audit_report.identity_integrity_passed is True

    catalog_ids = set(catalog_labs.keys())
    cache_ids = set(rec["internal_id"] for rec in cache_records)
    assert catalog_ids == cache_ids


def test_02_duplicate_detection(cache_records):
    """Criterion 2: Zero duplicate internal_ids and zero duplicate cache_keys."""
    internal_ids = [rec["internal_id"] for rec in cache_records]
    cache_keys = [rec["cache_key"] for rec in cache_records]

    assert len(internal_ids) == len(set(internal_ids)), "Duplicate internal_ids found!"
    assert len(cache_keys) == len(set(cache_keys)), "Duplicate cache_keys found!"


def test_03_rejected_laboratory_exclusion(cache_records):
    """Criterion 3: Rejected laboratory (ECO Laboratories, internal_id: 1184) is excluded."""
    rejected_id = 1184
    cache_ids = set(rec["internal_id"] for rec in cache_records)
    assert rejected_id not in cache_ids, "Rejected laboratory 1184 must not be in cache!"


def test_04_address_preservation(catalog_labs, cache_records):
    """Criterion 4: Statutory original BIS addresses match verbatim (100% fidelity)."""
    for rec in cache_records:
        lab_id = rec["internal_id"]
        cat_addr = catalog_labs[lab_id]["original_address"]
        cache_addr = rec["original_address"]
        assert cache_addr == cat_addr, f"Address mutated for lab {lab_id}"


def test_05_address_hash_integrity(catalog_labs, cache_records):
    """Criterion 5: Address hashes match sha256(clean_address) for current catalog address."""
    for rec in cache_records:
        lab_id = rec["internal_id"]
        cat_addr = catalog_labs[lab_id]["original_address"]
        expected_hash = compute_address_hash(cat_addr)
        assert rec["address_hash"] == expected_hash, f"Hash mismatch for lab {lab_id}"


def test_06_cache_key_integrity(catalog_labs, cache_records):
    """Criterion 6: Cache keys match generate_cache_key(internal_id, original_address)."""
    for rec in cache_records:
        lab_id = rec["internal_id"]
        cat_addr = catalog_labs[lab_id]["original_address"]
        expected_key = generate_cache_key(lab_id, cat_addr)
        assert rec["cache_key"] == expected_key, f"Key mismatch for lab {lab_id}"


def test_07_coordinate_bounds(cache_records):
    """Criterion 7: All SUCCESS records have coordinates within global and Indian bounds."""
    for rec in cache_records:
        if rec["status"] == "SUCCESS":
            lat = rec["latitude"]
            lon = rec["longitude"]
            assert isinstance(lat, float), f"Latitude not float in lab {rec['internal_id']}"
            assert isinstance(lon, float), f"Longitude not float in lab {rec['internal_id']}"
            assert -90.0 <= lat <= 90.0, f"Latitude out of global bounds in lab {rec['internal_id']}"
            assert -180.0 <= lon <= 180.0, f"Longitude out of global bounds in lab {rec['internal_id']}"
            # India territory check
            assert INDIA_LAT_MIN <= lat <= INDIA_LAT_MAX, f"Latitude outside India: {lat}"
            assert INDIA_LON_MIN <= lon <= INDIA_LON_MAX, f"Longitude outside India: {lon}"


def test_08_null_coordinate_invariant(cache_records):
    """Criterion 8: ZERO_RESULTS records have latitude=None and longitude=None strictly."""
    zero_records = [rec for rec in cache_records if rec["status"] == "ZERO_RESULTS"]
    assert len(zero_records) == 3

    for rec in zero_records:
        assert rec["latitude"] is None, f"Fabricated latitude in zero-result lab {rec['internal_id']}"
        assert rec["longitude"] is None, f"Fabricated longitude in zero-result lab {rec['internal_id']}"


def test_09_geographic_plausibility_detection(audit_report):
    """Criterion 9: Plausibility audit validates 0 coordinates outside India, flags discrepancies."""
    assert len(audit_report.outside_india_records) == 0
    assert audit_report.geographic_plausibility_passed is True

    # State discrepancies recorded as review flags (not fatal errors)
    assert len(audit_report.state_discrepancy_records) == 11


def test_10_provider_metadata_preservation(cache_records):
    """Criterion 10: Provider metadata (provider, formatted_address, disclaimer) is preserved."""
    for rec in cache_records:
        assert rec["provider"] == "GEOAPIFY"
        assert "authority_boundary" in rec
        assert "supplementary geographic metadata only" in rec["authority_boundary"]
        if rec["status"] == "SUCCESS":
            assert rec["formatted_address"] is not None
            assert len(rec["formatted_address"]) > 0


def test_11_quality_classification(audit_report):
    """Criterion 11: Objective quality classification reconciles to 580 total."""
    cls = audit_report.classification
    assert cls.high_confidence == 74
    assert cls.medium_confidence == 133
    assert cls.low_confidence == 360
    assert cls.review_required == 10
    assert cls.zero_results == 3
    assert cls.total() == 580


def test_12_empty_scope_geographic_separation(audit_report, catalog_labs, cache_records):
    """Criterion 12: All 39 empty-scope laboratories are present in cache without scope data."""
    assert audit_report.empty_scope_total == 39
    assert audit_report.empty_scope_with_coords == 39
    assert audit_report.empty_scope_without_coords == 0

    cache_by_id = {rec["internal_id"]: rec for rec in cache_records}
    for lab_id, cat_lab in catalog_labs.items():
        if cat_lab.get("scope_status") == "SCOPE_EMPTY":
            assert lab_id in cache_by_id
            rec = cache_by_id[lab_id]
            # Ensure no capability data in cache
            assert "scope" not in rec
            assert "standards" not in rec


def test_13_category_reconciliation(audit_report):
    """Criterion 13: Exact category reconciliation: 10 BIS-owned + 430 recognized + 140 empanelled = 580."""
    assert audit_report.bis_owned_total == 10
    assert audit_report.bis_owned_with_coords == 10
    assert audit_report.bis_owned_without_coords == 0

    assert audit_report.recognized_total == 430
    assert audit_report.recognized_with_coords == 427
    assert audit_report.recognized_without_coords == 3

    assert audit_report.empanelled_total == 140
    assert audit_report.empanelled_with_coords == 140
    assert audit_report.empanelled_without_coords == 0

    assert audit_report.bis_owned_total + audit_report.recognized_total + audit_report.empanelled_total == 580
    assert audit_report.successful_coordinates + audit_report.zero_results_count == 580


def test_14_persistence_roundtrip(tmp_path):
    """Criterion 14: Cache save and load cycle preserves 100% data fidelity."""
    cache = LabGeographicCache()
    assert len(cache) == 580

    roundtrip_file = tmp_path / "roundtrip_cache.jsonl"
    cache.save_to_disk(cache_file=roundtrip_file)

    cache2 = LabGeographicCache(cache_file=roundtrip_file)
    assert len(cache2) == 580

    for internal_id, item1 in cache._by_id.items():
        item2 = cache2.get_by_id(internal_id)
        assert item2 is not None
        assert item1.to_dict() == item2.to_dict()


def test_15_stale_address_detection(cache_records):
    """Criterion 15: Address modification triggers cache miss and is_stale detection."""
    cache = LabGeographicCache()
    sample = cache_records[0]
    internal_id = sample["internal_id"]
    original_addr = sample["original_address"]
    new_addr = original_addr + " - NEW BLOCK EXTENSION 2026"

    # Current address matches
    assert cache.get_for_laboratory(internal_id, original_addr) is not None
    assert cache.is_stale(internal_id, original_addr) is False

    # Modified address fails cache lookup
    assert cache.get_for_laboratory(internal_id, new_addr) is None
    assert cache.is_stale(internal_id, new_addr) is True


def test_16_cross_contamination_detection(cache_records):
    """Criterion 16: Zero testing scope, clauses, fees, or accreditation evidence in cache."""
    forbidden_keys = {
        "scope", "clauses", "standards", "fees", "products",
        "accreditation", "validity_date", "test_names", "scope_records"
    }
    for rec in cache_records:
        rec_keys = set(rec.keys())
        overlap = rec_keys & forbidden_keys
        assert len(overlap) == 0, f"Cross-contamination detected in lab {rec['internal_id']}: {overlap}"


def test_17_matching_isolation():
    """Criterion 17: Presence of geographic metadata does not alter capability matching."""
    catalog_path = Path("data/catalog/phase_f3_lims")
    engine = LimsMatchingEngine(catalog_dir=catalog_path)
    req = LabMatchingRequest(standard="IS 4985")
    result = engine.match(req)

    assert result.status == MatchStatus.EXACT_MATCH
    assert result.total_candidates >= 1
    # Candidate matches contain only capability and BIS statutory data
    for cand in result.candidates:
        assert "4985" in cand.matching_standard
        # Matching candidate structure has not been contaminated with raw geographic cache objects
        assert not hasattr(cand, "latitude")
        assert not hasattr(cand, "longitude")


def test_18_deterministic_audit_results():
    """Criterion 18: Repeated audit execution produces identical metrics and classifications."""
    auditor = GeographicCacheAuditor()
    rep1 = auditor.run_audit()
    rep2 = auditor.run_audit()

    assert rep1.to_dict() == rep2.to_dict()
    assert rep1.audit_passed is True
    assert rep2.audit_passed is True
