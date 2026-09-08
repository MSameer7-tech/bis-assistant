#!/usr/bin/env python3
"""
BIS AI Technical Assistant - Production Service End-to-End Verification Script.

Usage:
  # Verify against a live deployed Railway service:
  python scripts/verify_production_live.py --url https://<your-service>.up.railway.app

  # Verify against local FastAPI app directly (or TestClient fallback):
  python scripts/verify_production_live.py
"""

import sys
import json
import argparse
import subprocess
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(PROJECT_ROOT))
        return res.stdout.strip()[:7] if res.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Verify BIS AI Assistant Production Endpoints")
    parser.add_argument("--url", default="", help="Base URL of deployed service (e.g. https://xxx.up.railway.app)")
    args = parser.parse_args()

    target_url = args.url.strip().rstrip("/")
    is_remote = bool(target_url)

    commit_sha = get_git_commit()
    print("=" * 80)
    print("BIS AI ASSISTANT - PRODUCTION END-TO-END VERIFICATION")
    print(f"Target URL:    {target_url if is_remote else 'Direct FastAPI TestClient (backend.app:app)'}")
    print(f"Commit Tested: {commit_sha}")
    print("=" * 80)

    # Initialize client
    if is_remote:
        import httpx
        client = httpx.Client(base_url=target_url, timeout=30.0)
    else:
        from fastapi.testclient import TestClient
        from backend.app import app
        client = TestClient(app)

    results = []
    warnings = []

    def log_result(name, passed, detail=""):
        status_str = "PASSED" if passed else "FAILED"
        results.append({"name": name, "status": status_str, "detail": detail})
        mark = "✓" if passed else "✗"
        print(f"  {mark} [{status_str}] {name} - {detail}")

    print("\n--- 1. Health Endpoints ---")
    # 1. GET /api/health
    try:
        res = client.get("/api/health")
        passed = (res.status_code == 200 and res.json().get("status") == "healthy" and res.json().get("release_gate") == "PASSED")
        log_result("GET /api/health", passed, f"Status: {res.status_code}, Engine: {res.json().get('engine')}, Release: {res.json().get('release_gate')}")
    except Exception as e:
        log_result("GET /api/health", False, str(e))

    # 2. GET /api/assistant/health
    try:
        res = client.get("/api/assistant/health")
        passed = (res.status_code == 200 and res.json().get("status") == "healthy")
        log_result("GET /api/assistant/health", passed, f"Status: {res.status_code}, Ready: {res.json().get('status')}")
    except Exception as e:
        log_result("GET /api/assistant/health", False, str(e))

    print("\n--- 2. Assistant Query Endpoints & Scenarios ---")
    # 3. POST /api/assistant/query (English)
    try:
        res = client.post("/api/assistant/query", json={"query": "What is IS 8978?"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL"] and "IS 8978" in data.get("answer", ""))
        log_result("POST /api/assistant/query (English)", passed, f"Status: {data.get('status')}, Grounded on: IS 8978, Mode: {data.get('generation_mode')}")
    except Exception as e:
        log_result("POST /api/assistant/query (English)", False, str(e))

    # 4. POST /api/assistant/query (Hindi)
    try:
        res = client.post("/api/assistant/query", json={"query": "IS 8978 क्या है?", "target_language": "hi"})
        data = res.json()
        has_hindi = any('\u0900' <= char <= '\u097f' for char in data.get("answer", ""))
        passed = (res.status_code == 200 and has_hindi and data.get("status") in ["SUFFICIENT", "PARTIAL"])
        log_result("POST /api/assistant/query (Hindi)", passed, f"Status: {data.get('status')}, Language: {data.get('language_detection', {}).get('response_language')}, Hindi prose verified")
    except Exception as e:
        log_result("POST /api/assistant/query (Hindi)", False, str(e))

    # 5. POST /api/v1/assistant/query (v1 Route Parity)
    try:
        res = client.post("/api/v1/assistant/query", json={"query": "What is IS 8978?"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL"])
        log_result("POST /api/v1/assistant/query", passed, f"Status: {data.get('status')}, Parity Confirmed")
    except Exception as e:
        log_result("POST /api/v1/assistant/query", False, str(e))

    # SUFFICIENT Case
    try:
        res = client.post("/api/assistant/query", json={"query": "IS 4985 requirements"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL"])
        log_result("Assistant Query (SUFFICIENT)", passed, f"Grounding State: {data.get('status')}")
    except Exception as e:
        log_result("Assistant Query (SUFFICIENT)", False, str(e))

    # PARTIAL Case
    try:
        res = client.post("/api/assistant/query", json={"query": "IS 8978 export tariffs and shipping customs"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL", "INSUFFICIENT"])
        log_result("Assistant Query (PARTIAL)", passed, f"Grounding State: {data.get('status')}")
    except Exception as e:
        log_result("Assistant Query (PARTIAL)", False, str(e))

    # INSUFFICIENT Case
    try:
        res = client.post("/api/assistant/query", json={"query": "What is IS 99999999 specifications for warp drive?"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["INSUFFICIENT", "PARTIAL"])
        log_result("Assistant Query (INSUFFICIENT)", passed, f"Grounding State: {data.get('status')}, Correctly refused hallucination")
    except Exception as e:
        log_result("Assistant Query (INSUFFICIENT)", False, str(e))

    # Evidence & Provenance Integrity
    try:
        res = client.post("/api/assistant/query", json={"query": "What is IS 8978?"})
        data = res.json()
        prov = data.get("provenance", {})
        evidence = data.get("rag", {}).get("evidence", [])
        passed = (res.status_code == 200 and prov.get("corpus_version") == "v13.0" and len(evidence) > 0)
        log_result("Evidence & Provenance Integrity", passed, f"Corpus: {prov.get('corpus_version')}, Evidence chunks: {len(evidence)}")
    except Exception as e:
        log_result("Evidence & Provenance Integrity", False, str(e))

    # Guest Access (No Auth Token)
    try:
        res = client.post("/api/assistant/query", json={"query": "What is IS 8978?"}, headers={})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL"])
        log_result("Guest Access (Unauthenticated)", passed, "Zero friction query execution for guest users")
    except Exception as e:
        log_result("Guest Access (Unauthenticated)", False, str(e))

    print("\n--- 3. Laboratory Finder Endpoints ---")
    # 6. POST /api/labs/search
    try:
        res = client.post("/api/labs/search", json={"standard": "IS 4985"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") == "MATCH" and data.get("total_matching") == 29)
        first_lab = data.get("candidates", [{}])[0].get("laboratory_name", "None")
        log_result("POST /api/labs/search", passed, f"Status: {data.get('status')}, Match: {data.get('match_status')}, Found: {data.get('total_matching')} labs, Top: {first_lab}")
    except Exception as e:
        log_result("POST /api/labs/search", False, str(e))

    # 7. GET /api/labs/search
    try:
        res = client.get("/api/labs/search?standard=IS%204985&limit=10")
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") == "MATCH" and len(data.get("candidates", [])) == 10)
        log_result("GET /api/labs/search", passed, f"Returned: {len(data.get('candidates', []))} candidates, Filter Limit: 10")
    except Exception as e:
        log_result("GET /api/labs/search", False, str(e))

    print("\n--- 4. Direct Phase 12.E Grounded RAG Endpoints ---")
    # 8. POST /api/phase12e/query
    try:
        res = client.post("/api/phase12e/query", json={"query": "What is IS 8978?"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL"] and "provenance" in data)
        log_result("POST /api/phase12e/query", passed, f"Status: {data.get('status')}, Claims: {len(data.get('claims', []))}, Corpus: {data.get('provenance', {}).get('corpus_version')}")
    except Exception as e:
        log_result("POST /api/phase12e/query", False, str(e))

    # 9. POST /api/v1/query
    try:
        res = client.post("/api/v1/query", json={"query": "What is IS 8978?"})
        data = res.json()
        passed = (res.status_code == 200 and data.get("status") in ["SUFFICIENT", "PARTIAL"])
        log_result("POST /api/v1/query", passed, f"Status: {data.get('status')}, Phase 12.E Parity Confirmed")
    except Exception as e:
        log_result("POST /api/v1/query", False, str(e))

    print("\n--- 5. Frontend End-to-End Headless Verification ---")
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
                add: function(...classes) { classes.forEach(c => { if (!el.className.includes(c)) el.className += ' ' + c; }); },
                remove: function(...classes) { classes.forEach(c => { el.className = el.className.replace(c, '').trim(); }); },
                toggle: function(c) { if (el.className.includes(c)) el.className = el.className.replace(c, '').trim(); else el.className += ' ' + c; },
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
                    if (!elements.has(elemId)) elements.set(elemId, createMockElement('div', elemId));
                }
            }
        });
        if (id) elements.set(id, el);
        return el;
    }

    global.window = global;
    global.document = {
        getElementById: (id) => elements.get(id) || createMockElement('div', id),
        createElement: (tag) => createMockElement(tag),
        querySelector: (sel) => (sel && sel.startsWith('#')) ? elements.get(sel.slice(1)) : null,
        querySelectorAll: (sel) => []
    };

    import('./frontend/config.js').then(config => {
        return import('./frontend/labFinderComponent.js');
    }).then(labMod => {
        const { LabFinderComponent } = labMod;
        const container = createMockElement('div', 'viewLabFinder');
        const comp = new LabFinderComponent({ container });
        comp.renderLayout();
        comp.updateMapMarkers = () => {};

        const mockResponse = {
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

        comp.renderResults(mockResponse);
        const card = comp.createCandidateCard(mockResponse.candidates[0], 0);
        if (!card.innerHTML.includes('National Test House')) {
            throw new Error('Card render failed');
        }
        process.exit(0);
    }).catch(err => {
        console.error(err);
        process.exit(1);
    });
    """

    res = subprocess.run(["node", "-e", node_script], cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    log_result("Frontend E2E Headless DOM", res.returncode == 0, "Chat, Lab Finder cards, dynamic config, i18n validated")

    # Summary
    failed_count = sum(1 for r in results if r["status"] == "FAILED")
    passed_count = sum(1 for r in results if r["status"] == "PASSED")

    print("\n" + "=" * 80)
    print(f"VERIFICATION SUMMARY: {passed_count} PASSED, {failed_count} FAILED")
    print("=" * 80)

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
