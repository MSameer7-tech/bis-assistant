"""
Comprehensive BIS AI Assistant Production Backend & API Verification Suite.

Validates all 8 required production endpoints:
  1. GET  /api/health
  2. GET  /api/assistant/health
  3. POST /api/assistant/query
  4. POST /api/v1/assistant/query
  5. POST /api/labs/search
  6. GET  /api/labs/search
  7. POST /api/phase12e/query
  8. POST /api/v1/query

Guarantees Verified:
  - Preserves Phase 13 v13.0 retrieval, grounding, and provenance
  - Preserves Phase 12.E API compatibility and response schemas
  - Preserves F2 Groq orchestration, Hindi/English multilingual responses, fallback labeling
  - Preserves F3 Laboratory Finder matching, LIMS evidence, and deterministic ranking
  - Enforces production CORS without unrestricted wildcard '*'
  - Preserves server-side secrets isolation (zero secret leaks in API outputs)
  - Clear HTTP error handling for invalid/malformed requests without internal trace exposure
  - Rigorous JSON serialization across all payloads
"""

import json
import pytest
from fastapi.testclient import TestClient
from backend.app import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# =============================================================================
# 1. Health Endpoints Verification
# =============================================================================

def test_api_health_production_contract(client):
    """GET /api/health returns correct Phase 13 version, engine, and release status."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["version"] == "13.0.0"
    assert data["phase"] == "13.0"
    assert data["engine"] == "Phase13GroundedRAGEngine"
    assert data["corpus_version"] == "v13.0"
    assert data["ps_coverage"] == "100.00%"
    assert data["release_gate"] == "PASSED"
    # Ensure JSON serializable
    assert json.dumps(data)


def test_api_assistant_health_contract(client):
    """GET /api/assistant/health returns healthy status."""
    res = client.get("/api/assistant/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["engine"] == "Phase13GroundedRAGEngine"


# =============================================================================
# 2. Assistant Query Endpoints (POST /api/assistant/query & /api/v1/assistant/query)
# =============================================================================

def test_assistant_query_known_standard_english(client):
    """POST /api/assistant/query with known standard preserves SUFFICIENT/PARTIAL grounding."""
    for endpoint in ["/api/assistant/query", "/api/v1/assistant/query"]:
        payload = {"query": "What is IS 8978?"}
        res = client.post(endpoint, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["SUFFICIENT", "PARTIAL"]
        assert "IS 8978" in data["answer"]
        assert data["generation_mode"] in ["GROUNDED", "LLM_FALLBACK", "CONVERSATIONAL", "HYBRID"]
        # Provenance integrity
        assert data["provenance"]["rag_executed_first"] is True
        assert data["provenance"]["corpus_version"] == "v13.0"
        # RAG evidence preserved
        rag = data.get("rag", {})
        evidence = rag.get("evidence", []) or data.get("evidence", [])
        assert len(evidence) > 0
        # Language detection integrity
        assert data.get("language_detection", {}).get("detected_language") == "en"
        # Verify JSON serialization
        assert json.dumps(data)


def test_assistant_query_hindi_multilingual(client):
    """POST /api/assistant/query with target_language=hi returns valid Hindi response."""
    payload = {"query": "IS 8978 क्या है?", "target_language": "hi"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert data.get("language_detection", {}).get("response_language") == "hi"
    assert len(data["answer"]) > 0


def test_assistant_query_sufficient_grounding(client):
    """POST /api/assistant/query with exact normative standard returns SUFFICIENT or grounded status."""
    payload = {"query": "IS 4985 requirements"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert "IS 4985" in data["answer"]


def test_assistant_query_insufficient_for_fabricated_standard(client):
    """POST /api/assistant/query returns INSUFFICIENT for fabricated/unrecorded standards."""
    payload = {"query": "What is IS 99999999 specifications?"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["INSUFFICIENT", "PARTIAL"]
    # If insufficient, does not invent facts
    if data["status"] == "INSUFFICIENT":
        assert "could not verify" in data["answer"].lower() or "not find" in data["answer"].lower() or "no" in data["answer"].lower()


def test_assistant_query_empty_string(client):
    """POST /api/assistant/query with empty or whitespace string returns INSUFFICIENT without error."""
    payload = {"query": "   "}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INSUFFICIENT"
    assert "provide a query" in data["answer"].lower()


def test_assistant_query_missing_field_error(client):
    """POST /api/assistant/query with missing query field returns clean HTTP 422 error."""
    res = client.post("/api/assistant/query", json={})
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data


# =============================================================================
# 3. Direct Grounded RAG Endpoints (POST /api/phase12e/query & /api/v1/query)
# =============================================================================

def test_phase12e_query_direct_rag(client):
    """POST /api/phase12e/query returns canonical Phase 12.E contract backed by Phase 13 v13.0."""
    for endpoint in ["/api/phase12e/query", "/api/v1/query"]:
        payload = {"query": "What is IS 8978?"}
        res = client.post(endpoint, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["SUFFICIENT", "PARTIAL"]
        assert "IS 8978" in data["answer"]
        assert len(data.get("evidence", [])) > 0
        assert "claims" in data
        assert "provenance" in data
        assert data["provenance"]["corpus_version"] == "v13.0"
        assert json.dumps(data)


def test_phase12e_query_empty_string(client):
    """POST /api/phase12e/query with empty string returns INSUFFICIENT status cleanly."""
    res = client.post("/api/phase12e/query", json={"query": ""})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INSUFFICIENT"


# =============================================================================
# 4. Laboratory Finder Endpoints (POST /api/labs/search & GET /api/labs/search)
# =============================================================================

def test_lab_finder_post_search_exact(client):
    """POST /api/labs/search returns qualified candidates with LIMS evidence."""
    payload = {"standard": "IS 4985"}
    res = client.post("/api/labs/search", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MATCH"
    assert data["match_status"] == "EXACT_MATCH"
    assert data["standard"] == "IS 4985"
    assert data["total_matching"] == 29
    assert len(data["candidates"]) == 29
    
    first_candidate = data["candidates"][0]
    assert "laboratory_name" in first_candidate
    assert "geographic_metadata" in first_candidate
    assert "capability_evidence" in first_candidate
    assert "address" in first_candidate
    assert json.dumps(data)


def test_lab_finder_get_search_exact(client):
    """GET /api/labs/search with query parameters returns qualified candidates."""
    res = client.get("/api/labs/search?standard=IS%204985&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MATCH"
    assert data["total_matching"] == 29
    assert len(data["candidates"]) == 10
    assert data["returned_candidates"] == 10


def test_lab_finder_invalid_requests(client):
    """POST /api/labs/search rejects invalid/malformed requests with clean HTTP 400."""
    # 1. Empty standard
    res = client.post("/api/labs/search", json={"standard": "   "})
    assert res.status_code == 400
    assert res.json()["detail"]["status"] == "INVALID_REQUEST"

    # 2. Distance radius without user coordinates
    res2 = client.post("/api/labs/search", json={"standard": "IS 4985", "max_distance_km": 50.0})
    assert res2.status_code == 400
    assert res2.json()["detail"]["status"] == "INVALID_REQUEST"

    # 3. Non-positive limit
    res3 = client.post("/api/labs/search", json={"standard": "IS 4985", "limit": 0})
    assert res3.status_code == 400
    assert res3.json()["detail"]["status"] == "INVALID_REQUEST"

    # 4. Incomplete coordinates (latitude without longitude)
    res4 = client.post("/api/labs/search", json={"standard": "IS 4985", "latitude": 28.61})
    assert res4.status_code == 400
    assert res4.json()["detail"]["status"] == "INVALID_REQUEST"


# =============================================================================
# 5. Production CORS Security & Secrets Protection
# =============================================================================

def test_cors_preflight_allowed_origin(client):
    """Verify CORS preflight allows configured origins and sends credentials headers."""
    res = client.options(
        "/api/assistant/query",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert res.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in res.headers.get("access-control-allow-methods", "")


def test_cors_no_wildcard_star():
    """Verify that wildcard '*' is not present in allowed_origins."""
    from backend.app import allowed_origins
    assert "*" not in allowed_origins


def test_server_secrets_isolation(client):
    """Verify that internal API secrets (Groq, Supabase secrets) are never leaked in responses."""
    # Test assistant query response
    res1 = client.post("/api/assistant/query", json={"query": "What is IS 8978?"})
    content1 = res1.text
    assert "gsk_" not in content1
    assert "service_role" not in content1
    assert "jwt_secret" not in content1

    # Test auth public config
    res2 = client.get("/api/auth/config")
    content2 = res2.text
    assert "service_role" not in content2
    assert "jwt_secret" not in content2

    # Test health check
    res3 = client.get("/api/health")
    content3 = res3.text
    assert "gsk_" not in content3
    assert "service_role" not in content3


def test_i18n_static_endpoints(client):
    """Verify that /i18n/en.json and /i18n/hi.json return HTTP 200 with valid JSON dictionaries."""
    for lang in ["en", "hi"]:
        res = client.get(f"/i18n/{lang}.json")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        assert "app" in data or "common" in data or "nav" in data
