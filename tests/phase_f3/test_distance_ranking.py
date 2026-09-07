"""
Phase F3 Step 6: Focused Unit Tests for Deterministic Distance & Geographic Ranking Engine.

Tests all required criteria:
1. Haversine calculation accuracy
2. Zero distance (identical coordinates)
3. Invalid/null coordinates
4. Missing cache record
5. ZERO_RESULTS handling (null coordinates, null distance)
6. Capability mismatch exclusion
7. Qualified candidates ranked geographically (ascending distance)
8. Equal-distance deterministic tie-break
9. Category and provenance preservation
10. Empty-scope isolation
11. No external API calls
12. Deterministic repeated execution
13. Invalid user coordinates safety
14. Max distance filtering
"""

import math
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from ai.geo.distance import (
    haversine_distance_km,
    safe_haversine_distance_km,
    validate_coordinates,
    EARTH_RADIUS_KM,
)
from ai.geo.models import (
    LabGeographicMetadata,
    compute_address_hash,
    generate_cache_key,
)
from ai.geo.cache import LabGeographicCache
from ai.geo.ranking import (
    GeographicDistanceMetadata,
    GeographicRankingEngine,
)
from ai.lims.models import LabCategory
from ai.lims.matching_models import (
    MatchStatus,
    ScopeCompleteness,
    MatchReason,
    LabMatchingRequest,
    LabCandidateMatch,
    LabMatchingResult,
)
from ai.lims.matching_engine import LimsMatchingEngine


# Reference Coordinates
DELHI_COORDS = (28.6139, 77.2090)        # Connaught Place / Central Delhi
NOIDA_COORDS = (28.5355, 77.3910)        # Noida (~20 km from Delhi)
MUMBAI_COORDS = (19.0760, 72.8777)       # Mumbai (~1150 km from Delhi)
BENGALURU_COORDS = (12.9716, 77.5946)    # Bengaluru (~1740 km from Delhi)
KOLKATA_COORDS = (22.5726, 88.3639)      # Kolkata (~1305 km from Delhi)


# --- 1. Haversine Calculation Accuracy ---

def test_01_haversine_calculation_accuracy():
    """Criterion 1: Haversine distance matches known geodesic distances within 0.5% tolerance."""
    # Delhi to Mumbai distance is ~1148 - 1152 km
    dist_delhi_mumbai = haversine_distance_km(
        DELHI_COORDS[0], DELHI_COORDS[1], MUMBAI_COORDS[0], MUMBAI_COORDS[1]
    )
    assert 1145.0 <= dist_delhi_mumbai <= 1155.0

    # Delhi to Kolkata distance is ~1300 - 1315 km
    dist_delhi_kolkata = haversine_distance_km(
        DELHI_COORDS[0], DELHI_COORDS[1], KOLKATA_COORDS[0], KOLKATA_COORDS[1]
    )
    assert 1300.0 <= dist_delhi_kolkata <= 1315.0

    # Delhi to Noida (~18 - 25 km)
    dist_delhi_noida = haversine_distance_km(
        DELHI_COORDS[0], DELHI_COORDS[1], NOIDA_COORDS[0], NOIDA_COORDS[1]
    )
    assert 15.0 <= dist_delhi_noida <= 25.0


# --- 2. Zero Distance ---

def test_02_zero_distance():
    """Criterion 2: Identical coordinates yield exactly 0.0 km."""
    dist = haversine_distance_km(28.6139, 77.2090, 28.6139, 77.2090)
    assert dist == 0.0

    dist_safe = safe_haversine_distance_km(19.0760, 72.8777, 19.0760, 72.8777)
    assert dist_safe == 0.0


# --- 3. Invalid / Null Coordinates ---

def test_03_invalid_null_coordinates():
    """Criterion 3: Out-of-bounds, non-numeric, or null coordinates are rejected safely."""
    # Out of bounds latitude (> 90 or < -90)
    assert validate_coordinates(91.0, 77.0) is False
    assert validate_coordinates(-90.1, 77.0) is False
    with pytest.raises(ValueError, match="Invalid coordinate"):
        haversine_distance_km(91.0, 77.0, 28.0, 77.0)

    # Out of bounds longitude (> 180 or < -180)
    assert validate_coordinates(28.0, 180.5) is False
    assert validate_coordinates(28.0, -180.5) is False
    with pytest.raises(ValueError, match="Invalid coordinate"):
        haversine_distance_km(28.0, 77.0, 28.0, 185.0)

    # Null coordinates
    assert validate_coordinates(None, 77.0) is False
    assert validate_coordinates(28.0, None) is False
    assert safe_haversine_distance_km(None, 77.0, 28.0, 77.0) is None
    assert safe_haversine_distance_km(28.0, 77.0, None, None) is None

    # NaN / Inf coordinates
    assert validate_coordinates(float("nan"), 77.0) is False
    assert validate_coordinates(28.0, float("inf")) is False


