"""
Phase PC-7: Interactive Natural Language Clarification & Recommendation Layer Test Suite.

Automated validation covering:
1. Ambiguous query ('pvc') -> ClarificationState.AMBIGUOUS with 5 candidates, no journey generated
2. Specific query ('PVC pipes for potable water') -> ClarificationState.CLEAR resolving to IS 4985
3. Explicit standard ('PVC pipes under IS 4985') -> ClarificationState.CLEAR with standard precedence
4. Incomplete query ('I manufacture pipes') -> ClarificationState.INCOMPLETE with adaptive attribute groups
5. Proximity extraction ('I manufacture PVC pipes in Delhi') -> Extracts location 'Delhi' for lab qualification
6. Unknown product ('timber doors') -> ClarificationState.CLEAR passing to PC-5 returning STANDARD_NOT_ESTABLISHED (HTTP 200)
7. QCO Conflict ('IS 374') -> ClarificationState.CLEAR passing to PC-5 returning QCO_CONFLICT
8. QCO Unknown ('IS 15750') -> ClarificationState.CLEAR passing to PC-5 returning QCO_STATUS_UNKNOWN
9. Multi-turn follow-up ('pvc' + 'water supply pipes') -> Contextually combines and resolves to IS 4985
10. Candidate selection -> Standard selection payload triggers full 10-stage journey
11. NLU Fallback safety -> Graceful fallback on exception without hallucinating standards
12. Concurrency & determinism -> 20 concurrent requests execute deterministically with zero state leakage
"""

import concurrent.futures
from typing import Dict, Any
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from ai.compliance.nlu_clarification import (
    ComplianceNLUClarificationEngine,
    ComplianceClarificationRequest,
    ClarificationState,
)

client = TestClient(app)
engine = ComplianceNLUClarificationEngine()


# ==============================================================================
# CASE 1: AMBIGUOUS QUERY ('pvc')
# ==============================================================================
def test_case_1_ambiguous_query_pvc():
    """Entering broad 'pvc' must return AMBIGUOUS with 5 grounded candidates and no journey."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "pvc"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "AMBIGUOUS"
    assert data["resolved_standard"] is None
    assert data["clarification"] is not None
    assert "PVC" in data["clarification"]["title"]

    candidates = data["clarification"]["candidates"]
    assert len(candidates) == 5

    candidate_stds = [c["standard_number"] for c in candidates]
    expected_stds = ["IS 4985", "IS 694", "IS 12254", "IS 13592", "IS 9537 (PART 3)"]
    for std in expected_stds:
        assert std in candidate_stds, f"Expected grounded standard {std} in PVC candidates"

    # Verify disclaimer is present
    assert "disclaimer" in data["clarification"]
    assert "narrows user intent" in data["clarification"]["disclaimer"]


# ==============================================================================
# CASE 2: SPECIFIC INTENT ('PVC pipes for potable water supplies')
# ==============================================================================
def test_case_2_specific_intent_potable_water():
    """Specific query with material + application resolves directly to CLEAR (IS 4985)."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "I manufacture PVC pipes for potable water supplies"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "CLEAR"
    assert data["resolved_standard"] == "IS 4985"
    assert data["refined_request"]["standard"] == "IS 4985"

    # Verify that calling PC-5 with this refined request returns a valid journey
    journey_resp = client.post(
        "/api/compliance/journey",
        json=data["refined_request"]
    )
    assert journey_resp.status_code == 200
    j_data = journey_resp.json()
    assert j_data["status"] == "JOURNEY_ESTABLISHED"
    assert j_data["applicable_standards"]["primary_standard"] == "IS 4985"
    assert j_data["mandatory_certification"]["status"] == "MANDATORY_CERTIFICATION_CONFIRMED"


