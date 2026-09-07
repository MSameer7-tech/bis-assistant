"""
Phase F3 Step 7 Tests: Laboratory Finder Backend Search API.

Validates:
1. Exact BIS standard match (POST and GET)
2. No-match standard (empty candidates, status NO_MATCH)
3. Qualified labs returned with comprehensive capability evidence
4. State filter verification
5. City/district filter verification
6. Reference coordinates provided and attached
7. Ascending distance ordering
8. Max-distance radius filtering
9. Missing coordinates handling (distance_km is None, deterministic non-geographic ordering)
10. ZERO_RESULTS lab handling (null coords, null distance, retained capability)
11. Empty-scope exclusion (0 of 39 empty-scope labs ever qualify)
12. Capability mismatch exclusion (clause exclusion, complete-scope requirement)
13. Deterministic repeated requests
14. Provenance preservation and authority boundaries
15. Invalid coordinates rejection (HTTP 400)
16. Invalid requests rejection (missing standard, max_distance without coords, limit <= 0, etc.)
17. Result limiting (limit parameter)
18. Zero external network/API calls
"""

import pytest
import socket
import urllib.request
from pathlib import Path
from typing import List, Set
from fastapi.testclient import TestClient

from backend.app import app
from ai.lims.retrieval_layer import LimsRetrievalLayer
from ai.geo.cache import LabGeographicCache


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provides TestClient bound to the FastAPI application."""
    return TestClient(app)


@pytest.fixture(scope="module")
def empty_scope_ids() -> Set[int]:
    """Retrieves all 39 empty-scope laboratory internal_ids from the catalog."""
    layer = LimsRetrievalLayer.load_from_catalog(Path("data/catalog/phase_f3_lims"))
    return {
        lab.internal_id
        for lab in layer._labs.values()
        if lab.internal_id not in layer._scopes_by_lab_id
        or len(layer._scopes_by_lab_id[lab.internal_id]) == 0
    }


# ---------------------------------------------------------------------------
# Test 1: Exact BIS Standard Match (POST and GET)
# ---------------------------------------------------------------------------

def test_exact_bis_standard_match(client: TestClient):
    """Verifies that an exact BIS standard returns MATCH with qualified candidates via both POST and GET."""
    # POST
    resp_post = client.post("/api/labs/search", json={"standard": "IS 4985"})
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["status"] == "MATCH"
    assert data_post["match_status"] == "EXACT_MATCH"
    assert data_post["standard"] == "IS 4985"
    assert data_post["total_matching"] == 29
    assert len(data_post["candidates"]) == 29

    # GET
    resp_get = client.get("/api/labs/search?standard=IS%204985")
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert data_get["status"] == "MATCH"
    assert data_get["match_status"] == "EXACT_MATCH"
    assert data_get["total_matching"] == 29
    assert len(data_get["candidates"]) == 29


# ---------------------------------------------------------------------------
# Test 2: No-Match Standard
# ---------------------------------------------------------------------------

def test_no_match_standard(client: TestClient):
    """Verifies that a standard absent from BIS catalog returns HTTP 200 with NO_MATCH and empty candidates."""
    resp = client.post("/api/labs/search", json={"standard": "IS 999999"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "NO_MATCH"
    assert data["match_status"] == "NO_MATCH"
    assert data["total_matching"] == 0
    assert data["returned_candidates"] == 0
    assert data["candidates"] == []


# ---------------------------------------------------------------------------
# Test 3: Qualified Labs Returned With Evidence
# ---------------------------------------------------------------------------

def test_qualified_labs_returned_with_evidence(client: TestClient):
    """Verifies that returned candidates include complete capability and statutory evidence."""
    resp = client.post("/api/labs/search", json={"standard": "IS 4985"})
    assert resp.status_code == 200
    cand = resp.json()["candidates"][0]

    # Statutory BIS Identity
    assert isinstance(cand["internal_id"], int)
    assert cand["public_lab_code"] is not None
    assert len(cand["laboratory_name"]) > 0
    assert cand["category"] in {"BIS_OWNED", "BIS_RECOGNIZED", "BIS_EMPANELLED"}
    assert len(cand["address"]["original_address"]) > 0

    # Capability Evidence
    evidence = cand["capability_evidence"]
    assert "IS 4985" in evidence["matching_standard"]
    assert len(evidence["matching_scope_id"]) > 0
    assert evidence["scope_completeness"] in {"COMPLETE_SCOPE", "PARTIAL_SCOPE"}
    assert evidence["match_score"] > 0
    assert len(evidence["match_reasons"]) > 0
    assert len(evidence["provenance_url"]) > 0
    assert len(evidence["provenance_sha256"]) == 64


# ---------------------------------------------------------------------------
# Test 4: State Filter
# ---------------------------------------------------------------------------

def test_state_filter(client: TestClient):
    """Verifies that state filtering restricts candidates to the specified state."""
    resp = client.post("/api/labs/search", json={"standard": "IS 4985", "state": "GUJARAT"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "MATCH"
    assert 0 < data["total_matching"] < 29

    for cand in data["candidates"]:
        addr = cand["address"]
        state_match = (
            (addr["state"] and "GUJARAT" in addr["state"].upper())
            or ("GUJARAT" in addr["original_address"].upper())
        )
        assert state_match, f"Candidate {cand['laboratory_name']} does not match state GUJARAT"


# ---------------------------------------------------------------------------
# Test 5: City / District Filter
# ---------------------------------------------------------------------------

def test_city_district_filter(client: TestClient):
    """Verifies that city and district filtering restricts candidates accurately."""
    resp = client.post("/api/labs/search", json={"standard": "IS 4985", "city": "DELHI"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "MATCH"
    assert len(data["candidates"]) > 0

    for cand in data["candidates"]:
        addr = cand["address"]
        city_match = (
            (addr["city"] and "DELHI" in addr["city"].upper())
            or ("DELHI" in addr["original_address"].upper())
        )
        assert city_match, f"Candidate {cand['laboratory_name']} does not match city DELHI"


# ---------------------------------------------------------------------------
# Test 6: Reference Coordinates Provided
# ---------------------------------------------------------------------------

def test_reference_coordinates_provided(client: TestClient):
    """Verifies that supplying reference coordinates echoes user coords and attaches distances."""
    delhi_lat, delhi_lon = 28.6139, 77.2090
    resp = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": delhi_lat,
        "longitude": delhi_lon
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["query_criteria"]["user_coordinates"] == {"latitude": delhi_lat, "longitude": delhi_lon}

    cands_with_coords = [c for c in data["candidates"] if c["geographic_metadata"]["has_coordinates"]]
    assert len(cands_with_coords) > 0

    for cand in cands_with_coords:
        dist = cand["geographic_metadata"]["distance_km"]
        assert dist is not None
        assert dist >= 0.0


# ---------------------------------------------------------------------------
# Test 7: Distance Ordering (Ascending Distance)
# ---------------------------------------------------------------------------

def test_distance_ordering(client: TestClient):
    """Verifies that candidates with coordinates are ordered by ascending distance."""
    resp = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 28.6139,
        "longitude": 77.2090
    })
    assert resp.status_code == 200
    candidates = resp.json()["candidates"]

    # Labs with coordinates must come first, sorted by distance ascending
    coord_candidates = [c for c in candidates if c["geographic_metadata"]["has_coordinates"]]
    distances = [c["geographic_metadata"]["distance_km"] for c in coord_candidates]

    for i in range(len(distances) - 1):
        assert distances[i] <= distances[i + 1], (
            f"Distance at rank {i+1} ({distances[i]}) > distance at rank {i+2} ({distances[i+1]})"
        )


# ---------------------------------------------------------------------------
# Test 8: Max-Distance Radius Filtering
# ---------------------------------------------------------------------------

def test_max_distance_filtering(client: TestClient):
    """Verifies that max_distance_km strictly filters candidates within the radius."""
    delhi_lat, delhi_lon = 28.6139, 77.2090

    # 50km radius around Delhi
    resp_50 = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": delhi_lat,
        "longitude": delhi_lon,
        "max_distance_km": 50.0
    })
    assert resp_50.status_code == 200
    data_50 = resp_50.json()

    assert data_50["status"] == "MATCH"
    assert data_50["total_matching"] < 29
    for cand in data_50["candidates"]:
        dist = cand["geographic_metadata"]["distance_km"]
        assert dist is not None and dist <= 50.0

    # 10km radius around Delhi (tighter)
    resp_10 = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": delhi_lat,
        "longitude": delhi_lon,
        "max_distance_km": 10.0
    })
    assert resp_10.status_code == 200
    data_10 = resp_10.json()
    assert data_10["total_matching"] <= data_50["total_matching"]


# ---------------------------------------------------------------------------
# Test 9: Missing Coordinates (Deterministic Non-Geographic Ordering)
# ---------------------------------------------------------------------------

def test_missing_coordinates(client: TestClient):
    """Verifies that omitting user coordinates returns distance_km=None and deterministic sorting."""
    resp = client.post("/api/labs/search", json={"standard": "IS 4985"})
    assert resp.status_code == 200
    data = resp.json()

    for cand in data["candidates"]:
        assert cand["geographic_metadata"]["distance_km"] is None
        assert cand["geographic_metadata"]["geocoding_status"] in {
            "SUCCESS_NO_USER_LOCATION", "ZERO_RESULTS", "UNKNOWN"
        }

    # First candidate should be BIS_OWNED according to deterministic tie-breaker
    assert data["candidates"][0]["category"] == "BIS_OWNED"


# ---------------------------------------------------------------------------
# Test 10: ZERO_RESULTS Lab Handling
# ---------------------------------------------------------------------------

def test_zero_results_lab_handling(client: TestClient):
    """Verifies that ZERO_RESULTS labs retain null coordinates/distance and no fabricated coords."""
    # Lab 1610 (Arakonam, Tamil Nadu) has scope for IS 269 and ZERO_RESULTS in cache
    resp = client.post("/api/labs/search", json={
        "standard": "IS 269",
        "latitude": 12.9716,
        "longitude": 77.5946
    })
    assert resp.status_code == 200
    candidates = resp.json()["candidates"]

    zero_cand = next((c for c in candidates if c["internal_id"] == 1610), None)
    assert zero_cand is not None, "Lab 1610 with IS 269 capability should be included in candidates"

    geo = zero_cand["geographic_metadata"]
    assert geo["has_coordinates"] is False
    assert geo["latitude"] is None
    assert geo["longitude"] is None
    assert geo["distance_km"] is None
    assert geo["geocoding_status"] == "ZERO_RESULTS"


# ---------------------------------------------------------------------------
# Test 11: Empty-Scope Exclusion
# ---------------------------------------------------------------------------

def test_empty_scope_exclusion(client: TestClient, empty_scope_ids: Set[int]):
    """Verifies that none of the 39 empty-scope laboratories ever qualify for any standard."""
    assert len(empty_scope_ids) == 39

    test_standards = ["IS 4985", "IS 8978", "IS 269", "IS 10500", "IS 1786"]
    for std in test_standards:
        resp = client.post("/api/labs/search", json={"standard": std})
        if resp.status_code == 200:
            cands = resp.json().get("candidates", [])
            for c in cands:
                assert c["internal_id"] not in empty_scope_ids, (
                    f"Empty-scope lab {c['internal_id']} ({c['laboratory_name']}) was illegally matched for {std}!"
                )


# ---------------------------------------------------------------------------
# Test 12: Capability Mismatch Exclusion
# ---------------------------------------------------------------------------

def test_capability_mismatch_exclusion(client: TestClient):
    """Verifies that laboratories missing required capability, clauses, or category are appropriately evaluated."""
    # Complete scope requirement excludes partial scopes
    resp_complete = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "require_complete_scope": True
    })
    assert resp_complete.status_code == 200
    for cand in resp_complete.json()["candidates"]:
        assert cand["capability_evidence"]["scope_completeness"] == "COMPLETE_SCOPE"

    # Requested clause missing from laboratory scope is flagged in evidence
    resp_clause = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "clauses": ["9999.9999"]
    })
    assert resp_clause.status_code == 200
    data_clause = resp_clause.json()
    assert data_clause["match_status"] == "PARTIAL_MATCH"
    for cand in data_clause["candidates"]:
        ev = cand["capability_evidence"]
        assert "9999.9999" in ev["unmatched_requested_clauses"]
        assert "MISSING_REQUIRED_CLAUSES" in ev["match_reasons"]
        assert len(ev["matched_clauses"]) == 0

    # Category mismatch: IS 1011 has only BIS_RECOGNIZED labs, so searching for BIS_OWNED returns NO_MATCH
    resp_cat = client.post("/api/labs/search", json={
        "standard": "IS 1011",
        "category": "BIS_OWNED"
    })
    assert resp_cat.status_code == 200
    assert resp_cat.json()["status"] == "NO_MATCH"
    assert resp_cat.json()["total_matching"] == 0


# ---------------------------------------------------------------------------
# Test 13: Deterministic Repeated Requests
# ---------------------------------------------------------------------------

def test_deterministic_repeated_requests(client: TestClient):
    """Verifies that repeated identical searches yield bitwise identical candidates and ranking."""
    payload = {
        "standard": "IS 4985",
        "latitude": 28.6139,
        "longitude": 77.2090
    }
    first_resp = client.post("/api/labs/search", json=payload).json()
    for _ in range(5):
        subsequent_resp = client.post("/api/labs/search", json=payload).json()
        assert first_resp["total_matching"] == subsequent_resp["total_matching"]
        assert first_resp["candidates"] == subsequent_resp["candidates"]


# ---------------------------------------------------------------------------
# Test 14: Provenance Preservation
# ---------------------------------------------------------------------------

def test_provenance_preservation(client: TestClient):
    """Verifies that authoritative BIS LIMS and geographic ranking provenance are strictly maintained."""
    resp = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 28.6139,
        "longitude": 77.2090
    })
    assert resp.status_code == 200
    data = resp.json()
    prov = data["provenance"]

    assert "bis_lims_matching" in prov
    assert "geographic_ranking" in prov
    assert "authority_disclaimer" in prov["geographic_ranking"]
    assert "Phase F3 Step 6 Deterministic Haversine Ranking" in prov["geographic_ranking"]["ranking_engine"]


# ---------------------------------------------------------------------------
# Test 15: Invalid Coordinates Rejection
# ---------------------------------------------------------------------------

def test_invalid_coordinates_rejection(client: TestClient):
    """Verifies that out-of-range coordinates or mismatched lat/lon return HTTP 400."""
    # Latitude > 90
    resp_lat = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 95.0,
        "longitude": 77.0
    })
    assert resp_lat.status_code == 400
    assert resp_lat.json()["detail"]["status"] == "INVALID_REQUEST"

    # Longitude > 180
    resp_lon = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 28.0,
        "longitude": 185.0
    })
    assert resp_lon.status_code == 400
    assert resp_lon.json()["detail"]["status"] == "INVALID_REQUEST"

    # Only latitude provided
    resp_half = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 28.0
    })
    assert resp_half.status_code == 400
    assert resp_half.json()["detail"]["status"] == "INVALID_REQUEST"


# ---------------------------------------------------------------------------
# Test 16: Invalid Requests Rejection
# ---------------------------------------------------------------------------

def test_invalid_requests_rejection(client: TestClient):
    """Verifies structural request validation errors return HTTP 400."""
    # Empty standard
    resp1 = client.post("/api/labs/search", json={"standard": "  "})
    assert resp1.status_code == 400
    assert resp1.json()["detail"]["status"] == "INVALID_REQUEST"

    # Too short standard
    resp2 = client.post("/api/labs/search", json={"standard": "I"})
    assert resp2.status_code == 400
    assert resp2.json()["detail"]["status"] == "INVALID_REQUEST"

    # max_distance_km without coordinates
    resp3 = client.post("/api/labs/search", json={"standard": "IS 4985", "max_distance_km": 50.0})
    assert resp3.status_code == 400
    assert resp3.json()["detail"]["status"] == "INVALID_REQUEST"

    # negative max_distance_km
    resp4 = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 28.0,
        "longitude": 77.0,
        "max_distance_km": -10.0
    })
    assert resp4.status_code == 400
    assert resp4.json()["detail"]["status"] == "INVALID_REQUEST"

    # negative limit
    resp5 = client.post("/api/labs/search", json={"standard": "IS 4985", "limit": 0})
    assert resp5.status_code == 400
    assert resp5.json()["detail"]["status"] == "INVALID_REQUEST"

    # invalid category
    resp6 = client.post("/api/labs/search", json={"standard": "IS 4985", "category": "INVALID_CAT"})
    assert resp6.status_code == 400
    assert resp6.json()["detail"]["status"] == "INVALID_REQUEST"


# ---------------------------------------------------------------------------
# Test 17: Result Limiting
# ---------------------------------------------------------------------------

def test_result_limiting(client: TestClient):
    """Verifies that the limit parameter restricts returned candidates while preserving total_matching."""
    resp = client.post("/api/labs/search", json={"standard": "IS 4985", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matching"] == 29
    assert data["returned_candidates"] == 5
    assert len(data["candidates"]) == 5
    for idx, cand in enumerate(data["candidates"], start=1):
        assert cand["rank"] == idx


# ---------------------------------------------------------------------------
# Test 18: Zero External API Calls
# ---------------------------------------------------------------------------

def test_zero_external_api_calls(client: TestClient, monkeypatch):
    """Verifies that the entire search pipeline executes offline with zero network calls."""
    def forbidden_socket(*args, **kwargs):
        raise AssertionError("Network access attempted during offline Lab Finder API execution!")

    monkeypatch.setattr(socket, "create_connection", forbidden_socket)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden_socket)

    # Search without coordinates
    resp1 = client.post("/api/labs/search", json={"standard": "IS 4985"})
    assert resp1.status_code == 200
    assert resp1.json()["total_matching"] == 29

    # Search with coordinates
    resp2 = client.post("/api/labs/search", json={
        "standard": "IS 4985",
        "latitude": 28.6139,
        "longitude": 77.2090,
        "max_distance_km": 100.0
    })
    assert resp2.status_code == 200
    assert resp2.json()["total_matching"] > 0
