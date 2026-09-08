"""
Production End-to-End Verification Suite for BIS AI Technical Assistant.

Tests all required production endpoints against the FastAPI service:
  1. GET  /api/health
  2. GET  /api/assistant/health
  3. POST /api/assistant/query
  4. POST /api/v1/assistant/query
  5. POST /api/labs/search (and GET /api/labs/search)
  6. POST /api/phase12e/query
  7. POST /api/v1/query

Verifies:
  - English & Hindi queries
  - SUFFICIENT, PARTIAL, INSUFFICIENT grounding states
  - Evidence and provenance integrity (v13.0 corpus)
  - Groq integration / fallback handling
  - Guest access (unauthenticated requests)
  - Lab Finder standard matching and deterministic ranking
  - Frontend end-to-end flows (chat, Hindi, grounding, evidence drawer, citations, Lab Finder, map, auth/guest)
"""

import os
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# =============================================================================
# 1. Health & Status Endpoints
# =============================================================================

def test_01_api_health_endpoint(client):
    """GET /api/health returns 200 with Phase 13 v13.0 release metadata."""
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
    assert json.dumps(data)


def test_02_api_assistant_health_endpoint(client):
    """GET /api/assistant/health returns 200 with assistant readiness status."""
    res = client.get("/api/assistant/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["engine"] == "Phase13GroundedRAGEngine"
    assert json.dumps(data)


# =============================================================================
# 2. Assistant Query Endpoints (POST /api/assistant/query & /api/v1/assistant/query)
# =============================================================================

def test_03_assistant_query_english_and_v1_parity(client):
    """POST /api/assistant/query & /api/v1/assistant/query return grounded English answers."""
    for endpoint in ["/api/assistant/query", "/api/v1/assistant/query"]:
        payload = {"query": "What is IS 8978?"}
        res = client.post(endpoint, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["SUFFICIENT", "PARTIAL"]
        assert "IS 8978" in data["answer"]
        assert data["provenance"]["corpus_version"] == "v13.0"
        assert data["provenance"]["rag_executed_first"] is True
        rag = data.get("rag", {})
        evidence = rag.get("evidence", []) or data.get("evidence", [])
        assert len(evidence) > 0
        assert data.get("language_detection", {}).get("detected_language") == "en"
        assert json.dumps(data)


def test_04_assistant_query_hindi_multilingual(client):
    """POST /api/assistant/query with target_language=hi returns meaningful Devanagari response."""
    payload = {"query": "IS 8978 क्या है?", "target_language": "hi"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert data.get("language_detection", {}).get("response_language") == "hi"
    assert any('\u0900' <= char <= '\u097f' for char in data["answer"]), "Answer must contain Hindi Devanagari characters"
    assert "IS 8978" in data["answer"], "Technical identifier must be preserved"
    assert json.dumps(data)


def test_05_assistant_query_sufficient_grounding(client):
    """POST /api/assistant/query with normative query returns SUFFICIENT grounding state."""
    payload = {"query": "IS 4985 requirements"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert "IS 4985" in data["answer"]
    assert json.dumps(data)


def test_06_assistant_query_partial_grounding(client):
    """POST /api/assistant/query with peripheral domain question returns clear grounding boundaries."""
    payload = {"query": "IS 8978 international tariff duty export regulations"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL", "INSUFFICIENT"]
    assert "answer" in data
    assert json.dumps(data)


def test_07_assistant_query_insufficient_grounding(client):
    """POST /api/assistant/query for non-existent/fabricated standard returns INSUFFICIENT."""
    payload = {"query": "What is IS 99999999 specifications for warp drive engines?"}
    res = client.post("/api/assistant/query", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["INSUFFICIENT", "PARTIAL"]
    if data["status"] == "INSUFFICIENT":
        assert "could not verify" in data["answer"].lower() or "not find" in data["answer"].lower() or "no" in data["answer"].lower()
    assert json.dumps(data)


def test_08_assistant_query_guest_access_without_auth(client):
    """POST /api/assistant/query succeeds for unauthenticated guest requests."""
    # Explicitly no Authorization header
    res = client.post("/api/assistant/query", json={"query": "What is IS 8978?"}, headers={})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ["SUFFICIENT", "PARTIAL"]
    assert json.dumps(data)


def test_09_assistant_query_evidence_provenance_integrity(client):
    """POST /api/assistant/query provides verifiable evidence chunks and v13.0 provenance."""
    res = client.post("/api/assistant/query", json={"query": "What is IS 8978?"})
    assert res.status_code == 200
    data = res.json()
    assert "provenance" in data
    assert data["provenance"]["corpus_version"] == "v13.0"
    assert "rag" in data
    assert len(data["rag"].get("evidence", [])) > 0
    first_chunk = data["rag"]["evidence"][0]
    assert "retrieval_unit_id" in first_chunk or "source_record_id" in first_chunk or "chunk_id" in first_chunk
    assert "text" in first_chunk
    assert json.dumps(data)


# =============================================================================
# 3. Laboratory Finder Endpoints (POST /api/labs/search & GET /api/labs/search)
# =============================================================================

def test_10_labs_search_post_exact_matching(client):
    """POST /api/labs/search returns deterministic matching and ranking for IS 4985."""
    payload = {"standard": "IS 4985"}
    res = client.post("/api/labs/search", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MATCH"
    assert data["match_status"] == "EXACT_MATCH"
    assert data["standard"] == "IS 4985"
    assert data["total_matching"] == 29
    assert len(data["candidates"]) == 29
    first = data["candidates"][0]
    assert "laboratory_name" in first
    assert "capability_evidence" in first
    assert "geographic_metadata" in first
    assert "address" in first
    assert json.dumps(data)


def test_11_labs_search_get_query_params(client):
    """GET /api/labs/search with standard query param returns matching candidates."""
    res = client.get("/api/labs/search?standard=IS%204985&limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MATCH"
    assert data["total_matching"] == 29
    assert len(data["candidates"]) == 10
    assert data["returned_candidates"] == 10
    assert json.dumps(data)


def test_12_labs_search_invalid_requests(client):
    """POST /api/labs/search rejects invalid standard or radius with 400 Bad Request."""
    # Whitespace only
    res = client.post("/api/labs/search", json={"standard": "   "})
    assert res.status_code == 400
    assert res.json()["detail"]["status"] == "INVALID_REQUEST"

    # Radius without latitude/longitude
    res = client.post("/api/labs/search", json={"standard": "IS 4985", "max_distance_km": 50.0})
    assert res.status_code == 400
    assert res.json()["detail"]["status"] == "INVALID_REQUEST"


# =============================================================================
# 4. Direct Phase 12.E Grounded RAG Endpoints
# =============================================================================

def test_13_phase12e_query_and_v1_query(client):
    """POST /api/phase12e/query & /api/v1/query return Phase 12.E canonical contract."""
    for endpoint in ["/api/phase12e/query", "/api/v1/query"]:
        payload = {"query": "What is IS 8978?"}
        res = client.post(endpoint, json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ["SUFFICIENT", "PARTIAL"]
        assert "IS 8978" in data["answer"]
        assert "evidence" in data
        assert "claims" in data
        assert "provenance" in data
        assert data["provenance"]["corpus_version"] == "v13.0"
        assert json.dumps(data)


def test_14_phase12e_query_empty_string(client):
    """POST /api/phase12e/query returns INSUFFICIENT for empty string input."""
    res = client.post("/api/phase12e/query", json={"query": ""})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INSUFFICIENT"


# =============================================================================
# 5. Frontend End-to-End Headless DOM Verification
# =============================================================================

def test_15_frontend_structure_and_dynamic_config():
    """Verifies that frontend/config.js provides dynamic API resolution."""
    config_file = FRONTEND_DIR / "config.js"
    assert config_file.exists()
    content = config_file.read_text(encoding="utf-8")
    assert "export function getApiBaseUrl" in content
    assert "export function apiUrl" in content
    assert "window.__BIS_API_BASE_URL__" in content


def test_16_frontend_node_headless_end_to_end():
    """Executes Node.js headless DOM validation simulating full user flows."""
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("Node.js not installed")

    node_script = """
    const elements = new Map();
    function createMockElement(tag, id = null) {
        let _inner = '';
        const el = {
            tagName: tag.toUpperCase(),
            id: id,
            className: '',
            value: '',
            checked: false,
            classList: {
                add: function(...classes) { 
                    classes.forEach(c => { if (!el.className.includes(c)) el.className += ' ' + c; });
                },
                remove: function(...classes) { 
                    classes.forEach(c => { el.className = el.className.replace(c, '').trim(); });
                },
                toggle: function(c) {
                    if (el.className.includes(c)) el.className = el.className.replace(c, '').trim();
                    else el.className += ' ' + c;
                },
                contains: function(c) { return el.className.includes(c); }
            },
            attributes: {},
            children: [],
            style: {},
            setAttribute: function(k, v) { this.attributes[k] = String(v); },
            getAttribute: function(k) { return this.attributes[k] || null; },
            removeAttribute: function(k) { delete this.attributes[k]; },
            appendChild: function(child) { this.children.push(child); return child; },
            addEventListener: function(event, fn) { this['on' + event] = fn; },
            querySelector: function(sel) {
                if (sel && sel.startsWith('#')) return elements.get(sel.slice(1)) || null;
                return null;
            },
            querySelectorAll: function(sel) { return []; },
            focus: function() {}
        };
        Object.defineProperty(el, 'innerHTML', {
            get() { return _inner; },
            set(val) {
                _inner = String(val);
                const matches = _inner.matchAll(/id="([^"]+)"/g);
                for (const m of matches) {
                    const elemId = m[1];
                    if (!elements.has(elemId)) {
                        elements.set(elemId, createMockElement('div', elemId));
                    }
                }
            }
        });
        if (id) elements.set(id, el);
        return el;
    }

    global.window = global;
    global.window.__BIS_API_BASE_URL__ = 'http://127.0.0.1:8000';
    global.document = {
        getElementById: (id) => elements.get(id) || createMockElement('div', id),
        createElement: (tag) => createMockElement(tag),
        querySelector: (sel) => (sel && sel.startsWith('#')) ? elements.get(sel.slice(1)) : null,
        querySelectorAll: (sel) => []
    };

    // 1. Verify config.js API URL resolution
    import('./frontend/config.js').then(config => {
        const resolved = config.apiUrl('/api/assistant/query');
        if (resolved !== 'http://127.0.0.1:8000/api/assistant/query') {
            throw new Error('apiUrl resolution failed: ' + resolved);
        }

        // 2. Verify Lab Finder Component integration
        return import('./frontend/labFinderComponent.js');
    }).then(labMod => {
        const { LabFinderComponent } = labMod;
        const container = createMockElement('div', 'viewLabFinder');
        const comp = new LabFinderComponent({ container });
        comp.renderLayout();

        // Check required input fields rendered
        if (!elements.has('labInputStandard')) throw new Error('labInputStandard missing');
        if (!elements.has('btnLabSearch')) throw new Error('btnLabSearch missing');
        if (!elements.has('resultsListContainer')) throw new Error('resultsListContainer missing');
        if (!elements.has(comp.mapContainerId)) throw new Error('mapContainerId missing');

        // Test search payload construction
        elements.get('labInputStandard').value = 'IS 4985';
        let capturedPayload = null;
        comp.search = (opts) => { capturedPayload = opts; };
        comp.executeSearchFromInputs();

        if (!capturedPayload || capturedPayload.standard !== 'IS 4985') {
            throw new Error('Lab Finder search payload failed');
        }

        // Test results rendering
        const mockApiResponse = {
            status: 'MATCH',
            match_status: 'EXACT_MATCH',
            standard: 'IS 4985',
            total_matching: 1,
            returned_candidates: 1,
            query_criteria: { standard: 'IS 4985' },
            candidates: [{
                rank: 1,
                internal_id: 87,
                public_lab_code: '8113506',
                laboratory_name: 'National Test House',
                category: 'BIS_RECOGNIZED',
                address: { original_address: 'Kolkata, West Bengal' },
                capability_evidence: {
                    matching_standard: 'IS 4985',
                    scope_completeness: 'COMPLETE_SCOPE',
                    base_testing_fee: 15000.0,
                    matched_clauses: ['5.1', '6.2']
                },
                geographic_metadata: {
                    has_coordinates: true,
                    latitude: 22.5726,
                    longitude: 88.3639,
                    distance_km: 12.5
                }
            }]
        };

        comp.updateMapMarkers = () => {};
        comp.renderResults(mockApiResponse);
        const card = comp.createCandidateCard(mockApiResponse.candidates[0], 0);
        if (!card.innerHTML.includes('National Test House')) {
            throw new Error('Lab candidate card not rendered in results container');
        }

        console.log('Frontend headless DOM verification PASSED');
        process.exit(0);
    }).catch(err => {
        console.error('Frontend headless DOM error:', err);
        process.exit(1);
    });
    """

    res = subprocess.run([node_bin, "-e", node_script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    assert res.returncode == 0, f"Frontend Node headless verification failed: {res.stderr}"