# --- Helper Fixture: Synthetic Mock Candidates & Cache ---

@pytest.fixture
def sample_candidates_and_cache(tmp_path):
    """
    Creates controlled candidate matches and a mock cache for testing ranking.
    """
    cache_file = tmp_path / "test_geo_cache.jsonl"
    cache = LabGeographicCache(cache_file=cache_file)

    # Lab 1: Delhi (very close to user in Delhi, ~5 km)
    addr1 = "Plot 1, Okhla, New Delhi - 110020"
    cache.put(LabGeographicMetadata(
        internal_id=101,
        public_lab_code="CL_DELHI",
        original_address=addr1,
        address_hash=compute_address_hash(addr1),
        cache_key=generate_cache_key(101, addr1),
        status="SUCCESS",
        latitude=28.5500,
        longitude=77.2500,
        formatted_address="Okhla, New Delhi"
    ))

    # Lab 2: Noida (medium distance, ~20 km)
    addr2 = "Sector 62, Noida - 201301"
    cache.put(LabGeographicMetadata(
        internal_id=102,
        public_lab_code="REC_NOIDA",
        original_address=addr2,
        address_hash=compute_address_hash(addr2),
        cache_key=generate_cache_key(102, addr2),
        status="SUCCESS",
        latitude=28.6200,
        longitude=77.3600,
        formatted_address="Sector 62, Noida"
    ))

    # Lab 3: Mumbai (far distance, ~1150 km)
    addr3 = "Andheri East, Mumbai - 400069"
    cache.put(LabGeographicMetadata(
        internal_id=103,
        public_lab_code="EMP_MUMBAI",
        original_address=addr3,
        address_hash=compute_address_hash(addr3),
        cache_key=generate_cache_key(103, addr3),
        status="SUCCESS",
        latitude=19.1100,
        longitude=72.8700,
        formatted_address="Andheri, Mumbai"
    ))

    # Lab 4: ZERO_RESULTS lab (null coordinates)
    addr4 = "Remote Village Without Pin, Haryana - 122001"
    cache.put(LabGeographicMetadata(
        internal_id=104,
        public_lab_code="REC_ZERO",
        original_address=addr4,
        address_hash=compute_address_hash(addr4),
        cache_key=generate_cache_key(104, addr4),
        status="ZERO_RESULTS",
        latitude=None,
        longitude=None
    ))

    # Lab candidates already qualified for a standard (e.g. IS 8978)
    candidates = [
        LabCandidateMatch(
            laboratory_identity="BIS Central Lab Delhi",
            public_lab_code="CL_DELHI",
            internal_id=101,
            category=LabCategory.BIS_OWNED,
            original_address=addr1,
            matching_standard="IS 8978",
            scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
            match_score=100.0
        ),
        LabCandidateMatch(
            laboratory_identity="Noida Testing Lab",
            public_lab_code="REC_NOIDA",
            internal_id=102,
            category=LabCategory.BIS_RECOGNIZED,
            original_address=addr2,
            matching_standard="IS 8978",
            scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
            match_score=95.0
        ),
        LabCandidateMatch(
            laboratory_identity="Mumbai Empanelled Lab",
            public_lab_code="EMP_MUMBAI",
            internal_id=103,
            category=LabCategory.BIS_EMPANELLED,
            original_address=addr3,
            matching_standard="IS 8978",
            scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
            match_score=90.0
        ),
        LabCandidateMatch(
            laboratory_identity="Zero Result Lab",
            public_lab_code="REC_ZERO",
            internal_id=104,
            category=LabCategory.BIS_RECOGNIZED,
            original_address=addr4,
            matching_standard="IS 8978",
            scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
            match_score=85.0
        ),
        LabCandidateMatch(
            laboratory_identity="Uncached Lab",
            public_lab_code="REC_UNCACHED",
            internal_id=105,  # Not in cache!
            category=LabCategory.BIS_RECOGNIZED,
            original_address="Uncached Street 99",
            matching_standard="IS 8978",
            scope_completeness=ScopeCompleteness.PARTIAL_SCOPE,
            match_score=80.0
        ),
    ]

    return candidates, cache