# ==============================================================================
# CASE 3: EXPLICIT STANDARD PRECEDENCE ('PVC pipes under IS 4985')
# ==============================================================================
def test_case_3_explicit_standard_precedence():
    """Explicit standard token ('IS 4985') overrides broad ambiguous product token."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "PVC pipes under IS 4985"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "CLEAR"
    assert data["resolved_standard"] == "IS 4985"
    assert data["slots"]["standard"] == "IS 4985"


# ==============================================================================
# CASE 4: INCOMPLETE QUERY ('I manufacture pipes')
# ==============================================================================
def test_case_4_incomplete_query_pipes():
    """Generic category ('pipes') returns INCOMPLETE with Material and Application attribute options."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "I manufacture pipes"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "INCOMPLETE"
    assert data["resolved_standard"] is None
    assert data["clarification"] is not None

    attr_groups = data["clarification"]["attribute_groups"]
    assert len(attr_groups) >= 2

    group_ids = [g["group_id"] for g in attr_groups]
    assert "material" in group_ids
    assert "application" in group_ids

    # Check that PVC and Potable water options are available
    material_opts = [opt["value"].lower() for g in attr_groups if g["group_id"] == "material" for opt in g["options"]]
    assert "pvc" in material_opts
    assert "hdpe" in material_opts


# ==============================================================================
# CASE 5: LOCATION EXTRACTION ('I manufacture PVC pipes in Delhi')
# ==============================================================================
def test_case_5_location_extraction_delhi():
    """Query with location 'in Delhi' extracts location for downstream laboratory qualification."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "I manufacture PVC pipes for water in Delhi"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "CLEAR"
    assert data["slots"]["location"] == "Delhi"
    assert data["refined_request"]["location"] == "Delhi"

    # Pass to PC-5 journey and ensure location filter was received
    journey_resp = client.post(
        "/api/compliance/journey",
        json=data["refined_request"]
    )
    assert journey_resp.status_code == 200
    j_data = journey_resp.json()
    assert j_data["laboratories"]["location_filter_applied"] == "Delhi"
    assert j_data["laboratories"]["capability_evaluated_first"] is True
    assert len(j_data["laboratories"]["qualified_laboratories"]) > 0


# ==============================================================================
# CASE 6: UNKNOWN PRODUCT ('timber doors')
# ==============================================================================
def test_case_6_unknown_product_timber_doors():
    """Unknown product passes to PC-5 returning STANDARD_NOT_ESTABLISHED safely with HTTP 200."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "timber doors"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "CLEAR"
    assert data["resolved_standard"] is None

    # Call PC-5 journey
    journey_resp = client.post(
        "/api/compliance/journey",
        json={"product": "timber doors"}
    )
    assert journey_resp.status_code == 200
    j_data = journey_resp.json()
    assert j_data["status"] == "STANDARD_NOT_ESTABLISHED"
    assert j_data["applicable_standards"]["status"] == "STANDARD_NOT_ESTABLISHED"
    assert j_data["mandatory_certification"]["status"] == "MANDATORY_CERTIFICATION_NOT_ESTABLISHED"
    assert any("could not be established from available BIS evidence" in lim for lim in j_data["limitations"])


