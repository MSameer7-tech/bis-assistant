"""
Phase F3 Step 5B: Comprehensive Unit Tests for Controlled Bulk Geocoding.

Tests all 20 required criteria with 100% mocked provider responses (zero live network calls):
1. first-time geocoding
2. cache hit
3. cache miss
4. changed address
5. interrupted batch/resume
6. repeated batch idempotency
7. successful result
8. zero result
9. rate limiting
10. API error
11. network error
12. missing API key
13. missing address
14. null coordinate invariant
15. invalid coordinate response
16. provider-call accounting
17. no duplicate provider calls
18. checkpoint consistency
19. category accounting
20. authoritative catalog immutability
"""

import json
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.geo.cache import LabGeographicCache
from ai.geo.bulk_geocoder import (
    ControlledBulkGeocoder,
    BatchAccountingSummary,
    GeocodingCheckpointManager,
)
from ai.services.geocoding_service import (
    GeoapifyGeocodingService,
    GeocodingResult,
)


@pytest.fixture
def mock_catalog(tmp_path):
    """Creates a temporary synthetic catalog of laboratories covering all categories."""
    catalog_path = tmp_path / "mock_catalog.jsonl"
    labs = [
        {
            "internal_id": 1,
            "lab_code": "CL01",
            "lab_name": "BIS Central Laboratory",
            "category": "BIS_OWNED",
            "original_address": "Plot 20/9, Site IV, Sahibabad, Ghaziabad, UP - 201010",
            "scope_status": "SCOPE_AVAILABLE"
        },
        {
            "internal_id": 2,
            "lab_code": "REC01",
            "lab_name": "Shriram Institute for Industrial Research",
            "category": "BIS_RECOGNIZED",
            "original_address": "19, University Road, Delhi - 110007",
            "scope_status": "SCOPE_AVAILABLE"
        },
        {
            "internal_id": 3,
            "lab_code": "EMP01",
            "lab_name": "Regional Reference Standards Laboratory",
            "category": "BIS_EMPANELLED",
            "original_address": "PB No 5800, Tumkur Road, Bengaluru - 560058",
            "scope_status": "SCOPE_AVAILABLE"
        },
        {
            "internal_id": 4,
            "lab_code": "REC02",
            "lab_name": "Empty Scope Laboratory",
            "category": "BIS_RECOGNIZED",
            "original_address": "Sector 62, Noida, UP - 201301",
            "scope_status": "SCOPE_EMPTY"
        },
    ]
    with open(catalog_path, "w", encoding="utf-8") as f:
        for lab in labs:
            f.write(json.dumps(lab) + "\n")
    return catalog_path, labs


@pytest.fixture
def mock_geocoder_setup(tmp_path, mock_catalog):
    catalog_path, labs = mock_catalog
    cache_file = tmp_path / "cache.jsonl"
    checkpoint_file = tmp_path / "checkpoint.json"
    mock_service = MagicMock(spec=GeoapifyGeocodingService)

    geocoder = ControlledBulkGeocoder(
        catalog_path=catalog_path,
        cache_file=cache_file,
        checkpoint_file=checkpoint_file,
        geocoding_service=mock_service,
        delay_seconds=0.0  # Zero delay in tests
    )
    return geocoder, mock_service, cache_file, checkpoint_file, labs


def test_01_first_time_geocoding(mock_geocoder_setup):
    """Criterion 1: First-time geocoding invokes provider and persists result."""
    geocoder, mock_service, cache_file, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.6860,
        longitude=77.4322,
        formatted_address="Sahibabad, UP",
        original_address=labs[0]["original_address"]
    )

    summary = geocoder.run_batch(max_records=1)

    assert summary.processed == 1
    assert summary.provider_calls == 1
    assert summary.cache_hits == 0
    assert summary.success == 1
    assert mock_service.geocode.call_count == 1

    # Verify cached entry
    cached = geocoder.cache.get_by_id(1)
    assert cached is not None
    assert cached.status == "SUCCESS"
    assert cached.latitude == 28.6860
    assert cached.longitude == 77.4322