# --- 4. Missing Cache Record Handling ---

def test_04_missing_cache_record(sample_candidates_and_cache):
    """Criterion 4: Candidate not found in geographic cache receives has_coordinates=False and distance=None."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    uncached_cand = candidates[4]  # internal_id: 105
    engine.attach_distance(uncached_cand, user_lat=DELHI_COORDS[0], user_lon=DELHI_COORDS[1])

    geo = uncached_cand.external_geographic_metadata
    assert geo is not None
    assert geo["has_coordinates"] is False
    assert geo["distance_km"] is None
    assert geo["geocoding_status"] == "MISSING_CACHE_RECORD"


# --- 5. ZERO_RESULTS Handling ---

def test_05_zero_results_handling(sample_candidates_and_cache):
    """Criterion 5: ZERO_RESULTS lab preserves null coordinates, null distance, and status."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    zero_cand = candidates[3]  # internal_id: 104
    engine.attach_distance(zero_cand, user_lat=DELHI_COORDS[0], user_lon=DELHI_COORDS[1])

    geo = zero_cand.external_geographic_metadata
    assert geo is not None
    assert geo["has_coordinates"] is False
    assert geo["distance_km"] is None
    assert geo["laboratory_latitude"] is None
    assert geo["laboratory_longitude"] is None
    assert geo["geocoding_status"] == "ZERO_RESULTS"


# --- 6. Capability Mismatch Exclusion ---

def test_06_capability_mismatch_exclusion():
    """
    Criterion 6: Geographic ranking operates ONLY on already-qualified candidates.
    A laboratory that fails capability matching can NEVER enter the ranked list.
    """
    catalog_path = Path("data/catalog/phase_f3_lims")
    matching_engine = LimsMatchingEngine(catalog_dir=catalog_path)
    ranking_engine = GeographicRankingEngine()

    # Search for an authentic standard: IS 4985 (Unplasticized PVC Pipes)
    req = LabMatchingRequest(standard="IS 4985")
    match_res = matching_engine.match(req)

    assert match_res.status == MatchStatus.EXACT_MATCH
    initial_candidate_ids = {c.internal_id for c in match_res.candidates}

    # Rank geographically for a user in Delhi
    ranked_candidates = ranking_engine.rank_candidates(
        candidates=match_res.candidates,
        user_lat=DELHI_COORDS[0],
        user_lon=DELHI_COORDS[1]
    )

    ranked_ids = {c.internal_id for c in ranked_candidates}
    # No new candidates were created or added
    assert ranked_ids == initial_candidate_ids
    # Every single ranked candidate matches IS 4985
    for c in ranked_candidates:
        assert "4985" in c.matching_standard


# --- 7. Qualified Candidates Ranked Geographically ---