# ==============================================================================
# CASE 7: REGULATORY CONFLICT ('IS 374')
# ==============================================================================
def test_case_7_regulatory_conflict_is_374():
    """Known conflict standard ('IS 374') returns CLEAR, and PC-5 preserves QCO_CONFLICT."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "IS 374"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "CLEAR"
    assert data["resolved_standard"] == "IS 374"

    journey_resp = client.post(
        "/api/compliance/journey",
        json=data["refined_request"]
    )
    assert journey_resp.status_code == 200
    j_data = journey_resp.json()
    assert j_data["regulatory_status"]["status"] == "QCO_CONFLICT"
    assert len(j_data["regulatory_status"]["conflict_ids"]) > 0


# ==============================================================================
# CASE 8: UNKNOWN REGULATORY STATUS ('IS 15750')
# ==============================================================================
def test_case_8_regulatory_unknown_is_15750():
    """Standard with no QCO record ('IS 15750') returns CLEAR, PC-5 returns QCO_STATUS_UNKNOWN."""
    response = client.post(
        "/api/compliance/clarify",
        json={"query": "IS 15750"}
    )
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "CLEAR"
    assert data["resolved_standard"] == "IS 15750"

    journey_resp = client.post(
        "/api/compliance/journey",
        json=data["refined_request"]
    )
    assert journey_resp.status_code == 200
    j_data = journey_resp.json()
    assert j_data["regulatory_status"]["status"] == "QCO_STATUS_UNKNOWN"


# ==============================================================================
# CASE 9: MULTI-TURN FOLLOW-UP MEMORY
# ==============================================================================
def test_case_9_multi_turn_follow_up():
    """Turn 1 'pvc' followed by Turn 2 'water supply pipes' combines memory to resolve IS 4985."""
    # Turn 1
    t1_resp = client.post(
        "/api/compliance/clarify",
        json={"query": "pvc"}
    )
    assert t1_resp.json()["state"] == "AMBIGUOUS"

    # Turn 2 with previous context
    t2_resp = client.post(
        "/api/compliance/clarify",
        json={
            "query": "water supply pipes",
            "context": {
                "previous_query": "pvc",
                "previous_state": "AMBIGUOUS"
            }
        }
    )
    assert t2_resp.status_code == 200
    t2_data = t2_resp.json()
    assert t2_data["state"] == "CLEAR"
    assert t2_data["resolved_standard"] == "IS 4985"
    assert t2_data["slots"]["material"].lower() == "pvc"


# ==============================================================================
# CASE 10: CANDIDATE SELECTION
# ==============================================================================
def test_case_10_candidate_selection_payload():
    """Selecting candidate from clarification card passes explicit standard and triggers journey."""
    selection_payload = {
        "product": "PVC pipes for potable water supplies",
        "standard": "IS 4985"
    }
    clarify_resp = client.post(
        "/api/compliance/clarify",
        json=selection_payload
    )
    assert clarify_resp.status_code == 200
    clarify_data = clarify_resp.json()
    assert clarify_data["state"] == "CLEAR"
    assert clarify_data["resolved_standard"] == "IS 4985"

    journey_resp = client.post(
        "/api/compliance/journey",
        json=clarify_data["refined_request"]
    )
    assert journey_resp.status_code == 200
    j_data = journey_resp.json()
    assert j_data["status"] == "JOURNEY_ESTABLISHED"
    assert j_data["testing"]["total_tests"] > 0
    assert len(j_data["laboratories"]["qualified_laboratories"]) > 0


# ==============================================================================
# CASE 11: NLU FALLBACK SAFETY ON EXCEPTION
# ==============================================================================
def test_case_11_nlu_fallback_safety():
    """If NLU slot extraction encounters an error, it gracefully falls back without inventing standards."""
    bad_req = ComplianceClarificationRequest(query=None, product=None, standard=None)
    result = engine.analyze_clarification(bad_req)
    assert result.state in [ClarificationState.CLEAR, ClarificationState.INCOMPLETE]
    assert result.resolved_standard is None

    # Test empty payload via API
    resp = client.post("/api/compliance/clarify", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] in ["CLEAR", "INCOMPLETE"]
    assert data["resolved_standard"] is None


# ==============================================================================
# CASE 12: CONCURRENCY & ZERO STATE LEAKAGE
# ==============================================================================
def test_case_12_concurrent_clarification():
    """20 concurrent clarification requests execute deterministically without state corruption."""
    test_queries = [
        ("pvc", "AMBIGUOUS"),
        ("I manufacture pipes", "INCOMPLETE"),
        ("IS 4985", "CLEAR"),
        ("PVC cables", "CLEAR"),
        ("timber doors", "CLEAR"),
    ] * 4  # 20 queries

    def execute_query(item):
        q, expected_state = item
        r = client.post("/api/compliance/clarify", json={"query": q})
        assert r.status_code == 200
        return r.json()["state"] == expected_state

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(execute_query, test_queries))

    assert all(results)
    assert len(results) == 20