def test_02_cache_hit(mock_geocoder_setup):
    """Criterion 2: Pre-existing valid cache entry skips provider call."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    lab = labs[0]

    # Pre-populate cache
    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6860,
        longitude=77.4322,
        formatted_address="Sahibabad, UP",
        original_address=lab["original_address"]
    )
    geocoder.cache.record_geocoding_result(
        internal_id=lab["internal_id"],
        public_lab_code=lab["lab_code"],
        original_address=lab["original_address"],
        result=mock_result
    )

    summary = geocoder.run_batch(max_records=1)

    assert summary.processed == 1
    assert summary.cache_hits == 1
    assert summary.provider_calls == 0
    assert mock_service.geocode.call_count == 0


def test_03_cache_miss(mock_geocoder_setup):
    """Criterion 3: Uncached entry triggers provider call."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.6918,
        longitude=77.2175,
        original_address=labs[1]["original_address"]
    )

    # Only lab 1 is cached, lab 2 is a miss
    geocoder.cache.record_geocoding_result(
        internal_id=labs[0]["internal_id"],
        public_lab_code=labs[0]["lab_code"],
        original_address=labs[0]["original_address"],
        result=GeocodingResult(status="SUCCESS", latitude=28.68, longitude=77.43, original_address=labs[0]["original_address"])
    )

    summary = geocoder.run_batch(max_records=2)

    assert summary.processed == 2
    assert summary.cache_hits == 1
    assert summary.provider_calls == 1
    assert mock_service.geocode.call_count == 1


def test_04_changed_address(mock_geocoder_setup):
    """Criterion 4: Changed address invalidates cache and triggers new provider call."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    lab = labs[0]

    # Pre-populate cache with OLD address
    old_address = "Old Sahibabad address from 2020"
    geocoder.cache.record_geocoding_result(
        internal_id=lab["internal_id"],
        public_lab_code=lab["lab_code"],
        original_address=old_address,
        result=GeocodingResult(status="SUCCESS", latitude=28.0, longitude=77.0, original_address=old_address)
    )

    # Provider returns new coords for new address
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.6860,
        longitude=77.4322,
        original_address=lab["original_address"]
    )

    summary = geocoder.run_batch(max_records=1)

    assert summary.processed == 1
    assert summary.cache_hits == 0
    assert summary.provider_calls == 1
    # Cache must now contain new coordinates
    cached = geocoder.cache.get_by_id(lab["internal_id"])
    assert cached.original_address == lab["original_address"]
    assert cached.latitude == 28.6860


def test_05_interrupted_batch_resume(mock_geocoder_setup):
    """Criterion 5: Interrupted run safely resumes from checkpoint without re-geocoding."""
    geocoder, mock_service, cache_file, checkpoint_file, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    # Run first 2 records
    summary1 = geocoder.run_batch(max_records=2)
    assert summary1.processed == 2
    assert summary1.provider_calls == 2

    # Instantiate a NEW geocoder pointing to the same cache and checkpoint
    geocoder2 = ControlledBulkGeocoder(
        catalog_path=geocoder.catalog_path,
        cache_file=cache_file,
        checkpoint_file=checkpoint_file,
        geocoding_service=mock_service,
        delay_seconds=0.0
    )

    # Run all 4 records
    summary2 = geocoder2.run_batch(max_records=4)
    assert summary2.processed == 4
    assert summary2.cache_hits == 2      # First 2 were cached
    assert summary2.provider_calls == 2  # Only next 2 called provider
    assert mock_service.geocode.call_count == 4  # Total 4 calls across both runs


def test_06_repeated_batch_idempotency(mock_geocoder_setup):
    """Criterion 6: Repeated batch execution results in 0 provider calls."""
    geocoder, mock_service, _, _, _ = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    # Run complete batch of 4
    summary1 = geocoder.run_batch(max_records=4)
    assert summary1.provider_calls == 4
    assert summary1.cache_hits == 0

    # Run again immediately
    summary2 = geocoder.run_batch(max_records=4)
    assert summary2.provider_calls == 0
    assert summary2.cache_hits == 4
    assert mock_service.geocode.call_count == 4


def test_07_successful_result(mock_geocoder_setup):
    """Criterion 7: SUCCESS status has non-null float coordinates."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.686014,
        longitude=77.432251,
        place_id="place_123",
        original_address=labs[0]["original_address"]
    )

    summary = geocoder.run_batch(max_records=1)
    assert summary.success == 1
    assert summary.coordinates_available == 1
    meta = geocoder.cache.get_by_id(1)
    assert meta.has_valid_coordinates() is True
    assert isinstance(meta.latitude, float)
    assert isinstance(meta.longitude, float)


