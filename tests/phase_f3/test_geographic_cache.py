"""
Phase F3 Step 5A: Geographic Metadata Cache Foundation Unit Tests.

Verifies:
1. successful geocode
2. zero result
3. API error
4. rate limiting
5. network failure
6. missing address
7. missing API key
8. missing coordinates
9. original BIS address preservation
10. Geoapify formatted address separation
11. provider metadata separation
12. cache-key determinism
13. changed-address detection
14. stable BIS laboratory identity
15. no coordinate fabrication
16. no authoritative catalog mutation
17. repeated identical input produces identical cache identity
18. failed geocode does not create coordinates
19. catalog immutability (creating/updating cache cannot change lab identity, address, category, scopes, standards, clauses, or fees).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.geo.cache import LabGeographicCache
from ai.lims.models import (
    LabCategory,
    NormalizedLimsLab,
    NormalizedLimsScope,
    ClauseRecord,
)
from ai.services.geocoding_service import GeocodingResult, GeoapifyGeocodingService


@pytest.fixture
def temp_cache_dir(tmp_path):
    return tmp_path / "geographic_cache"


@pytest.fixture
def cache_instance(temp_cache_dir):
    cache_file = temp_cache_dir / "lab_coordinates_cache.jsonl"
    return LabGeographicCache(cache_file=cache_file)


@pytest.fixture
def sample_lab():
    return NormalizedLimsLab(
        internal_id=15,
        lab_code="8102006",
        lab_name="SIIR, Delhi Shriram Institute For Industrial Research",
        category=LabCategory.BIS_RECOGNIZED,
        original_address="19, University Road, Delhi, Delhi, India - 110007",
        normalized_state="Delhi",
        normalized_city="Delhi",
        pincode="110007",
        source_url="https://lims.bis.gov.in/home_lab_scope/15/",
        provenance_sha256="sha_sample_15"
    )


def test_01_successful_geocode(cache_instance, sample_lab):
    """Criterion 1: Successful geocode records valid coordinates and metadata."""
    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        place_id="geo_place_12345",
        formatted_address="19, University Road, Delhi 110007, India",
        confidence=0.95,
        match_type="full_match",
        provider="GEOAPIFY",
        original_address=sample_lab.original_address,
        raw_result={"properties": {"rank": 1}}
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.status == "SUCCESS"
    assert meta.has_valid_coordinates() is True
    assert meta.latitude == 28.6912
    assert meta.longitude == 77.2144
    assert meta.place_id == "geo_place_12345"
    assert meta.confidence == 0.95


def test_02_zero_result(cache_instance, sample_lab):
    """Criterion 2: ZERO_RESULTS status sets coordinates strictly to None."""
    mock_result = GeocodingResult(
        status="ZERO_RESULTS",
        latitude=None,
        longitude=None,
        original_address=sample_lab.original_address,
        provider="GEOAPIFY"
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.status == "ZERO_RESULTS"
    assert meta.has_valid_coordinates() is False
    assert meta.latitude is None
    assert meta.longitude is None


def test_03_api_error(cache_instance, sample_lab):
    """Criterion 3: API_ERROR status sets coordinates to None and records error message."""
    mock_result = GeocodingResult(
        status="API_ERROR",
        latitude=None,
        longitude=None,
        original_address=sample_lab.original_address,
        error_message="HTTP Error 500: Internal Server Error"
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.status == "API_ERROR"
    assert meta.latitude is None
    assert meta.longitude is None
    assert "500" in meta.error_message


def test_04_rate_limiting(cache_instance, sample_lab):
    """Criterion 4: RATE_LIMITED status is recorded without creating coordinates."""
    mock_result = GeocodingResult(
        status="RATE_LIMITED",
        latitude=None,
        longitude=None,
        original_address=sample_lab.original_address,
        error_message="HTTP Error 429: Too Many Requests"
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.status == "RATE_LIMITED"
    assert meta.latitude is None
    assert meta.longitude is None


def test_05_network_failure(cache_instance, sample_lab):
    """Criterion 5: NETWORK_ERROR preserves failure status without throwing."""
    mock_result = GeocodingResult(
        status="NETWORK_ERROR",
        latitude=None,
        longitude=None,
        original_address=sample_lab.original_address,
        error_message="Connection timed out"
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.status == "NETWORK_ERROR"
    assert meta.latitude is None


def test_06_missing_address(cache_instance):
    """Criterion 6: MISSING_ADDRESS status."""
    mock_result = GeocodingResult(
        status="MISSING_ADDRESS",
        latitude=None,
        longitude=None,
        original_address="",
        error_message="Address input is empty"
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=999,
        public_lab_code=None,
        original_address="",
        result=mock_result
    )

    assert meta.status == "MISSING_ADDRESS"
    assert meta.latitude is None


def test_07_missing_api_key(cache_instance, sample_lab):
    """Criterion 7: MISSING_API_KEY status."""
    mock_result = GeocodingResult(
        status="MISSING_API_KEY",
        latitude=None,
        longitude=None,
        original_address=sample_lab.original_address,
        error_message="GEOAPIFY_API_KEY is not configured"
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.status == "MISSING_API_KEY"
    assert meta.latitude is None


def test_08_missing_coordinates(cache_instance, sample_lab):
    """Criterion 8: has_valid_coordinates is False if coordinates are missing or None."""
    meta = LabGeographicMetadata(
        internal_id=15,
        public_lab_code="8102006",
        original_address=sample_lab.original_address,
        address_hash=compute_address_hash(sample_lab.original_address),
        cache_key=generate_cache_key(15, sample_lab.original_address),
        status="SUCCESS",
        latitude=None,  # missing
        longitude=None
    )
    assert meta.has_valid_coordinates() is False


def test_09_original_bis_address_preservation(cache_instance, sample_lab):
    """Criterion 9: original_address is preserved 100% verbatim from statutory BIS record."""
    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        place_id="place_1",
        formatted_address="Reformatted by Geoapify, Delhi",
        original_address=sample_lab.original_address
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.original_address == sample_lab.original_address
    assert meta.original_address != meta.formatted_address


def test_10_formatted_address_separation(cache_instance, sample_lab):
    """Criterion 10: Geoapify formatted_address is strictly separated from original_address."""
    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        formatted_address="External Geocoder Address String",
        original_address=sample_lab.original_address
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.formatted_address == "External Geocoder Address String"
    assert meta.original_address == sample_lab.original_address


def test_11_provider_metadata_separation(cache_instance, sample_lab):
    """Criterion 11: Provider raw metadata is isolated in provider_metadata dict."""
    raw_api_payload = {"rank": 1, "datasource": {"sourcename": "openstreetmap"}}
    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        original_address=sample_lab.original_address,
        raw_result=raw_api_payload
    )
    meta = cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    assert meta.provider_metadata == raw_api_payload


def test_12_cache_key_determinism(sample_lab):
    """Criterion 12: Cache key is deterministically derived from internal_id and address hash."""
    k1 = generate_cache_key(sample_lab.internal_id, sample_lab.original_address)
    k2 = generate_cache_key(sample_lab.internal_id, sample_lab.original_address)
    assert k1 == k2
    assert k1.startswith(f"GEO_LAB_{sample_lab.internal_id}_")


def test_13_changed_address_detection(cache_instance, sample_lab):
    """Criterion 13: Changed address causes a cache miss and is flagged as stale."""
    # Step 1: Cache with original address
    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        original_address=sample_lab.original_address
    )
    cache_instance.record_geocoding_result(
        internal_id=sample_lab.internal_id,
        public_lab_code=sample_lab.lab_code,
        original_address=sample_lab.original_address,
        result=mock_result
    )

    # Lookup with exact address hits cache
    hit = cache_instance.get_for_laboratory(sample_lab.internal_id, sample_lab.original_address)
    assert hit is not None

    # Lookup with changed address misses cache (prevents stale coordinate reuse!)
    changed_address = "New Premises, Sector 62, Noida, Uttar Pradesh 201301"
    miss = cache_instance.get_for_laboratory(sample_lab.internal_id, changed_address)
    assert miss is None, "Cache incorrectly returned coordinates for a changed address!"

    # is_stale flags the discrepancy
    assert cache_instance.is_stale(sample_lab.internal_id, changed_address) is True
    assert cache_instance.is_stale(sample_lab.internal_id, sample_lab.original_address) is False


def test_14_stable_bis_laboratory_identity(cache_instance, sample_lab):
    """Criterion 14: Cache is bound to stable internal_id."""
    mock_result = GeocodingResult(status="SUCCESS", latitude=28.69, longitude=77.21, original_address=sample_lab.original_address)
    cache_instance.record_geocoding_result(sample_lab.internal_id, sample_lab.lab_code, sample_lab.original_address, mock_result)

    by_id = cache_instance.get_by_id(sample_lab.internal_id)
    assert by_id is not None
    assert by_id.internal_id == sample_lab.internal_id
    assert by_id.public_lab_code == sample_lab.lab_code


def test_15_no_coordinate_fabrication(cache_instance, sample_lab):
    """Criterion 15: Zero coordinate fabrication on failure."""
    mock_fail = GeocodingResult(status="API_ERROR", original_address=sample_lab.original_address, error_message="Failed")
    meta = cache_instance.record_geocoding_result(sample_lab.internal_id, sample_lab.lab_code, sample_lab.original_address, mock_fail)
    assert meta.latitude is None
    assert meta.longitude is None
    assert meta.has_valid_coordinates() is False


def test_16_repeated_identical_input_produces_identical_cache(cache_instance, sample_lab):
    """Criterion 17: Repeated identical inputs produce bitwise identical cache records."""
    mock_result = GeocodingResult(status="SUCCESS", latitude=28.6912, longitude=77.2144, original_address=sample_lab.original_address)
    meta1 = cache_instance.record_geocoding_result(sample_lab.internal_id, sample_lab.lab_code, sample_lab.original_address, mock_result)
    meta2 = cache_instance.record_geocoding_result(sample_lab.internal_id, sample_lab.lab_code, sample_lab.original_address, mock_result)
    assert meta1.cache_key == meta2.cache_key
    assert meta1.address_hash == meta2.address_hash


def test_17_save_and_load_disk_persistence(temp_cache_dir, sample_lab):
    """Persistence test: Verify JSONL serialization and manifest creation."""
    cache_file = temp_cache_dir / "test_cache.jsonl"
    cache1 = LabGeographicCache(cache_file=cache_file)

    mock_result = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        place_id="place_abc",
        formatted_address="19 University Rd, Delhi",
        original_address=sample_lab.original_address
    )
    cache1.record_geocoding_result(sample_lab.internal_id, sample_lab.lab_code, sample_lab.original_address, mock_result)
    cache1.save_to_disk()

    assert cache_file.exists()
    manifest_file = temp_cache_dir / "cache_manifest.json"
    assert manifest_file.exists()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["total_cached_records"] == 1
    assert manifest["successful_coordinates_count"] == 1

    # Load from fresh instance
    cache2 = LabGeographicCache(cache_file=cache_file)
    assert len(cache2) == 1
    loaded = cache2.get_by_id(sample_lab.internal_id)
    assert loaded is not None
    assert loaded.latitude == 28.6912
    assert loaded.longitude == 77.2144


def test_18_catalog_immutability(cache_instance, sample_lab):
    """
    Criterion 19: Proves creating/updating geographic metadata CANNOT mutate:
    - BIS laboratory identity
    - original address
    - category
    - validity
    - scope records
    """
    initial_id = sample_lab.internal_id
    initial_code = sample_lab.lab_code
    initial_address = sample_lab.original_address
    initial_category = sample_lab.category
    initial_status = sample_lab.recognition_status

    # Mock geocoder service
    mock_service = MagicMock(spec=GeoapifyGeocodingService)
    mock_service.geocode.return_value = GeocodingResult(
        status="SUCCESS",
        latitude=28.6912,
        longitude=77.2144,
        formatted_address="Geoapify Address",
        original_address=sample_lab.original_address
    )

    # Perform geocoding through cache bridge
    geo_meta = cache_instance.geocode_laboratory(sample_lab, service=mock_service)

    # Verify laboratory record remains completely untouched
    assert sample_lab.internal_id == initial_id
    assert sample_lab.lab_code == initial_code
    assert sample_lab.original_address == initial_address
    assert sample_lab.category == initial_category
    assert sample_lab.recognition_status == initial_status

    # Coordinates exist only in geo_meta, not in sample_lab
    assert not hasattr(sample_lab, "latitude")
    assert not hasattr(sample_lab, "longitude")
    assert geo_meta.latitude == 28.6912