def test_07_qualified_candidates_ranked_geographically(sample_candidates_and_cache):
    """Criterion 7: Candidates with coordinates are ranked by distance ascending; nearest lab first."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    user_lat, user_lon = DELHI_COORDS
    ranked = engine.rank_candidates(candidates, user_lat=user_lat, user_lon=user_lon)

    assert len(ranked) == 5

    # Expected order:
    # 1. Lab 101 (Delhi, ~8 km)
    # 2. Lab 102 (Noida, ~20 km)
    # 3. Lab 103 (Mumbai, ~1150 km)
    # 4. Lab 104 (ZERO_RESULTS, no coords)
    # 5. Lab 105 (Uncached, no coords)
    assert ranked[0].internal_id == 101
    assert ranked[1].internal_id == 102
    assert ranked[2].internal_id == 103

    # Check rank numbers
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
    assert ranked[2].rank == 3
    assert ranked[3].rank == 4
    assert ranked[4].rank == 5

    # Check ascending distances
    dist0 = ranked[0].external_geographic_metadata["distance_km"]
    dist1 = ranked[1].external_geographic_metadata["distance_km"]
    dist2 = ranked[2].external_geographic_metadata["distance_km"]

    assert dist0 < dist1 < dist2
    assert ranked[3].external_geographic_metadata["has_coordinates"] is False
    assert ranked[4].external_geographic_metadata["has_coordinates"] is False


# --- 8. Equal-Distance Deterministic Tie-Break ---

def test_08_equal_distance_deterministic_tie_break(tmp_path):
    """
    Criterion 8: When two candidates have identical distance, tie-breaking deterministically
    evaluates: scope completeness -> match score -> category -> internal_id.
    """
    cache_file = tmp_path / "tie_cache.jsonl"
    cache = LabGeographicCache(cache_file=cache_file)

    # Two labs with identical coordinates (same building/industrial complex)
    addr = "Okhla Industrial Area Phase 1, New Delhi"
    for lab_id, code in [(201, "CODE_A"), (202, "CODE_B")]:
        cache.put(LabGeographicMetadata(
            internal_id=lab_id,
            public_lab_code=code,
            original_address=addr,
            address_hash=compute_address_hash(addr),
            cache_key=generate_cache_key(lab_id, addr),
            status="SUCCESS",
            latitude=28.5300,
            longitude=77.2700
        ))

    cand_a = LabCandidateMatch(
        laboratory_identity="Lab A (Partial Scope)",
        public_lab_code="CODE_A",
        internal_id=201,
        category=LabCategory.BIS_OWNED,
        original_address=addr,
        matching_standard="IS 8978",
        scope_completeness=ScopeCompleteness.PARTIAL_SCOPE,
        match_score=100.0
    )
    cand_b = LabCandidateMatch(
        laboratory_identity="Lab B (Complete Scope)",
        public_lab_code="CODE_B",
        internal_id=202,
        category=LabCategory.BIS_OWNED,
        original_address=addr,
        matching_standard="IS 8978",
        scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
        match_score=100.0
    )

    engine = GeographicRankingEngine(cache=cache)

    # Pass in [cand_a, cand_b]
    ranked = engine.rank_candidates([cand_a, cand_b], user_lat=28.6139, user_lon=77.2090)

    # COMPLETE_SCOPE must precede PARTIAL_SCOPE regardless of initial order
    assert ranked[0].internal_id == 202
    assert ranked[1].internal_id == 201

    # Now test tie-break when completeness and score are identical: internal_id ascending
    cand_c = LabCandidateMatch(
        laboratory_identity="Lab C",
        public_lab_code="CODE_C",
        internal_id=205,
        category=LabCategory.BIS_RECOGNIZED,
        original_address=addr,
        matching_standard="IS 8978",
        scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
        match_score=90.0
    )
    cand_d = LabCandidateMatch(
        laboratory_identity="Lab D",
        public_lab_code="CODE_D",
        internal_id=204,  # Lower ID should win
        category=LabCategory.BIS_RECOGNIZED,
        original_address=addr,
        matching_standard="IS 8978",
        scope_completeness=ScopeCompleteness.COMPLETE_SCOPE,
        match_score=90.0
    )

    ranked_cd = engine.rank_candidates([cand_c, cand_d], user_lat=28.6139, user_lon=77.2090)
    assert ranked_cd[0].internal_id == 204
    assert ranked_cd[1].internal_id == 205


# --- 9. Category & Provenance Preservation ---

def test_09_category_and_provenance_preservation(sample_candidates_and_cache):
    """Criterion 9: BIS laboratory identity, category, address, scope evidence, and provenance remain intact."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    cand = candidates[0]
    initial_category = cand.category
    initial_id = cand.internal_id
    initial_code = cand.public_lab_code
    initial_address = cand.original_address
    initial_standard = cand.matching_standard

    ranked = engine.rank_candidates([cand], user_lat=DELHI_COORDS[0], user_lon=DELHI_COORDS[1])
    res = ranked[0]

    assert res.category == initial_category
    assert res.internal_id == initial_id
    assert res.public_lab_code == initial_code
    assert res.original_address == initial_address
    assert res.matching_standard == initial_standard
    assert "authority_disclaimer" in res.external_geographic_metadata


# --- 10. Empty-Scope Isolation ---