def test_08_zero_result(mock_geocoder_setup):
    """Criterion 8: ZERO_RESULTS status has null coordinates."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="ZERO_RESULTS",
        latitude=None,
        longitude=None,
        original_address=labs[0]["original_address"]
    )

    summary = geocoder.run_batch(max_records=1)
    assert summary.zero_results == 1
    assert summary.coordinates_available == 0
    assert summary.coordinates_unavailable == 1
    meta = geocoder.cache.get_by_id(1)
    assert meta.status == "ZERO_RESULTS"
    assert meta.latitude is None
    assert meta.longitude is None


def test_09_rate_limiting(mock_geocoder_setup):
    """Criterion 9: RATE_LIMITED stops batch safely with null coordinates."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="RATE_LIMITED",
        latitude=None,
        longitude=None,
        original_address=labs[0]["original_address"],
        error_message="HTTP 429 Too Many Requests"
    )

    with pytest.raises(RuntimeError, match="rate limit"):
        geocoder.run_batch(max_records=2)

    # Must have recorded RATE_LIMITED with null coordinates before halting
    meta = geocoder.cache.get_by_id(1)
    assert meta is not None
    assert meta.status == "RATE_LIMITED"
    assert meta.latitude is None
    assert meta.longitude is None


def test_10_api_error(mock_geocoder_setup):
    """Criterion 10: API_ERROR is handled with null coordinates and error message."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="API_ERROR",
        latitude=None,
        longitude=None,
        original_address=labs[0]["original_address"],
        error_message="HTTP 500 Internal Server Error"
    )

    summary = geocoder.run_batch(max_records=1)
    assert summary.api_error == 1
    assert summary.coordinates_available == 0
    meta = geocoder.cache.get_by_id(1)
    assert meta.status == "API_ERROR"
    assert meta.latitude is None
    assert meta.longitude is None
    assert "500" in meta.error_message


def test_11_network_error(mock_geocoder_setup):
    """Criterion 11: NETWORK_ERROR is handled with null coordinates."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="NETWORK_ERROR",
        latitude=None,
        longitude=None,
        original_address=labs[0]["original_address"],
        error_message="Connection timed out"
    )

    summary = geocoder.run_batch(max_records=1)
    assert summary.network_error == 1
    meta = geocoder.cache.get_by_id(1)
    assert meta.status == "NETWORK_ERROR"
    assert meta.latitude is None
    assert meta.longitude is None