def test_10_empty_scope_isolation():
    """
    Criterion 10: Empty-scope laboratories have 0 capability and can NEVER be ranked
    as candidates for standard testing requests.
    """
    catalog_path = Path("data/catalog/phase_f3_lims")
    matching_engine = LimsMatchingEngine(catalog_dir=catalog_path)
    ranking_engine = GeographicRankingEngine()

    # Search for an active standard
    req = LabMatchingRequest(standard="IS 4985")
    match_res = matching_engine.match(req)

    # Empty-scope lab IDs from catalog audit
    # Find all empty-scope lab IDs
    empty_scope_ids = set()
    with open("data/catalog/phase_f3_lims/laboratories_normalized.jsonl", "r") as f:
        import json
        for line in f:
            if line.strip():
                lab = json.loads(line)
                if lab.get("scope_status") == "SCOPE_EMPTY":
                    empty_scope_ids.add(lab["internal_id"])

    assert len(empty_scope_ids) == 39

    ranked = ranking_engine.rank_candidates(
        candidates=match_res.candidates,
        user_lat=DELHI_COORDS[0],
        user_lon=DELHI_COORDS[1]
    )

    # Assert zero empty-scope labs exist among ranked candidates
    ranked_ids = set(c.internal_id for c in ranked)
    overlap = ranked_ids & empty_scope_ids
    assert len(overlap) == 0, f"Empty scope laboratories found in ranked candidates: {overlap}"


# --- 11. No External API Calls ---

def test_11_no_external_api_calls(sample_candidates_and_cache):
    """Criterion 11: Ranking engine makes zero HTTP/network requests."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    # Patch urllib and socket to prevent and detect any network attempt
    with patch("urllib.request.urlopen") as mock_urlopen, \
         patch("urllib.request.Request") as mock_req, \
         patch("socket.socket") as mock_socket:

        ranked = engine.rank_candidates(
            candidates,
            user_lat=DELHI_COORDS[0],
            user_lon=DELHI_COORDS[1]
        )

        assert len(ranked) == 5
        assert mock_urlopen.call_count == 0
        assert mock_req.call_count == 0
        assert mock_socket.call_count == 0


# --- 12. Deterministic Repeated Execution ---

def test_12_deterministic_repeated_execution(sample_candidates_and_cache):
    """Criterion 12: Repeated ranking runs produce 100% identical outputs."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    run1 = engine.rank_candidates(candidates, user_lat=DELHI_COORDS[0], user_lon=DELHI_COORDS[1])
    run2 = engine.rank_candidates(candidates, user_lat=DELHI_COORDS[0], user_lon=DELHI_COORDS[1])

    assert [c.internal_id for c in run1] == [c.internal_id for c in run2]
    assert [c.rank for c in run1] == [c.rank for c in run2]
    assert [c.external_geographic_metadata["distance_km"] for c in run1] == \
           [c.external_geographic_metadata["distance_km"] for c in run2]


# --- 13. Invalid User Coordinates Safety ---

def test_13_invalid_user_coordinates_safety(sample_candidates_and_cache):
    """Criterion 13: Invalid user coordinates (e.g. lat > 90) handled safely without crashing."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    ranked = engine.rank_candidates(candidates, user_lat=999.0, user_lon=77.0)
    assert len(ranked) == 5
    for c in ranked:
        geo = c.external_geographic_metadata
        assert geo["has_coordinates"] is False
        assert geo["distance_km"] is None
        assert geo["geocoding_status"] == "INVALID_USER_COORDINATES"


# --- 14. Max Distance Filtering ---

def test_14_max_distance_filtering(sample_candidates_and_cache):
    """Criterion 14: max_distance_km filters candidates strictly within the radius."""
    candidates, cache = sample_candidates_and_cache
    engine = GeographicRankingEngine(cache=cache)

    # Filter within 50 km from Delhi (should include Delhi ~8 km and Noida ~20 km, exclude Mumbai ~1150 km and no-coords)
    ranked = engine.rank_candidates(
        candidates,
        user_lat=DELHI_COORDS[0],
        user_lon=DELHI_COORDS[1],
        max_distance_km=50.0
    )

    assert len(ranked) == 2
    assert ranked[0].internal_id == 101  # Delhi
    assert ranked[1].internal_id == 102  # Noida
    assert ranked[0].external_geographic_metadata["distance_km"] <= 50.0
    assert ranked[1].external_geographic_metadata["distance_km"] <= 50.0