def test_12_missing_api_key(mock_geocoder_setup):
    """Criterion 12: MISSING_API_KEY is handled safely with null coordinates."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="MISSING_API_KEY",
        latitude=None,
        longitude=None,
        original_address=labs[0]["original_address"],
        error_message="GEOAPIFY_API_KEY not configured"
    )

    summary = geocoder.run_batch(max_records=1)
    assert summary.missing_api_key == 1
    meta = geocoder.cache.get_by_id(1)
    assert meta.status == "MISSING_API_KEY"
    assert meta.latitude is None
    assert meta.longitude is None


def test_13_missing_address(mock_geocoder_setup, tmp_path):
    """Criterion 13: MISSING_ADDRESS is handled safely with null coordinates."""
    catalog_path = tmp_path / "empty_addr_catalog.jsonl"
    with open(catalog_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "internal_id": 99,
            "lab_code": "EMPTY_ADDR",
            "category": "BIS_RECOGNIZED",
            "original_address": "   ",
            "scope_status": "SCOPE_AVAILABLE"
        }) + "\n")

    cache_file = tmp_path / "cache_empty.jsonl"
    mock_service = MagicMock(spec=GeoapifyGeocodingService)
    mock_service.geocode.return_value = GeocodingResult(
        status="MISSING_ADDRESS",
        latitude=None,
        longitude=None,
        original_address="   "
    )

    geocoder = ControlledBulkGeocoder(
        catalog_path=catalog_path,
        cache_file=cache_file,
        checkpoint_file=tmp_path / "cp.json",
        geocoding_service=mock_service,
        delay_seconds=0.0
    )

    summary = geocoder.run_batch()
    assert summary.missing_address == 1
    meta = geocoder.cache.get_by_id(99)
    assert meta.status == "MISSING_ADDRESS"
    assert meta.latitude is None
    assert meta.longitude is None


def test_14_null_coordinate_invariant(mock_geocoder_setup):
    """Criterion 14: All non-success statuses guarantee latitude=None, longitude=None."""
    geocoder, _, _, _, labs = mock_geocoder_setup
    non_success_statuses = [
        "ZERO_RESULTS",
        "MISSING_ADDRESS",
        "MISSING_API_KEY",
        "RATE_LIMITED",
        "API_ERROR",
        "NETWORK_ERROR"
    ]

    for status in non_success_statuses:
        res = GeocodingResult(
            status=status,
            latitude=28.0,  # Deliberately attempt to inject coordinates into failure result
            longitude=77.0,
            original_address=labs[0]["original_address"]
        )
        meta = geocoder.cache.record_geocoding_result(
            internal_id=labs[0]["internal_id"],
            public_lab_code=labs[0]["lab_code"],
            original_address=labs[0]["original_address"],
            result=res
        )
        assert meta.latitude is None, f"Failed for status {status}"
        assert meta.longitude is None, f"Failed for status {status}"
        assert meta.has_valid_coordinates() is False


def test_15_invalid_coordinate_response(mock_geocoder_setup):
    """Criterion 15: Out-of-bounds coordinates fail cache validation."""
    geocoder, _, _, _, labs = mock_geocoder_setup
    # Manually store out-of-bounds latitude (e.g. 150.0 degrees)
    meta = LabGeographicMetadata(
        internal_id=labs[0]["internal_id"],
        public_lab_code=labs[0]["lab_code"],
        original_address=labs[0]["original_address"],
        address_hash=compute_address_hash(labs[0]["original_address"]),
        cache_key=generate_cache_key(labs[0]["internal_id"], labs[0]["original_address"]),
        status="SUCCESS",
        latitude=150.0,  # Invalid latitude (> 90)
        longitude=77.0
    )
    geocoder.cache.put(meta)

    val = geocoder.validate_cache()
    assert val["validation_passed"] is False
    assert any("out of bounds" in iss for iss in val["issues"])


def test_16_provider_call_accounting(mock_geocoder_setup):
    """Criterion 16: Exact reconciliation: cache_hits + provider_calls == total_laboratories."""
    geocoder, mock_service, _, _, _ = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    summary = geocoder.run_batch(max_records=4)
    assert summary.reconcile() is True
    assert summary.cache_hits + summary.provider_calls == summary.total_laboratories
    assert summary.coordinates_available + summary.coordinates_unavailable == summary.total_laboratories


def test_17_no_duplicate_provider_calls(mock_geocoder_setup):
    """Criterion 17: Consecutive processing of identical entries avoids duplicate calls."""
    geocoder, mock_service, _, _, labs = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    # First run
    geocoder.run_batch(max_records=2)
    assert mock_service.geocode.call_count == 2

    # Second run without changes
    geocoder.run_batch(max_records=2)
    assert mock_service.geocode.call_count == 2  # Unchanged!


def test_18_checkpoint_consistency(mock_geocoder_setup):
    """Criterion 18: Checkpoint accurately reflects all processed laboratories."""
    geocoder, mock_service, _, checkpoint_file, _ = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    summary = geocoder.run_batch(max_records=3)
    assert checkpoint_file.exists()

    cp_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    assert cp_data["total_checkpointed"] == 3
    assert "1" in cp_data["items"]
    assert "2" in cp_data["items"]
    assert "3" in cp_data["items"]
    assert cp_data["items"]["1"]["geocoding_status"] == "SUCCESS"


def test_19_category_accounting(mock_geocoder_setup):
    """Criterion 19: Reconciles category counts: BIS-owned, recognized, empanelled, empty-scope."""
    geocoder, mock_service, _, _, _ = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    summary = geocoder.run_batch(max_records=4)
    assert summary.bis_owned_geocoded == 1
    assert summary.recognized_geocoded == 2
    assert summary.empanelled_geocoded == 1
    assert summary.empty_scope_geocoded == 1
    assert summary.bis_owned_geocoded + summary.recognized_geocoded + summary.empanelled_geocoded == 4


def test_20_authoritative_catalog_immutability(mock_geocoder_setup):
    """Criterion 20: Proves authoritative catalog files remain 100% untouched."""
    geocoder, mock_service, _, _, _ = mock_geocoder_setup
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.0,
        longitude=77.0,
        original_address="Sample"
    )

    # Compute SHA-256 before batch
    catalog_content_before = geocoder.catalog_path.read_bytes()
    hash_before = hashlib.sha256(catalog_content_before).hexdigest()

    geocoder.run_batch(max_records=4)

    # Verify SHA-256 after batch
    catalog_content_after = geocoder.catalog_path.read_bytes()
    hash_after = hashlib.sha256(catalog_content_after).hexdigest()

    assert hash_before == hash_after
    assert catalog_content_before == catalog_content_after
